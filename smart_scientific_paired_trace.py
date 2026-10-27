"""Read-only 224-draw evidence validation for the scientific SHADOW gate.

A pinned Git file proves archival identity, not predictive reproducibility.
Replayed=True is permitted only after a separate frozen-source engine replay.
Never issue model promotion authority from this module.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from smart_f11_predictive_nonregression import _tracked_blob_sha
from smart_paired_trace_guard import paired_sign_test

TRACE_PATH = "evidence/3075/SMART_3075_PAIRED_HOLDOUT_TRACE_224.json"
TRACE_GIT_BLOB = "26ef3fe6d730a862e68c8b9f79a731aaa4a85447"
TRACE_SHA256 = "3bb7a2535a657cde47d46515fe3b89a3359118a3642cffa912bd3218bbcb22cd"
CUTOFF_SNAPSHOT_SHA256 = "c87bde2b81af2a4c24800236b323711e7a96184ea7122b8cd958e7b78985caa6"
BASELINE_ENGINE_BLOB = "e5b3c1829158d163cd82785b83421c370e1c93d0"
CANDIDATE_ENGINE_BLOB = "3b0340fee746a699cf0ea57f265760ebbbd861f0"
BASELINE_ENGINE_SHA256 = "edf434aabe1a140a6b3fdb16aaa332cbc46077545abebd1612b109a6839a074a"
FIRST = 2851
LAST = 3074
N = LAST - FIRST + 1


def _card(value: Any) -> bool:
    return (type(value) is list and len(value) == 6
            and all(type(x) is int and 1 <= x <= 60 for x in value)
            and len(set(value)) == 6)


def _outcome(trace: dict[str, Any], expected: Mapping[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    metadata = trace.get("metadata")
    valid_metadata = (isinstance(metadata, dict)
                      and metadata.get("source_baseline_sha256") == BASELINE_ENGINE_SHA256
                      and metadata.get("frozen_data_sha256") == CUTOFF_SNAPSHOT_SHA256
                      and metadata.get("source_head_scoped_to_pr92") == CANDIDATE_ENGINE_BLOB
                      and metadata.get("model_selection_authorized") is False
                      and metadata.get("scientific_status") == "RETROSPECTIVE_REPLAY_VERIFIED_NOT_PROSPECTIVE")
    if (trace.get("schema") != "SMART_PAIRED_HOLDOUT_TRACE_1"
        or trace.get("target_contest") != 3075
        or trace.get("cutoff_contest") != LAST
        or trace.get("holdout_start") != FIRST
        or trace.get("holdout_end") != LAST
        or trace.get("snapshot_sha256") != CUTOFF_SNAPSHOT_SHA256
        or trace.get("baseline_engine_git_blob") != BASELINE_ENGINE_BLOB
        or trace.get("candidate_engine_git_blob") != CANDIDATE_ENGINE_BLOB
        or trace.get("future_result_used") is not False
        or trace.get("promotion_authorized") is not False
        or not valid_metadata):
        errors.append("PAIRED_TRACE_TEMPORAL_OR_SOURCE_INVALID")
    rows = trace.get("rows")
    if not isinstance(rows, list) or len(rows) != N:
        errors.append("PAIRED_TRACE_SEQUENCE_INVALID")
        rows = [] if not isinstance(rows, list) else rows

    w = l = t = b_total = c_total = 0
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append("PAIRED_TRACE_SEQUENCE_INVALID")
            continue
        contest = FIRST + i
        if (type(row.get("contest")) is not int or row["contest"] != contest
            or type(row.get("prediction_cutoff")) is not int
            or row["prediction_cutoff"] != contest - 1):
            errors.append("PAIRED_TRACE_SEQUENCE_INVALID")
        b, c = row.get("baseline_top6"), row.get("candidate_top6")
        if not _card(b) or not _card(c):
            errors.append("PAIRED_TRACE_CARDS_INVALID")
            continue
        bh, ch = row.get("baseline_hits"), row.get("candidate_hits")
        if (type(bh) is not int or not 0 <= bh <= 6
            or type(ch) is not int or not 0 <= ch <= 6):
            errors.append("PAIRED_TRACE_SUMMARY_INVALID")
            continue
        b_total += bh
        c_total += ch
        if ch > bh:
            w += 1
        elif ch < bh:
            l += 1
        else:
            t += 1
    p = paired_sign_test(w, l)
    summary = trace.get("summary")
    if not isinstance(summary, dict):
        errors.append("PAIRED_TRACE_SUMMARY_INVALID")
    else:
        expected_pairs = {
            "baseline_hits": b_total, "candidate_hits": c_total,
            "candidate_wins": w, "baseline_wins": l, "ties": t,
        }
        if any(type(summary.get(k)) is not int or summary[k] != v for k, v in expected_pairs.items()):
            errors.append("PAIRED_TRACE_SUMMARY_INVALID")
        claimed = summary.get("one_sided_p")
        if (type(claimed) not in (int, float) or not math.isfinite(claimed)
            or not math.isclose(claimed, p, rel_tol=0, abs_tol=1e-12)):
            errors.append("PAIRED_TRACE_SUMMARY_INVALID")
    e_base = expected.get("baseline", {}).get("holdout", {}).get("hits")
    e_new = expected.get("candidate", {}).get("holdout", {}).get("hits")
    e_pairs = expected.get("paired_holdout", {})
    if (b_total != e_base or c_total != e_new
        or w != e_pairs.get("candidate_wins")
        or l != e_pairs.get("baseline_wins")
        or t != e_pairs.get("ties")
        or not math.isclose(p, e_pairs.get("one_sided_sign_test_p", -1), abs_tol=1e-12)):
        errors.append("PAIRED_TRACE_AGGREGATE_DISAGREEMENT")
    return sorted(set(errors)), {
        "baseline_hits": b_total, "candidate_hits": c_total,
        "candidate_wins": w, "baseline_wins": l, "ties": t, "one_sided_p": p,
    }


def audit_paired_trace(
    root: str | Path,
    expected: Mapping[str, Any],
    *,
    trace_override: dict[str, Any] | None = None,
    independently_replayed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate signed, chronological evidence; don't mistake identity for replay."""
    root = Path(root).resolve()
    path = root / TRACE_PATH
    errors: list[str] = []
    disk_trace: dict[str, Any] | None = None
    raw: bytes | None = None
    try:
        raw = path.read_bytes()
        disk_trace = json.loads(raw.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        errors.append("PAIRED_TRACE_FILE_MISSING_OR_INVALID")
    pinned = (raw is not None and hashlib.sha256(raw).hexdigest() == TRACE_SHA256
              and _tracked_blob_sha(root, TRACE_PATH) == TRACE_GIT_BLOB
              and trace_override is None)
    if not pinned:
        errors.append("PAIRED_TRACE_ARTIFACT_NOT_PINNED")
    trace = trace_override if trace_override is not None else disk_trace
    if not isinstance(trace, dict):
        errors.append("PAIRED_TRACE_SEQUENCE_INVALID")
        trace = {}
    issues, paired = _outcome(trace, expected)
    errors.extend(issues)

    independently_verified = False
    if independently_replayed is not None:
        if (not isinstance(independently_replayed, dict)
            or independently_replayed != disk_trace or trace != disk_trace or not pinned):
            errors.append("INDEPENDENT_PAIRED_REPLAY_MISMATCH")
        else:
            independently_verified = True

    status = ("INVALID_EVIDENCE" if errors else
              ("VERIFIED_INDEPENDENT_REPLAY" if independently_verified
               else "PINNED_REPLAY_REQUIRED"))
    return {
        "status": status,
        "artifact_git_blob_verified": pinned,
        "archive_git_blob": TRACE_GIT_BLOB,
        "archive_sha256": TRACE_SHA256,
        "frozen_snapshot_sha256": CUTOFF_SNAPSHOT_SHA256,
        "chronological_rows": len(trace.get("rows", [])) if isinstance(trace.get("rows"), list) else 0,
        "holdout": paired,
        "per_draw_prediction_replayed": independently_verified,
        "retrospective_only": True,
        "promotion_authorized": False,
        "errors": sorted(set(errors)),
    }
