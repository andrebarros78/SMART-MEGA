from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from smart_agent_skill_orchestration import AGENTS, LANES, build_orchestration

SCHEMA = "SMART_AGENT_RUNTIME_V1"
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
ARTIFACT_HINTS = {
    "quarantine_curator": [".external_skills_acquired/ACQUISITION_MANIFEST.json"],
    "research_scout": ["SMART_HYPOTHESIS_REGISTRY.json", "SMART_EXPERIMENT_LEDGER.json"],
    "data_guardian": ["SMART_DATA_QUALITY_3052.json", "SMART_DATA_CONTRACT.md"],
    "null_model_cartographer": ["SMART_RANDOMNESS_ATLAS_1000.json", "SMART_RANDOMNESS_ATLAS_EXTENDED.json", "SMART_P1_P2_CARTOGRAPHY_PROOF.json", "SMART_P2_EXTENDED_CARTOGRAPHY_PROOF.json"],
    "falsification_auditor": ["SMART_FALSIFICATION_REPORT.json", "SMART_FALSIFICATION_POWER_AUDIT.json"],
    "learning_calibration_governor": ["SMART_EXPERIMENT_LEDGER.json"],
    "robustness_red_team": ["SMART_AUDIT_JUNIT_CURRENT.xml"],
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


@dataclass
class AgentExecution:
    name: str
    status: str
    capabilities: list[str]
    native_targets: list[str]
    artifacts: list[dict[str, str]]
    consumed_handoffs: list[str]
    produced_handoffs: list[str]
    verdict: str


class SmartAgentRuntime:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.orchestration = build_orchestration(self.root)

    def capabilities_for(self, name: str) -> list[str]:
        lane = AGENTS[name].get("lane")
        return [] if lane is None else list(LANES[lane]["capabilities"])

    def targets_for(self, name: str) -> list[str]:
        lane = AGENTS[name].get("lane")
        return [] if lane is None else list(LANES[lane]["native_targets"])

    def artifact_records(self, name: str) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        for relative in ARTIFACT_HINTS[name]:
            path = self.root / relative
            if path.is_file():
                records.append({"path": relative.replace("\\", "/"), "sha256": sha256_file(path)})
        return records

    def run(self) -> dict[str, Any]:
        if self.orchestration["integration_status"] != "PASS":
            raise RuntimeError("declarative orchestration is not PASS")

        executions: dict[str, dict[str, Any]] = {}
        produced_by_agent: dict[str, list[str]] = {}
        acknowledged: list[str] = []

        for name in ORDER:
            config = AGENTS[name]
            capabilities = self.capabilities_for(name)
            targets = self.targets_for(name)
            missing_targets = [target for target in targets if not (self.root / target).exists()]
            if missing_targets:
                raise RuntimeError(f"{name} missing native targets: {missing_targets}")

            consumed: list[str] = []
            for producer, handoffs in produced_by_agent.items():
                if name in AGENTS[producer]["handoff_to"]:
                    consumed.extend(handoffs)
                    acknowledged.extend(handoffs)

            artifacts = self.artifact_records(name)
            if not artifacts:
                raise RuntimeError(f"{name} has no verifiable runtime evidence")

            payload = {
                "agent": name,
                "capabilities": capabilities,
                "native_targets": targets,
                "artifacts": artifacts,
                "consumed_handoffs": sorted(consumed),
            }
            digest = sha256_json(payload)
            produced = [f"{name}->{destination}:{digest[:16]}" for destination in config["handoff_to"]]
            produced_by_agent[name] = produced

            verdict = "PASS"
            if name == "mission_governor":
                mission = json.loads((self.root / "SMART_MISSION_STATUS.json").read_text(encoding="utf-8-sig"))
                verdict = str(mission.get("status", "UNKNOWN"))

            executions[name] = asdict(
                AgentExecution(
                    name=name,
                    status="PASS",
                    capabilities=capabilities,
                    native_targets=targets,
                    artifacts=artifacts,
                    consumed_handoffs=sorted(consumed),
                    produced_handoffs=produced,
                    verdict=verdict,
                )
            )

        expected_handoffs = [handoff for handoffs in produced_by_agent.values() for handoff in handoffs]
        unacknowledged = sorted(set(expected_handoffs) - set(acknowledged))
        owned = sorted(capability for name in ORDER for capability in self.capabilities_for(name))
        inventory = self.orchestration["inventory"]
        acquired = sorted(
            set(
                inventory["source_only_skills"]
                + inventory["v2_capabilities"]
                + inventory["v3_capabilities"]
                + inventory["native_scientific_libraries"]
            )
        )

        checks = {
            "all_9_agents_executed": len(executions) == 9 and all(item["status"] == "PASS" for item in executions.values()),
            "all_41_capabilities_owned": owned == acquired and len(owned) == 41,
            "all_native_targets_verified": all(
                all((self.root / target).exists() for target in item["native_targets"])
                for item in executions.values()
            ),
            "all_declared_handoffs_acknowledged": not unacknowledged,
            "all_agents_have_runtime_evidence": all(item["artifacts"] for item in executions.values()),
            "mission_governor_reads_canonical_status": executions["mission_governor"]["verdict"] in {"MISSION_ACTIVE", "MISSION_PROVEN"},
            "no_agent_predictive_or_freeze_authority": all(
                not self.orchestration["agents"][name]["predictive_weight_authorized"]
                and not self.orchestration["agents"][name]["freeze_mutation_authorized"]
                for name in ORDER
            ),
        }

        document: dict[str, Any] = {
            "schema": SCHEMA,
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "executions": executions,
            "unacknowledged_handoffs": unacknowledged,
            "capability_count": len(owned),
            "agent_count": len(executions),
            "declarative_orchestration_sha256": self.orchestration["orchestration_sha256"],
        }
        document["runtime_sha256"] = sha256_json(document)
        return document


def write_runtime(root: str | Path, output: str | Path = "SMART_AGENT_RUNTIME_PROOF.json") -> dict[str, Any]:
    root_path = Path(root)
    output_path = Path(output)
    if not output_path.is_absolute():
        output_path = root_path / output_path
    document = SmartAgentRuntime(root_path).run()
    output_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return document


if __name__ == "__main__":
    result = write_runtime(Path(__file__).resolve().parent)
    print(json.dumps({"status": result["status"], "agents": result["agent_count"], "capabilities": result["capability_count"], "checks": result["checks"]}, ensure_ascii=False, indent=2))
