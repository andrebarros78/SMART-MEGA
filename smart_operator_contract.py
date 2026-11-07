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
        "supported_actions": ["status", "preflight", "result-preflight", "prepare", "withdraw", "recover-missed", "catch-up", "authorize-next-cycle", "authorize-generation", "freeze", "adjudicate", "post-result-report", "complete-result", "recover-cycle", "review", "hold", "generate-card", "show-card", "terminal"],
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
        "read_frozen_model_card_independent_of_adjudication": True,
        "explicit_result_completion_is_resumable": True,
        "result_completion_never_auto_promotes_scientific_claim": True,
        "next_contest_contingency_generation_independent_of_prior_adjudication": True,
        "implicit_contingency_fallback_forbidden": True,
        "contingency_card_never_proves_predictive_6of6": True,
        "generic_active_epoch_terminal_executor": True,
        "terminal_action_revalidates_official_consensus_and_scientific_guards": True,
        "arbitrary_future_target_supported_when_history_is_complete_through_target_minus_one": True,
        "fail_closed_on_history_gap_or_target_result_present": True,
        "scientific_terminal_claim_independent_of_product_completion": True,
        "all_attempts_preserved_across_epochs": True,
        "supersede_requires_completed_epoch_or_explicit_withdrawal": True,
        "preflight_is_read_only": True,
        "result_preflight_is_read_only": True,
        "official_result_does_not_update_weights_until_explicit_terminal": True,
        "preflight_fails_closed_on_stale_certification": True,
        "preflight_validates_active_epoch_integrity": True,
        "technical_withdrawal_allows_same_target_reauthorization_with_proof": True,
    }


def _predictive_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdefABCDEF" for c in value)


def _predictive_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")) or ":" in value:
        return False
    parts = value.replace("\\", "/").split("/")
    return all(p not in ("", ".", "..") for p in parts)


def require_predictive_card_result(result: Any, target: int) -> dict[str, Any]:
    """Validate actual freeze-operation output, not an invented wrapper schema.

    New freezes return the native full-process dict with proof and freeze;
    authenticated replays return SMART_FREEZE_OPERATION_1. Both are checked
    after the upstream source-bound consumer audit. Never reinterpret a
    contingency or a failed integration as a production model card.
    """
    target = int(target)
    if not isinstance(result, dict):
        raise ValueError("PREDICTIVE_CARD_ONLY: invalid model-generation response")
    consumer = result.get("consumer_integration")
    if not isinstance(consumer, dict) or consumer.get("status") != "PASS":
        raise ValueError("PREDICTIVE_CARD_ONLY: consumer evidence is not verified")
    if result.get("schema") == "SMART_FREEZE_OPERATION_1":
        if (result.get("status") != "FROZEN"
                or result.get("target_contest") != target
                or result.get("idempotent_replay") is not True
                or result.get("result_used") is not False
                or not _predictive_relative_path(result.get("freeze_file"))
                or not _predictive_sha256(result.get("freeze_sha256"))):
            raise ValueError("PREDICTIVE_CARD_ONLY: replay is not bound to model freeze")
        return result
    proof = result.get("proof")
    freeze = result.get("freeze")
    if (not isinstance(proof, dict) or not isinstance(freeze, dict)
            or proof.get("status") != "PASS"
            or proof.get("target_contest") != target
            or proof.get("result_used") is not False
            or not _predictive_relative_path(proof.get("freeze_file"))
            or not _predictive_sha256(proof.get("freeze_sha256"))
            or proof.get("freeze_sha256") != freeze.get("freeze_sha256")):
        raise ValueError("PREDICTIVE_CARD_ONLY: missing audited native model-generation proof")
    return result
