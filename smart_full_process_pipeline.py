from __future__ import annotations

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
from smart_learning_epoch_reset import ACTIVE_PATH, verify_active_epoch, write_active_epoch
from smart_prospective_cycle import register as register_prospective_cycle
from smart_procedural_actionability_gate import evaluate_freeze_window
from smart_target_schedule import assert_pre_draw_window, resolve_target_schedule
from smart_total_integration_gate import write as write_total_integration

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


def _files_under(path: Path) -> set[Path]:
    return {item.resolve() for item in path.rglob("*") if item.is_file()}


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


def run_full_process(root: str | Path = ".", start: int = 1000) -> dict[str, Any]:
    root = Path(root).resolve()
    active_path = root / ACTIVE_PATH
    active = verify_active_epoch(active_path)
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
    frontier_report_path = epoch_dir / "SMART_FRONTIER_HISTORICAL.json"
    frontier_freeze_path = epoch_dir / f"SMART_{int(active['target_contest'])}_FRONTIER_SHADOW_FREEZE.json"
    probability_ledger_path = epoch_dir / "SMART_PROBABILITY_PROSPECTIVE_LEDGER.json"

    ledger_before = load_ledger(ledger_path)
    draws, contests = engine.load_draws(data_path)
    target = int(active["target_contest"])
    cutoff = int(active["cutoff_contest"])
    schedule = resolve_target_schedule(root, target)
    freeze_window = evaluate_freeze_window(
        scheduled_datetime=str(schedule["scheduled_datetime"]),
        observed_at=datetime.now(timezone.utc).isoformat(),
    )
    pre_checks = {
        "epoch_reset_ready": active["status"] == "RESET_READY",
        "fresh_ledger_zero_events": ledger_before.get("events") == [],
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

    reset_ledger_sha = sha256_file(ledger_path)
    files_before = _files_under(epoch_dir)
    ledger_bytes = ledger_path.read_bytes()
    try:
        from smart_signal_agent import SIGNAL_NAMES
        from smart_signal_expansion_governance import load_registry, write_registry
        if not expansion_registry_path.exists():
            expansion_governance = load_registry(expansion_registry_path, tuple(SIGNAL_NAMES))
            write_registry(expansion_registry_path, expansion_governance)
        freeze_result = freeze_champion_challenger(
            data_path,
            target,
            freeze_path,
            ledger_path,
            state_path,
            start=int(start),
            allow_pre_result_supersede=False,
            activation_authority_path=activation_authority_path,
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
        raise

    final_ledger = load_ledger(ledger_path)
    freeze_events = [e for e in final_ledger.get("events", []) if e.get("event_type") == "FREEZE"]
    adjudications = [e for e in final_ledger.get("events", []) if e.get("event_type") == "ADJUDICATION"]

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
    })

    post_runtime = SmartAgentRuntime(root, phase="POST_FREEZE").run()
    post_gate_path = epoch_dir / "POST_FREEZE_TOTAL_INTEGRATION.json"
    post_gate = write_total_integration(root, post_gate_path, phase="POST_FREEZE")

    challenger = freeze_obj.get("challenger", {})
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
        "challenger_top6_valid": _valid_top6(challenger.get("top6")),
        "pre_freeze_integration_pass": pre_gate.get("status") == "PASS" and pre_gate.get("phase") == "PRE_FREEZE",
        "post_freeze_integration_pass": post_gate.get("status") == "PASS" and post_gate.get("phase") == "POST_FREEZE",
        "all_9_agents_operational_after_freeze": post_runtime.get("status") == "PASS" and post_runtime.get("agent_count") == 9,
        "all_41_capabilities_accounted_after_freeze": post_runtime.get("capability_count") == 41,
        "fresh_epoch_did_not_import_old_activation_authority": freeze_obj.get("learning_activation_authority", {}).get("status") == "FAIL_CLOSED_INACTIVE",
        "fresh_epoch_started_without_old_signal_expansion_registry": freeze_obj.get("signal_expansion_governance", {}).get("candidate_count") == 0,
        "frontier_candidates_registered_shadow_only_after_main_freeze": frontier_freeze.get("status") == "FROZEN_SHADOW_ONLY" and frontier_freeze.get("production_authority") is False and float(frontier_freeze.get("material_weight", -1)) == 0.0,
        "prospective_probability_registration_bound_to_current_freeze": probability_registration.get("main_freeze_file_sha256") == freeze_result["freeze_sha256"],
        "prospective_probability_registration_result_unused": probability_registration.get("result_used") is False and probability_registration.get("result_available_at_registration") is False,
        "all_60_frontier_probabilities_retained": probability_registration.get("all_60_probabilities_retained") is True,
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
        "frontier_freeze_file": _rel(root, frontier_freeze_path),
        "frontier_freeze_sha256": sha256_file(frontier_freeze_path),
        "probability_ledger_file": _rel(root, probability_ledger_path),
        "probability_ledger_sha256": sha256_file(probability_ledger_path),
        "pre_freeze_total_integration_sha256": pre_gate["sha256"],
        "post_freeze_total_integration_sha256": post_gate["sha256"],
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
    return {"proof": proof, "active_epoch": active_frozen, "freeze": freeze_result, "proof_file": _rel(root, proof_path)}


def main() -> None:
    root = Path(__file__).resolve().parent
    result = run_full_process(root)
    proof = result["proof"]
    print(json.dumps({
        "status": proof["status"],
        "epoch_id": proof["epoch_id"],
        "target_contest": proof["target_contest"],
        "target_date": proof["target_schedule"]["target_date"],
        "champion_top6": proof["champion_top6"],
        "challenger_top6": proof["challenger_top6"],
        "freeze_sha256": proof["freeze_sha256"],
        "scientific_claim_status": proof["scientific_claim_status"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
