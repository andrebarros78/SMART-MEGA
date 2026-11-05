"""Publish validated operator commits through GitHub Git Data API and a protected-main PR.

Executor-local Git credentials and GitHub Actions are deliberately not used.
Only the canonical repository is addressed; a scoped external GitHub credential
must be injected into the executor environment by its secret manager.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = "andrebarros78/SMART-MEGA"
BASE = "https://api.github.com/repos/" + REPO
HEADERS = {"Accept": "application/vnd.github+json",
           "X-GitHub-Api-Version": "2022-11-28"}
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class GitHubAPI:
    def __init__(self, token: str | None = None):
        self._token = token or next(
            (os.environ.get(name) for name in
             ("SMART_MEGA_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")
             if os.environ.get(name)), None)
        # Reuse an already-authorized GitHub CLI account on any executor.
        # The bearer never leaves this process through stdout or logs.
        if not self._token and shutil.which("gh"):
            probe = subprocess.run(
                ["gh", "auth", "token", "--hostname", "github.com"],
                capture_output=True, text=True, check=False, timeout=15,
            )
            if probe.returncode == 0:
                self._token = probe.stdout.strip() or None
        if not self._token:
            raise PermissionError("GitHub publication credential unavailable: "
                                  "configure an authorized scoped credential or gh auth")

    def call(self, method: str, path: str, payload: dict | None = None) -> dict:
        if not path.startswith("/") or "://" in path or ".." in path:
            raise ValueError("invalid canonical GitHub API path")
        body = None if payload is None else json.dumps(
            payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        headers = {**HEADERS, "Authorization": "Bearer " + self._token}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = Request(BASE + path, data=body, headers=headers, method=method)
        try:
            with urlopen(req, timeout=120) as response:
                return json.load(response)
        except HTTPError as exc:
            # Do not log headers, bodies, or the private credential.
            raise RuntimeError(f"GitHub API {method} {path} rejected "
                               f"(HTTP {exc.code})") from None
        except URLError as exc:
            raise RuntimeError(f"GitHub API transport unavailable for "
                               f"{method} {path}: {type(exc.reason).__name__}") from None


def _git(root: Path, *args: str, binary: bool = False) -> str | bytes:
    proc = subprocess.run(["git", *args], cwd=root, capture_output=True,
                          check=True, timeout=180)
    return proc.stdout if binary else proc.stdout.decode("utf-8").strip()


def _sha(raw: str) -> str:
    if not SHA_PATTERN.fullmatch(raw or ""):
        raise ValueError("invalid immutable Git SHA")
    return raw


def publish_commit(root: str | Path, operation: str, target: int,
                   expected_main_sha: str, local_commit_sha: str,
                   *, api: GitHubAPI | None = None) -> dict:
    """Publish one checked, already-committed transaction via PR, fail-closed.

    A branch is never merged if main changed after the executor's baseline.
    Binary artifacts retain their original Git blob IDs, including large
    hash-bound ledgers. Identical blobs are uploaded only once per operation.
    """
    from smart_github_operator import allowed_artifact

    root = Path(root).resolve()
    expected_main_sha = _sha(expected_main_sha)
    local_commit_sha = _sha(local_commit_sha)
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,50}", operation):
        raise ValueError("invalid operation")
    if type(target) is not int or target < 1:
        raise ValueError("invalid contest")
    if _git(root, "rev-parse", "HEAD") != local_commit_sha:
        raise RuntimeError("local commit changed")
    if _git(root, "rev-parse", "HEAD^") != expected_main_sha:
        raise RuntimeError("local publication is not based on canonical main")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise RuntimeError("local checkout is dirty; publication refused")
    origin = _git(root, "remote", "get-url", "origin")
    if origin not in {"https://github.com/" + REPO + ".git",
                      "https://github.com/" + REPO,
                      "git@github.com:" + REPO + ".git",
                      "ssh://git@github.com/" + REPO + ".git"}:
        raise PermissionError("noncanonical Git remote")

    # The GitHub credential is checked before any publication mutation.
    api = api or GitHubAPI()
    before = api.call("GET", "/branches/main")["commit"]["sha"]
    if before != expected_main_sha:
        raise RuntimeError("canonical main moved: rebase and rerun validation")

    changed = _git(root, "diff", "--name-only", "--no-renames", "-z",
                   expected_main_sha, local_commit_sha, binary=True)
    paths = sorted(p.decode("utf-8") for p in changed.split(b"\x00") if p)
    if not paths:
        raise ValueError("no operational artifacts to publish")
    if any(p != ".gitattributes" and not allowed_artifact(p) for p in paths):
        raise PermissionError("publication includes non-operational artifacts")
    tree = []
    sent: set[str] = set()
    for path in paths:
        raw = _git(root, "ls-tree", local_commit_sha, "--", path)
        if not raw:
            tree.append({"path": path, "mode": "100644",
                         "type": "blob", "sha": None})
            continue
        mode, kind, sha = raw.split("\t", 1)[0].split()
        sha = _sha(sha)
        if kind != "blob" or mode != "100644":
            raise PermissionError("symlink or nonregular artifact rejected")
        if sha not in sent:
            payload = {"content": base64.b64encode(_git(
                root, "cat-file", "blob", sha, binary=True)).decode("ascii"),
                       "encoding": "base64"}
            received = api.call("POST", "/git/blobs", payload)
            if received.get("sha") != sha:
                raise RuntimeError("GitHub blob SHA differs from immutable local blob")
            sent.add(sha)
        tree.append({"path": path, "mode": "100644",
                     "type": "blob", "sha": sha})

    root_tree = api.call("GET", "/git/commits/" + expected_main_sha)["tree"]["sha"]
    new_tree = api.call("POST", "/git/trees", {
        "base_tree": _sha(root_tree), "tree": tree})["sha"]
    published = api.call("POST", "/git/commits", {
        "message": f"operation: {operation} contest {target}",
        "tree": _sha(new_tree), "parents": [expected_main_sha]})["sha"]
    published = _sha(published)
    branch = f"operation/{operation}-{target}-{local_commit_sha[:12]}"
    api.call("POST", "/git/refs", {"ref": "refs/heads/" + branch,
                                   "sha": published})
    pr = api.call("POST", "/pulls", {
        "title": f"operation({target}): {operation} - canonical result",
        "body": ("Authenticated external executor; immutable artifact SHAs "
                 "verified. GitHub Actions prohibited. No direct main push."),
        "head": branch, "base": "main"})
    number = pr["number"]
    if type(number) is not int or number < 1:
        raise RuntimeError("invalid GitHub PR number")
    current = api.call("GET", "/branches/main")["commit"]["sha"]
    if current != expected_main_sha:
        raise RuntimeError("canonical main moved before PR merge")
    merged = api.call("PUT", f"/pulls/{number}/merge", {
        "sha": published, "merge_method": "squash"})
    if merged.get("merged") is not True:
        return {"status": "PR_REVIEW_REQUIRED", "pr_number": number,
                "pr_url": pr.get("html_url"), "source_commit": local_commit_sha}
    remote = api.call("GET", "/branches/main")["commit"]["sha"]
    if remote != merged.get("sha"):
        raise RuntimeError("GitHub main failed post-merge SHA verification")
    return {"status": "PUBLISHED_CANONICAL_MAIN",
            "remote_commit": remote, "local_commit": local_commit_sha,
            "pr_number": number, "pr_url": pr.get("html_url"),
            "target_contest": target, "changed_files": paths,
            "uploaded_unique_blobs": len(sent)}
