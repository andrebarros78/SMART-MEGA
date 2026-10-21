"""SMART-MEGA V6 B2 read-only physical checkpoint observational gate.

The consumer operates only on *temporary isolated copies* of the validated
source bytes. Source timestamps are self-reported, NOT independent PIT proof.
This module never permits promotion of observational metrics into lottery
outcomes or predictive authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from smart_video_learning import (
    audit_checkpoint_inventory,
    get_visual_features,
    get_visual_learning_memory,
    _cutoff,
)
from smart_video_observation import PREDICTIVE_EVIDENCE

SCHEMA = "SMART_B2_PHYSICAL_LEARNING_AUDIT_V1"
SOURCE_PATTERN = re.compile(r"contest_([1-9][0-9]{0,11})\.json\Z")
MAX_BYTES = 1024 * 1024


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _result(status: str, root: Path, target: str, cutoff: str, expected: int) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": status,
        "physical_source_path": str(root),
        "target_contest": target,
        "cutoff_utc": cutoff,
        "cutoff_basis": "CALLER_SUPPLIED_NOT_EXTERNALLY_ATTESTED",
        "physical_source_claim": "LOCAL_FILESYSTEM_ONLY_IF_READ_SUCCESS",
        "expected_checkpoint_count": expected,
        "physical_files_read": 0,
        "file_integrity": None,
        "checkpoint_sha256": {},
        "snapshot_manifest_sha256": None,
        "temporal_provenance": {
            "self_reported_pre_cutoff": 0,
            "self_reported_post_cutoff": 0,
            "independently_attested": 0,
            "metadata_class": "UNTRUSTED_SOURCE_DECLARATION",
        },
        "pit_independently_attested": False,
        "observational_utility": None,
        "measured_predictive_gain": None,
        "predictive_evidence": PREDICTIVE_EVIDENCE,
        "predictive_weight": 0.0,
        "original_source_modified": False,
        "read_only_source": True,
        "model_execution_enabled": False,
        "limitations": [
            "File and checkpoint hashes establish current content identity, not historical existence.",
            "created_at_utc and filesystem modification times cannot independently attest pre-cutoff capture.",
            "Event observations are not proven Mega-Sena ball events or predictive gains.",
        ],
    }


def audit_b2_physical_learning(
    checkpoint_dir: str | Path,
    target_contest: str,
    cutoff_utc: str,
    *,
    expected_count: int = 13,
) -> dict[str, Any]:
    target = str(target_contest)
    if not target.isascii() or not target.isdecimal() or int(target) < 1:
        raise ValueError("INVALID_TARGET_CONTEST")
    cutoff = _cutoff(cutoff_utc)
    if type(expected_count) is not int or not 1 <= expected_count <= 512:
        raise ValueError("INVALID_CHECKPOINT_EXPECTATION")

    root = Path(checkpoint_dir)
    result = _result("PHYSICAL_SOURCE_UNAVAILABLE", root, target, cutoff, expected_count)
    if root.is_symlink() or not root.is_dir():
        return result

    inventory = audit_checkpoint_inventory(root, expected_count=expected_count)
    result["file_integrity"] = {
        "status": inventory["status"],
        "files_discovered": inventory["files_discovered"],
        "valid_count": inventory["valid_count"],
        "invalid_count": inventory["invalid_count"],
        "truncated": inventory["truncated"],
        "records": inventory["records"],
    }
    result["physical_files_read"] = inventory["valid_count"] + inventory["invalid_count"]
    if inventory["invalid_count"] or inventory["truncated"]:
        result["status"] = "PHYSICAL_INTEGRITY_REJECTED"
        return result
    if inventory["status"] != "CHECKPOINT_INTEGRITY_PASS":
        result["status"] = "PHYSICAL_COUNT_NOT_VERIFIED"
        return result

    # Copy once, then compare each saved source digest to the independently
    # checked inventory. Consume the isolated copy only: original B2 root
    # remains free of SQLite indexes, learning states and other writes.
    bytes_by_id: dict[str, bytes] = {}
    rows: dict[str, dict[str, Any]] = {}
    pre, post = 0, 0
    source_digests: dict[str, str] = {}
    for recorded in inventory["records"]:
        contest = str(recorded["contest_id"])
        path = root / f"contest_{contest}.json"
        if (not SOURCE_PATTERN.fullmatch(path.name)
                or path.is_symlink() or not path.is_file()):
            result["status"] = "PHYSICAL_INTEGRITY_REJECTED"
            return result
        if path.stat().st_size > MAX_BYTES:
            result["status"] = "PHYSICAL_INTEGRITY_REJECTED"
            return result
        raw = path.read_bytes()
        digest = _sha(raw)
        if digest != recorded.get("sha256"):
            result["status"] = "PHYSICAL_MUTATED_DURING_AUDIT"
            return result
        row = json.loads(raw)
        observed = datetime.fromisoformat(_cutoff(row["created_at_utc"]))
        if observed <= datetime.fromisoformat(cutoff):
            pre += 1
        else:
            post += 1
        bytes_by_id[contest] = raw
        source_digests[contest] = digest
        rows[contest] = row

    result["checkpoint_sha256"] = dict(sorted(source_digests.items(), key=lambda x: int(x[0])))
    manifest = json.dumps(result["checkpoint_sha256"], sort_keys=True, separators=(",", ":"))
    result["snapshot_manifest_sha256"] = _sha(manifest.encode("utf-8"))
    result["temporal_provenance"]["self_reported_pre_cutoff"] = pre
    result["temporal_provenance"]["self_reported_post_cutoff"] = post

    try:
        with tempfile.TemporaryDirectory(prefix="smartmega-b2-shadow-") as scratch:
            isolated = Path(scratch)
            for contest, raw in bytes_by_id.items():
                (isolated / f"contest_{contest}.json").write_bytes(raw)
            features = get_visual_features(target, cutoff, isolated)
            episodes = get_visual_learning_memory(target, cutoff, isolated)
            expected = features["source_sha256"]
            actual = {
                str(x["contest_id"]): x["checkpoint_sha256"] for x in episodes["episodic"]
            }
            if (features["predictive_weight"] != 0.0
                    or episodes["predictive_weight"] != 0.0
                    or episodes["predictive_evidence"] != "NOT_ESTABLISHED"
                    or episodes["source_gate"] != "BLOCKED"
                    or expected != actual
                    or episodes["semantic"]["observed_event_count"]
                        != episodes["graph"]["edge_count"]):
                raise ValueError("CONSUMER_INTEGRITY_MISMATCH")
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        result["status"] = "PHYSICAL_CONSUMER_REJECTED"
        result["consumer_rejection_class"] = type(exc).__name__
        return result

    eligible = features["source_contests"]
    if not all(0 < n < int(target) for n in eligible):
        result["status"] = "PHYSICAL_CONSUMER_REJECTED"
        return result
    event_counts = [x["motion_event_count"] for x in episodes["episodic"]]
    result["observational_utility"] = {
        "scope": "DESCRIPTIVE_VIDEO_MOTION_ONLY",
        "verified_physical_checkpoints": len(rows),
        "candidate_checkpoints": sum(r.get("status") == "CANDIDATE" for r in rows.values()),
        "eligible_episodes": len(eligible),
        "excluded_from_consumer": len(rows) - len(eligible),
        "eligible_contest_ids": eligible,
        "observed_motion_events": sum(event_counts),
        "events_per_eligible_episode_median": (
            statistics.median(event_counts) if event_counts else None
        ),
        "graph_edges": episodes["graph"]["edge_count"],
        "normalized_event_histogram": episodes["semantic"][
            "observational_motion_histogram_10_bins"
        ],
        "cache_index_hit": episodes["metrics"]["index_hit"],
        "source_sha256": expected,
        "provenance_sha256": episodes["provenance_sha256"],
        "utility_for_prediction": "NOT_MEASURED",
        "downstream_card_consumption": "NOT_MEASURED",
    }
    result["status"] = "OBSERVATIONAL_SHADOW_ONLY"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="B2 physical checkpoint read-only learning gate")
    parser.add_argument("--checkpoint-dir", required=True)
    parser.add_argument("--target-contest", required=True)
    parser.add_argument("--cutoff-utc", required=True)
    parser.add_argument("--expected-count", type=int, default=13)
    args = parser.parse_args()
    result = audit_b2_physical_learning(
        args.checkpoint_dir, args.target_contest, args.cutoff_utc,
        expected_count=args.expected_count,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "OBSERVATIONAL_SHADOW_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
