"""Publish exactly one operator-authorized card receipt to canonical Git main.

GitHub Actions is not required. The caller must already have checked
operator authorization, pre-draw schedule, frozen epoch and receipt integrity.
This function fails closed on dirty unrelated files, divergent remote,
non-main checkout or a different repository. It never pushes a prediction
or rewrites a previously committed receipt.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from smart_github_operator import _git, _changes, _pin_artifact_bytes, _verify_staged_bytes
from smart_operator_card_requests import _verified_receipt

CANONICAL_REMOTES = frozenset({
    "https://github.com/andrebarros78/SMART-MEGA.git",
    "git@github.com:andrebarros78/SMART-MEGA.git",
})


def publish_operator_card(root, receipt, *, pre_draw_check, allowed_remotes=CANONICAL_REMOTES):
    """Commit only the new card receipt and byte pin, then verify remote HEAD."""
    root = Path(root).resolve()
    if not callable(pre_draw_check):
        raise PermissionError("pre-draw operator authority callback required")
    if not isinstance(receipt, dict):
        raise ValueError("issued card receipt required")
    target = receipt.get("target_contest")
    ordinal = receipt.get("request_ordinal")
    request_id = receipt.get("operator_request_id")
    expected_sha = receipt.get("sha256")
    freeze_sha = receipt.get("freeze_sha256")
    if (type(target) is not int or target <= 0
            or type(ordinal) is not int or ordinal <= 0
            or not isinstance(request_id, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", request_id) is None
            or not isinstance(expected_sha, str)
            or not isinstance(freeze_sha, str) or len(freeze_sha) != 64):
        raise ValueError("invalid requested-card publication identity")
    if Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ValueError("operator publication requires Git root")
    if _git(root, "branch", "--show-current") != "main":
        raise PermissionError("operator card publication requires canonical main checkout")
    origin = _git(root, "remote", "get-url", "origin")
    if origin not in allowed_remotes:
        raise PermissionError("origin is not approved SMART-MEGA GitHub repository")

    relative = f"runtime/operator_card_requests/{target}/CARD-{ordinal:04d}-{request_id}.json"
    path = root / relative
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError("operator card receipt path unavailable or unsafe")
    record = _verified_receipt(path, target, freeze_sha)
    if record != receipt or record["sha256"] != expected_sha:
        raise ValueError("operator card payload differs from signed receipt")
    if (record.get("explicit_operator_request") is not True
            or record.get("result_used") is not False
            or record.get("model_weights_changed") is not False
            or record.get("cards_issued_for_this_request") != 1):
        raise PermissionError("unapproved or result-contaminated operator card")

    changed = set(_changes(root))
    head = _git(root, "rev-parse", "HEAD")
    remote_output = _git(root, "ls-remote", "origin", "refs/heads/main").split()
    if len(remote_output) != 2 or remote_output[1] != "refs/heads/main":
        raise ValueError("canonical remote main could not be independently resolved")
    remote = remote_output[0]
    pre_draw_check()  # authoritative schedule must be validated immediately before commit
    if not changed and head == remote:
        # Exactly this receipt is already persisted in verified canonical HEAD.
        committed_bytes = _git(root, "show", f"HEAD:{relative}")
        if hashlib.sha256((committed_bytes + "\n").encode("utf-8")).hexdigest() != hashlib.sha256(path.read_bytes()).hexdigest():
            # Git show text output strips trailing newlines. Compare canonical JSON instead.
            committed = json.loads(_git(root, "show", f"HEAD:{relative}"))
            if committed != record:
                raise ValueError("canonical receipt differs from requested card")
        return {"status": "ALREADY_PUBLISHED", "target_contest": target, "request_id": request_id,
                "receipt_path": relative, "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "commit": head, "remote_main_verified": True}

    if changed == {relative} and head == remote:
        attrs_changed = _pin_artifact_bytes(root, [relative])
        expected_files = {relative} | ({".gitattributes"} if attrs_changed else set())
        _git(root, "add", "--", *sorted(expected_files))
        _git(root, "-c", "core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol",
             "diff", "--cached", "--check")
        _verify_staged_bytes(root, [relative])
        _git(root, "-c", "user.name=SMART-MEGA Operator",
             "-c", "user.email=smart-mega-operator@users.noreply.github.com",
             "commit", "-m", f"operation: request-card contest {target} request {request_id}")
        head = _git(root, "rev-parse", "HEAD")
    elif not changed and head != remote:
        # A failed network push may leave one local commit with our exact card.
        delta = _git(root, "diff", "--name-only", remote, head).splitlines()
        commits = _git(root, "rev-list", "--count", f"{remote}..{head}")
        if commits != "1" or set(delta) - {relative, ".gitattributes"}:
            raise RuntimeError("unpublished local Git state is not a single card receipt")
    else:
        raise RuntimeError("operator card publication sees other changes or diverged main")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise RuntimeError("operator card publication left uncommitted changes")
    pre_draw_check()
    _git(root, "push", "origin", "HEAD:refs/heads/main")
    confirmed = _git(root, "ls-remote", "origin", "refs/heads/main").split()
    if not confirmed or confirmed[0] != head:
        raise RuntimeError("published card commit not confirmed on remote main")
    return {
        "status": "CARD_RECEIPT_PUBLISHED_GITHUB_NATIVE",
        "target_contest": target,
        "request_id": request_id,
        "receipt_path": relative,
        "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "commit": head,
        "remote_main_verified": True,
    }
