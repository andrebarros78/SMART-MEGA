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
    "thinktank-me-multi-expert-framework-middle": "smart_meta_governor.MetaGovernor.select/update",
    "bayesian-workflow": "smart_rank_score_calibration.RankScoreCalibrator.predict/update",
    "extremizing-forecasts": "smart_rank_score_calibration.RankScoreCalibrator.predict/brier_score",
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
    elif capability in {"bayesian-workflow", "extremizing-forecasts"}:
        # The frozen rank posterior provides enough statistics for an *exact*
        # reconstruction because every prior contest updates all 60 ranks.
        # No current-target information enters predict(), only the later audit.
        from smart_rank_score_calibration import RankScoreCalibrator
        calibration = challenger.get("rank_score_calibration")
        if not isinstance(calibration, dict):
            raise ValueError("frozen Bayesian rank calibration unavailable")
        obs = int(calibration["observations"])
        prior = float(calibration["prior_strength"])
        strength = float(calibration["strength"])
        raw_posterior = np.asarray(calibration["raw_posterior_by_rank"], dtype=float)
        if (obs < 1 or not math.isfinite(prior) or prior <= 0
                or not math.isfinite(strength) or not 0 <= strength <= 1
                or raw_posterior.shape != (60,) or not np.all(np.isfinite(raw_posterior))):
            raise ValueError("invalid frozen Bayesian rank posterior")
        inferred_hits = raw_posterior * (obs + prior) - prior * 0.1
        nearest_hits = np.rint(inferred_hits)
        integrality_error = float(np.max(np.abs(inferred_hits - nearest_hits)))
        if (integrality_error > 1e-7
                or np.any(nearest_hits < 0) or np.any(nearest_hits > obs)):
            raise ValueError("frozen Bayesian rank posterior cannot reconstruct pre-result hits")
        audit_state = RankScoreCalibrator(
            strength=strength, prior_strength=prior, observations=obs,
            hits_by_rank=nearest_hits.copy(),
            trials_by_rank=np.full(60, obs, dtype=float),
            cumulative_brier=float(calibration["cumulative_brier"]),
            cumulative_uniform_brier=float(calibration["cumulative_uniform_brier"]),
        )
        ranking = challenger.get("ranking60")
        scores = challenger.get("aggregate_scores")
        old_probs, reproduced_audit = audit_state.predict(ranking, scores)
        original_probs = calibration.get("probabilities_by_number")
        if (reproduced_audit["sha256"] != calibration.get("sha256")
                or not isinstance(original_probs, dict)
                or set(old_probs) != set(original_probs)
                or any(abs(old_probs[k] - float(original_probs[k])) > 1e-12 for k in old_probs)):
            raise ValueError("frozen Bayesian calibration does not reproduce signed pre-result prediction")
        if capability == "bayesian-workflow":
            replay = audit_state.update(ranking, actual, old_probs)
            result = {
                "reconstructed_prior_observations": obs,
                "reconstructed_hits_integrality_max_error": integrality_error,
                "signed_frozen_calibration_sha256": reproduced_audit["sha256"],
                "before_result_frozen_probability_reproduced": True,
                "proper_score_from_disposable_posterior_update": replay["brier"],
                "uniform_reference_brier": replay["uniform_brier"],
                "hypothetical_observations_after_result": audit_state.observations,
                "posterior_updated_only_after_result": True,
                "source_uses_external_pymc": False,
                "state_persisted": False,
            }
        else:
            # A bounded scientific COUNTERFACTUAL: an isotonic posterior at a
            # small, explicitly unapproved strength. Compare proper scoring
            # to what was actually frozen and to uniform. The shadow candidate
            # cannot affect today's card or be promoted from a single draw.
            shadow_strength = 0.10
            audit_state.strength = shadow_strength
            shadow_probs, shadow_audit = audit_state.predict(ranking, scores)
            shadow_score = brier_score(shadow_probs, actual)
            frozen_score = brier_score(old_probs, actual)
            baseline = brier_score({str(n): 0.1 for n in range(1, 61)}, actual)
            if not all(math.isfinite(v) for v in (shadow_score, frozen_score, baseline)):
                raise ValueError("shadow extremizing calibration Brier is not finite")
            result = {
                "shadow_strength": shadow_strength,
                "frozen_strength": strength,
                "frozen_brier": frozen_score,
                "shadow_brier": shadow_score,
                "uniform_brier": baseline,
                "shadow_minus_frozen_brier": shadow_score - frozen_score,
                "shadow_minus_uniform_brier": shadow_score - baseline,
                "shadow_probability_mass": float(sum(shadow_probs.values())),
                "shadow_monotonic": shadow_audit["monotonic_after_isotonic"],
                "selection_or_weight_changed": False,
                "prospective_superiority_proven": False,
                "state_persisted": False,
                "external_extremizing_skill_executed": False,
            }
    elif capability == "thinktank-me-multi-expert-framework-middle":
        from smart_meta_governor import MetaGovernor
        from smart_multi_challengers import POLICY_IDS, sha256_json as policy_sha256
        multi = challenger.get("multi_challengers")
        snapshot = challenger.get("meta_governor")
        if not isinstance(multi, dict) or not isinstance(snapshot, dict):
            raise ValueError("multi-expert governance freeze unavailable")
        if multi.get("policy_ids") != list(POLICY_IDS) or set(multi.get("policies", {})) != set(POLICY_IDS):
            raise ValueError("frozen multi-expert policy identifiers mismatch")
        prior = float(snapshot["prior_mix"])
        if not 0 <= prior < 1:
            raise ValueError("invalid frozen multi-expert prior")
        published = snapshot.get("policy_weights_before_result")
        if not isinstance(published, dict) or set(published) != set(POLICY_IDS):
            raise ValueError("multi-expert frozen policy weights incomplete")
        stripped = {pid: (float(published[pid]) - prior / len(POLICY_IDS)) / (1 - prior)
                    for pid in POLICY_IDS}
        if any(not math.isfinite(v) or v <= 0 for v in stripped.values()):
            raise ValueError("multi-expert weights cannot be reconstructed")
        # The compact freeze retains only the selected hedge's cumulative
        # hit difference, not the entire historical hit vector. Reconstruct
        # the one difference used by the actual causal selection gate so a
        # *legitimately promoted* alternate will also replay correctly.
        evidence = snapshot.get("alternate_evidence")
        hedge = snapshot.get("hedge_candidate_policy")
        if not isinstance(evidence, dict) or hedge not in POLICY_IDS:
            raise ValueError("frozen multi-expert alternate evidence incomplete")
        hit_lead = int(evidence["cumulative_hit_lead_vs_anchor"])
        hits_before = {pid: 0 for pid in POLICY_IDS}
        if hit_lead >= 0:
            hits_before[hedge] = hit_lead
        else:
            hits_before["quality_dynamic"] = -hit_lead
        replay = MetaGovernor(
            eta=float(snapshot["eta"]), prior_mix=prior,
            allow_alternate_selection=bool(snapshot["allow_alternate_selection"]),
            automatic_evidence_guard=bool(snapshot["automatic_evidence_guard"]),
            observations=int(snapshot["observations_before_result"]),
            log_weights={pid: math.log(stripped[pid]) for pid in POLICY_IDS},
            cumulative_hits=hits_before,
        )
        max_replay_error = max(abs(replay.weights()[pid] - float(published[pid]))
                               for pid in POLICY_IDS)
        if max_replay_error > 1e-10:
            raise ValueError("multi-expert frozen governor weights do not replay")
        policies = multi["policies"]
        for pid in POLICY_IDS:
            document = policies[pid]
            if document.get("policy_id") != pid:
                raise ValueError("frozen multi-expert policy id inconsistent")
            checksum = document.get("sha256")
            if checksum != policy_sha256({k: v for k, v in document.items() if k != "sha256"}):
                raise ValueError("frozen multi-expert policy SHA mismatch")
        selected_before = replay.select(multi)
        if (selected_before["selected_policy"] != snapshot.get("selected_policy")
                or selected_before["selected_top6"] != snapshot.get("selected_top6")
                or selected_before["alternate_authorized"] != snapshot.get("alternate_authorized")
                or selected_before["hedge_candidate_policy"] != hedge
                or selected_before["alternate_evidence"]["cumulative_hit_lead_vs_anchor"] != hit_lead):
            raise ValueError("multi-expert pre-result selection did not replay")
        # Outcome is used only AFTER selection has been reconstructed.
        actual_set = set(actual)
        policy_hits = {pid: len(set(policies[pid]["top6"]) & actual_set)
                       for pid in POLICY_IDS}
        shadow = replay.update(policy_hits, selected_before["selected_policy"])
        if not shadow["update_after_result_only"]:
            raise ValueError("multi-expert update violates causal order")
        result = {"policy_hits": policy_hits,
                  "policy_count": len(policy_hits),
                  "frozen_pre_result_selected_policy": selected_before["selected_policy"],
                  "frozen_selected_policy_hits": policy_hits[selected_before["selected_policy"]],
                  "pre_result_weights_replay_max_error": max_replay_error,
                  "selected_before_current_result": True,
                  "disposable_shadow_weights_after_result": shadow["weights_after_result"],
                  "shadow_meta_governor_update_sha256": shadow["sha256"],
                  "production_policy_changed": False,
                  "learning_state_persisted": False,
                  "named_external_thinktank_agent_executed": False,
                  "scope": "FROZEN_FIVE_POLICY_POST_RESULT_COMPARISON_SHADOW_ONLY"}
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
    "combinatorialist",
    "time-series-forecasting",
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

    Only observational diagnostics and bounded CP-SAT controls are produced;
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
    from smart_randomness_cartography import fit_transition_weights

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
    # A genuine time-series transition fit using ONLY pre-result history.
    # These are rank INDICATORS, not calibrated probabilities and not scoring
    # authority. Never substitute them for the frozen Champion or Challenger.
    transition = fit_transition_weights(draws)
    if transition.shape != (60, 60) or not np.all(np.isfinite(transition)):
        raise ValueError("temporal transition matrix missing or invalid")
    temporal_indicators = np.mean(transition[np.asarray(draws[-1], dtype=int) - 1], axis=0)
    if temporal_indicators.shape != (60,) or not np.all(np.isfinite(temporal_indicators)):
        raise ValueError("temporal transition indicators not finite")
    temporal_top = [int(i) + 1 for i in np.lexsort((np.arange(1, 61), -temporal_indicators))[:6]]
    # Exact hypergeometric 6-of-60 random baseline, never learned from target.
    random_denominator = math.comb(60, 6)
    hypergeometric = {str(k): math.comb(6, k) * math.comb(54, 6 - k) / random_denominator
                      for k in range(7)}
    if abs(sum(hypergeometric.values()) - 1.0) > 1e-14:
        raise ValueError("exact random match distribution does not normalize")
    expected_hits = sum(k * hypergeometric[str(k)] for k in range(7))
    if abs(expected_hits - 0.6) > 1e-12:
        raise ValueError("exact random match expectation invalid")
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
        "combinatorialist": ("math.comb / exact_hypergeometric_6_of_60",
                             {"uniform_match_distribution_0_to_6": hypergeometric,
                              "expected_random_matches": expected_hits,
                              "all_possible_six_number_combinations": random_denominator,
                              "exact_six_match_probability": 1.0 / random_denominator,
                              "uses_target_result": False,
                              "predictive_superiority_proven": False}),
        "time-series-forecasting": ("smart_randomness_cartography.fit_transition_weights",
                                    {"transition_matrix_shape": [60, 60],
                                     "fit_draws": int(len(draws)),
                                     "cutoff": cutoff,
                                     "candidate_top6": temporal_top,
                                     "candidate_overlap_with_frozen_champion": len(set(temporal_top) & set(champion_card)),
                                     "indicator_range": [float(temporal_indicators.min()),
                                                         float(temporal_indicators.max())],
                                     "calibrated_probabilities": False,
                                     "frozen_champion_changed": False,
                                     "future_information_used": False,
                                     "predictive_promotion_authorized": False}),
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
