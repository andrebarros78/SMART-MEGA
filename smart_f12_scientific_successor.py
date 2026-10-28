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

# These reversals are comparison-only. Production never executes the old
# directory-name shortcuts. The final bytes must still match the immutable
# approved hash, so no scoring or parameter change is authorized here.
AUTHORIZATION_SOURCE_REVERSALS = (
    (b"import smart_canonical_identity as _test_identity\n", b""),
    (b"if _test_identity._authorized_pytest_sandbox(root):",
     b'if "pytest-" in str(root).lower():'),
    (b"if not (_test_identity._authorized_pytest_sandbox(root) and epoch_dir.resolve() == root.resolve()):",
     b'if not ("pytest-" in str(root).lower() and epoch_dir.resolve() == root.resolve()):'),
)
# Comparison-only inversions of non-predictive, source-bound evidence changes.
# Reconstructed hashes must still match the immutable pre-change F11 bytes.
RAG_EVIDENCE_REVERSALS = (
    (b'        from smart_rag_freeze_evidence import prepare_rag_freeze_evidence\n'
     b'        rag_evidence = prepare_rag_freeze_evidence(root, data_path, cutoff, epoch_dir, target)\n', b''),
    (b'        "rag_preparation_evidence": rag_evidence,\n', b''),
)
SELECTOR_EVIDENCE_REVERSALS = (
    (b'        "primary_card_matches_selector_output": primary_card_numbers == [int(n) for n in primary_selection["selected_numbers"]],',
     b'        "primary_card_not_forced_to_champion_top6": primary_card_numbers != sorted(champion_top6) or primary_selection["selected_band_counts"] == primary_selection["pure_top6_band_counts"],'),
    (b'''        "primary_card_comparison": {
            "identical_to_champion_top6": sorted(primary_card_numbers) == sorted(champion_top6),
            "independent_selection_gain_proven": False,
            "score_source": "champion",
            "selection_computed": True,
        },
''', b''),
)


# Exact comparison-only inverse of the validated SHA-256 bookkeeping repair.
# No model scores, weights, candidate policy or historical data are modified.
# The restored source must still match the immutable F11 fingerprint bytewise.
CALIBRATION_AUDIT_REVERSALS = (
    (
        b"\n\n        # The per-number probability vector is part of the signed audit.\n"
        b"        # Rebind its digest after attaching all 60 values; historical freezes\n"
        b"        # remain immutable and no predictive calibration is activated here.\n"
        b"        signed_calibration = dict(calibration_audit)\n"
        b"        signed_calibration.pop('sha256', None)\n"
        b"        calibration_audit['sha256'] = sha256_json(signed_calibration)",
        b"",
    ),
)


# This predecessor-only inverse removes the explicitly recorded 3060/3061
# continuation decision. The real selector always keeps these unsigned
# observations in quarantine. No missing freeze is fabricated or promoted.
HISTORICAL_CONTINUATION_REVERSALS = (
    (
        b'    # 3060/3061 absence is documented, never a prerequisite to generate a\n'
        b'    # new prospective card. Unknown quarantine cases still demand review.\n'
        b'    continuation = (rescue_profile or {}).get("historical_freeze_continuation") or {}\n'
        b'    if continuation and continuation.get("operational_continuation_allowed") is not True:\n'
        b'        raise ValueError("unreviewed historical quarantine: card generation requires review")\n',
        b'',
    ),
)


# Comparison-only reversal of the root-bound feedback correction.
# The operational root binding remains active; only F11 evidence reconstruction
# reverses these exact bytes and verifies the original pinned source digest.
FREEZE_ROOT_BINDING_REVERSALS = (
    (b'    freeze_path = Path(freeze_path).resolve()\n',
     b'    freeze_path = Path(freeze_path)\n'),
    (
        b'    # Only use feedback belonging to the same source root as the frozen model.\n'
        b'    # Production freezes live under this repository; isolated test/replay freezes\n'
        b'    # must not silently consume reports from the module import location.\n'
        b'    module_root = Path(__file__).resolve().parent\n'
        b'    feedback_root = module_root if freeze_path.is_relative_to(module_root) else freeze_path.parent\n'
        b'    rescue_profile = build_profile_from_reports(feedback_root, through_contest=cutoff)\n',
        b'    rescue_profile = build_profile_from_reports(Path(__file__).resolve().parent, through_contest=cutoff)\n',
    ),
)


GUARD_SOURCE_REVERSALS = {
    "smart_signal_agent.py": CALIBRATION_AUDIT_REVERSALS,
    "smart_portfolio_pipeline.py": (
        *SELECTOR_EVIDENCE_REVERSALS,
        *HISTORICAL_CONTINUATION_REVERSALS,
        *FREEZE_ROOT_BINDING_REVERSALS,
        AUTHORIZATION_SOURCE_REVERSALS[0],
        (b"if _test_identity._authorized_pytest_sandbox(freeze_path):",
         b'if "pytest-" in str(freeze_path).lower():'),
    ),
    "smart_learning_epoch_reset.py": (
        AUTHORIZATION_SOURCE_REVERSALS[0],
        (b"            if _test_identity._authorized_pytest_sandbox(path):",
         b'            test_path = str(path.resolve()).lower()\n            if "pytest-" in test_path :'),
    ),
}


# These two source changes are not F11-identical. Their exact reviewed PR80
# bytes are pinned separately, rather than mislabelled as historical F11 source.
# A different fine-tuning policy or execution gate must fail this integrity check.
APPROVED_SCOPED_SUCCESSOR_SHA256 = {
    "smart_ai_fine_tuning.py": "1ae2fab15661f623c9cc832c4a8d4bf1483cfb59b96113f957085b2802c60242",
    "smart_champion_challenger.py": "d8925e5cbdb398ae4ea243efdd0e495471c809851a754fb3a7520665144fb757",
}


def reconstruct_guard_only_source(path: str, value: bytes) -> bytes | None:
    """Accept only exact inverse guard substitutions and the pinned F11 hash."""
    expected = BASELINE_SOURCE_SHA256[path]
    for variant in _canonical_variants(value):
        restored = variant
        for candidate, original in GUARD_SOURCE_REVERSALS[path]:
            if restored.count(candidate) != 1:
                break
            restored = restored.replace(candidate, original, 1)
        else:
            if _matches_expected_code(restored, expected):
                return restored
    return None


def reconstruct_approved_f12_source(value: bytes) -> bytes | None:
    '''Return the exact pre-operator F12 pipeline; reject arbitrary diffs.'''
    if _matches_expected_code(value, APPROVED_F12_PIPELINE_SHA256):
        return value
    # Accept only the exact read-only RAG receipt additions before applying
    # the historic operator/scheduling reversals. Reject all unrelated code.
    for variant in _canonical_variants(value):
        modified = variant
        for insertion, original in RAG_EVIDENCE_REVERSALS:
            if modified.count(insertion) != 1:
                break
            modified = modified.replace(insertion, original, 1)
        else:
            value = modified
            break
    # Search the same EOL variants already accepted by the pinned SHA proof.
    # Multiline source reversals must not depend on Git's checkout EOL policy.
    for variant in _canonical_variants(value):
        for reversals in (OPERATOR_SOURCE_REVERSALS, AUTHORIZATION_SOURCE_REVERSALS,
                          AUTHORIZATION_SOURCE_REVERSALS + OPERATOR_SOURCE_REVERSALS):
            restored = variant
            for candidate, original in reversals:
                if restored.count(candidate) != 1:
                    break
                restored = restored.replace(candidate, original, 1)
            else:
                if _matches_expected_code(restored, APPROVED_F12_PIPELINE_SHA256):
                    return restored
    return None


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
        elif path in GUARD_SOURCE_REVERSALS:
            same = same or reconstruct_guard_only_source(path, raw) is not None
        scoped_successor_pinned = (path in APPROVED_SCOPED_SUCCESSOR_SHA256 and
            _matches_expected_code(raw, APPROVED_SCOPED_SUCCESSOR_SHA256[path]))
        sources[path] = {"approved_f11_source_preserved": bool(same),
                         "approved_scoped_successor_source_pinned": bool(scoped_successor_pinned),
                         "current_canonical_lf_sha256": _sha256(raw.replace(b"\r\n", b"\n")),
                         "f11_source_sha256": expected,
                         "repair_scope": path == PREDICTIVE_FILE,
                         "authorization_guard_scope": path in GUARD_SOURCE_REVERSALS}
    live_f11 = evaluate_f11(root)
    operator_delta_proven = reconstruct_approved_f12_source((root / PREDICTIVE_FILE).read_bytes()) is not None
    check = {
        "operator_schedule_only_change_reversible_to_F12": operator_delta_proven,
        "f11_historical_report_reproducible": archived == reproduced,
        "f11_historical_report_pass": archived.get("status") == "PASS"
            and archived.get("sha256") == _json_sha({k: v for k, v in archived.items() if k != "sha256"}),
        "f11_historical_evidence_integrity": reproduced["checks"]["historical_artifacts_git_blob_identical_to_F10"]
            and all(reproduced["checks"].values()),
        "all_other_sources_f11_identical_or_explicitly_pinned_successor": all(
            row["approved_f11_source_preserved"] or row["approved_scoped_successor_source_pinned"]
            for row in sources.values() if not row["repair_scope"]
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
        "scope": "F11_HISTORICAL_SCIENCE_PRESERVED__F12_CAUSAL_TRACE_REPAIR__PINNED_PR80_STATISTICAL_AND_ROOT_GUARDS",
        "historical_baseline_head": BASELINE_HEAD,
        "historical_f11_report_file": F11_ARCHIVE,
        "historical_f11_report_sha256": _sha256((root / F11_ARCHIVE).read_bytes()),
        "checks": check,
        "sources": sources,
        "historical_comparison": reproduced["comparison"],
        "predictive_implementation_changed": False if check["candidate_diff_exactly_explained_by_guard"] else None,
        "fine_tuning_promotion_policy_changed_since_f11": True,
        "fine_tuning_superiority_proven": False,
        "engineering_consumer_trace_fix_approved": all(check.values()),
        "scientific_predictive_status": "UNPROVEN_PROSPECTIVE_6_OF_6",
        "prospective_advantage_proven": False,
        "six_of_six_proven": False,
        "additional_prospective_samples_since_F11": 0,
        "note": "Historical F11 report and original predictive generator are independently verified. New root-bound feedback and fine-tuning promotion guards are explicitly pinned as PR80 successor source changes, not misrepresented as F11-identical. Comparison-only reversals are never executed. This integrity check does not prove superior lottery prediction.",
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
