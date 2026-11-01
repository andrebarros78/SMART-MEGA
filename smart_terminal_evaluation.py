"""Read-only terminal eligibility evaluation, isolated from file I/O and promotion.

The engine verifies the frozen artifact, supplies its live target/cutoff, then
passes immutable-read evidence to this module. This does not promote a model.
"""
from __future__ import annotations

from typing import Any


def evaluate_terminal_evidence(
    *,
    freeze_event: dict[str, Any],
    freeze: dict[str, Any],
    adjudications: list[dict[str, Any]],
    ledger: dict[str, Any],
    consensus: dict[str, Any],
    audit: dict[str, Any],
    sequence_validation: dict[str, Any],
    target: int,
    cutoff: int,
    expected_freeze_sha256: str,
) -> dict[str, Any]:
    if len(adjudications) != 1:
        raise ValueError("terminal rule requires exactly one 3054 adjudication")
    adjudication = adjudications[0]
    actual = sorted(int(x) for x in adjudication["actual_numbers"])
    champion_top6 = sorted(int(x) for x in freeze["champion"]["top6"])
    recomputed_hits = len(set(actual) & set(champion_top6))
    target_adjudication_count = len(adjudications)
    total_adjudication_count = sum(1 for event in ledger.get("events", []) if event.get("event_type") == "ADJUDICATION")
    prospective = audit.get("prospective_ledger", {})
    primary = consensus.get("primary", {})
    audited_pairs = prospective.get("pair_count")
    checks = {
        "freeze_hash_immutable": freeze_event.get("freeze_sha256") == expected_freeze_sha256,
        "freeze_before_result": freeze_event.get("frozen_before_result") is True and freeze.get("frozen_before_result") is True,
        "causal_cutoff_3053": int(freeze_event.get("cutoff_contest", -1)) == cutoff and int(freeze.get("cutoff_contest", -1)) == cutoff,
        "single_active_production_top6": freeze.get("champion_remains_active") is True and freeze.get("production_switch_performed") is False,
        "official_primary_validated": primary.get("validated") is True,
        "official_numbers_match_adjudication": sorted(int(x) for x in primary.get("numbers", [])) == actual,
        "sequential_proof_valid": sequence_validation.get("valid") is True and sequence_validation.get("proof_recorded") is True,
        "independent_audit_pass": audit.get("status") == "PASS" and prospective.get("status") == "PASS",
        "all_attempts_counted": type(audited_pairs) is int and audited_pairs >= 0 and audited_pairs == total_adjudication_count,
        "no_future_leakage": prospective.get("no_future_leakage") is True,
        "source_corroborated": consensus.get("terminal_source_corroboration_authorized") is True,
        "exact_6of6": recomputed_hits == 6 and int(adjudication.get("champion_hits", -1)) == 6,
        "retroactive_rewrite_absent": adjudication.get("retroactive_rewrite") is False,
    }
    exact = checks["exact_6of6"]
    non_source_checks = all(value for key, value in checks.items() if key != "source_corroborated")
    eligible = all(checks.values())
    if not exact:
        status = "MISSION_ACTIVE_RESULT_ADJUDICATED_NO_6OF6"
    elif not checks["source_corroborated"] and non_source_checks:
        status = "MISSION_ACTIVE_6OF6_PENDING_SOURCE_CORROBORATION"
    elif eligible:
        status = "MISSION_PROVEN_ELIGIBLE"
    else:
        status = "MISSION_ACTIVE_6OF6_BLOCKED_BY_TERMINAL_GUARD"
    return {
        "schema": "SMART_TERMINAL_RULE_EVALUATION_1",
        "target_contest": target,
        "status": status,
        "eligible_for_mission_proven": eligible,
        "frozen_top6": champion_top6,
        "actual_numbers": actual,
        "recomputed_hits": recomputed_hits,
        "adjudication_count": target_adjudication_count,
        "total_adjudication_count": total_adjudication_count,
        "audited_pair_count": prospective.get("pair_count"),
        "checks": checks,
    }

