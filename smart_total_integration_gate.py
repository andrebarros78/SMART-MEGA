from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from smart_agent_runtime import ORDER, sha256_json
from smart_agent_skill_functional_gate import evaluate as evaluate_functional

SCHEMA = "SMART_TOTAL_INTEGRATION_GATE_V3"


def _file_audit(root: Path, matrix: list[dict[str, Any]]) -> dict[str, Any]:
    required = {
        "SMART_MISSION_STATUS.json",
        "smart_agent_runtime.py",
        "smart_skill_runtime.py",
        "smart_agent_skill_functional_gate.py",
    }
    required.update(target for row in matrix for target in row["native_targets"])
    missing = sorted(path for path in required if not (root / path).exists())
    empty = sorted(
        path for path in required
        if (root / path).is_file() and (root / path).stat().st_size == 0
    )
    return {"required": len(required), "missing": missing, "empty": empty,
            "pass": not (missing or empty)}


def evaluate(root: str | Path, phase: str = "AUTO") -> dict[str, Any]:
    """Bind the total gate to executed native role and skill proofs.

    External skill code remains quarantined. Restart, parallel stress and
    predictive advantage are outside this gate and are not inferred from it.
    """
    root = Path(root).resolve()
    functional = evaluate_functional(root, phase=phase)
    runtime = functional["runtime_proof"]
    skills = functional["skill_runtime_proof"]
    matrix = functional["matrix"]
    executions = runtime["executions"]
    operational_handoffs = runtime["operational_handoff_ledger"]
    calls = [row for row in matrix if row["pertinent"]]
    quarantine = [row for row in matrix if not row["pertinent"]]
    files = _file_audit(root, matrix)
    agents = [
        {
            "name": name,
            "runtime": "DETERMINISTIC_ROLE_EXECUTOR",
            "autonomous_ai_agent": False,
            "llm_model": False,
            "prompt_driven": False,
            "probe_id": executions[name]["probe_id"],
            "probe_result": executions[name]["probe_result"],
            "consumed_handoffs": executions[name]["consumed_handoffs"],
            "produced_handoffs": executions[name]["produced_handoffs"],
        }
        for name in ORDER if name in executions
    ]
    gates = {
        "G1_ROLE_EXECUTORS": {
            "nine_executed": len(agents) == 9 and runtime["agent_count"] == 9,
            "all_native_probes_pass": all(
                agent["probe_result"].get("pass") is True for agent in agents
            ),
            "handoffs_acknowledged": runtime["unacknowledged_handoffs"] == [],
        },
        "G2_CAPABILITY_BINDINGS": {
            "forty_one_registered": len(matrix) == 41 and skills["counts"]["registered"] == 41,
            "thirty_seven_native_invocations": len(calls) == 37 and all(
                row["alias_invocation"] and row["alias_invocation"]["status"] == "PASS"
                for row in calls
            ),
            "four_quarantined": len(quarantine) == 4 and all(
                not row["callable"] and row["alias_invocation"] is None
                for row in quarantine
            ),
        },
        "G3_FILES": {
            "native_targets_present": not files["missing"],
            "native_targets_nonempty": not files["empty"],
        },
        "G4_RUNTIME": {
            "agent_runtime_pass": runtime["status"] == "PASS" and all(runtime["checks"].values()),
            "skill_runtime_pass": skills["status"] == "PASS" and all(skills["checks"].values()),
            "functional_gate_pass": functional["status"] == "PASS" and all(functional["checks"].values()),
        },
        "G5_INTEGRATION": {
            "phase_consistent": functional["phase"] == runtime["phase"] == skills["phase"],
            "every_alias_bound_to_executed_owner": all(
                row["probe_id"] == executions[row["agent_owner"]]["probe_id"]
                and row["probe_pass"] is True for row in calls
            ),
            "all_handoffs_consumed": runtime["unacknowledged_handoffs"] == [],
            "operational_handoff_ledger_pass": operational_handoffs["status"] == "PASS",
            "all_operational_handoffs_consumed_exactly_once": operational_handoffs["checks"]["all_consumed_exactly_once"],
        },
        "G6_FUNCTIONAL_PATH": {
            "each_pertinent_invoked": all(
                row["executed_functions"] and row["runtime_evidence"] for row in calls
            ),
            "nonpertinent_not_invoked": all(
                row["alias_invocation"] is None for row in quarantine
            ),
        },
        "G7_STATE_SAFETY": {
            "agent_probe_read_only": runtime["critical_hashes_before"] == runtime["critical_hashes_after"],
            "skill_probe_read_only": skills["critical_hashes_before"] == skills["critical_hashes_after"],
            "freeze_authority_reserved_for_operator": runtime["checks"]["no_agent_predictive_or_freeze_authority"],
        },
        "G8_SECURITY_STATE": {
            "external_sources_quarantined": all(not row["external_skill_source_executed"] for row in matrix),
            "canonical_state_unchanged": runtime["checks"]["critical_canonical_files_unchanged"]
            and skills["checks"]["canonical_state_unchanged"],
        },
        "G9_SEMANTIC_TRUTH": {
            "agents_not_misrepresented_as_llm": all(
                not agent["autonomous_ai_agent"] and not agent["llm_model"] for agent in agents
            ),
            "skills_not_misrepresented_as_direct_execution": all(
                not row["direct_named_skill_execution"] for row in matrix
            ),
            "external_sources_remain_quarantined": all(
                not row["external_skill_source_executed"] for row in matrix
            ),
        },
    }
    passed = all(value is True for group in gates.values() for value in group.values())
    document: dict[str, Any] = {
        "schema": SCHEMA,
        "phase": functional["phase"],
        "status": "PASS" if passed else "FAIL",
        "health": "HEALTHY" if passed else "UNHEALTHY",
        "service_model": "BATCH_EXECUTION_WITH_PERSISTENT_CANONICAL_ARTIFACTS",
        "gates": gates,
        "agent_inventory": agents,
        "operational_handoff_ledger": operational_handoffs,
        "skill_inventory": matrix,
        "file_audit": files,
        "native_invocations": [row["alias_invocation"] for row in calls],
        "agent_runtime_sha256": runtime["runtime_sha256"],
        "skill_runtime_sha256": skills["sha256"],
        "functional_integration_sha256": functional["sha256"],
        "restart": {"status": "NOT_EVALUATED"},
        "parallel_stress": {"status": "NOT_EVALUATED"},
        "scientific_mission_status": "MISSION_ACTIVE",
        "claim_boundary": "Executed deterministic native role probes plus schema/hash/route-validated operational evidence handoffs. Handoffs have evidence-gate effect only and no predictive-weight or freeze authority. No autonomous/LLM agent claim, third-party skill execution, process restart proof, parallel stress proof or predictive advantage claim.",
    }
    document["sha256"] = sha256_json(document)
    return document


def write(root: str | Path, out: str | Path = "SMART_TOTAL_INTEGRATION_PROOF.json",
          phase: str = "AUTO") -> dict[str, Any]:
    root = Path(root)
    output = Path(out)
    if not output.is_absolute():
        output = root / output
    document = evaluate(root, phase=phase)
    if document["status"] != "PASS":
        raise RuntimeError(f"total integration failed: {document['gates']}")
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return document


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["BUILD", "PRE_FREEZE", "POST_FREEZE"], default="POST_FREEZE")
    parser.add_argument("--output", default="SMART_TOTAL_INTEGRATION_PROOF.json")
    arguments = parser.parse_args()
    result = write(Path(__file__).resolve().parent, arguments.output, phase=arguments.phase)
    print(json.dumps({"status": result["status"], "phase": result["phase"], "gates": result["gates"]},
                     ensure_ascii=False, indent=2))
