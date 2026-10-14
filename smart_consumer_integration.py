"""Bind native validation and actual signal/SDK consumption to the frozen card.

The champion remains authoritative. This audit never learns from a target result
or grants quarantined sources predictive authority.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from importlib import metadata
from datetime import datetime
from pathlib import Path
from typing import Any

import smart_v2_engine as engine
from smart_agent_handoff_runtime import consume_handoff
from smart_data_quality_gate import audit_draw_file
from smart_portfolio_optimizer import PortfolioConfig, optimize_from_freeze
from smart_primary_card_selector import PrimaryCardSelectorConfig, select_primary_card
from smart_signal_weights import dynamic_weights
from smart_target_schedule import assert_pre_draw_window, resolve_target_schedule

SCHEMA = "SMART_CONSUMER_INTEGRATION_V2"
RUNTIME_SDK_ROLES = {
    "pandas": "CAUSAL_HISTORY_AND_SIGNAL_REPLAY",
    "river": "FROZEN_ADWIN_QUALITY_INPUT_TO_CHALLENGER_WEIGHTS",
    "ortools": "FROZEN_SCORE_AUXILIARY_PORTFOLIO_REPLAY",
    "pydantic": "TYPED_OPERATIONAL_HANDOFF_CONSUMPTION",
    "pypdf": "ARCHIVED_OFFICIAL_SCHEDULE_REPLAY",
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_json(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _hashed(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    try:
        return doc.get("sha256") == _sha256_json({k: v for k, v in doc.items() if k != "sha256"})
    except (ValueError, TypeError):
        return False


def _path(root: Path, path: str | Path) -> Path:
    resolved = (root / path).resolve()
    resolved.relative_to(root)
    return resolved


def _finite(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _vector(values: Any) -> bool:
    return (isinstance(values, dict) and set(values) == {str(n) for n in range(1, 61)}
            and all(_finite(v) for v in values.values()))


def _weights(values: Any, names: set[str]) -> bool:
    return (isinstance(values, dict) and set(values) == names
            and all(_finite(v) and v >= 0 for v in values.values())
            and math.isclose(sum(values.values()), 1.0, abs_tol=1e-8))


def _require(checks: dict[str, bool]) -> None:
    failed = [name for name, passed in checks.items() if passed is not True]
    if failed:
        raise RuntimeError(f"consumer integration failed closed: {failed}")


def _replay(root: Path, target: int, freeze_path: Path, freeze: dict,
            package: dict, card: dict, gates: tuple[dict, dict]) -> dict:
    """Recompute actual frozen inputs; ablation is diagnostic, never promotion."""
    assert_pre_draw_window(freeze["target_schedule"], now=datetime.fromisoformat(freeze["frozen_utc"].replace("Z", "+00:00")))
    data = _path(root, freeze["data_file"])
    quality = audit_draw_file(data, target - 1)
    _require({"causal_history_hash_and_quality": quality.status == "PASS"
              and quality.contest_max == target - 1
              and quality.file_sha256 == freeze["data_sha256"] == package["source_data_sha256"]})
    draws, contests = engine.load_draws(data)
    pre = engine.precompute_scores(engine.onehot(draws))
    raw = freeze["challenger"]["raw_signals"]
    names = set(pre)
    _require({"all_raw_signals_causal_and_complete": set(raw) == names and all(
        row.get("signal_id") == name and row.get("target_contest") == target
        and row.get("cutoff_contest") == target - 1 and row.get("causal") is True
        and row.get("family") == engine.family_of(name)
        and _vector(row.get("values")) and row.get("values_sha256") == _sha256_json(row["values"])
        for name, row in raw.items())})
    signals = {name: {str(n): float(pre[name][len(draws), n - 1]) for n in range(1, 61)}
               for name in pre}
    _require({"raw_signals_recomputed_from_history": all(
        math.isclose(signals[name][n], raw[name]["values"][n], rel_tol=1e-10, abs_tol=1e-12)
        for name in names for n in signals[name])})

    challenger = freeze["challenger"]
    metrics, river = challenger["quality_metrics"], challenger["river_state"]
    _require({"river_quality_consumed_by_dynamic_weights": set(metrics) == set(river) == names and all(
        river[name].get("n_oos", 0) > 0 and river[name].get("adwin_width", 0) > 0
        and all(metrics[name][k] == river[name][k] for k in ("quality", "confidence"))
        for name in names)})
    replay_weights, _ = dynamic_weights(metrics, {name: engine.family_of(name) for name in metrics})
    _require({"dynamic_weights_recomputed_from_quality": all(
        math.isclose(replay_weights[name], challenger["weights"][name], rel_tol=1e-10, abs_tol=1e-12)
        for name in names)})

    ablations = []
    for head, weight_key in (("champion", "expert_weights"), ("challenger", "weights")):
        obj = freeze[head]
        weights = obj[weight_key]
        _require({f"{head}_weights_and_scores_complete": _weights(weights, names)
                  and _vector(obj.get("aggregate_scores"))})
        aggregate = {n: sum(weights[name] * signals[name][n] for name in pre)
                     for n in signals[next(iter(pre))]}
        _require({f"{head}_scores_recomputed_from_signals_and_weights": all(
            math.isclose(aggregate[n], obj["aggregate_scores"][n], rel_tol=1e-10, abs_tol=1e-12)
            for n in aggregate)})
        ranking = sorted(range(1, 61), key=lambda n: (-aggregate[str(n)], n))
        _require({f"{head}_ranking_recomputed": obj["ranking60"] == ranking
                  and (head != "champion" or obj["top6"] == ranking[:6])})
        for name in pre:
            mass = 1.0 - weights[name]
            without = {n: (aggregate[n] - weights[name] * signals[name][n]) / mass
                       for n in aggregate} if mass > 1e-12 else dict(aggregate)
            ablations.append({"head": head, "signal": name, "weight": weights[name],
                              "max_score_delta_without_signal": max(abs(aggregate[n] - without[n]) for n in aggregate),
                              "effective_primary_card_weight": weights[name] if head == "champion" else 0.0,
                              "predictive_benefit_proven": False})

    rescue = card["false_negative_rescue"]
    _require({"selector_and_rescue_hashes_valid": _hashed(card["selector"]) and _hashed(rescue)
              and rescue.get("result_used") is False and card["selector"].get("result_used") is False})
    deltas = rescue.get("nonzero_deltas", {})
    _require({"unqualified_rescue_remains_neutral": isinstance(deltas, dict)
              and all(n in freeze["champion"]["aggregate_scores"] and _finite(v) for n, v in deltas.items())
              and (rescue.get("status") == "PASS" or not deltas)})
    scores = {n: value + deltas.get(n, 0.0) for n, value in freeze["champion"]["aggregate_scores"].items()}
    selected = select_primary_card(scores, config=PrimaryCardSelectorConfig(**card["selector"]["config"]))
    _require({"primary_selector_recomputed_from_effective_scores": selected == card["selector"]})

    handoff_count = 0
    for gate in gates:
        ledger = gate["operational_handoff_ledger"]
        _require({"typed_handoff_ledger_valid": _hashed(ledger) and ledger.get("status") == "PASS"
                  and ledger.get("records") and all(v is True for v in ledger["checks"].values())})
        ids = []
        for record in ledger["records"]:
            envelope = {k: v for k, v in record.items() if k != "status"}
            receipt = consume_handoff(envelope, consumer=record["consumer"],
                                     consumer_sequence=record["consumption_result"]["consumed_sequence"])
            _require({"typed_handoff_receipt_recomputed": receipt == envelope})
            ids.append(record["handoff_id"])
        _require({"handoff_ids_distinct": len(ids) == len(set(ids)) == ledger["produced_count"] == ledger["consumed_count"]})
        handoff_count += len(ids)

    schedule = resolve_target_schedule(root, target)
    _require({"official_schedule_recomputed_without_result": all(
        schedule[k] == freeze["target_schedule"][k]
        for k in ("target_contest", "scheduled_datetime", "source_sha256", "result_used"))
        and schedule["result_used"] is False})
    portfolio = optimize_from_freeze(freeze_path, PortfolioConfig(**package["config"]), head="champion")
    _require({"or_tools_consumes_frozen_champion_scores": portfolio["solver_status"] == "OPTIMAL"
              and math.isclose(portfolio["objective_value"], package["solver"]["objective_value"], abs_tol=1e-8)})
    return {"data_sha256": quality.file_sha256, "history_rows": len(draws),
            "cutoff_contest": int(contests[-1]), "signals_recomputed": len(names),
            "signal_ablations": ablations, "typed_handoffs_consumed": handoff_count,
            "portfolio_solver_status": portfolio["solver_status"],
            "portfolio_recomputed_objective": portfolio["objective_value"],
            "schedule_source_sha256": schedule["source_sha256"],
            "selector_sha256": selected["sha256"], "target_result_used": False,
            "ablation_scope": "FROZEN_SCORE_INFLUENCE_ONLY__NOT_OUT_OF_SAMPLE_BENEFIT"}


def evaluate(*, root: str | Path, target: int, epoch_id: str,
             freeze_path: str | Path, portfolio_path: str | Path,
             primary_card: dict[str, Any], pre_gate: dict[str, Any], post_gate: dict[str, Any]) -> dict:
    root = Path(root).resolve()
    freeze_path, portfolio_path = _path(root, freeze_path), _path(root, portfolio_path)
    freeze = json.loads(freeze_path.read_text(encoding="utf-8-sig"))
    package = json.loads(portfolio_path.read_text(encoding="utf-8-sig"))
    agents, skills = post_gate.get("agent_inventory", []), post_gate.get("skill_inventory", [])
    invocations = post_gate.get("native_invocations", [])
    native = [r for r in skills if r.get("pertinent") is True]
    references = [r for r in skills if r.get("pertinent") is False]
    champion, challenger = freeze.get("champion", {}), freeze.get("challenger", {})
    names = {"freq25", "freq50", "freq100", "freq250", "freq500", "freq1000",
             "freq_global", "ewma10", "ewma25", "ewma50", "ewma100", "ewma250"}
    numbers = primary_card.get("numbers", [])
    sdk = []
    for name, role in RUNTIME_SDK_ROLES.items():
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            version = None
        sdk.append({"name": name, "version": version, "installed": version is not None,
                    "role": role, "runtime_installation_is_not_predictive_evidence": True})
    checks = {
        "pre_and_post_execution_gates_pass": (pre_gate.get("status"), pre_gate.get("phase"),
            post_gate.get("status"), post_gate.get("phase")) == ("PASS", "PRE_FREEZE", "PASS", "POST_FREEZE"),
        "gates_self_hash_and_checks_valid": all(_hashed(g) and g.get("gates")
            and all(v is True for group in g["gates"].values() for v in group.values())
            for g in (pre_gate, post_gate)),
        "nine_distinct_native_agents": len(agents) == 9 and len({r.get("name") for r in agents}) == 9
            and all(r.get("probe_result", {}).get("pass") is True for r in agents),
        "37_native_skill_aliases_invoked": len(native) == len(invocations) == 37
            and len({r.get("capability") for r in native}) == 37
            and all(r.get("status") == "PASS" and r.get("direct_named_skill_execution") is False
                    and r.get("predictive_weight_authorized") is False for r in invocations),
        "four_reference_only_not_executed": len(references) == 4
            and all(r.get("alias_invocation") is None for r in references),
        "external_third_party_code_quarantined": len(skills) == 41 and all(
            r.get("external_skill_source_executed") is False and r.get("direct_named_skill_execution") is False for r in skills),
        "five_consumed_sdk_packages_installed": all(row["installed"] for row in sdk),
        "adapter_registry_consistent": isinstance(pre_gate.get("skill_adapter_registry_sha256"), str)
            and pre_gate["skill_adapter_registry_sha256"] == post_gate.get("skill_adapter_registry_sha256"),
        "twelve_valid_challenger_signal_weights": _weights(challenger.get("weights"), names),
        "champion_scores_cover_universe": _vector(champion.get("aggregate_scores")),
        "target_result_not_consumed": type(target) is int and freeze.get("target_contest") == target
            and freeze.get("cutoff_contest") == target - 1 and freeze.get("frozen_before_result") is True
            and package.get("target_contest") == primary_card.get("target_contest") == target
            and package.get("cutoff_contest") == primary_card.get("cutoff_contest") == target - 1
            and primary_card.get("result_used") is False and primary_card.get("run_id") == epoch_id,
        "primary_consumes_champion_head": primary_card.get("source_head") == "champion"
            and package.get("primary_card", {}).get("source_head") == "champion"
            and primary_card.get("source_top6_ordered") == champion.get("top6"),
        "six_numbers_exactly_from_selector_and_portfolio": numbers == primary_card.get("selector", {}).get("selected_numbers")
            == package.get("primary_card", {}).get("numbers") and len(numbers) == len(set(numbers)) == 6
            and all(type(n) is int and 1 <= n <= 60 for n in numbers),
        "freeze_and_portfolio_byte_hashes_bound": primary_card.get("freeze_sha256") == _sha256_file(freeze_path)
            == package.get("freeze_sha256") and primary_card.get("portfolio_sha256") == _sha256_file(portfolio_path),
        "primary_card_self_hash_valid": _hashed(primary_card),
        "no_external_llm_authority_claimed": all(g.get("sdk_llm_selection", {}).get("provider") is None
            and g.get("sdk_llm_selection", {}).get("external_network_calls") == 0
            for g in (pre_gate, post_gate)),
    }
    _require(checks)
    replay = _replay(root, target, freeze_path, freeze, package, primary_card, (pre_gate, post_gate))
    doc = {"schema": SCHEMA, "status": "PASS", "target_contest": target, "epoch_id": epoch_id,
           "freeze_file": freeze_path.relative_to(root).as_posix(), "freeze_sha256": _sha256_file(freeze_path),
           "portfolio_file": portfolio_path.relative_to(root).as_posix(), "portfolio_sha256": _sha256_file(portfolio_path),
           "card_numbers": numbers, "effective_decision_head": "champion",
           "challenger_weight_role": "SHADOW_UNLESS_EVIDENCE_PROMOTED",
           "native_agents_executed": len(agents), "native_skill_aliases_invoked": len(invocations),
           "external_skill_source_executions": 0, "external_llm_provider_calls": 0,
           "sdk": sdk, "checks": checks, "consumption_replay": replay, "result_used": False,
           "predictive_advantage_proven": False,
           "claim_boundary": "Native role and methodology probes gate evidence. Actual history, raw signals, both weighted score heads, handoffs, schedule, optimizer and primary selector are replayed. Frozen ablation measures influence, not predictive benefit; challenger remains shadow."}
    doc["sha256"] = _sha256_json(doc)
    return doc


def audit_generation(root: str | Path, proof: dict) -> dict:
    """Consume the already completed generation; persist outside frozen epoch."""
    root = Path(root).resolve()
    _require({"full_process_proof_valid": _hashed(proof) and proof.get("status") == "PASS"
              and proof.get("schema") == "SMART_FULL_PROCESS_PROOF_2"
              and proof.get("result_used") is False and proof.get("trace_checks")
              and all(v is True for v in proof["trace_checks"].values())})
    freeze_path, portfolio_path = _path(root, proof["freeze_file"]), _path(root, proof["portfolio_file"])
    card_path = _path(root, proof["primary_card_file"])
    epoch = card_path.parent
    pre = json.loads((epoch / "PRE_FREEZE_TOTAL_INTEGRATION.json").read_text(encoding="utf-8-sig"))
    post = json.loads((epoch / "POST_FREEZE_TOTAL_INTEGRATION.json").read_text(encoding="utf-8-sig"))
    card = json.loads(card_path.read_text(encoding="utf-8-sig"))
    _require({"full_process_artifacts_bound": proof["freeze_sha256"] == _sha256_file(freeze_path)
              and proof["portfolio_sha256"] == _sha256_file(portfolio_path)
              and proof["primary_card_sha256"] == _sha256_file(card_path) and proof["primary_card"] == card
              and proof["data_sha256"] == json.loads(freeze_path.read_text(encoding="utf-8-sig"))["data_sha256"]
              and proof["pre_freeze_total_integration_sha256"] == pre.get("sha256")
              and proof["post_freeze_total_integration_sha256"] == post.get("sha256")})
    doc = evaluate(root=root, target=proof["target_contest"], epoch_id=proof["epoch_id"],
                   freeze_path=freeze_path, portfolio_path=portfolio_path, primary_card=card, pre_gate=pre, post_gate=post)
    doc["full_process_proof_sha256"] = proof["sha256"]
    doc["sha256"] = _sha256_json({k: v for k, v in doc.items() if k != "sha256"})
    destination = epoch.relative_to(root)
    # Use the bound epoch path, never an unchecked epoch_id as a filesystem path.
    out = _path(root, Path("runtime") / "card_consumption" / destination.name / "SMART_CARD_CONSUMER_INTEGRATION.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(doc, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if not out.is_file() or out.read_bytes() != payload:
        fd, temporary = tempfile.mkstemp(dir=out.parent, prefix=".consumer-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload.decode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, out)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return {"status": "PASS", "file": out.relative_to(root).as_posix(),
            "sha256": _sha256_file(out), "proof_sha256": doc["sha256"], "card_numbers": doc["card_numbers"]}
