from __future__ import annotations
from smart_canonical_identity import canonical_root

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from smart_agent_runtime import SmartAgentRuntime, sha256_file, sha256_json
from smart_agent_skill_orchestration import AGENTS, LANES
from smart_skill_adapter_registry import build_registry as build_adapter_registry

SCHEMA = "SMART_SKILL_RUNTIME_V1"
QUARANTINE_LANE = "retained_quarantine_no_current_lane"


def _owner_map() -> dict[str, str]:
    owners: dict[str, str] = {}
    for agent, config in AGENTS.items():
        lane_name = config.get("lane")
        if lane_name is None:
            continue
        for capability in LANES[lane_name]["capabilities"]:
            if capability in owners:
                raise ValueError(f"duplicate capability owner: {capability}")
            owners[capability] = agent
    return owners


OWNERS = _owner_map()
ALL_CAPABILITIES = tuple(sorted(OWNERS))
QUARANTINED_CAPABILITIES = frozenset(LANES[QUARANTINE_LANE]["capabilities"])
PERTINENT_CAPABILITIES = tuple(sorted(set(ALL_CAPABILITIES) - QUARANTINED_CAPABILITIES))


@dataclass(frozen=True)
class CapabilityRegistration:
    capability: str
    agent_owner: str
    lane: str
    authority: str
    pertinent: bool
    callable: bool
    execution_mode: str
    external_source_executed: bool
    direct_named_skill_execution: bool
    semantic_binding_kind: str
    native_targets: tuple[str, ...]


class SmartSkillRuntime:
    """Fail-closed registry and invocation layer for SMART-MEGA capabilities.

    Third-party source trees remain source-only. Pertinent capabilities are exposed
    through bounded native adapters; quarantined non-pertinent references are
    intentionally not callable.
    """

    def __init__(self, root: str | Path, phase: str = "AUTO"):
        self.root = Path(root).resolve()
        self.agent_runtime = SmartAgentRuntime(self.root) if str(phase).upper() == "AUTO" else SmartAgentRuntime(self.root, phase=phase)
        self.phase = self.agent_runtime.phase
        self._registrations = self._build_registrations()
        self.adapter_registry = build_adapter_registry(self.root)
        if self.adapter_registry["gate"]["status"] != "PASS":
            raise RuntimeError(f"skill adapter registry invalid: {self.adapter_registry['gate']}")
        self._adapter_by_name = {
            row["capability_id"]: row for row in self.adapter_registry["adapters"]
        }

    def _build_registrations(self) -> dict[str, CapabilityRegistration]:
        registrations: dict[str, CapabilityRegistration] = {}
        for capability, owner in OWNERS.items():
            lane_name = str(AGENTS[owner]["lane"])
            lane = LANES[lane_name]
            pertinent = lane_name != QUARANTINE_LANE
            targets = tuple(str(x) for x in lane["native_targets"])
            if pertinent and not targets:
                raise RuntimeError(f"pertinent capability has no native target: {capability}")
            registrations[capability] = CapabilityRegistration(
                capability=capability,
                agent_owner=owner,
                lane=lane_name,
                authority=str(lane["authority"]),
                pertinent=pertinent,
                callable=pertinent,
                execution_mode="BOUNDED_NATIVE_ADAPTER" if pertinent else "SOURCE_ONLY_QUARANTINE",
                external_source_executed=False,
                direct_named_skill_execution=False,
                semantic_binding_kind="METHODOLOGY_ALIAS_TO_NATIVE_ROLE_PROBE" if pertinent else "SOURCE_REFERENCE_ONLY",
                native_targets=targets,
            )
        if set(registrations) != set(ALL_CAPABILITIES) or len(registrations) != 41:
            raise RuntimeError("capability registry is incomplete")
        return registrations

    def registrations(self) -> list[dict[str, Any]]:
        return [asdict(self._registrations[name]) for name in sorted(self._registrations)]

    def registration(self, capability: str) -> CapabilityRegistration:
        if capability not in self._registrations:
            raise KeyError(f"unknown SMART capability: {capability}")
        return self._registrations[capability]

    def invoke(self, capability: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        registration = self.registration(capability)
        binding = self._adapter_by_name[capability]
        if (
            binding["agent_owner"] != registration.agent_owner
            or binding["callable"] != registration.callable
            or binding["execution_mode"] != registration.execution_mode
            or binding["binding_sha256"] != sha256_json({k: v for k, v in binding.items() if k != "binding_sha256"})
        ):
            raise RuntimeError(f"skill adapter binding mismatch: {capability}")
        if binding["state"] not in {"NATIVE_ADAPTER", "REFERENCE_ONLY"}:
            raise RuntimeError(f"unproved skill adapter state: {capability}")
        if not registration.callable:
            raise PermissionError(
                f"capability is intentionally non-pertinent and quarantined: {capability}"
            )
        if payload is not None and not isinstance(payload, dict):
            raise TypeError("capability payload must be an object when provided")
        # The adapter executes the owner's native probe now. This is an actual
        # function invocation, not a declarative PASS copied from a manifest.
        probe = self.agent_runtime._probe_for(registration.agent_owner)
        if not probe.get("pass"):
            raise RuntimeError(f"native adapter failed for {capability}: {probe}")
        targets = []
        for relative in registration.native_targets:
            path = self.root / relative
            if not path.exists():
                raise FileNotFoundError(f"native target missing for {capability}: {relative}")
            if path.is_file():
                targets.append({"path": relative.replace("\\", "/"), "sha256": sha256_file(path)})
            else:
                targets.append({"path": relative.replace("\\", "/"), "kind": "directory"})
        evidence = {
            "capability": capability,
            "agent_owner": registration.agent_owner,
            "lane": registration.lane,
            "execution_mode": registration.execution_mode,
            "probe_id": probe.get("probe_id"),
            "executed_functions": list(probe.get("executed_functions", [])),
            "native_targets": targets,
            "external_source_executed": False,
            "direct_named_skill_execution": False,
            "semantic_binding_kind": registration.semantic_binding_kind,
            "payload_shape": sorted(payload.keys()) if payload else [],
            "adapter_state": binding["state"],
            "adapter_binding_sha256": binding["binding_sha256"],
            "adapter_registry_sha256": self.adapter_registry["registry_sha256"],
            "native_probe_result_sha256": sha256_json(probe),
            "external_source_state": binding["external_source_state"],
            "decision_effect": binding["decision_effect"],
            "predictive_weight_authorized": False,
            "freeze_mutation_authorized": False,
            "status": "PASS",
        }
        evidence["invocation_sha256"] = sha256_json(evidence)
        return evidence

    def execute_gate(self) -> dict[str, Any]:
        critical_before = self.agent_runtime._critical_hashes()
        rows: list[dict[str, Any]] = []
        for capability in ALL_CAPABILITIES:
            registration = self.registration(capability)
            if registration.callable:
                invocation = self.invoke(capability, {"gate": "functional"})
                row = {**asdict(registration), "invocation": invocation, "status": "PASS"}
            else:
                row = {
                    **asdict(registration),
                    "invocation": None,
                    "status": "NON_PERTINENT_QUARANTINED",
                    "reason": "No current SMART-MEGA functional gap justifies activation; source retained for research reference only.",
                }
            rows.append(row)
        critical_after = self.agent_runtime._critical_hashes()
        callable_rows = [r for r in rows if r["callable"]]
        quarantined_rows = [r for r in rows if not r["callable"]]
        checks = {
            "all_41_registered": len(rows) == 41 and len({r["capability"] for r in rows}) == 41,
            "all_pertinent_callable": len(callable_rows) == 37 and all(r["status"] == "PASS" and r["invocation"] for r in callable_rows),
            "each_pertinent_invoked_individually": all(r["invocation"]["capability"] == r["capability"] and r["invocation"]["invocation_sha256"] for r in callable_rows),
            "all_nonpertinent_explicitly_quarantined": len(quarantined_rows) == 4 and all(r["status"] == "NON_PERTINENT_QUARANTINED" for r in quarantined_rows),
            "external_source_never_executed": all(not r["external_source_executed"] for r in rows),
            "no_direct_named_skill_execution_is_claimed": all(not r["direct_named_skill_execution"] for r in rows),
            "pertinent_bindings_are_explicit_native_aliases": all(r["semantic_binding_kind"] == "METHODOLOGY_ALIAS_TO_NATIVE_ROLE_PROBE" for r in callable_rows),
            "native_targets_present": all(all((self.root / p).exists() for p in r["native_targets"]) for r in callable_rows),
            "canonical_state_unchanged": critical_before == critical_after,
            "f07_adapter_registry_pass": self.adapter_registry["gate"]["status"] == "PASS",
            "f07_external_sources_quarantined": self.adapter_registry["summary"]["external_quarantined_sources"] == 21 and self.adapter_registry["summary"]["external_executions"] == 0,
            "f07_no_unproven_active_native": self.adapter_registry["summary"]["active_native"] == 0,
            "f07_per_invocation_binding_consumed": all(
                row["invocation"]["adapter_binding_sha256"] == self._adapter_by_name[row["capability"]]["binding_sha256"]
                and row["invocation"]["adapter_state"] == "NATIVE_ADAPTER"
                and row["invocation"]["native_probe_result_sha256"]
                for row in callable_rows
            ),
        }
        document: dict[str, Any] = {
            "schema": SCHEMA,
            "phase": self.phase,
            "status": "PASS" if all(checks.values()) else "FAIL",
            "scope": "Per-capability methodology-alias resolution to bounded native role probes; this does NOT prove direct execution of the named third-party skill/library.",
            "claim_boundary": "A registered capability name is a methodology/reference binding. Direct named external-skill execution is false unless separately evidenced.",
            "checks": checks,
            "counts": {
                "registered": len(rows),
                "pertinent_callable": len(callable_rows),
                "nonpertinent_quarantined": len(quarantined_rows),
            },
            "capabilities": rows,
            "adapter_registry": self.adapter_registry,
            "critical_hashes_before": critical_before,
            "critical_hashes_after": critical_after,
        }
        document["sha256"] = sha256_json(document)
        return document


def write_gate(root: str | Path, output: str | Path = "SMART_SKILL_RUNTIME_PROOF.json", phase: str = "AUTO") -> dict[str, Any]:
    root = Path(root)
    output = Path(output)
    if not output.is_absolute():
        output = root / output
    result = SmartSkillRuntime(root).execute_gate() if str(phase).upper() == "AUTO" else SmartSkillRuntime(root, phase=phase).execute_gate()
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    root = canonical_root()
    result = write_gate(root)
    print(json.dumps({"status": result["status"], "counts": result["counts"], "checks": result["checks"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

# Operational consumption is deliberately separate from invoke(): a registry
# probe is NOT evidence that a named method processed product data.
LIVE_POST_RESULT_BINDINGS = {
    "openai-validate-data": "smart_signal_attribution._snapshot_arrays",
    "pandera-data-contracts": "smart_signal_attribution._snapshot_arrays",
    "openai-analyze-data-quality": "smart_signal_weights.dynamic_weights",
    "machine-learning-model-validation": "smart_signal_weights.dynamic_weights",
    "statistical-analysis": "smart_signal_marginal_utility.analyze_marginal_utility_snapshot",
    "evo-memory": "smart_signal_marginal_utility.analyze_marginal_utility_snapshot",
    "experiment-design": "smart_signal_marginal_utility.analyze_marginal_utility_snapshot",
    "model-drift-management": "numpy.count_nonzero",
    "regime-detection": "smart_context_regime.frozen_regime_evidence",
    "superforecasting": "smart_rank_score_calibration.brier_score",
    "benchmarking-uncertainty-calibration-long-form": "smart_rank_score_calibration.brier_score",
    "simulation": "smart_experiment_lab.monte_carlo_null_hits",
    "live-evo-online-evolution-agentic": "smart_bounded_online_learning.BoundedOnlineLearningGuard.update",
}


def invoke_live_native(capability: str, freeze: dict[str, Any], actual_numbers: list[int]) -> dict[str, Any]:
    """Execute a native operation on a real pre-result frozen signal snapshot.

    Every call returns hashed per-capability evidence. Methodology aliases are
    NOT third-party skill execution. Never modifies freeze, prediction or weights.
    """
    import math
    import numpy as np
    from smart_signal_attribution import _snapshot_arrays
    from smart_signal_marginal_utility import analyze_marginal_utility_snapshot
    from smart_signal_weights import dynamic_weights
    from smart_rank_score_calibration import brier_score

    if capability not in LIVE_POST_RESULT_BINDINGS or capability not in PERTINENT_CAPABILITIES:
        raise KeyError(f"no real post-result native execution: {capability}")
    challenger = freeze.get("challenger")
    if not isinstance(challenger, dict):
        raise ValueError("native execution requires real frozen challenger")
    arrays, weights = _snapshot_arrays(challenger)
    raw = challenger["raw_signals"]
    quality = challenger.get("quality_metrics")
    if not isinstance(quality, dict) or set(quality) != set(arrays):
        raise ValueError("native execution quality ids mismatch")
    if any(record.get("causal") is not True
           or record.get("cutoff_contest") != freeze.get("cutoff_contest")
           or record.get("target_contest") != freeze.get("target_contest")
           for record in raw.values()):
        raise ValueError("native execution requires causal and same-target frozen signals")
    actual = sorted(int(n) for n in actual_numbers)
    if len(actual) != 6 or len(set(actual)) != 6 or min(actual) < 1 or max(actual) > 60:
        raise ValueError("native execution requires six valid official numbers")
    methods = LIVE_POST_RESULT_BINDINGS
    method = methods[capability]
    result: dict[str, Any]
    if capability in {"openai-validate-data", "pandera-data-contracts"}:
        # _snapshot_arrays above actually executes the 60-value/weight validator.
        result = {"validated_signal_count": len(arrays), "values_per_signal": 60,
                  "normalized_weight_mass": round(sum(weights.values()), 12)}
    elif capability in {"openai-analyze-data-quality", "machine-learning-model-validation"}:
        families = {name: raw[name]["family"] for name in arrays}
        recomputed, components = dynamic_weights(quality, families)
        err = max(abs(float(recomputed[name]) - float(challenger["weights"][name])) for name in arrays)
        if err > 1e-9:
            raise ValueError("native weights do not reproduce frozen Challenger")
        result = {"signals": len(components), "max_abs_weight_error": err,
                  "reproduces_frozen_weights": True}
    elif capability in {"statistical-analysis", "evo-memory", "experiment-design"}:
        utility = analyze_marginal_utility_snapshot(challenger, actual)
        result = {"marginal_utility_sha256": utility["marginal_utility_sha256"],
                  "real_target_hits": int(utility["full_ensemble"]["hits"]),
                  "signals_evaluated": len(utility["per_signal"]),
                  "retrospective_only": True, "memory_state_mutated": False}
    elif capability == "simulation":
        from smart_experiment_lab import monte_carlo_null_hits
        # Real official adjudication, but a *single contest* is explicitly
        # insufficient for any claim about predictive superiority.
        top = set(int(x) for x in challenger["top6"])
        hits = len(top.intersection(actual))
        null = monte_carlo_null_hits([hits], replications=4096,
                                     seed=int(freeze["cutoff_contest"]))
        if null["contest_count"] != 1 or null["observed_total_hits"] != hits:
            raise ValueError("null simulation does not reproduce observed frozen hits")
        result = {"observed_hits": hits, "replications": null["replications"],
                  "uniform_expected_hits": null["uniform_expected_total_hits"],
                  "tail_probability": null["p_null_ge_observed"],
                  "scope": "SINGLE_CONTEST_DIAGNOSTIC_NOT_PREDICTIVE_PROOF"}
    elif capability == "live-evo-online-evolution-agentic":
        from smart_bounded_online_learning import BoundedOnlineLearningGuard
        # Independent, disposable WHAT-IF update; never mutate the frozen
        # learning authority or any file. Not an autonomous agent invocation.
        snapshot = challenger.get("bounded_online_learning")
        expert = snapshot.get("expert") if isinstance(snapshot, dict) else None
        if not isinstance(expert, dict):
            raise ValueError("frozen bounded online expert evidence absent")
        guard = BoundedOnlineLearningGuard(
            eta=float(expert["eta"]), baseline_hits=float(expert["baseline_hits"]),
            max_abs_step=float(expert["max_abs_step"]),
            warmup_max_abs_step=float(expert["warmup_max_abs_step"]),
            prior_observations=int(expert["prior_observations"]),
            warmup_full_after=int(expert["warmup_full_after"]),
            min_warmup_scale=float(expert["min_warmup_scale"]),
            max_abs_centered_logit=float(expert["max_abs_centered_logit"]),
        )
        log_weights = {name: math.log(float(weights[name])) for name in sorted(arrays)}
        if any(not math.isfinite(v) for v in log_weights.values()):
            raise ValueError("shadow learning requires finite positive frozen weights")
        hit_set = set(actual)
        rewards = {}
        for name in sorted(arrays):
            values = arrays[name]
            top_indices = np.lexsort((np.arange(1, 61), -values))[:6]
            rewards[name] = len({int(i) + 1 for i in top_indices}.intersection(hit_set))
        proposed, audit = guard.update(log_weights, rewards)
        if set(proposed) != set(weights) or not audit["update_after_result_only"]:
            raise ValueError("online shadow update is inconsistent with frozen weights")
        if max(abs(float(x)) for x in audit["applied_delta"].values()) > guard.max_abs_step + 1e-12:
            raise ValueError("bounded shadow learning exceeds per-result step cap")
        result = {"signal_count": len(rewards), "reward_hits": rewards,
                  "reward_sum": int(sum(rewards.values())),
                  "shadow_applied_delta": audit["applied_delta"],
                  "max_abs_applied_delta": float(max(abs(v) for v in audit["applied_delta"].values())),
                  "weight_state_persisted": False,
                  "model_or_agent_promoted": False,
                  "mode": "DISPOSABLE_POST_RESULT_SHADOW_UPDATE"}
    elif capability == "model-drift-management":
        flags = np.array([bool(quality[k].get("drift_active")) for k in sorted(arrays)], dtype=int)
        drift_count = int(np.count_nonzero(flags))
        result = {"signals": len(flags), "drift_active_count": drift_count}
    elif capability == "regime-detection":
        # Frozen pre-result regime audit was executed during scoring, not
        # recalculated using the official draw. Verify the actual audit values.
        context = challenger.get("context_regime")
        if not isinstance(context, dict) or not math.isfinite(float(context.get("l1_score", float("nan")))):
            raise ValueError("native regime evidence absent or invalid")
        result = {"frozen_regime_active": bool(context.get("active")),
                  "frozen_l1_score": float(context["l1_score"]),
                  "native_method": "frozen_context_regime_audit_validation"}
        method = "smart_context_regime.frozen_context_regime_audit_validation"
    else:
        calibration = challenger.get("rank_score_calibration")
        if not isinstance(calibration, dict):
            raise ValueError("native calibration evidence missing")
        probabilities = calibration.get("probabilities_by_number")
        if not isinstance(probabilities, dict) or set(probabilities) != {str(n) for n in range(1, 61)}:
            raise ValueError("native calibration requires 60 frozen probabilities")
        if any(not math.isfinite(float(p)) or not 0 <= float(p) <= 1 for p in probabilities.values()):
            raise ValueError("native calibration probabilities invalid")
        if abs(sum(float(p) for p in probabilities.values()) - 6.0) > 1e-8:
            raise ValueError("native calibration probability mass mismatch")
        scored = brier_score(probabilities, actual)
        reference = brier_score({str(n): 0.1 for n in range(1, 61)}, actual)
        result = {"brier": scored, "uniform_brier": reference,
                  "delta_vs_uniform": scored - reference,
                  "frozen_calibration_neutralized": bool(calibration.get("neutralized"))}
    receipt = {
        "schema": "SMART_NATIVE_LIVE_CAPABILITY_EXECUTION_1",
        "capability": capability,
        "native_function_executed": method,
        "target_contest": int(freeze["target_contest"]),
        "cutoff_contest": int(freeze["cutoff_contest"]),
        "frozen_inputs_sha256": sha256_json({"raw_signals": raw, "weights": challenger["weights"],
                                             "quality_metrics": quality}),
        "official_result_sha256": sha256_json(actual),
        "observed_output": result,
        "consumer": "smart_post_result_report._operational_capability_consumption",
        "external_skill_code_executed": False,
        "decision_effect": "POST_RESULT_DIAGNOSTIC_ONLY",
        "predictive_weight_authorized": False,
    }
    receipt["execution_sha256"] = sha256_json(receipt)
    return receipt


FROZEN_STRUCTURAL_CAPABILITIES = (
    "data-analysis",
    "google-or-tools",
    "multiple-testing-fdr-statsmodels",
    "networkx",
    "operations-research-algorithm-developer",
    "ruptures",
    "statsmodels",
)


def consume_frozen_structural_capabilities(freeze: dict[str, Any], root: str | Path) -> dict[str, Any]:
    """Run real independent libraries on hash-bound pre-draw product data.

    Only observational diagnostics and a one-game CP-SAT control are produced;
    these outputs cannot promote signals, models, odds or operational cards.
    The official outcome is deliberately not an input to any of these methods.
    """
    import math
    import numpy as np
    from statsmodels.stats.multitest import multipletests
    from smart_data_quality_gate import enforce_draw_quality
    from smart_v2_engine import load_draws
    from smart_cartography_extended import temporal_memory, network_structure, regime_structure
    from smart_portfolio_optimizer import optimize_portfolio, PortfolioConfig

    path_str = freeze.get("data_file")
    if not isinstance(path_str, str) or not path_str:
        return {"status": "UNAVAILABLE_LEGACY_FREEZE", "receipts": {},
                "predictive_weight_authorized": False}
    if freeze.get("frozen_before_result") is not True:
        raise ValueError("structural consumption requires a genuine pre-result freeze")
    cutoff = int(freeze["cutoff_contest"])
    target = int(freeze["target_contest"])
    if target != cutoff + 1:
        raise ValueError("structural consumption cutoff must precede target")
    base = Path(root).resolve()
    file_path = (base / path_str).resolve()
    if not file_path.is_relative_to(base) or not file_path.is_file():
        raise ValueError("frozen structural data missing or outside canonical root")
    expected_hash = freeze.get("data_sha256")
    if not isinstance(expected_hash, str) or sha256_file(file_path) != expected_hash:
        raise ValueError("frozen structural data digest mismatch")
    quality = enforce_draw_quality(file_path, expected_max_contest=cutoff)
    if int(quality.contest_max) != cutoff:
        raise ValueError("structural source cutoff does not match frozen contest")
    draws, contests = load_draws(file_path)
    if int(contests[-1]) != cutoff or len(draws) != quality.row_count:
        raise ValueError("structural source rows and cutoff inconsistent")

    champion = freeze.get("champion", {})
    if not isinstance(champion, dict) or not isinstance(champion.get("aggregate_scores"), dict):
        raise ValueError("structural consumption requires frozen champion scores")
    if set(champion["aggregate_scores"]) != {str(i) for i in range(1, 61)}:
        raise ValueError("structural consumption requires 60 champion scores")
    if not set(FROZEN_STRUCTURAL_CAPABILITIES) <= set(PERTINENT_CAPABILITIES):
        raise ValueError("structural capability missing from pertinent registered skills")
    memory = temporal_memory(draws)  # actual statsmodels acorr_ljungbox
    structure = network_structure(draws)  # actual NetworkX graph
    regimes = regime_structure(draws)  # actual ruptures Binseg
    pvals = memory.get("ljung_box_sum_pvalues")
    if not isinstance(pvals, dict) or not pvals:
        raise ValueError("statsmodels temporal diagnostic did not produce p-values")
    numeric_p = [float(pvals[k]) for k in sorted(pvals, key=int)]
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in numeric_p):
        raise ValueError("invalid p-values from temporal diagnostic")
    # Ljung-Box lag tests overlap; BY-FDR remains valid under arbitrary
    # dependence, unlike a naive unadjusted/independence-only declaration.
    reject, adj, _, _ = multipletests(numeric_p, alpha=0.05, method="fdr_by")
    multiplicity = {"method": "statsmodels.stats.multitest.multipletests:fdr_by",
                    "hypotheses": len(numeric_p), "adjusted_p_values": [float(v) for v in adj],
                    "rejected_count": int(np.count_nonzero(reject)),
                    "predictive_signals_authorized": False}
    cp_config = PortfolioConfig(game_count=1, candidate_pool_size=6,
                                coverage_bonus=0.0, rank_bonus=0.02,
                                time_limit_seconds=5.0, random_seed=42)
    control = optimize_portfolio(champion["aggregate_scores"], config=cp_config)
    game = control["games"][0]
    champion_card = champion.get("top6")
    if control["solver_status"] != "OPTIMAL" or not isinstance(champion_card, list) or set(game) != set(champion_card):
        raise ValueError("OR-Tools control failed to reproduce frozen Champion")
    if control["contract"].get("predictive_scores_unchanged") is not True:
        raise ValueError("OR-Tools must preserve frozen score authority")
    # An independent OR-Tools invocation evaluates *portfolio constraints*,
    # not just the single-card replication above. No predictive claim follows.
    constrained = optimize_portfolio(
        champion["aggregate_scores"], config=PortfolioConfig(
            game_count=2, candidate_pool_size=9, max_pairwise_overlap=3,
            coverage_bonus=0.35, rank_bonus=0.02,
            time_limit_seconds=5.0, random_seed=42,
        ),
    )
    if (constrained["solver_status"] != "OPTIMAL"
            or constrained["metrics"]["max_pairwise_overlap_observed"] > 3
            or constrained["contract"].get("predictive_scores_unchanged") is not True):
        raise ValueError("OR-Tools constrained portfolio verification failed")

    method_outputs = {
        "data-analysis": ("smart_data_quality_gate.enforce_draw_quality",
                          {"status": quality.status, "contest_max": quality.contest_max,
                           "row_count": quality.row_count}),
        "statsmodels": ("smart_cartography_extended.temporal_memory/statsmodels.stats.diagnostic.acorr_ljungbox", memory),
        "networkx": ("smart_cartography_extended.network_structure/networkx.Graph", structure),
        "ruptures": ("smart_cartography_extended.regime_structure/ruptures.Binseg", regimes),
        "multiple-testing-fdr-statsmodels": ("statsmodels.stats.multitest.multipletests", multiplicity),
        "google-or-tools": ("smart_portfolio_optimizer.optimize_portfolio/ortools.cp_model.CpSolver",
                            {"solver_status": control["solver_status"], "single_card": game,
                             "objective_value": control["objective_value"],
                             "frozen_champion_reproduced": True}),
        "operations-research-algorithm-developer": (
            "smart_portfolio_optimizer.optimize_portfolio/ortools.cp_model.CpSolver",
            {"solver_status": constrained["solver_status"],
             "game_count": len(constrained["games"]),
             "max_pairwise_overlap_observed": constrained["metrics"]["max_pairwise_overlap_observed"],
             "overlap_limit": 3, "objective_value": constrained["objective_value"],
             "independent_constrained_solver_executed": True}),
    }
    receipts = {}
    for capability, (method, result) in method_outputs.items():
        receipt = {
            "schema": "SMART_NATIVE_FROZEN_STRUCTURAL_CONSUMPTION_1",
            "capability": capability, "native_function_executed": method,
            "target_contest": target, "cutoff_contest": cutoff,
            "frozen_source_sha256": expected_hash,
            "observed_output": result,
            "consumer": "smart_post_result_report._structural_capability_diagnostic",
            "outcome_used_for_structural_methods": False,
            "external_skill_source_code_executed": False,
            "execution_mode": "NATIVE_LIBRARY_METHOD_ON_FROZEN_DATA",
            "predictive_weight_authorized": False,
        }
        receipt["execution_sha256"] = sha256_json(receipt)
        receipts[capability] = receipt
    result = {
        "status": "PASS", "source_file": path_str,
        "frozen_source_sha256": expected_hash,
        "data_quality": {"status": quality.status, "rows": quality.row_count, "cutoff": cutoff},
        "execution_receipts_count": len(receipts), "receipts": receipts,
        "shared_solver_executions": 2,
        "third_party_libraries_actually_called": ["statsmodels", "networkx", "ruptures", "ortools"],
        "outcome_used_for_structural_methods": False,
        "predictive_weight_authorized": False, "prospective_superiority_proven": False,
    }
    result["sha256"] = sha256_json(result)
    return result
