"""Regression: protected canonical main must be published by authenticated PR, never direct push."""
import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from smart_protected_pr_publication import publish_commit


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                          text=True).stdout.strip()


def _fixture(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "test")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "remote", "add", "origin", "https://github.com/andrebarros78/SMART-MEGA.git")
    (root / "SMART_SAMPLE.json").write_text("before\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "before")
    base = git(root, "rev-parse", "HEAD")
    one = root / "runtime" / "epochs" / "SMART_BIG.json"
    two = root / "SMART_COPY.json"
    one.parent.mkdir(parents=True)
    content = (b"{\n" + b"  \"value\": 123,\n" * 1000 + b"}\n")
    one.write_bytes(content)
    two.write_bytes(content)
    (root / "SMART_SAMPLE.json").write_text("after\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "after")
    return root, base, git(root, "rev-parse", "HEAD")


class FakeAPI:
    def __init__(self, base):
        self.base = base
        self.calls = []
        self.shas = []
        self.new_sha = "b" * 40

    def call(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "GET" and path == "/branches/main":
            return {"commit": {"sha": self.base if not any(x[1].endswith("/merge") for x in self.calls) else self.new_sha}}
        if method == "GET" and path.startswith("/git/commits/"):
            return {"tree": {"sha": "a" * 40}}
        if method == "POST" and path == "/git/blobs":
            import base64
            data = base64.b64decode(payload["content"])
            sha = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()
            self.shas.append(sha)
            return {"sha": sha}
        if method == "POST" and path == "/git/trees":
            return {"sha": "c" * 40}
        if method == "POST" and path == "/git/commits":
            return {"sha": self.new_sha}
        if method == "POST" and path == "/git/refs":
            assert payload["ref"].startswith("refs/heads/operation/")
            return {"ref": payload["ref"]}
        if method == "POST" and path == "/pulls":
            assert payload["base"] == "main"
            return {"number": 321, "html_url": "https://github.com/andrebarros78/SMART-MEGA/pull/321"}
        if method == "PUT" and path == "/pulls/321/merge":
            assert payload["sha"] == self.new_sha
            return {"merged": True, "sha": self.new_sha}
        raise AssertionError((method, path))


def test_pr_first_publisher_transports_large_duplicate_artifacts_once(tmp_path):
    root, base, local = _fixture(tmp_path)
    api = FakeAPI(base)
    result = publish_commit(root, "complete-result", 3081, base, local, api=api)
    assert result["status"] == "PUBLISHED_CANONICAL_MAIN"
    assert result["remote_commit"] == api.new_sha
    assert result["pr_number"] == 321
    assert sum(method == "POST" and path == "/git/blobs" for method, path, _ in api.calls) == 2
    assert not any(method == "PATCH" and path.endswith("/main") for method, path, _ in api.calls)
    assert not any(method == "POST" and path == "/git/refs" and
                   payload["ref"] == "refs/heads/main" for method, path, payload in api.calls)


def test_rejects_stale_canonical_main_without_mutation(tmp_path):
    root, base, local = _fixture(tmp_path)
    api = FakeAPI("f" * 40)
    with pytest.raises(RuntimeError, match="main moved"):
        publish_commit(root, "complete-result", 3081, base, local, api=api)
    assert not any(method != "GET" for method, _, _ in api.calls)


def test_rejects_missing_credentials_before_network(monkeypatch):
    from smart_protected_pr_publication import GitHubAPI
    monkeypatch.delenv("SMART_MEGA_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(__import__("shutil"), "which", lambda _: None)
    with pytest.raises(PermissionError, match="credential"):
        GitHubAPI()

def test_canonical_operator_rejects_missing_auth_before_running_any_action(
        tmp_path, monkeypatch):
    import smart_github_operator as operator
    root, _, head = _fixture(tmp_path)
    monkeypatch.setattr(operator, "__file__", str(root / "smart_github_operator.py"))
    monkeypatch.setattr(operator, "_require_external_operator_authority",
                        lambda *_: None)
    monkeypatch.setattr(operator, "command_args",
                        lambda *_: pytest.fail("operator work began without publication auth"))
    for key in ("SMART_MEGA_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(__import__("shutil"), "which", lambda _: None)
    with pytest.raises(PermissionError, match="credential"):
        operator.execute("prepare", "3081")
    assert git(root, "rev-parse", "HEAD") == head
    assert git(root, "status", "--porcelain") == ""

def test_reuses_existing_github_cli_authorization_when_env_missing(monkeypatch):
    import shutil
    import subprocess
    from smart_protected_pr_publication import GitHubAPI
    for key in ("SMART_MEGA_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(shutil, "which",
                        lambda executable: "gh" if executable == "gh" else None)
    real_run = subprocess.run

    def fake_run(args, **kwargs):
        if args[:2] == ["gh", "auth"]:
            return subprocess.CompletedProcess(args, 0,
                                               stdout="fake-scoped-token\n",
                                               stderr="")
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)
    api = GitHubAPI()
    assert api._token == "fake-scoped-token"
