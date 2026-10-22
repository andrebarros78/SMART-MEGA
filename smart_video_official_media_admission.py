"""Read-only, fail-closed bridge between B2's official queue and frame acquisition.

A public YouTube oEmbed success proves at most video metadata. Neither an HTML
response nor a catalog record proves frame decoding, source access authority
or point-in-time availability. No cookies, proxy, or network calls are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

SCHEMA = "SMART_VIDEO_OFFICIAL_MEDIA_ADMISSION_V1"
OFFICIAL_CHANNEL_ID = "UCPbhr02AfVb2nd5pm12BxTw"
EXPECTED_AUTHOR_URL = "https://www.youtube.com/@caixa"
GATE_FILE = "SMART_CAIXA_MEDIA_SOURCE_CURRENT.json"
QUEUE_FILE = "SMART_CAIXA_VISUAL_QUEUE_CURRENT.json"
REASONS = {"YOUTUBE_SIGN_IN_REQUIRED", "HTTP_403", "HTTP_429", "SOURCE_POLICY_RESTRICTED"}
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_COMMAND = re.compile(r"netcmd_[0-9a-f]{32}\Z")
_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")
_CONTEST = re.compile(r"[1-9][0-9]{0,11}\Z")
OUTCOME_FIELDS = {
    "winning_numbers", "drawn_numbers", "result_numbers",
    "dezenas_sorteadas", "hit_count", "official_result", "sorteadas",
    "numero_sorteado", "actual_winners", "winner_information",
    "prize_distribution",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _read_hashed_json(path: Path, max_bytes: int) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("FILE_UNAVAILABLE_OR_SYMLINK")
    if not 2 <= path.stat().st_size <= max_bytes:
        raise ValueError("FILE_SIZE_INVALID")
    obj = json.loads(path.read_bytes())
    if not isinstance(obj, dict) or not _SHA.fullmatch(str(obj.get("sha256") or "")):
        raise ValueError("DOCUMENT_OR_HASH_INVALID")
    if obj["sha256"] != _sha({k: v for k, v in obj.items() if k != "sha256"}):
        raise ValueError("DOCUMENT_HASH_MISMATCH")
    return obj


def _has_outcome_labels(item: Any) -> bool:
    if isinstance(item, dict):
        return any(str(k).casefold() in OUTCOME_FIELDS or _has_outcome_labels(v)
                   for k, v in item.items())
    if isinstance(item, list):
        return any(_has_outcome_labels(v) for v in item)
    return False


def _valid_public_queue(queue: dict[str, Any], contest_id: str) -> dict[str, Any]:
    if (queue.get("schema") != "SMART_CAIXA_VISUAL_QUEUE_V1"
            or queue.get("official_channel_id") != OFFICIAL_CHANNEL_ID
            or queue.get("predictive_evidence") != "NOT_ESTABLISHED"
            or type(queue.get("predictive_weight")) not in (float, int)
            or queue.get("predictive_weight") != 0.0):
        raise ValueError("OFFICIAL_QUEUE_CONTRACT_INVALID")
    records = queue.get("records")
    if not isinstance(records, dict) or not 1 <= len(records) <= 2000:
        raise ValueError("OFFICIAL_QUEUE_RECORDS_INVALID")
    record = records.get(contest_id)
    if not isinstance(record, dict) or _has_outcome_labels(record):
        raise ValueError("OFFICIAL_QUEUE_RECORD_UNAVAILABLE_OR_RESULT_LEAKAGE")
    vid = record.get("video_id")
    if not isinstance(vid, str) or not _VIDEO_ID.fullmatch(vid):
        raise ValueError("OFFICIAL_QUEUE_VIDEO_ID_INVALID")
    expected_url = f"https://www.youtube.com/watch?v={vid}"
    if (record.get("contest_id") != contest_id
            or record.get("source_url") != expected_url):
        raise ValueError("OFFICIAL_QUEUE_SOURCE_MISMATCH")
    path = str(queue.get("checkpoint_dir") or "").replace("\\", "/").upper().split("/")
    if any(component.startswith("SYNTHETIC_ONLY") for component in path):
        raise ValueError("OFFICIAL_QUEUE_SYNTHETIC_ROOT")
    return record


def _validate_blocked_gate(root: Path, gate: dict[str, Any]) -> None:
    if (gate.get("schema") != "SMART_CAIXA_MEDIA_SOURCE_GATE_V1"
            or gate.get("official_channel_id") != OFFICIAL_CHANNEL_ID
            or gate.get("state") != "BLOCKED"
            or gate.get("reason") not in REASONS
            or gate.get("release_policy") != "REQUIRES_AUTHORIZED_SOURCE_ACCESS_PROOF"
            or gate.get("predictive_weight") != 0.0
            or not _COMMAND.fullmatch(str(gate.get("evidence_command_id") or ""))):
        raise ValueError("SOURCE_GATE_SCHEMA_OR_POLICY_INVALID")
    history = root / "source_gate_history" / (gate["sha256"] + ".json")
    encoded = (json.dumps(gate, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if history.is_symlink() or not history.is_file() or history.read_bytes() != encoded:
        raise ValueError("SOURCE_GATE_HISTORY_INVALID")


def _probe_status(probe: dict[str, Any] | None, video_id: str) -> tuple[str, dict[str, Any]]:
    metadata = {
        "status": "NO_RECENT_PUBLIC_PROBE", "video_id": video_id,
        "oembed_http_status": None, "watch_http_status": None,
        "oembed_sha256": None, "receipt": None,
        "receipt_cryptographically_verified": False,
        "scope": "PUBLIC_VIDEO_METADATA_ONLY",
    }
    if probe is None:
        return "NOT_PROBED", metadata
    if not isinstance(probe, dict) or probe.get("video_id") != video_id:
        return "ID_MISMATCH", metadata
    watch = probe.get("watch_http_status")
    oembed = probe.get("oembed_http_status")
    metadata.update(oembed_http_status=oembed, watch_http_status=watch)
    watch_receipt = str(probe.get("watch_command_id") or "")
    metadata["watch_receipt"] = watch_receipt if _COMMAND.fullmatch(watch_receipt) else None
    if watch is not None and not metadata["watch_receipt"]:
        access = "WATCH_RESPONSE_RECEIPT_UNATTESTED"
    elif watch == 429:
        access = "HTTP_429_RESTRICTED"
    elif watch in (401, 403):
        access = "AUTHENTICATION_OR_POLICY_REQUIRED"
    elif watch == 200:
        access = "HTML_ONLY_NO_FRAME_EVIDENCE"
    else:
        access = "STREAM_ACCESS_UNPROVEN"
    # Separate independently governed commands: one public watch-page
    # attempt and another public oEmbed metadata receipt.
    receipt = str(probe.get("oembed_command_id") or "")
    stamp = str(probe.get("probe_utc") or "")
    try:
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        timestamp_valid = dt.tzinfo is not None and dt <= datetime.now(timezone.utc) + timedelta(minutes=5)
    except ValueError:
        timestamp_valid = False
    metadata["receipt"] = receipt if _COMMAND.fullmatch(receipt) else None
    if (oembed == 200
            and _SHA.fullmatch(str(probe.get("oembed_sha256") or ""))
            and probe.get("oembed_author_name") == "CAIXA"
            and probe.get("oembed_author_url") == EXPECTED_AUTHOR_URL
            and _COMMAND.fullmatch(receipt)
            and timestamp_valid):
        # The consumer can validate receipt syntax, not independently query
        # the signed network-command journal. Never promote a caller-supplied
        # netcmd ID or self-reported oEmbed digest to an authenticated proof.
        metadata["status"] = "REPORTED_METADATA_ONLY"
        metadata["oembed_sha256"] = probe["oembed_sha256"]
    else:
        metadata["status"] = "UNVERIFIED_METADATA"
    return access, metadata


def audit_official_media_admission(
    queue_dir: str | Path,
    contest_id: str,
    *,
    probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Do not authorize extraction from catalog metadata or an old blocked gate.

    In this V1 no source-release contract exists, so this deliberately never
    returns an allow signal. Decoding needs independently reviewed source
    authorization and actual extracted-frame proof before any checkpoint.
    """
    target = str(contest_id)
    if not _CONTEST.fullmatch(target):
        raise ValueError("INVALID_CONTEST_ID")
    root = Path(queue_dir)
    output: dict[str, Any] = {
        "schema": SCHEMA, "status": "OFFICIAL_QUEUE_UNAVAILABLE",
        "contest_id": target, "official_channel_id": OFFICIAL_CHANNEL_ID,
        "queue_sha256": None, "source_gate_sha256": None,
        "source_gate_reason": None, "source_url": None,
        "public_metadata": None, "video_access_status": "NOT_PROBED",
        "media_capture_authorized": False,
        "checkpoint_generation_authorized": False,
        "physical_frames_verified": None,
        "capture_manifest_sha256": None,
        "real_observational_utility": None,
        "pit_independently_attested": False,
        "predictive_evidence": "NOT_ESTABLISHED", "predictive_weight": 0.0,
        "read_only": True,
        "limitations": [
            "Public oEmbed metadata and video page HTML never establish decodable frames.",
            "An existing source gate cannot be released by a public HTTP success.",
            "No historical timestamp, cutoff, or future predictive benefit is asserted.",
        ],
    }
    parts = str(root).replace("\\", "/").upper().split("/")
    if any(component.startswith("SYNTHETIC_ONLY") for component in parts):
        output["status"] = "SYNTHETIC_SOURCE_QUARANTINED"
        return output
    if root.is_symlink() or not root.is_dir():
        return output
    try:
        queue = _read_hashed_json(root / QUEUE_FILE, max_bytes=2 * 1024 * 1024)
        record = _valid_public_queue(queue, target)
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError):
        output["status"] = "OFFICIAL_QUEUE_REJECTED"
        return output
    output["queue_sha256"] = queue["sha256"]
    output["source_url"] = record["source_url"]
    access, metadata = _probe_status(probe, record["video_id"])
    output["video_access_status"] = access
    output["public_metadata"] = metadata
    if access == "ID_MISMATCH":
        output["status"] = "PUBLIC_PROBE_ID_MISMATCH"
        return output
    gate_pointer = root / GATE_FILE
    if not gate_pointer.exists() and not gate_pointer.is_symlink():
        output["status"] = "SOURCE_AUTHORIZATION_NOT_ATTESTED"
        return output
    try:
        gate = _read_hashed_json(gate_pointer, max_bytes=10240)
        _validate_blocked_gate(root, gate)
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError):
        output["status"] = "SOURCE_GATE_INTEGRITY_REJECTED"
        return output
    output["source_gate_sha256"] = gate["sha256"]
    output["source_gate_reason"] = gate["reason"]
    output["status"] = "OFFICIAL_MEDIA_SOURCE_BLOCKED"
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="SMART-MEGA CAIXA metadata/source authorization audit")
    parser.add_argument("--queue-dir", required=True)
    parser.add_argument("--contest", required=True)
    parser.add_argument("--probe-json", help="Saved public probe receipt; never a cookie or auth secret")
    args = parser.parse_args()
    probe = None
    if args.probe_json:
        p = Path(args.probe_json)
        if p.is_symlink() or not p.is_file() or p.stat().st_size > 32768:
            parser.error("probe receipt unavailable or oversized")
        probe = json.loads(p.read_text("utf-8"))
    report = audit_official_media_admission(args.queue_dir, args.contest, probe=probe)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    # V1 contains no independently authorized video-stream release operation.
    # An audit that completes correctly must not be interpreted as "media ready".
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
