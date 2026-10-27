"""Independent, fail-closed candidate *review*, not an F11/F12 replacement.

F11 and F12 remain immutable historical certificates. This reviewer records the
source divergence, validates a pinned historical comparison, and refuses to
authorize predictive deployment without independently verified prospective
evidence. A successful review only means "safe to keep in SHADOW".
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from smart_f11_predictive_nonregression import (
    BASELINE_SOURCE_SHA256,
    _tracked_blob_sha,
    evaluate as evaluate_f11,
)
from smart_f12_scientific_successor import evaluate as evaluate_f12

SCHEMA = "SMART_SCIENTIFIC_SHADOW_SUCCESSION_REVIEW_1"
EVIDENCE = "evidence/3075/SMART_3075_CAP_RETROSPECTIVE_COMPARISON.json"
PINNED_EVIDENCE_BLOB = "94e91be77014c5a313aed5d51aaa90e327d9eba0"
ARCHIVED_F12_SHA = "8d6dcee89c4f8ea686b43c508a5dddf46c5b8f00374d0655f3260c2719ef8502"


def _sha(doc: dict[str, Any]) -> str:
    payload = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_evidence(root: str | Path) -> dict[str, Any]:
    return json.loads((Path(root) / EVIDENCE).read_text(encoding="utf-8-sig"))


def _paired_sign_test(wins: int, losses: int) -> float:
    """Exact one-sided conditional sign p, ignoring ties (not an efficacy claim)."""
    if not isinstance(wins, int) or not isinstance(losses, int) or min(wins, losses) < 0:
        raise ValueError("invalid paired counts")
    discordances = wins + losses
    if not discordances:
        return 1.0
    return sum(math.comb(discordances, k) for k in range(wins, discordances + 1)) / (2**discordances)


def _validate_retrospective(evidence: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    try:
        if (evidence.get("schema") != "SMART_3075_CAP_REPAIR_RETROSPECTIVE_ONLY_1"
            or evidence.get("status") != "RESEARCH_SHADOW_NOT_PROMOTABLE"
            or evidence.get("decision") != "KEEP_CHAMPION"
            or evidence.get("promotion_authorized") is not False
            or evidence.get("predictive_advantage_proven") is not False):
            errors.append("FALSE_AUTHORITY_OR_SCHEMA")

        target, cutoff = evidence["target_contest"], evidence["cutoff_contest"]
        windows = evidence["data_windows"]
        expected = {"calibration": [1500, 2499],
                    "validation": [2500, 2850],
                    "holdout": [2851, 3074],
                    "global": [1001, 3074]}
        if (target != 3075 or cutoff != 3074
            or evidence.get("future_result_3075_used_in_experiment") is not False
            or windows != expected):
            errors.append("TEMPORAL_LEAKAGE_OR_BAD_CUTOFF")

        counts = {}
        for key, (lo, hi) in expected.items():
            b, c = evidence["baseline"][key], evidence["candidate"][key]
            n = hi - lo + 1
            for sample in (b, c):
                if (type(sample["n"]) is not int or sample["n"] != n
                    or type(sample["hits"]) is not int or not 0 <= sample["hits"] <= 6 * n):
                    errors.append("PARTITION_COUNTS_INVALID")
            counts[key] = int(c["hits"]) - int(b["hits"])

        h = evidence["paired_holdout"]
        wins, losses, ties = (h[k] for k in ("candidate_wins", "baseline_wins", "ties"))
        if (not all(type(x) is int and x >= 0 for x in (wins, losses, ties))
            or wins + losses + ties != expected["holdout"][1] - expected["holdout"][0] + 1
            or wins - losses != counts["holdout"]
            or not isinstance(h["one_sided_sign_test_p"], (int, float))
            or not math.isfinite(h["one_sided_sign_test_p"])
            or not math.isclose(float(h["one_sided_sign_test_p"]), _paired_sign_test(wins, losses),
                                rel_tol=0.0, abs_tol=1e-12)):
            errors.append("PAIRED_EVIDENCE_INCONSISTENT")
        else:
            p = _paired_sign_test(wins, losses)
    except (KeyError, ValueError, TypeError, OverflowError, AttributeError):
        errors.append("MALFORMED_RETROSPECTIVE_EVIDENCE")
        counts = {}
        wins, losses, ties, p = 0, 0, 0, 1.0

    if "p" not in locals():
        p = 1.0
    return sorted(set(errors)), {
        "comparisons": {key + "_gain": value for key, value in counts.items()},
        "holdout": {
            "candidate_wins": wins, "baseline_wins": losses, "ties": ties,
            "one_sided_p": p, "per_draw_trace_verified": False,
        },
    }


def review(root: str | Path, *,
           evidence_override: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    evidence = deepcopy(evidence_override) if evidence_override is not None else read_evidence(root)
    errors, metrics = _validate_retrospective(evidence)

    f11_arch = json.loads((root / "SMART_F11_PREDICTIVE_NONREGRESSION.json").read_text(encoding="utf-8-sig"))
    f12_arch = json.loads((root / "SMART_F12_SCIENTIFIC_SUCCESSOR.json").read_text(encoding="utf-8-sig"))
    f11_hist = evaluate_f11(root, source_hashes=dict(BASELINE_SOURCE_SHA256))
    f12_live = evaluate_f12(root)

    f11_ok = (f11_hist["status"] == "PASS" and
              f11_hist == f11_arch and
              f11_hist["prospective_advantage_proven"] is False)
    f12_arch_ok = (f12_arch["status"] == "PASS" and
                   f12_arch.get("sha256") == ARCHIVED_F12_SHA and
                   f12_arch["sha256"] == _sha({k: v for k, v in f12_arch.items() if k != "sha256"}))
    f12_checks = f12_live["checks"]
    f12_historical_ok = all(f12_checks.get(key) is True for key in (
        "f11_historical_report_reproducible", "f11_historical_report_pass",
        "f11_historical_evidence_integrity", "no_prospective_superiority_fabricated",
    ))
    # Only the *known* strict source-identity check may fail in the candidate.
    # An unrelated historical, operator, leakage or temporal guard failure
    # must invalidate even a read-only shadow certificate.
    allowed_drift_check = "all_other_predictive_sources_preserved_after_exact_guard_reversal"
    failed_checks = {name for name, ok in f12_checks.items() if ok is not True}
    if failed_checks - {allowed_drift_check}:
        errors.append("UNEXPECTED_F12_GUARD_FAILURE")
    source_divergence = sorted(
        path for path, item in f12_live["sources"].items()
        if item["approved_f11_source_preserved"] is False
    )
    reviewed_diff_scope = {
        "smart_ai_fine_tuning.py", "smart_champion_challenger.py",
        "smart_portfolio_pipeline.py", "smart_signal_agent.py", "smart_v2_engine.py",
    }
    if not set(source_divergence).issubset(reviewed_diff_scope):
        errors.append("UNREVIEWED_PREDICTIVE_SOURCE_DIFF")
    if bool(failed_checks) == (f12_live["status"] == "PASS"):
        errors.append("INCONSISTENT_F12_STATUS")
    if source_divergence and allowed_drift_check not in failed_checks:
        errors.append("INCONSISTENT_F12_SOURCE_REPORT")
    evidence_clean = evidence_override is None and _tracked_blob_sha(root, EVIDENCE) == PINNED_EVIDENCE_BLOB
    if not evidence_clean:
        errors.append("EVIDENCE_NOT_GIT_PINNED")
    if not f11_ok or not f12_arch_ok or not f12_historical_ok:
        errors.append("HISTORICAL_SCIENCE_INTEGRITY_FAILED")

    gains = metrics["comparisons"]
    paired = metrics["holdout"]
    discordances = paired["candidate_wins"] + paired["baseline_wins"]
    significant = (paired["one_sided_p"] <= 0.01 and discordances >= 20
                   and gains.get("holdout_gain", 0) > 0)
    blockers = []
    if f12_live["status"] != "PASS":
        blockers.append("F12_SOURCE_SUCCESSION_NOT_CERTIFIED")
    if not significant:
        blockers.append("PAIRED_GAIN_NOT_SIGNIFICANT")
    if (gains.get("global_gain", -1) < 0 or gains.get("validation_gain", -1) < 0
        or gains.get("calibration_gain", -1) < 0):
        blockers.append("GLOBAL_NONREGRESSION_FAILED")
    blockers.extend(("NO_VERIFIED_PER_DRAW_PAIRED_TRACE", "PROSPECTIVE_SUPERIORITY_NOT_PROVEN"))
    blockers.extend(errors)
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "INVALID_EVIDENCE" if errors else "PASS_SHADOW_ONLY",
        "historical_f11_reproduced": f11_ok,
        "archived_f12_certificate_intact": f12_arch_ok,
        "live_f12_status": f12_live["status"],
        "source_divergence": source_divergence,
        "evidence_git_blob_verified": evidence_clean,
        "comparison_cutoff": evidence.get("cutoff_contest"),
        "comparisons": gains,
        "holdout": paired,
        "blockers": sorted(set(blockers)),
        "promotion_authorized": False,
        "prospective_advantage_proven": False,
        "six_of_six_proven": False,
        "read_only": True,
        "note": "Shadow engineering assessment only; no F11/F12 rewrite, no model or ticket promotion.",
    }
    report["sha256"] = _sha(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only scientific shadow succession review")
    parser.add_argument("--write", type=Path, default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    result = review(root)
    if args.write is not None:
        path = args.write if args.write.is_absolute() else root / args.write
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS_SHADOW_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
