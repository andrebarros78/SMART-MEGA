"""F12: immutable F11 historical science plus narrowly scoped causal trace repair.

The scientific evidence remains the signed-off F11 historical record.  This
successor authorizes an engineering repair only when removing that repair
reconstructs the exact F11-scoped source.  It makes no claim of 6/6 prediction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from smart_f11_predictive_nonregression import (
    BASELINE_HEAD,
    BASELINE_SOURCE_SHA256,
    evaluate as evaluate_f11,
)

SCHEMA = "SMART_F12_SCIENTIFIC_SUCCESSOR_1"
PREDICTIVE_FILE = "smart_full_process_pipeline.py"
F11_ARCHIVE = "SMART_F11_PREDICTIVE_NONREGRESSION.json"
REPAIR_START = b"def _fine_tuning_consumed_by_challenger("
REPAIR_END = b'@locked_operation("FULL_PROCESS_FREEZE"'
NEW_CHECK = b'"fine_tuning_consumed_by_challenger": _fine_tuning_consumed_by_challenger(freeze_obj, fine_tuning),'
OLD_CHECK = b'"fine_tuning_consumed_by_challenger": challenger.get("ai_hyperparameter_authority", {}).get("sha256") == fine_tuning["authority_sha256"],'


# F12-approved live source is anchored to the pre-operator change revision.
# These exact inverse transformations prove the operator change affects only
# scheduling/authorization, not predictive scoring, weights or historical data.
APPROVED_F12_PIPELINE_SHA256 = "59f6635b841d54f381fc725171110a3b5bf1db487d7f54eb36d9405278bae21c"
OPERATOR_SOURCE_REVERSALS = (
    (
        b"from smart_procedural_actionability_gate import FreezeWindowResult, evaluate_freeze_window",
        b"from smart_procedural_actionability_gate import evaluate_freeze_window",
    ),
    (
        b'''    if schedule.get("authority") == "OPERATOR_SELECTED_TARGET":
        # The operator directs generation; a draw timestamp is not invented
        # or misrepresented as independently verified.
        freeze_window = FreezeWindowResult(
            status="OPERATOR_UNVERIFIED_DRAW_TIME",
            scheduled_datetime="",
            observed_at=datetime.now(timezone.utc).isoformat(),
            before_draw=False,
            freeze_authority_allowed=True,
            reason="operator requested target; no externally verified draw time",
        )
    else:
        freeze_window = evaluate_freeze_window(
            scheduled_datetime=str(schedule["scheduled_datetime"]),
            observed_at=datetime.now(timezone.utc).isoformat(),
        )''',
        b'''    freeze_window = evaluate_freeze_window(
        scheduled_datetime=str(schedule["scheduled_datetime"]),
        observed_at=datetime.now(timezone.utc).isoformat(),
    )''',
    ),
    (
        b'''        "target_authority_bound": (
            schedule.get("authority") in {"CAIXA_ARCHIVED_CRONOGRAM_PDF", "OPERATOR_SELECTED_TARGET"}
            and schedule.get("result_used") is False
        ),''',
        b'''        "official_schedule_bound": schedule.get("authority") == "CAIXA_ARCHIVED_CRONOGRAM_PDF" and schedule.get("result_used") is False,''',
    ),
)


def reconstruct_approved_f12_source(value: bytes) -> bytes | None:
    '''Return the exact pre-operator F12 pipeline; reject arbitrary diffs.'''
    if _matches_expected_code(value, APPROVED_F12_PIPELINE_SHA256):
        return value
    restored = value
    for candidate, original in OPERATOR_SOURCE_REVERSALS:
        if restored.count(candidate) != 1:
            return None
        restored = restored.replace(candidate, original, 1)
    return restored if _matches_expected_code(restored, APPROVED_F12_PIPELINE_SHA256) else None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_sha(doc: dict[str, Any]) -> str:
    return _sha256(json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def _canonical_variants(value: bytes) -> tuple[bytes, ...]:
    lf = value.replace(b"\r\n", b"\n")
    # F11's pinned pipeline contains exactly one historical mixed-EOL import.
    # Restore that byte rather than normalizing away the immutable source proof.
    mixed_line = b"from smart_operational_lifecycle import assert_state as assert_lifecycle_state, transition as transition_lifecycle\n"
    historical_mixed = (lf.replace(mixed_line, mixed_line[:-1] + b"\r\n", 1)
                        if lf.count(mixed_line) == 1 else lf)
    return tuple(dict.fromkeys((value, lf, lf.replace(b"\n", b"\r\n"), historical_mixed)))


def _matches_expected_code(value: bytes, sha256: str) -> bool:
    return any(_sha256(item) == sha256 for item in _canonical_variants(value))


def reconstruct_predecessor(value: bytes) -> bytes | None:
    """Prove operator-only delta, then recover the immutable F11 source exactly."""
    value = reconstruct_approved_f12_source(value)
    if value is None:
        return None
    if value.count(REPAIR_START) != 1 or value.count(REPAIR_END) != 1 or value.count(NEW_CHECK) != 1:
        return None
    start = value.index(REPAIR_START)
    end = value.index(REPAIR_END, start)
    helper = value[start:end]
    # The helper must genuinely check effective parameters and causal bindings.
    requirements = (
        b'authority = freeze.get("ai_hyperparameter_authority")',
        b'lineage = freeze.get("promotion_lineage")',
        b'authority.get("sha256") != expected',
        b'lineage.get("ai_hyperparameter_authority_sha256") != expected',
        b'("eta", "redundancy_threshold", "meta_strength")',
        b'expected_value != effective_value',
        b'authority.get("future_result_used") is not False',
        b'authority.get("holdout_used_for_selection") is not False',
    )
    if not all(token in helper for token in requirements):
        return None
    predecessor = value[:start] + value[end:]
    return predecessor.replace(NEW_CHECK, OLD_CHECK, 1)


def evaluate(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    archived = json.loads((root / F11_ARCHIVE).read_text(encoding="utf-8-sig"))
    reproduced = evaluate_f11(root, source_hashes=dict(BASELINE_SOURCE_SHA256))
    sources: dict[str, dict[str, Any]] = {}
    for path, expected in BASELINE_SOURCE_SHA256.items():
        raw = (root / path).read_bytes()
        same = _matches_expected_code(raw, expected)
        if path == PREDICTIVE_FILE:
            original = reconstruct_predecessor(raw)
            same = original is not None and _matches_expected_code(original, expected)
        sources[path] = {"approved_f11_source_preserved": bool(same),
                         "current_canonical_lf_sha256": _sha256(raw.replace(b"\r\n", b"\n")),
                         "f11_source_sha256": expected,
                         "repair_scope": path == PREDICTIVE_FILE}
    live_f11 = evaluate_f11(root)
    operator_delta_proven = reconstruct_approved_f12_source((root / PREDICTIVE_FILE).read_bytes()) is not None
    check = {
        "operator_schedule_only_change_reversible_to_F12": operator_delta_proven,
        "f11_historical_report_reproducible": archived == reproduced,
        "f11_historical_report_pass": archived.get("status") == "PASS"
            and archived.get("sha256") == _json_sha({k: v for k, v in archived.items() if k != "sha256"}),
        "f11_historical_evidence_integrity": reproduced["checks"]["historical_artifacts_git_blob_identical_to_F10"]
            and all(reproduced["checks"].values()),
        "all_other_production_sources_unchanged": all(
            row["approved_f11_source_preserved"] for row in sources.values()
            if not row["repair_scope"]
        ),
        "candidate_diff_exactly_explained_by_guard": sources[PREDICTIVE_FILE]["approved_f11_source_preserved"],
        "candidate_f11_live_rejects_source_change": live_f11["status"] == "FAIL"
            and live_f11["errors"] == ["production_prediction_source_unchanged_from_F10"],
        "p10_no_regression_vs_reference": reproduced["comparison"]["p10"]["total_delta"] == 0
            and reproduced["comparison"]["p10"]["holdout_delta"] == 0,
        "p05_no_holdout_regression": reproduced["comparison"]["p05"]["holdout_delta"] == 0,
        "p06_weakness_disclosed": reproduced["comparison"]["p06"]["approved_for_predictive_promotion"] is False
            and reproduced["comparison"]["p06"]["candidate_minus_uniform_holdout_brier"] > 0,
        "fine_tuning_false_promotion_rejected": reproduced["comparison"]["fine_tuning"]["promotion_authorized"] is False
            and reproduced["comparison"]["fine_tuning"]["effective_candidate_id"] == "baseline",
        "no_prospective_superiority_fabricated": reproduced["prospective_advantage_proven"] is False
            and reproduced["six_of_six_proven"] is False,
    }
    report = {
        "schema": SCHEMA,
        "status": "PASS" if all(check.values()) else "FAIL",
        "project": "SMART-MEGA",
        "scope": "F11_HISTORICAL_SCIENCE_PRESERVED__F12_CAUSAL_TRACE_REPAIR__OPERATOR_SCHEDULE_ADAPTER",
        "historical_baseline_head": BASELINE_HEAD,
        "historical_f11_report_file": F11_ARCHIVE,
        "historical_f11_report_sha256": _sha256((root / F11_ARCHIVE).read_bytes()),
        "checks": check,
        "sources": sources,
        "historical_comparison": reproduced["comparison"],
        "predictive_implementation_changed": False if check["candidate_diff_exactly_explained_by_guard"] else None,
        "engineering_consumer_trace_fix_approved": all(check.values()),
        "scientific_predictive_status": "UNPROVEN_PROSPECTIVE_6_OF_6",
        "prospective_advantage_proven": False,
        "six_of_six_proven": False,
        "additional_prospective_samples_since_F11": 0,
        "note": "The immutable F11 predictor is reconstructed byte-for-byte after reversing only the exact approved F12 causal guard and operator-target scheduling delta. This proves a restricted source change, not superior lottery prediction.",
    }
    report["sha256"] = _json_sha(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Independent F12 scoped scientific successor gate")
    parser.add_argument("--write", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    report = evaluate(root)
    body = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        (args.write if args.write.is_absolute() else root / args.write).write_text(body, encoding="utf-8")
    if args.check:
        path = args.check if args.check.is_absolute() else root / args.check
        if not path.is_file() or path.read_text(encoding="utf-8") != body:
            raise SystemExit("F12 successor report absent or stale")
    print(json.dumps({"status": report["status"], "checks": report["checks"],
                      "scientific_predictive_status": report["scientific_predictive_status"]},
                     ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
