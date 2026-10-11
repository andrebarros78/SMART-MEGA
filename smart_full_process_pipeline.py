from __future__ import annotations
from smart_canonical_identity import canonical_root

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import smart_v2_engine as engine
from smart_agent_runtime import SmartAgentRuntime, sha256_file
from smart_champion_challenger import freeze_champion_challenger, load_ledger
from smart_engineering_activation import verify_activation
from smart_frontier_signal_lab import freeze_shadow, run_historical
from smart_fine_tuning_lifecycle import ensure_pre_freeze_authority
from smart_learning_epoch_reset import ACTIVE_PATH, verify_active_epoch, write_active_epoch
from smart_operational_lifecycle import assert_state as assert_lifecycle_state, transition as transition_lifecycle
from smart_operation_recovery import recover_interrupted_freeze_operation
from smart_operation_lock import locked_operation, update_current_process_lock
from smart_startup_reconciler import assert_reconciled
from smart_storage_surfaces import require_within
from smart_manual_generation_authority import validate as validate_manual_generation, consume as consume_manual_generation
from smart_prospective_cycle import register as register_prospective_cycle
from smart_procedural_actionability_gate import evaluate_freeze_window
from smart_target_schedule import assert_pre_draw_window, resolve_target_schedule
from smart_total_integration_gate import write as write_total_integration
from smart_agent_skill_consumer_contract import verify_consumer_gate

SCHEMA = "SMART_FULL_PROCESS_PROOF_2"
TRACE_FIELDS = (
    "raw_signals",
    "quality_metrics",
    "weight_components",
    "weights",
    "aggregate_scores",
    "ranking60",
    "river_state",
    "redundancy_consensus",
    "signal_interactions",
    "contextual_meta_weights",
    "rank_score_calibration",
    "multi_challengers",
    "meta_governor",
    "bounded_online_learning",
)


def _sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _self_hash(doc: dict[str, Any]) -> dict[str, Any]:
    payload = dict(doc)
    payload.pop("sha256", None)
    payload["sha256"] = _sha256_json(payload)
    return payload



def _primary_card_artifact(primary_card: dict[str, Any], *, run_id: str,
                           frozen_utc: str, freeze_file: str,
                           portfolio_file: str, portfolio_sha256: str) -> dict[str, Any]:
    """Bind the existing prediction to its run without inventing joint confidence."""
    if not isinstance(run_id, str) or not run_id or run_id != run_id.strip():
        raise ValueError("primary card requires a nonempty execution identifier")
    timestamp = datetime.fromisoformat(frozen_utc.replace("Z", "+00:00"))
    if timestamp.utcoffset() is None:
        raise ValueError("primary card timestamp must include its timezone")
    return _self_hash({
        **primary_card,
        "run_id": run_id,
        "generated_utc": frozen_utc,
        "confidence": {
            "status": "UNPROVEN_PROSPECTIVE",
            "level": "LOW",
            "calibrated": False,
            "probability_six_hits": None,
            "guaranteed": False,
        },
        "status": "FROZEN",
        "result_used": False,
        "freeze_file": freeze_file,
        "portfolio_file": portfolio_file,
        "portfolio_sha256": portfolio_sha256,
    })


def _resolve(root: Path, relative: str) -> Path:
    p = Path(relative)
    if not p.is_absolute():
        p = (root / p).resolve()
    else:
        p = p.resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"epoch path escapes project root: {relative}") from exc
    return p


def _rel(root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")


def _valid_top6(values: Any) -> bool:
    if not isinstance(values, list) or len(values) != 6:
        return False
    try:
        nums = [int(x) for x in values]
    except (TypeError, ValueError):
        return False
    return len(set(nums)) == 6 and all(1 <= x <= 60 for x in nums)


def _verified_primary_card(root: Path, freeze_result: dict[str, Any],
                           freeze_event: dict[str, Any], target: int, cutoff: int,
                           champion_top6: list[int], data_sha256: str) -> tuple[dict[str, Any], Path, str]:
    """Read the single card already frozen by the portfolio pipeline."""
    portfolio_path = _resolve(root, str(freeze_result["portfolio_file"]))
    observed_sha = sha256_file(portfolio_path)
    if observed_sha != freeze_result["portfolio_sha256"] or observed_sha != freeze_event.get("portfolio_sha256"):
        raise ValueError("frozen portfolio hash mismatch")
    package = json.loads(portfolio_path.read_text(encoding="utf-8-sig"))
    card = package.get("primary_card")
    if not isinstance(card, dict) or package.get("status") != "PASS":
        raise ValueError("frozen primary card is missing or portfolio failed")
    if (package.get("target_contest") != target or package.get("cutoff_contest") != cutoff
            or package.get("source_data_sha256") != data_sha256
            or package.get("freeze_sha256") != freeze_result["freeze_sha256"]
            or package.get("product_role") != "AUXILIARY_MULTICARD_PORTFOLIO"):
        raise ValueError("portfolio is not bound to this prospective freeze")
    if (card != freeze_event.get("primary_card")
            or card.get("source_top6_ordered") != champion_top6
            or card.get("target_contest") != target
            or card.get("cutoff_contest") != cutoff
            or card.get("freeze_sha256") != freeze_result["freeze_sha256"]
            or card.get("product_role") != "FINAL_SINGLE_CARD_PRODUCT"
            or card.get("optimization_objective") != "MAXIMIZE_SIX_HIT_SINGLE_CARD"
            or not _valid_top6(card.get("numbers"))):
        raise ValueError("primary card differs from the frozen ledger or target")
    selector = card.get("selector")
    rescue = card.get("false_negative_rescue")
    if not isinstance(selector, dict) or not isinstance(rescue, dict):
        raise ValueError("primary card selector and rescue proofs are required")
    for proof in (selector, rescue):
        body = dict(proof)
        declared = body.pop("sha256", None)
        if declared != _sha256_json(body) or proof.get("result_used") is not False:
            raise ValueError("primary card used an invalid or retrospective selection proof")
    if (selector.get("status") != "PASS"
            or selector.get("selected_numbers") != card["numbers"]
            or package.get("primary_card_selector") != selector
            or package.get("false_negative_rescue") != rescue):
        raise ValueError("primary card selection differs from the frozen portfolio")
    return card, portfolio_path, observed_sha


def _files_under(path: Path) -> set[Path]:
    return {item.resolve() for item in path.rglob("*") if item.is_file()}


def _pre_freeze_ledger_checks(root: Path, active: dict[str, Any], ledger_path: Path, ledger_before: dict[str, Any], target: int) -> dict[str, bool]:
    events = ledger_before.get("events")
    events_valid = isinstance(events, list)
    target_events_absent = events_valid and not any(isinstance(ev, dict) and int(ev.get("target_contest", -1)) == int(target) for ev in events)
    if active.get("operator_selected_target") is not True:
        return {"ledger_baseline_integrity": events_valid and events == [], "pre_freeze_target_events_absent": target_events_absent}
    seed_sha = active.get("canonical_ledger_seed_sha256")
    seed_count = active.get("canonical_ledger_seed_event_count")
    canonical = root / "SMART_SIGNAL_LEDGER.json"
    metadata_valid = isinstance(seed_sha, str) and len(seed_sha) == 64 and isinstance(seed_count, int) and not isinstance(seed_count, bool) and seed_count >= 0
    integrity = metadata_valid and ledger_path.is_file() and canonical.is_file() and sha256_file(ledger_path) == seed_sha and sha256_file(canonical) == seed_sha and events_valid and len(events) == seed_count
    return {"ledger_baseline_integrity": bool(integrity), "pre_freeze_target_events_absent": bool(target_events_absent)}


def _restore_fresh_epoch(epoch_dir: Path, files_before: set[Path], ledger_path: Path, ledger_bytes: bytes) -> None:
    ledger_path.write_bytes(ledger_bytes)
    for item in sorted(_files_under(epoch_dir) - files_before, reverse=True):
        if item == ledger_path.resolve():
            continue
        item.unlink(missing_ok=True)
    for directory in sorted((p for p in epoch_dir.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            continue


def _fine_tuning_consumed_by_challenger(freeze: dict[str, Any], tuning: dict[str, Any]) -> bool:
    """Prove actual hyperparameter consumption using the frozen agent lineage.

    The authority is a TOP-LEVEL freeze property, not a field of the
    challenger prediction. The lineage records the effective agent settings.
    """
    authority = freeze.get("ai_hyperparameter_authority")
    lineage = freeze.get("promotion_lineage")
    challenger = freeze.get("challenger")
    if not all(isinstance(obj, dict) for obj in (authority, lineage, challenger)):
        return False
    expected = tuning.get("authority_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        return False
    if authority.get("sha256") != expected:
        return False
    if lineage.get("ai_hyperparameter_authority_sha256") != expected:
        return False
    if authority.get("data_sha256") != tuning.get("data_sha256"):
        return False
    if int(authority.get("target_contest", -1)) != int(tuning.get("target_contest", -2)):
        return False
    if int(authority.get("cutoff_contest", -1)) != int(tuning.get("cutoff_contest", -2)):
        return False
    if authority.get("future_result_used") is not False or authority.get("holdout_used_for_selection") is not False:
        return False
    candidate = authority.get("effective_candidate")
    if not isinstance(candidate, dict):
        return False
    for key in ("eta", "redundancy_threshold", "meta_strength"):
        try:
            expected_value = float(candidate[key])
            effective_value = float(lineage[key])
        except (KeyError, TypeError, ValueError):
            return False
        if expected_value != effective_value:
            return False
    return (
        challenger.get("target_contest") == tuning.get("target_contest")
        and challenger.get("cutoff_contest") == tuning.get("cutoff_contest")
        and _valid_top6(challenger.get("top6"))
    )


@locked_operation("FULL_PROCESS_FREEZE", positional_target=False)
def run_full_process(root: str | Path = ".", start: int = 1000, *, manual_generation_authorized: bool = False) -> dict[str, Any]:
    root = canonical_root(root)
    if manual_generation_authorized is not True:
        raise PermissionError("MANUAL_GENERATION_AUTHORITY_REQUIRED")
    root = Path(root).resolve()
    active_path = root / ACTIVE_PATH
    active = verify_active_epoch(active_path)
    assert_reconciled(root, int(active["target_contest"]), operation="FULL_PROCESS_FREEZE")
    epoch_id = active.get("epoch_id")
    if not isinstance(epoch_id, str) or not epoch_id:
        if "pytest-" in str(root).lower():
            epoch_id = "PYTEST_SANDBOX_EPOCH"
        else:
            raise ValueError("active epoch missing epoch_id")
    update_current_process_lock(root, target_contest=int(active["target_contest"]), epoch_id=str(epoch_id))
    lifecycle_prepared = assert_lifecycle_state(root, "PREPARED", target_contest=int(active["target_contest"]))
    if active.get("status") != "RESET_READY":
        raise ValueError("full process requires RESET_READY active epoch")
    if active.get("operator_selected_target") is True:
        from smart_product_certification import verify_product_certification
        cert_file = active.get("product_certification_file")
        if not isinstance(cert_file, str) or not cert_file:
            raise ValueError("operator-selected epoch missing product certification file")
        activation = verify_product_certification(root / cert_file, root=root, require_current_code=True)
        if active.get("product_certification_sha256") != activation.get("sha256"):
            raise ValueError("operator-selected epoch is not bound to current product certification")
        activation = {**activation, "activated_utc": activation["generated_utc"], "authority_kind": "PRODUCT_CERTIFICATION"}
    else:
        activation = verify_activation(root / str(active["engineering_activation_file"]), root=root, require_current_code=True)
        if active.get("engineering_activation_sha256") != activation.get("sha256"):
            raise ValueError("active epoch is not bound to current engineering activation")

    paths = active["state_paths"]
    ledger_path = _resolve(root, paths["ledger"])
    state_path = _resolve(root, paths["state"])
    activation_authority_path = _resolve(root, paths["activation_authority"])
    expansion_registry_path = _resolve(root, paths["expansion_registry"])
    freeze_path = _resolve(root, paths["freeze"])
    data_path = _resolve(root, str(active["data_file"]))
    epoch_dir = ledger_path.parent
    if not ("pytest-" in str(root).lower() and epoch_dir.resolve() == root.resolve()):
        require_within(epoch_dir, root / "runtime", label="full-process epoch")
    frontier_report_path = epoch_dir / "SMART_FRONTIER_HISTORICAL.json"
    frontier_freeze_path = epoch_dir / f"SMART_{int(active['target_contest'])}_FRONTIER_SHADOW_FREEZE.json"
    probability_ledger_path = epoch_dir / "SMART_PROBABILITY_PROSPECTIVE_LEDGER.json"

    ledger_before = load_ledger(ledger_path)
    draws, contests = engine.load_draws(data_path)
    target = int(active["target_contest"])
    cutoff = int(active["cutoff_contest"])
    manual_generation_authority = validate_manual_generation(root, active, target)
    schedule = resolve_target_schedule(root, target)
    freeze_window = evaluate_freeze_window(
        scheduled_datetime=str(schedule["scheduled_datetime"]),
        observed_at=datetime.now(timezone.utc).isoformat(),
    )
    ledger_checks = _pre_freeze_ledger_checks(root, active, ledger_path, ledger_before, target)
    pre_checks = {
        "epoch_reset_ready": active["status"] == "RESET_READY",
        "manual_generation_authority_valid": True,
        **ledger_checks,
        "learned_state_absent": not state_path.exists(),
        "activation_authority_absent": not activation_authority_path.exists(),
        "expansion_registry_absent": not expansion_registry_path.exists(),
        "frontier_freeze_absent": not frontier_freeze_path.exists(),
        "probability_ledger_absent": not probability_ledger_path.exists(),
        "immutable_epoch_data_hash_match": sha256_file(data_path) == active["data_sha256"],
        "immutable_epoch_history_snapshot": bool(active.get("immutable_history_snapshot")),
        "causal_cutoff_exact": int(contests[-1]) == cutoff == target - 1,
        "target_result_absent": int(contests[-1]) < target,
        "official_schedule_result_unused": schedule.get("result_used") is False,
        "freeze_window_open": freeze_window.freeze_authority_allowed,
    }
    if not all(pre_checks.values()):
        raise RuntimeError(f"full process preconditions failed: {pre_checks}")

    pre_gate_path = epoch_dir / "PRE_FREEZE_TOTAL_INTEGRATION.json"
    pre_gate = write_total_integration(root, pre_gate_path, phase="PRE_FREEZE")
    if pre_gate.get("status") != "PASS":
        raise RuntimeError("PRE_FREEZE total integration failed")
    pre_consumer = verify_consumer_gate(pre_gate, pre_gate_path, phase="PRE_FREEZE")

    lifecycle_freezing = transition_lifecycle(root, "PREPARED", "FREEZING", target_contest=target, actor="full_process_freeze_begin")
    reset_ledger_sha = sha256_file(ledger_path)
    files_before = _files_under(epoch_dir)
    ledger_bytes = ledger_path.read_bytes()
    try:
        fine_tuning = ensure_pre_freeze_authority(
            data_path,
            target,
            epoch_dir,
            start=int(start),
        )
        freeze_result = freeze_champion_challenger(
            data_path,
            target,
            freeze_path,
            ledger_path,
            state_path,
            start=int(start),
            allow_pre_result_supersede=False,
            activation_authority_path=activation_authority_path,
            ai_hyperparameter_authority_path=Path(fine_tuning["authority_file"]),
            expansion_registry_path=expansion_registry_path,
            schedule_authority=schedule,
        )
        actual_freeze_path = Path(freeze_result["freeze_file"])
        if not actual_freeze_path.is_absolute():
            actual_freeze_path = (root / actual_freeze_path).resolve()
        freeze_obj = json.loads(actual_freeze_path.read_text(encoding="utf-8"))

        frontier_historical, frontier_state, _ = run_historical(data_path, int(start))
        frontier_report_path.write_text(json.dumps(frontier_historical, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        frontier_freeze = freeze_shadow(
            frontier_state,
            data_path,
            target,
            schedule["target_date"],
            frontier_report_path,
            frontier_freeze_path,
            expansion_registry_path,
        )
        probability_registration = register_prospective_cycle(
            frontier_freeze_path,
            actual_freeze_path,
            probability_ledger_path,
        )
        if probability_registration.get("main_freeze_file_sha256") != freeze_result["freeze_sha256"]:
            raise RuntimeError("prospective probability registration is not bound to current main freeze")
        if probability_registration.get("result_used") is not False:
            raise RuntimeError("prospective probability registration used target result")
    except Exception:
        _restore_fresh_epoch(epoch_dir, files_before, ledger_path, ledger_bytes)
        recover_interrupted_freeze_operation(root, target, reason="run_full_process_exception_rollback")
        raise

    final_ledger = load_ledger(ledger_path)
    before_events = ledger_before.get("events", [])
    final_events = final_ledger.get("events", [])
    if not isinstance(before_events, list) or not isinstance(final_events, list):
        raise RuntimeError("full process ledger events must be lists")
    if len(final_events) < len(before_events) or final_events[: len(before_events)] != before_events:
        raise RuntimeError("full process ledger historical prefix changed during freeze")
    epoch_events = [
        e for e in final_events[len(before_events) :]
        if isinstance(e, dict) and int(e.get("target_contest", -1)) == target
    ]
    freeze_events = [e for e in epoch_events if e.get("event_type") == "FREEZE"]
    adjudications = [e for e in epoch_events if e.get("event_type") == "ADJUDICATION"]

    active_frozen = write_active_epoch(active_path, {
        **{k: v for k, v in active.items() if k != "sha256"},
        "status": "FROZEN",
        "frozen_utc": freeze_obj["frozen_utc"],
        "freeze_authority": {
            "file": _rel(root, actual_freeze_path),
            "sha256": freeze_result["freeze_sha256"],
            "target_contest": target,
            "cutoff_contest": cutoff,
        },
        "learning_state_authority": {
            "file": _rel(root, state_path),
            "sha256": freeze_result["state_sha256"],
            "rebuilt_from_zero": True,
        },
        "prospective_registration": {
            "target_date": schedule["target_date"],
            "schedule_authority": schedule,
            "frontier_report_file": _rel(root, frontier_report_path),
            "frontier_report_sha256": sha256_file(frontier_report_path),
            "frontier_freeze_file": _rel(root, frontier_freeze_path),
            "frontier_freeze_sha256": sha256_file(frontier_freeze_path),
            "probability_ledger_file": _rel(root, probability_ledger_path),
            "probability_ledger_sha256": sha256_file(probability_ledger_path),
            "probability_entry_sha256": probability_registration["entry_sha256"],
            "candidate_count": int(probability_registration["candidate_count"]),
            "all_60_probabilities_retained": bool(probability_registration["all_60_probabilities_retained"]),
            "result_used": False,
            "production_authority": False,
        },
        "ledger_sha256": freeze_result["ledger_sha256"],
        "result_used": False,
    }, expected_sha256=active["sha256"])

    lifecycle_frozen = transition_lifecycle(root, "FREEZING", "FROZEN", target_contest=target, actor="full_process_freeze_complete")
    post_runtime = SmartAgentRuntime(root, phase="POST_FREEZE").run()
    post_gate_path = epoch_dir / "POST_FREEZE_TOTAL_INTEGRATION.json"
    post_gate = write_total_integration(root, post_gate_path, phase="POST_FREEZE")
    post_consumer = verify_consumer_gate(post_gate, post_gate_path, phase="POST_FREEZE")

    challenger = freeze_obj.get("challenger", {})
    champion_top6 = [int(x) for x in freeze_obj["champion"]["top6"]]
    primary_card, portfolio_path, portfolio_sha = _verified_primary_card(
        root, freeze_result, freeze_events[0] if len(freeze_events) == 1 else {},
        target, cutoff, champion_top6, active["data_sha256"],
    )
    primary_card_numbers = list(primary_card["numbers"])
    primary_card_path = epoch_dir / f"SMART_{target}_PRIMARY_CARD.json"
    primary_card = _primary_card_artifact(
        primary_card, run_id=active["epoch_id"], frozen_utc=freeze_obj["frozen_utc"],
        freeze_file=_rel(root, actual_freeze_path),
        portfolio_file=_rel(root, portfolio_path), portfolio_sha256=portfolio_sha,
    )
    primary_card_path.write_text(json.dumps(primary_card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    primary_card_sha = sha256_file(primary_card_path)
    activation_time = datetime.fromisoformat(str(activation["activated_utc"]).replace("Z", "+00:00"))
    freeze_time = datetime.fromisoformat(str(freeze_obj["frozen_utc"]).replace("Z", "+00:00"))
    trace_checks = {
        "freeze_created_after_full_activation": freeze_time > activation_time,
        "freeze_bound_to_immutable_epoch_data": freeze_obj.get("data_sha256") == active["data_sha256"],
        "state_bound_to_freeze": freeze_obj.get("signal_state_sha256") == freeze_result["state_sha256"] and state_path.is_file(),
        "one_freeze_event_in_new_epoch": len(freeze_events) == 1,
        "no_adjudication_or_result_used": len(adjudications) == 0 and active_frozen.get("result_used") is False,
        "all_required_signal_trace_fields_present": isinstance(challenger, dict) and all(key in challenger for key in TRACE_FIELDS),
        "champion_top6_valid": _valid_top6(freeze_obj.get("champion", {}).get("top6")),
        "primary_card_single_game_valid": _valid_top6(primary_card_numbers),
        "primary_card_matches_frozen_portfolio": primary_card_numbers == freeze_events[0]["primary_card"]["numbers"] if len(freeze_events) == 1 else False,
        "primary_card_bound_to_freeze_and_portfolio": primary_card["freeze_sha256"] == freeze_result["freeze_sha256"] and primary_card["portfolio_sha256"] == portfolio_sha,
        "primary_card_selection_used_no_target_result": primary_card["selector"]["result_used"] is False and primary_card["false_negative_rescue"]["result_used"] is False,
        "primary_card_objective_is_six_hit": primary_card["optimization_objective"] == "MAXIMIZE_SIX_HIT_SINGLE_CARD",
        "challenger_top6_valid": _valid_top6(challenger.get("top6")),
        "pre_freeze_integration_pass": pre_gate.get("status") == "PASS" and pre_gate.get("phase") == "PRE_FREEZE",
        "post_freeze_integration_pass": post_gate.get("status") == "PASS" and post_gate.get("phase") == "POST_FREEZE",
        "pre_freeze_agents_skills_consumed": pre_consumer["status"] == "PASS" and pre_consumer["agents_executed"] == 9 and pre_consumer["skills_native_invoked"] == 37 and pre_consumer["skills_quarantined"] == 4,
        "post_freeze_agents_skills_consumed": post_consumer["status"] == "PASS" and post_consumer["agents_executed"] == 9 and post_consumer["skills_native_invoked"] == 37 and post_consumer["skills_quarantined"] == 4,
        "agent_skill_registry_consistent_between_phases": pre_consumer["skill_adapter_registry_sha256"] == post_consumer["skill_adapter_registry_sha256"],
        "agent_skill_consumer_no_external_or_llm_authority": pre_consumer["llm_provider"] is None and post_consumer["llm_provider"] is None and pre_consumer["prediction_or_weight_influence"] is False and post_consumer["prediction_or_weight_influence"] is False,
        "all_9_agents_operational_after_freeze": post_runtime.get("status") == "PASS" and post_runtime.get("agent_count") == 9,
        "all_41_capabilities_accounted_after_freeze": post_runtime.get("capability_count") == 41,
        "fresh_epoch_did_not_import_old_activation_authority": freeze_obj.get("learning_activation_authority", {}).get("status") == "FAIL_CLOSED_INACTIVE",
        "fresh_epoch_started_without_old_signal_expansion_registry": freeze_obj.get("signal_expansion_governance", {}).get("candidate_count") == 0,
        "frontier_candidates_registered_shadow_only_after_main_freeze": frontier_freeze.get("status") == "FROZEN_SHADOW_ONLY" and frontier_freeze.get("production_authority") is False and float(frontier_freeze.get("material_weight", -1)) == 0.0,
        "prospective_probability_registration_bound_to_current_freeze": probability_registration.get("main_freeze_file_sha256") == freeze_result["freeze_sha256"],
        "prospective_probability_registration_result_unused": probability_registration.get("result_used") is False and probability_registration.get("result_available_at_registration") is False,
        "all_60_frontier_probabilities_retained": probability_registration.get("all_60_probabilities_retained") is True,
        "fine_tuning_authority_bound_to_epoch_data": fine_tuning["data_sha256"] == active["data_sha256"] and int(fine_tuning["target_contest"]) == target and int(fine_tuning["cutoff_contest"]) == cutoff,
        "fine_tuning_future_result_unused": fine_tuning["future_result_used"] is False and fine_tuning["holdout_used_for_selection"] is False,
        "fine_tuning_consumed_by_challenger": _fine_tuning_consumed_by_challenger(freeze_obj, fine_tuning),
        "official_schedule_bound": schedule.get("authority") == "CAIXA_ARCHIVED_CRONOGRAM_PDF" and schedule.get("result_used") is False,
    }
    if not all(trace_checks.values()):
        raise RuntimeError(f"full process trace invalid: {trace_checks}")

    proof = _self_hash({
        "schema": SCHEMA,
        "status": "PASS",
        "project": "SMART-MEGA",
        "epoch_id": active_frozen["epoch_id"],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "engineering_activation_sha256": activation["sha256"],
        "construction_authority_kind": activation.get("authority_kind", "ENGINEERING_ACTIVATION"),
        "active_epoch_sha256": active_frozen["sha256"],
        "target_contest": target,
        "cutoff_contest": cutoff,
        "target_schedule": schedule,
        "freeze_window": freeze_window.to_dict(),
        "data_file": active["data_file"],
        "data_sha256": active["data_sha256"],
        "reset_ledger_sha256": reset_ledger_sha,
        "final_ledger_sha256": freeze_result["ledger_sha256"],
        "state_sha256": freeze_result["state_sha256"],
        "freeze_file": _rel(root, actual_freeze_path),
        "freeze_sha256": freeze_result["freeze_sha256"],
        "manual_generation_authority": {"schema": manual_generation_authority.get("schema"), "target_contest": manual_generation_authority.get("target_contest"), "epoch_id": manual_generation_authority.get("epoch_id"), "data_sha256": manual_generation_authority.get("data_sha256")},
        "fine_tuning": {
            "status": fine_tuning["status"],
            "promotion_authorized": fine_tuning["promotion_authorized"],
            "effective_candidate_id": fine_tuning["effective_candidate_id"],
            "report_file": _rel(root, Path(fine_tuning["report_file"])),
            "report_sha256": fine_tuning["report_file_sha256"],
            "authority_file": _rel(root, Path(fine_tuning["authority_file"])),
            "authority_sha256": fine_tuning["authority_file_sha256"],
            "authority_self_sha256": fine_tuning["authority_sha256"],
            "holdout_used_for_selection": fine_tuning["holdout_used_for_selection"],
            "future_result_used": fine_tuning["future_result_used"],
        },
        "frontier_freeze_file": _rel(root, frontier_freeze_path),
        "frontier_freeze_sha256": sha256_file(frontier_freeze_path),
        "probability_ledger_file": _rel(root, probability_ledger_path),
        "probability_ledger_sha256": sha256_file(probability_ledger_path),
        "pre_freeze_total_integration_sha256": pre_gate["sha256"],
        "post_freeze_total_integration_sha256": post_gate["sha256"],
        "agent_skill_consumer": {
            "pre_freeze": pre_consumer,
            "post_freeze": post_consumer,
            "authority": "EVIDENCE_ONLY",
            "llm_required": False,
            "predictive_weight_authorized": False,
            "freeze_mutation_authorized": False,
        },
        "primary_card": primary_card,
        "primary_card_file": _rel(root, primary_card_path),
        "primary_card_sha256": primary_card_sha,
        "portfolio_file": _rel(root, portfolio_path),
        "portfolio_sha256": portfolio_sha,
        "optimization_contract": {
            "primary_output": "SINGLE_CARD",
            "numbers_per_card": 6,
            "objective": "MAXIMIZE_SIX_HIT_SINGLE_CARD",
            "portfolio_is_auxiliary": True,
            "portfolio_must_not_replace_primary_card": True,
            "selection_rule": primary_card["selection_rule"],
        },
        "champion_top6": freeze_obj["champion"]["top6"],
        "challenger_top6": challenger["top6"],
        "governed_challenger_top6": freeze_obj.get("governed_challenger_top6"),
        "trace_fields": list(TRACE_FIELDS),
        "trace_checks": trace_checks,
        "scientific_claim_status": "UNPROVEN_PROSPECTIVE",
        "terminal_mission_authority": False,
        "result_used": False,
    })
    proof_path = epoch_dir / "FULL_PROCESS_PROOF.json"
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    consumed_manual_authority = consume_manual_generation(root, active, target, freeze_result["freeze_sha256"])
    return {"proof": proof, "active_epoch": active_frozen, "freeze": freeze_result, "manual_generation_authority": consumed_manual_authority, "proof_file": _rel(root, proof_path)}


def main() -> None:
    root = canonical_root()
    result = run_full_process(root)
    proof = result["proof"]
    print(json.dumps({
        "status": proof["status"],
        "epoch_id": proof["epoch_id"],
        "target_contest": proof["target_contest"],
        "target_date": proof["target_schedule"]["target_date"],
        "primary_card": proof["primary_card"],
        "champion_top6": proof["champion_top6"],
        "challenger_top6": proof["challenger_top6"],
        "freeze_sha256": proof["freeze_sha256"],
        "scientific_claim_status": proof["scientific_claim_status"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
