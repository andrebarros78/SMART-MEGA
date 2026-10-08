from __future__ import annotations

from typing import Any, Iterable

SCHEMA = "SMART_OPERATOR_CONTRACT_V1"


def validate_target_sequence(contests: Iterable[int], target: int) -> dict[str, int]:
    values = [int(x) for x in contests]
    if isinstance(target, bool) or not isinstance(target, int) or target <= 1:
        raise ValueError("operator target must be a positive contest integer greater than 1")
    if not values:
        raise ValueError("canonical contest history is empty")
    if len(values) != len(set(values)):
        raise ValueError("canonical contest history contains duplicates")
    ordered = sorted(values)
    if ordered != list(range(ordered[0], ordered[-1] + 1)):
        raise ValueError("canonical contest history contains gaps")
    cutoff = int(target) - 1
    if ordered[-1] != cutoff:
        raise ValueError(f"operator target requires canonical history through contest {cutoff}; observed max={ordered[-1]}")
    return {"target_contest": int(target), "cutoff_contest": cutoff, "history_max": ordered[-1]}


def contract() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "product_completion_independent_of_operation": True,
        "operator_selects_target": True,
        "target_required_for_prepare_and_freeze": True,
        "supported_actions": ["status", "preflight", "prepare", "withdraw", "recover-missed", "catch-up", "authorize-next-cycle", "authorize-generation", "freeze", "adjudicate", "post-result-report", "review", "hold", "terminal"],
        "post_result_review_required_before_next_prepare": True,
        "prepare_requires_explicit_next_cycle_authority": True,
        "automatic_next_target_prepare_forbidden": True,
        "post_result_terminal_state": "AWAITING_OPERATOR_APPLY_OR_GENERATE",
        "pre_freeze_withdrawal_preserves_failed_preparation": True,
        "missed_unfrozen_recovery_is_non_predictive": True,
        "missed_unfrozen_recovery_requires_post_draw_official_result": True,
        "missed_unprepared_recovery_is_non_predictive": True,
        "missed_unprepared_recovery_requires_completed_prior_epoch": True,
        "missed_result_catchup_is_non_predictive_and_chainable": True,
        "freeze_is_operational_not_construction_gate": True,
        "manual_generation_authority_required_for_prospective_freeze": True,
        "analysis_calibration_and_testing_do_not_require_generation_authority": True,
        "adjudication_is_operational_not_construction_gate": True,
        "generic_active_epoch_terminal_executor": True,
        "terminal_action_revalidates_official_consensus_and_scientific_guards": True,
        "arbitrary_future_target_supported_when_history_is_complete_through_target_minus_one": True,
        "fail_closed_on_history_gap_or_target_result_present": True,
        "scientific_terminal_claim_independent_of_product_completion": True,
        "all_attempts_preserved_across_epochs": True,
        "supersede_requires_completed_epoch_or_explicit_withdrawal": True,
        "preflight_is_read_only": True,
        "preflight_fails_closed_on_stale_certification": True,
        "preflight_validates_active_epoch_integrity": True,
        "technical_withdrawal_allows_same_target_reauthorization_with_proof": True,
    }
