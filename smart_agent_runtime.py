from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from smart_agent_skill_orchestration import AGENTS, LANES, build_orchestration, resolve_runtime_phase

SCHEMA = "SMART_AGENT_RUNTIME_V2"
ORDER = [
    "quarantine_curator",
    "research_scout",
    "data_guardian",
    "null_model_cartographer",
    "falsification_auditor",
    "learning_calibration_governor",
    "robustness_red_team",
    "combinatorial_solver",
    "mission_governor",
]
BASE_CRITICAL_CANONICAL_FILES = [
    "SMART_SIGNAL_STATE.json",
    "SMART_SIGNAL_LEDGER.json",
]
ARTIFACT_HINTS = {
    "quarantine_curator": ["SMART_EXTERNAL_SKILLS_QUARANTINE_MANIFEST.json"],
    "research_scout": ["SMART_HYPOTHESIS_REGISTRY.json", "SMART_EXPERIMENT_LEDGER.json"],
    "data_guardian": ["SMART_DATA_CONTRACT.md"],
    "null_model_cartographer": ["SMART_RANDOMNESS_ATLAS_1000.json", "SMART_RANDOMNESS_ATLAS_EXTENDED.json"],
    "falsification_auditor": ["SMART_FALSIFICATION_REPORT.json", "SMART_FALSIFICATION_POWER_AUDIT.json"],
    "learning_calibration_governor": ["SMART_EXPERIMENT_LEDGER.json"],
    "robustness_red_team": ["SMART_P09_RED_TEAM_LATEST.json", "smart_continuous_red_team.py"],
    "combinatorial_solver": ["smart_portfolio_optimizer.py", "smart_portfolio_pipeline.py"],
    "mission_governor": ["SMART_MISSION_STATUS.json"],
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _synthetic_draws(seed: int = 20260905, n: int = 80) -> np.ndarray:
    rng = np.random.default_rng(seed)
    universe = np.arange(1, 61)
    return np.asarray([np.sort(rng.choice(universe, 6, replace=False)) for _ in range(n)], dtype=int)


@dataclass
class AgentExecution:
    name: str
    status: str
    capabilities: list[str]
    native_targets: list[str]
    artifacts: list[dict[str, str]]
    consumed_handoffs: list[dict[str, Any]]
    produced_handoffs: list[dict[str, Any]]
    probe_id: str
    probe_result: dict[str, Any]
    verdict: str


class SmartAgentRuntime:
    def __init__(self, root: str | Path, phase: str = "AUTO"):
        self.root = Path(root)
        self.phase = resolve_runtime_phase(self.root, phase)
        self.orchestration = build_orchestration(self.root, phase=self.phase)
        self.active_context = dict(self.orchestration["active_context"])

    def capabilities_for(self, name: str) -> list[str]:
        lane = AGENTS[name].get("lane")
        return [] if lane is None else list(LANES[lane]["capabilities"])

    def targets_for(self, name: str) -> list[str]:
        lane = AGENTS[name].get("lane")
        return [] if lane is None else list(LANES[lane]["native_targets"])

    def artifact_records(self, name: str) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        hints = list(ARTIFACT_HINTS[name])
        if name == "data_guardian":
            hints.insert(0, str(self.active_context["data_file"]))
        for relative in hints:
            path = self.root / relative
            if path.is_file():
                records.append({"path": relative.replace("\\", "/"), "sha256": sha256_file(path)})
        return records

    def _critical_files(self) -> list[str]:
        # BUILD certifies the product without depending on an operational epoch.
        # Older/unit-created instances may intentionally bypass __init__; preserve
        # the historical AUTO behavior instead of raising AttributeError.
        phase = getattr(self, "phase", "AUTO")
        files = [] if phase == "BUILD" else list(BASE_CRITICAL_CANONICAL_FILES)
        for key in ("freeze_file", "data_file", "signal_state_file", "ledger_file"):
            value = self.active_context.get(key)
            if value:
                files.append(str(value))
        if phase != "BUILD" and (self.root / "SMART_ACTIVE_EPOCH.json").is_file():
            files.append("SMART_ACTIVE_EPOCH.json")
        return sorted(set(files))

    def _critical_hashes(self) -> dict[str, str | None]:
        return {r: sha256_file(self.root / r) if (self.root / r).is_file() else None for r in self._critical_files()}

    def _probe_quarantine_curator(self) -> dict[str, Any]:
        p = self.root / "SMART_EXTERNAL_SKILLS_QUARANTINE_MANIFEST.json"
        manifest = json.loads(p.read_text(encoding="utf-8-sig"))
        items = manifest.get("items", [])
        bad = []
        for item in items:
            if item.get("status") != "ACQUIRED_VERIFIED" or item.get("execution_policy") != "SOURCE_ONLY_QUARANTINE":
                bad.append(item.get("name"))
        payload_required = manifest.get("source_payload_required_at_runtime")
        auto_execute = manifest.get("external_code_auto_execute")
        optional_payload_present = (self.root / ".external_skills_acquired").is_dir()
        return {
            "probe_id": "quarantine_manifest_integrity",
            "executed_functions": ["json.loads"],
            "items": len(items),
            "invalid_items": bad,
            "source_payload_required_at_runtime": payload_required,
            "optional_source_payload_present": optional_payload_present,
            "external_code_executed": False,
            "pass": len(items) == 21 and not bad and payload_required is False and auto_execute is False,
        }

    def _probe_research_scout(self) -> dict[str, Any]:
        paths = [self.root / "SMART_HYPOTHESIS_REGISTRY.json", self.root / "SMART_EXPERIMENT_LEDGER.json"]
        docs = [json.loads(p.read_text(encoding="utf-8-sig")) for p in paths]
        return {"probe_id": "research_registry_read_validation", "executed_functions": ["json.loads"], "documents": [p.name for p in paths], "hashes": [sha256_file(p) for p in paths], "pass": all(isinstance(d, (dict, list)) for d in docs)}

    def _probe_data_guardian(self) -> dict[str, Any]:
        from smart_data_quality_gate import audit_draw_file
        cutoff = int(self.active_context["cutoff_contest"])
        data_file = str(self.active_context["data_file"])
        report = audit_draw_file(self.root / data_file, cutoff)
        return {"probe_id": "canonical_draw_quality_audit", "executed_functions": ["smart_data_quality_gate.audit_draw_file"], "data_file": data_file, "target_contest": int(self.active_context["target_contest"]), "status": report.status, "rows": report.row_count, "contest_max": report.contest_max, "checks": report.checks, "pass": report.status == "PASS" and report.contest_max == cutoff and all(report.checks.values())}

    def _probe_null_model_cartographer(self) -> dict[str, Any]:
        from smart_randomness_cartography import atlas_descriptors
        from smart_cartography_extended import regime_structure
        draws = _synthetic_draws()
        desc = atlas_descriptors(draws)
        regime = regime_structure(draws)
        return {"probe_id": "synthetic_cartography_execution", "executed_functions": ["smart_randomness_cartography.atlas_descriptors", "smart_cartography_extended.regime_structure"], "descriptor_count": len(desc), "regime_method": regime.get("method"), "regime_diagnostic_only": regime.get("diagnostic_only"), "pass": len(desc) >= 10 and bool(regime.get("diagnostic_only"))}

    def _probe_falsification_auditor(self) -> dict[str, Any]:
        from smart_falsification_lab import holm_adjust, regime_max_cusum
        draws = _synthetic_draws(seed=20260906)
        cusum = float(regime_max_cusum(draws))
        adjusted = [float(x) for x in holm_adjust([0.01, 0.20, 0.50])]
        return {"probe_id": "synthetic_falsification_execution", "executed_functions": ["smart_falsification_lab.regime_max_cusum", "smart_falsification_lab.holm_adjust"], "cusum": cusum, "holm_adjusted": adjusted, "pass": np.isfinite(cusum) and adjusted == sorted(adjusted) and all(0 <= x <= 1 for x in adjusted)}

    def _probe_learning_calibration_governor(self) -> dict[str, Any]:
        from smart_bounded_online_learning import BoundedOnlineLearningGuard
        from smart_rank_score_calibration import RankScoreCalibrator
        guard = BoundedOnlineLearningGuard(eta=0.1)
        new_weights, update = guard.update({"a": 0.0, "b": 0.0}, {"a": 2, "b": 0})
        calibrator = RankScoreCalibrator(strength=0.25)
        ranking = list(range(1, 61))
        probabilities, audit = calibrator.predict(ranking)
        score = calibrator.update(ranking, [1, 2, 3, 4, 5, 6], probabilities)
        return {"probe_id": "bounded_learning_and_calibration_execution", "executed_functions": ["smart_bounded_online_learning.BoundedOnlineLearningGuard.update", "smart_rank_score_calibration.RankScoreCalibrator.predict", "smart_rank_score_calibration.RankScoreCalibrator.update"], "weights_changed": new_weights != {"a": 0.0, "b": 0.0}, "update_after_result_only": bool(update.get("update_after_result_only")), "probability_sum": float(sum(probabilities.values())), "brier_delta": float(score["delta_vs_uniform"]), "calibration_mode": audit.get("calibration_mode"), "pass": new_weights != {"a": 0.0, "b": 0.0} and bool(update.get("update_after_result_only")) and abs(sum(probabilities.values()) - 6.0) < 1e-9}

    def _probe_robustness_red_team(self) -> dict[str, Any]:
        from smart_continuous_red_team import scenario_false_signal_and_recovery, scenario_missing_and_corrupt_data
        corrupt = scenario_missing_and_corrupt_data()
        recovery = scenario_false_signal_and_recovery()
        return {"probe_id": "red_team_safety_execution", "executed_functions": ["smart_continuous_red_team.scenario_missing_and_corrupt_data", "smart_continuous_red_team.scenario_false_signal_and_recovery"], "corrupt_input_pass": bool(corrupt.get("pass")), "false_signal_recovery_pass": bool(recovery.get("pass")), "pass": bool(corrupt.get("pass")) and bool(recovery.get("pass"))}

    def _probe_combinatorial_solver(self) -> dict[str, Any]:
        from smart_portfolio_optimizer import PortfolioConfig, optimize_portfolio
        scores = {i: float(61 - i) for i in range(1, 61)}
        result = optimize_portfolio(scores, PortfolioConfig(game_count=2, candidate_pool_size=12, max_pairwise_overlap=4, time_limit_seconds=1.0))
        games = result.get("games", [])
        valid = len(games) == 2 and all(len(g) == 6 and len(set(g)) == 6 for g in games)
        overlap = len(set(games[0]) & set(games[1])) if valid else 99
        return {"probe_id": "or_tools_portfolio_execution", "executed_functions": ["smart_portfolio_optimizer.optimize_portfolio"], "solver_status": result.get("solver_status"), "games": games, "pairwise_overlap": overlap, "pass": result.get("solver_status") == "OPTIMAL" and valid and overlap <= 4}

    def _probe_mission_governor(self) -> dict[str, Any]:
        p = self.root / "SMART_MISSION_STATUS.json"
        mission = json.loads(p.read_text(encoding="utf-8-sig"))
        status = str(mission.get("status", "UNKNOWN"))
        terminal = bool(mission.get("terminal_6of6_proven", False))
        consistent = status in {"MISSION_ACTIVE", "MISSION_PROVEN"} and ((status == "MISSION_PROVEN") == terminal)
        return {"probe_id": "canonical_mission_status_resolution", "executed_functions": ["json.loads"], "mission_status": status, "terminal_6of6_proven": terminal, "pass": consistent}

    def _probe_for(self, name: str) -> dict[str, Any]:
        probes: dict[str, Callable[[], dict[str, Any]]] = {
            "quarantine_curator": self._probe_quarantine_curator,
            "research_scout": self._probe_research_scout,
            "data_guardian": self._probe_data_guardian,
            "null_model_cartographer": self._probe_null_model_cartographer,
            "falsification_auditor": self._probe_falsification_auditor,
            "learning_calibration_governor": self._probe_learning_calibration_governor,
            "robustness_red_team": self._probe_robustness_red_team,
            "combinatorial_solver": self._probe_combinatorial_solver,
            "mission_governor": self._probe_mission_governor,
        }
        result = probes[name]()
        if not isinstance(result, dict) or not result.get("pass"):
            raise RuntimeError(f"{name} native probe failed: {result}")
        return result

    def run(self) -> dict[str, Any]:
        if self.orchestration["integration_status"] != "PASS":
            raise RuntimeError("declarative orchestration is not PASS")
        hashes_before = self._critical_hashes()
        executions: dict[str, dict[str, Any]] = {}
        produced_by_agent: dict[str, list[dict[str, Any]]] = {}
        acknowledged_ids: list[str] = []
        for name in ORDER:
            config = AGENTS[name]
            capabilities = self.capabilities_for(name)
            targets = self.targets_for(name)
            missing_targets = [t for t in targets if not (self.root / t).exists()]
            if missing_targets:
                raise RuntimeError(f"{name} missing native targets: {missing_targets}")
            consumed: list[dict[str, Any]] = []
            for producer, handoffs in produced_by_agent.items():
                if name in AGENTS[producer]["handoff_to"]:
                    consumed.extend(handoffs)
                    acknowledged_ids.extend(h["handoff_id"] for h in handoffs)
            artifacts = self.artifact_records(name)
            if not artifacts:
                raise RuntimeError(f"{name} has no verifiable runtime evidence")
            probe_result = self._probe_for(name)
            payload = {"agent": name, "capabilities": capabilities, "native_targets": targets, "artifacts": artifacts, "consumed_handoff_ids": sorted(h["handoff_id"] for h in consumed), "probe_result": probe_result}
            digest = sha256_json(payload)
            produced = [{"handoff_id": f"{name}->{dst}:{digest[:16]}", "producer": name, "consumer": dst, "payload_sha256": digest, "probe_id": probe_result["probe_id"]} for dst in config["handoff_to"]]
            produced_by_agent[name] = produced
            verdict = str(probe_result.get("mission_status", "PASS"))
            executions[name] = asdict(AgentExecution(name, "PASS", capabilities, targets, artifacts, consumed, produced, str(probe_result["probe_id"]), probe_result, verdict))
        expected_ids = [h["handoff_id"] for hs in produced_by_agent.values() for h in hs]
        unacknowledged = sorted(set(expected_ids) - set(acknowledged_ids))
        owned = sorted(c for name in ORDER for c in self.capabilities_for(name))
        inv = self.orchestration["inventory"]
        acquired = sorted(set(inv["source_only_skills"] + inv["v2_capabilities"] + inv["v3_capabilities"] + inv["native_scientific_libraries"]))
        hashes_after = self._critical_hashes()
        checks = {
            "all_9_agents_native_probed": len(executions) == 9 and all(e["status"] == "PASS" and e["probe_result"].get("pass") for e in executions.values()),
            "all_41_capabilities_owned": owned == acquired and len(owned) == 41,
            "all_native_targets_verified": all(all((self.root / t).exists() for t in e["native_targets"]) for e in executions.values()),
            "all_declared_handoffs_acknowledged": not unacknowledged,
            "all_agents_have_runtime_evidence": all(e["artifacts"] for e in executions.values()),
            "all_agents_have_executed_function_evidence": all(e["probe_result"].get("executed_functions") for e in executions.values()),
            "mission_governor_reads_canonical_status": executions["mission_governor"]["verdict"] in {"MISSION_ACTIVE", "MISSION_PROVEN"},
            "no_agent_predictive_or_freeze_authority": all(not self.orchestration["agents"][n]["predictive_weight_authorized"] and not self.orchestration["agents"][n]["freeze_mutation_authorized"] for n in ORDER),
            "critical_canonical_files_unchanged": hashes_before == hashes_after,
        }
        doc: dict[str, Any] = {"schema": SCHEMA, "phase": self.phase, "status": "PASS" if all(checks.values()) else "FAIL", "claim_scope": "The nine named agents are deterministic SMART role executors validated by read-only/synthetic native probes; they are not autonomous AI/LLM agents. External skill source code remains quarantined and is not executed.", "checks": checks, "executions": executions, "unacknowledged_handoffs": unacknowledged, "capability_count": len(owned), "agent_count": len(executions), "critical_hashes_before": hashes_before, "critical_hashes_after": hashes_after, "declarative_orchestration_sha256": self.orchestration["orchestration_sha256"]}
        doc["runtime_sha256"] = sha256_json(doc)
        return doc


def write_runtime(root: str | Path, output: str | Path = "SMART_AGENT_RUNTIME_PROOF.json", phase: str = "AUTO") -> dict[str, Any]:
    root_path = Path(root)
    output_path = Path(output)
    if not output_path.is_absolute():
        output_path = root_path / output_path
    document = SmartAgentRuntime(root_path).run() if str(phase).upper() == "AUTO" else SmartAgentRuntime(root_path, phase=phase).run()
    output_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return document


def main(argv: list[str] | None = None) -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["BUILD", "PRE_FREEZE", "POST_FREEZE"], default="POST_FREEZE")
    parser.add_argument("--output", default="SMART_AGENT_RUNTIME_PROOF.json")
    args = parser.parse_args([] if argv is None else argv)
    result = write_runtime(Path(__file__).resolve().parent) if args.phase == "POST_FREEZE" and args.output == "SMART_AGENT_RUNTIME_PROOF.json" else write_runtime(Path(__file__).resolve().parent, args.output, phase=args.phase)
    print(json.dumps({"status": result["status"], "phase": result.get("phase", "POST_FREEZE"), "agents": result["agent_count"], "capabilities": result["capability_count"], "checks": result["checks"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":  # pragma: no cover
    import sys
    main(sys.argv[1:])
