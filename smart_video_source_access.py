"""Governed CAIXA media-access circuit breaker, separate from video metadata catalog.

An official metadata listing does not authorize stream extraction or
predictive inference. A source gate survives reruns and cannot silently expire
after an anti-bot or authentication challenge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from smart_video_official_catalog import CHANNEL

SCHEMA = "SMART_CAIXA_MEDIA_SOURCE_GATE_V1"
POINTER = "SMART_CAIXA_MEDIA_SOURCE_CURRENT.json"
REASONS = {"YOUTUBE_SIGN_IN_REQUIRED", "HTTP_403", "HTTP_429", "SOURCE_POLICY_RESTRICTED"}


def _encode(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                     ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def read_source_gate(queue_root):
    root = Path(queue_root)
    pointer = root / POINTER
    if pointer.is_symlink():
        raise ValueError("SOURCE_GATE_SYMLINK")
    if not pointer.exists():
        return {"state": "UNBLOCKED", "reason": None}
    if not pointer.is_file() or pointer.stat().st_size > 10240:
        raise ValueError("SOURCE_GATE_SIZE_INVALID")
    obj = json.loads(pointer.read_text("utf-8"))
    if not isinstance(obj, dict) or obj.get("schema") != SCHEMA or obj.get("official_channel_id") != CHANNEL:
        raise ValueError("SOURCE_GATE_SCHEMA_INVALID")
    actual = obj.get("sha256")
    if not isinstance(actual, str) or _sha({k: v for k, v in obj.items() if k != "sha256"}) != actual:
        raise ValueError("SOURCE_GATE_SHA_INVALID")
    if obj.get("state") != "BLOCKED" or obj.get("reason") not in REASONS:
        raise ValueError("SOURCE_GATE_STATE_INVALID")
    history = root / "source_gate_history" / (actual + ".json")
    if history.is_symlink() or not history.is_file() or history.read_bytes() != _encode(obj):
        raise ValueError("SOURCE_GATE_HISTORY_INVALID")
    return obj


def block_source(queue_root, reason, evidence_command_id):
    if reason not in REASONS:
        raise ValueError("SOURCE_GATE_REASON_INVALID")
    if not isinstance(evidence_command_id, str) or not re.fullmatch(r"netcmd_[0-9a-f]{32}", evidence_command_id):
        raise ValueError("SOURCE_GATE_EVIDENCE_ID_INVALID")
    # Reuse the exact OS lock of the queue itself; never race an active worker.
    from smart_video_official_queue import _exclusive
    root = Path(queue_root)
    if root.is_symlink() or not (root / "SMART_CAIXA_VISUAL_QUEUE_CURRENT.json").is_file():
        raise ValueError("OFFICIAL_QUEUE_NOT_INITIALIZED")
    with _exclusive(root):
        previous = read_source_gate(root)
        if previous["state"] == "BLOCKED":
            if previous.get("reason") == reason and previous.get("evidence_command_id") == evidence_command_id:
                return previous
            raise ValueError("SOURCE_ALREADY_BLOCKED_REQUIRES_EXPLICIT_REVIEW")
        body = {
            "schema": SCHEMA,
            "official_channel_id": CHANNEL,
            "state": "BLOCKED",
            "reason": reason,
            "evidence_command_id": evidence_command_id,
            "release_policy": "REQUIRES_AUTHORIZED_SOURCE_ACCESS_PROOF",
            "predictive_weight": 0.0,
        }
        doc = dict(body, sha256=_sha(body))
        history_dir = root / "source_gate_history"
        if history_dir.is_symlink():
            raise ValueError("SOURCE_GATE_HISTORY_SYMLINK")
        history_dir.mkdir(exist_ok=True)
        archive = history_dir / (doc["sha256"] + ".json")
        if archive.exists() or archive.is_symlink():
            if archive.is_symlink() or archive.read_bytes() != _encode(doc):
                raise ValueError("SOURCE_GATE_ARCHIVE_CONFLICT")
        else:
            with archive.open("xb") as w:
                w.write(_encode(doc))
                w.flush()
                os.fsync(w.fileno())
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(dir=root, mode="wb",
                                             prefix=".source-gate.", suffix=".tmp",
                                             delete=False) as w:
                tmp = Path(w.name)
                w.write(_encode(doc))
                w.flush()
                os.fsync(w.fileno())
            os.replace(tmp, root / POINTER)
            tmp = None
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
        return doc


def main():
    p = argparse.ArgumentParser(description="Official CAIXA video access circuit breaker")
    p.add_argument("--queue-dir", required=True)
    p.add_argument("--block-reason", choices=sorted(REASONS))
    p.add_argument("--evidence-command-id")
    args = p.parse_args()
    if bool(args.block_reason) != bool(args.evidence_command_id):
        p.error("block reason and evidence must be given together")
    result = (block_source(args.queue_dir, args.block_reason, args.evidence_command_id)
              if args.block_reason else read_source_gate(args.queue_dir))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
