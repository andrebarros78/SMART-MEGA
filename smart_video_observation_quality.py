"""Read-only per-video observational quality for official CAIXA checkpoints.

Reports distinguish official metadata, stream access, real decoded frames,
motion candidates and predictive validation. No missing media is invented.
Quality snapshots use immutable SHA256 history plus an atomic current pointer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from smart_video_official_catalog import read_current
from smart_video_official_queue import _read_state, _checkpoint_proof, _exclusive, _digest
from smart_video_observation import ObservationConfig
from smart_video_source_access import read_source_gate

SCHEMA = "SMART_CAIXA_OBSERVATIONAL_QUALITY_V1"
CURRENT = "SMART_CAIXA_OBSERVATIONAL_QUALITY_CURRENT.json"


def _bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _frame_counts(row):
    sample_sets = [row.get("coarse"), row.get("analyzed_windows")]
    windows = [s for samples in sample_sets if isinstance(samples, list)
               for s in samples if isinstance(s, dict)]
    good = [s for s in windows if s.get("status") == "OK"]
    return {
        "sample_windows": len(windows),
        "successful_sample_windows": len(good),
        "frames_read": sum(int(s.get("read_frames") or 0) for s in good
                           if isinstance(s.get("read_frames"), (int, float))
                           and not isinstance(s.get("read_frames"), bool)
                           and 0 <= s.get("read_frames") <= 10000000),
        "frames_analyzed": sum(int(s.get("analyzed_frames") or 0) for s in good
                               if isinstance(s.get("analyzed_frames"), (int, float))
                               and not isinstance(s.get("analyzed_frames"), bool)
                               and 0 <= s.get("analyzed_frames") <= 10000000),
    }


def _entry(contest, row, cp_root, cfg, hypothesis_id, blocked):
    status, sha, cp_status = _checkpoint_proof(cp_root, row, cfg, hypothesis_id)
    state = row.get("state")
    report = {
        "contest_id": contest,
        "video_id": row["video_id"],
        "queue_state": state,
        "source_access_blocked": blocked,
        "checkpoint_status": cp_status,
        "checkpoint_sha256": None,
        "observation_quality": "NOT_OBSERVED",
        "sample_windows": 0,
        "successful_sample_windows": 0,
        "frames_read": 0,
        "frames_analyzed": 0,
        "segment_guard_passed": False,
        "spatial_consensus_recurrent": False,
        "event_count": 0,
        "coverage_ratio": None,
        "semantic_result": "NOT_VERIFIED",
        "predictive_weight": 0.0,
    }
    if state == "VERIFIED" and status != "VERIFIED":
        report["observation_quality"] = "CHECKPOINT_CORRUPT_OR_MISSING"
        return report
    if state == "VERIFIED" and sha != row.get("checkpoint_sha256"):
        report["observation_quality"] = "CHECKPOINT_SHA_MISMATCH"
        return report
    if state != "VERIFIED":
        if status == "TAMPERED" or state == "QUARANTINED":
            report["observation_quality"] = "CHECKPOINT_UNTRUSTED"
        elif status == "FAILED":
            report["observation_quality"] = "PROCESSING_UNAVAILABLE"
        else:
            report["observation_quality"] = "SOURCE_ACCESS_BLOCKED" if blocked else "NOT_OBSERVED"
        return report
    cp_path = cp_root / ("contest_" + contest + ".json")
    if cp_path.is_symlink() or not cp_path.is_file() or cp_path.stat().st_size > 1048576:
        report["observation_quality"] = "CHECKPOINT_CORRUPT_OR_MISSING"
        return report
    doc = json.loads(cp_path.read_bytes())
    report["checkpoint_sha256"] = sha
    report.update(_frame_counts(doc))
    scope = doc.get("analysis_scope")
    report["segment_guard_passed"] = isinstance(scope, dict) and scope.get("segment_guard_passed") is True
    report["spatial_consensus_recurrent"] = (doc.get("spatial_consensus") or {}).get("recurrent") is True
    times = doc.get("event_timestamps_s")
    report["event_count"] = len(times) if isinstance(times, list) else 0
    coverage = doc.get("coverage_ratio")
    report["coverage_ratio"] = round(float(coverage), 6) if isinstance(coverage, (int, float)) and not isinstance(coverage, bool) and 0 <= coverage <= 1 else None
    if report["frames_analyzed"] == 0:
        report["observation_quality"] = "NO_DECODED_FRAME_PROOF"
    elif doc.get("status") == "CANDIDATE" and report["segment_guard_passed"] and report["spatial_consensus_recurrent"]:
        report["observation_quality"] = "MOTION_CANDIDATE_OBSERVED"
        report["semantic_result"] = "MOTION_ONLY_NOT_LOTTERY_PREDICTION"
    else:
        report["observation_quality"] = "MOTION_EVIDENCE_INSUFFICIENT"
    return report


def quality_snapshot(catalog_dir, checkpoint_dir, queue_dir, *, workers=1):
    root = Path(queue_dir)
    cp_root = Path(checkpoint_dir)
    if not root.is_dir() or root.is_symlink() or cp_root.is_symlink():
        raise ValueError("QUALITY_ROOT_INVALID")
    cat = read_current(Path(catalog_dir))
    queue = _read_state(root)
    if cat is None or queue is None or queue.get("catalog_sha256") != cat.get("sha256"):
        raise ValueError("QUALITY_CATALOG_QUEUE_MISMATCH")
    cfg = ObservationConfig(workers=workers).validated()
    if queue.get("config_sha256") != _digest(vars(cfg)) or queue.get("checkpoint_dir") != str(cp_root.resolve()):
        raise ValueError("QUALITY_CONFIG_DRIFT")
    blocker = read_source_gate(root)
    blocked = blocker["state"] == "BLOCKED"
    records = [_entry(contest, row, cp_root, cfg, queue.get("hypothesis_id"), blocked)
               for contest, row in sorted(queue["records"].items(), key=lambda x: int(x[0]))]
    counts = {status: sum(r["observation_quality"] == status for r in records)
              for status in sorted({r["observation_quality"] for r in records})}
    summary = {
        "schema": SCHEMA,
        "catalog_sha256": cat["sha256"],
        "queue_sha256": queue["sha256"],
        "source_gate_sha256": blocker.get("sha256"),
        "source_access_state": blocker["state"],
        "source_access_reason": blocker.get("reason"),
        "official_contests_in_queue": len(records),
        "count_by_quality": counts,
        "checkpoints_reporting_decoded_frames": sum(r["frames_analyzed"] > 0 for r in records),
        "records": records,
        "predictive_evidence": "NOT_ESTABLISHED",
        "predictive_weight_authorized": False,
        "predictive_weight": 0.0,
        "real_media_verified": False,
    }
    return summary


def save_quality_snapshot(catalog_dir, checkpoint_dir, queue_dir, *, workers=1,
                          output_dir=None):
    """Persist optional isolated quality ledger; source queue remains read-only."""
    root = Path(output_dir) if output_dir is not None else Path(queue_dir)
    if root.is_symlink():
        raise ValueError("QUALITY_OUTPUT_SYMLINK")
    if output_dir is not None and any(
        root.resolve() == Path(path).resolve()
        for path in (catalog_dir, checkpoint_dir, queue_dir)
    ):
        raise ValueError("QUALITY_OUTPUT_ROOT_COLLISION")
    with _exclusive(root):
        state = quality_snapshot(catalog_dir, checkpoint_dir, queue_dir, workers=workers)
        previous_path = root / CURRENT
        if previous_path.is_symlink():
            raise ValueError("QUALITY_POINTER_SYMLINK")
        previous = None
        if previous_path.exists():
            previous = json.loads(previous_path.read_text("utf-8"))
            prior_sha = previous.get("sha256")
            if not isinstance(prior_sha, str) or _digest({k: v for k, v in previous.items()
                                                        if k != "sha256"}) != prior_sha:
                raise ValueError("QUALITY_PREVIOUS_SHA_INVALID")
            prior_archive = root / "quality_history" / (prior_sha + ".json")
            if prior_archive.is_symlink() or not prior_archive.is_file() or prior_archive.read_bytes() != _bytes(previous):
                raise ValueError("QUALITY_PREVIOUS_ARCHIVE_INVALID")
            if {k: v for k, v in previous.items() if k != "sha256"} == state:
                return previous
        doc = dict(state, sha256=_digest(state))
        archive_dir = root / "quality_history"
        if archive_dir.is_symlink():
            raise ValueError("QUALITY_ARCHIVE_SYMLINK")
        archive_dir.mkdir(exist_ok=True)
        archive = archive_dir / (doc["sha256"] + ".json")
        payload = _bytes(doc)
        if archive.is_symlink():
            raise ValueError("QUALITY_ARCHIVE_SYMLINK")
        if archive.exists():
            if archive.read_bytes() != payload:
                raise ValueError("QUALITY_ARCHIVE_CONFLICT")
        else:
            with archive.open("xb") as w:
                w.write(payload)
                w.flush()
                os.fsync(w.fileno())
        temp = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", dir=root, delete=False,
                                             prefix=".quality.", suffix=".tmp") as w:
                temp = Path(w.name)
                w.write(payload)
                w.flush()
                os.fsync(w.fileno())
            os.replace(temp, previous_path)
            temp = None
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
        return doc


def main():
    p = argparse.ArgumentParser(description="Read and persist per-video CAIXA observational quality")
    p.add_argument("--catalog-dir", required=True)
    p.add_argument("--checkpoint-dir", required=True)
    p.add_argument("--queue-dir", required=True)
    p.add_argument("--workers", type=int, default=1)
    args = p.parse_args()
    report = save_quality_snapshot(args.catalog_dir, args.checkpoint_dir, args.queue_dir,
                                   workers=args.workers)
    print(json.dumps({
        "schema": report["schema"],
        "sha256": report["sha256"],
        "official_contests_in_queue": report["official_contests_in_queue"],
        "source_access_state": report["source_access_state"],
        "source_access_reason": report["source_access_reason"],
        "count_by_quality": report["count_by_quality"],
        "checkpoints_reporting_decoded_frames": report["checkpoints_reporting_decoded_frames"],
        "predictive_weight": 0.0,
    }, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
