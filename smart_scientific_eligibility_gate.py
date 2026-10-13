"""Read-only scientific eligibility triage for the canonical SMART-MEGA ledger.

A matching historical freeze hash is necessary, never sufficient, for
independently witnessed prospective evidence. This diagnostic cannot replace
the unmodified independent P14/P15 audit or authorize a production card.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from smart_prospective_operator_request_gate import preflight

SCHEMA = "SMART_SCIENTIFIC_ELIGIBILITY_TRIAGE_V1"


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _date(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp missing")
    time = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if time.utcoffset() is None:
        raise ValueError("timestamp timezone missing")
    return time.astimezone(timezone.utc)


def _frozen_path(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("unsafe frozen path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("unsafe frozen path")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("frozen file escaped canonical root")
    return resolved


def _six(numbers: Any) -> bool:
    return (isinstance(numbers, list) and len(numbers) == 6
            and all(type(x) is int and 1 <= x <= 60 for x in numbers)
            and len(set(numbers)) == 6)


def _adjudication_evidence(
    root: Path, events: list[dict[str, Any]], index: int, adjudication: dict[str, Any]
) -> dict[str, Any]:
    target = adjudication.get("target_contest")
    sha = adjudication.get("freeze_sha256")
    row: dict[str, Any] = {
        "target_contest": target,
        "freeze_sha256": sha,
        "status": "EXCLUDED_UNVERIFIED",
        "freeze_path": None,
        "file_hash_verified": False,
        "causal_metadata_verified": False,
        "independent_pre_draw_witness_verified": False,
        "scientifically_admissible": False,
        "reason": "unknown",
    }
    if type(target) is not int or target < 1 or not isinstance(sha, str) or len(sha) != 64:
        row["reason"] = "MALFORMED_ADJUDICATION"
        return row
    try:
        int(sha, 16)
    except ValueError:
        row["reason"] = "MALFORMED_FREEZE_HASH"
        return row
    matches = [
        (i, event) for i, event in enumerate(events)
        if event.get("event_type") == "FREEZE"
        and event.get("target_contest") == target
        and event.get("freeze_sha256") == sha
    ]
    if len(matches) != 1 or matches[0][0] >= index:
        row["reason"] = "MISSING_AMBIGUOUS_OR_NONCAUSAL_FREEZE_EVENT"
        return row
    fi, freeze = matches[0]
    row["freeze_path"] = freeze.get("freeze_file")
    if (
        freeze.get("frozen_before_result") is not True
        or freeze.get("causal_cutoff") is not True
        or freeze.get("cutoff_contest") != target - 1
        or not _six(adjudication.get("actual_numbers"))
    ):
        row["reason"] = "INVALID_CAUSAL_OR_RESULT_METADATA"
        return row
    if any(
        later.get("target_contest") == target and later.get("event_type") in ("FREEZE", "SUPERSEDE")
        for later in events[index + 1:]
    ):
        row["reason"] = "FREEZE_OR_SUPERSEDE_AFTER_ADJUDICATION"
        return row
    try:
        if _date(freeze.get("created_utc")) >= _date(adjudication.get("created_utc")):
            row["reason"] = "FREEZE_TIMESTAMP_NOT_EARLIER"
            return row
        path = _frozen_path(root, freeze.get("freeze_file"))
    except (ValueError, TypeError, OverflowError):
        row["reason"] = "INVALID_FREEZE_PATH_OR_TIME"
        return row
    if not path.is_file():
        row["reason"] = "ORIGINAL_FREEZE_NOT_AVAILABLE"
        return row
    if _sha256(path) != sha:
        row["reason"] = "ORIGINAL_FREEZE_SHA256_MISMATCH"
        return row
    row["file_hash_verified"] = True
    try:
        frozen = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeDecodeError, OSError):
        row["reason"] = "FROZEN_FILE_NOT_VALID_JSON"
        return row
    if (
        not isinstance(frozen, dict)
        or frozen.get("target_contest") != target
        or frozen.get("cutoff_contest") != target - 1
        or frozen.get("frozen_before_result") is not True
        or frozen.get("causal_cutoff") is not True
    ):
        row["reason"] = "FROZEN_CONTENT_CAUSAL_CONTRACT_INVALID"
        return row
    row["causal_metadata_verified"] = True
    row["status"] = "HASH_VERIFIED_PRELIMINARY"
    row["reason"] = "INDEPENDENT_PRE_DRAW_WITNESS_AND_FULL_P14_NOT_VERIFIED"
    return row


def audit(root: str | Path) -> dict[str, Any]:
    """Inventory every adjudication. Never silently omit a missing original."""
    root = Path(root).resolve()
    ledger_file = root / "SMART_SIGNAL_LEDGER.json"
    ledger = json.loads(ledger_file.read_text(encoding="utf-8-sig"))
    if ledger.get("schema") != "SMART_SIGNAL_LEDGER_1" or not isinstance(ledger.get("events"), list):
        raise ValueError("canonical signal ledger is invalid")
    events = ledger["events"]
    if not all(isinstance(event, dict) for event in events):
        raise ValueError("malformed canonical ledger event")
    rows = [
        _adjudication_evidence(root, events, index, event)
        for index, event in enumerate(events) if event.get("event_type") == "ADJUDICATION"
    ]
    target_counts: dict[int, int] = {}
    for row in rows:
        target = row["target_contest"]
        target_counts[target] = target_counts.get(target, 0) + 1
    for row in rows:
        if target_counts[row["target_contest"]] > 1:
            row.update(status="EXCLUDED_UNVERIFIED", file_hash_verified=False,
                       causal_metadata_verified=False, reason="DUPLICATE_ADJUDICATION")
    counts = {
        "adjudications": len(rows),
        "freeze_hash_verified": sum(row["file_hash_verified"] for row in rows),
        "missing_or_unverified_freezes": sum(not row["file_hash_verified"] for row in rows),
        "independently_witnessed_pre_draw": 0,
        "scientifically_admissible_by_this_gate": 0,
    }
    hold = preflight(root)
    mission = json.loads((root / "SMART_MISSION_STATUS.json").read_text(encoding="utf-8-sig"))
    if (
        mission.get("status") != "MISSION_ACTIVE"
        or mission.get("terminal_6of6_proven") is not False
        or mission.get("scientific_predictive_status") != "UNPROVEN"
    ):
        raise ValueError("scientific mission authority inconsistent")
    report = {
        "schema": SCHEMA,
        "ledger_file": ledger_file.name,
        "ledger_sha256": _sha256(ledger_file),
        "mode": "READ_ONLY_INVENTORY_NOT_INDEPENDENT_P14",
        "historical_adjudications": rows,
        "counts": counts,
        "operational_preflight": hold,
        "scientific_evaluation": "NOT_PROVEN",
        "full_p14_validation": "NOT_SUBSTITUTED_BY_THIS_TRIAGE",
        "statistical_significance_claim": False,
        "retrospective_reselection_or_backfill": False,
        "production_card_generation_performed": False,
        "scientific_promotion_authorized": False,
        "terminal_6of6_proven": False,
    }
    report["report_sha256"] = _hash(report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--output", default=None, help="Optional explicit JSON report path")
    args = parser.parse_args()
    report = audit(args.root)
    if args.output is not None:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "counts": report["counts"],
        "operational_status": report["operational_preflight"]["status"],
        "scientific_evaluation": report["scientific_evaluation"],
        "report_sha256": report["report_sha256"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
