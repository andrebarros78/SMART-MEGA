from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from smart_agent_runtime import sha256_json


SCHEMA = "SMART_AGENT_SKILL_CONSUMER_BINDING_V1"


def verify_consumer_gate(gate: dict[str, Any], proof_file: str | Path, *, phase: str) -> dict[str, Any]:
    """Require actual deterministic role/skill executions before a card can be accepted.

    This is an evidence consumer. It never writes a card, changes a weight, or
    promotes external skills/LLMs to predictive authority.
    """
    path = Path(proof_file)
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("orchestration proof missing or unsafe")
    raw = path.read_bytes()
    stored = json.loads(raw)
    if not isinstance(gate, dict) or stored != gate:
        raise RuntimeError("orchestration proof file/returned payload mismatch")
    gate_hash = stored.get("sha256")
    if not isinstance(gate_hash, str) or gate_hash != sha256_json(
        {k: v for k, v in stored.items() if k != "sha256"}
    ):
        raise RuntimeError("orchestration proof self-hash mismatch")
    if (stored.get("schema") != "SMART_TOTAL_INTEGRATION_GATE_V3"
            or stored.get("status") != "PASS"
            or stored.get("phase") != phase
            or stored.get("health") != "HEALTHY"):
        raise RuntimeError("orchestration gate status or phase mismatch")

    gates = stored.get("gates")
    required = {
        "G1_ROLE_EXECUTORS", "G2_CAPABILITY_BINDINGS", "G3_FILES",
        "G4_RUNTIME", "G5_INTEGRATION", "G6_FUNCTIONAL_PATH",
        "G7_STATE_SAFETY", "G8_SECURITY_STATE",
        "G9_SEMANTIC_TRUTH", "G10_SKILL_ADAPTER_CONSUMPTION",
        "G11_SDK_LLM_SELECTIVE",
    }
    if (not isinstance(gates, dict) or not required.issubset(gates)
            or not all(isinstance(group, dict) and group and all(v is True for v in group.values())
                       for group in gates.values())):
        raise RuntimeError("required agent/skill consumer gate failed")

    agents = stored.get("agent_inventory")
    skills = stored.get("skill_inventory")
    invocations = stored.get("native_invocations")
    if (not isinstance(agents, list) or len(agents) != 9
            or not isinstance(skills, list) or len(skills) != 41
            or not isinstance(invocations, list) or len(invocations) != 37):
        raise RuntimeError("incomplete agent/skill consumer inventory")
    by_agent = {a.get("name"): a for a in agents if isinstance(a, dict)}
    if len(by_agent) != 9 or any(
        agent.get("probe_result", {}).get("pass") is not True
        or not agent.get("probe_id")
        or agent.get("autonomous_ai_agent") is not False
        or agent.get("llm_model") is not False
        for agent in by_agent.values()
    ):
        raise RuntimeError("agent execution or non-LLM contract invalid")
    by_invocation = {v.get("capability"): v for v in invocations if isinstance(v, dict)}
    if len(by_invocation) != 37:
        raise RuntimeError("duplicate or missing native skill invocation")
    registry_sha = stored.get("skill_adapter_registry_sha256")
    if not isinstance(registry_sha, str) or len(registry_sha) != 64:
        raise RuntimeError("skill registry proof missing")

    pertinent = 0
    quarantined = 0
    names = set()
    for row in skills:
        if not isinstance(row, dict) or not isinstance(row.get("capability"), str):
            raise RuntimeError("invalid skill capability record")
        name = row["capability"]
        if name in names:
            raise RuntimeError("duplicate capability in consumer")
        names.add(name)
        if row.get("direct_named_skill_execution") is not False or row.get("external_skill_source_executed") is not False:
            raise RuntimeError("external skill authority was improperly claimed")
        if row.get("pertinent") is True:
            pertinent += 1
            invoke = by_invocation.get(name)
            if (row.get("callable") is not True or row.get("status") != "PASS"
                    or row.get("probe_pass") is not True
                    or not row.get("executed_functions")
                    or not row.get("runtime_evidence")
                    or not isinstance(invoke, dict)
                    or row.get("alias_invocation") != invoke
                    or invoke.get("status") != "PASS"
                    or invoke.get("agent_owner") != row.get("agent_owner")
                    or invoke.get("probe_id") != by_agent.get(row.get("agent_owner"), {}).get("probe_id")
                    or invoke.get("adapter_state") != "NATIVE_ADAPTER"
                    or invoke.get("adapter_registry_sha256") != registry_sha
                    or invoke.get("predictive_weight_authorized") is not False
                    or invoke.get("freeze_mutation_authorized") is not False
                    or invoke.get("external_source_executed") is not False
                    or invoke.get("direct_named_skill_execution") is not False
                    or invoke.get("invocation_sha256") != sha256_json(
                        {k: v for k, v in invoke.items() if k != "invocation_sha256"}
                    )):
                raise RuntimeError(f"native skill was not consumed: {name}")
        else:
            quarantined += 1
            if row.get("callable") is not False or row.get("alias_invocation") is not None:
                raise RuntimeError(f"quarantined skill gained invocation: {name}")
    if pertinent != 37 or quarantined != 4 or set(by_invocation) != {
        s["capability"] for s in skills if s["pertinent"] is True
    }:
        raise RuntimeError("native skill consumption count mismatch")

    handoffs = stored.get("operational_handoff_ledger")
    if (not isinstance(handoffs, dict)
            or handoffs.get("status") != "PASS"
            or not isinstance(handoffs.get("produced_count"), int)
            or handoffs["produced_count"] < 1
            or handoffs.get("consumed_count") != handoffs["produced_count"]
            or not isinstance(handoffs.get("checks"), dict)
            or not all(v is True for v in handoffs["checks"].values())):
        raise RuntimeError("agent handoffs were not fully consumed")
    sdk = stored.get("sdk_llm_selection")
    if (not isinstance(sdk, dict) or sdk.get("provider") is not None
            or sdk.get("predictive_weight_authorized") is not False
            or sdk.get("freeze_mutation_authorized") is not False
            or sdk.get("external_network_calls") != 0):
        raise RuntimeError("unapproved model/provider or material authority in consumer")

    result = {
        "schema": SCHEMA,
        "status": "PASS",
        "phase": phase,
        "gate_schema": stored["schema"],
        "gate_sha256": gate_hash,
        "gate_file_sha256": hashlib.sha256(raw).hexdigest(),
        "agent_runtime_sha256": stored.get("agent_runtime_sha256"),
        "skill_runtime_sha256": stored.get("skill_runtime_sha256"),
        "skill_adapter_registry_sha256": registry_sha,
        "agents_executed": 9,
        "skills_native_invoked": pertinent,
        "skills_quarantined": quarantined,
        "handoffs_consumed": handoffs["consumed_count"],
        "llm_provider": None,
        "external_skill_code_executed": False,
        "prediction_or_weight_influence": False,
    }
    result["sha256"] = sha256_json(result)
    return result
from smart_agent_runtime import ORDER


EXECUTION_CONTRACT_SCHEMA = "SMART_AGENT_SKILL_EXECUTION_CONTRACT_V1"
EXPECTED_EXECUTION_CONTRACT_SHA256 = "8b789a0b1600aff882b0d40e34232623b1f5aaba7dfca94416fe6b5480ff8cbf"
CONSUMER_RECEIPT_SCHEMA = "SMART_AGENT_SKILL_EXECUTION_RECEIPT_V1"


def bind_consumer_execution(
    gate: dict[str, Any],
    proof_file: str | Path,
    *,
    contract_file: str | Path,
    epoch_dir: str | Path,
    phase: str,
    epoch_id: str,
    target_contest: int,
    cutoff_contest: int,
    data_sha256: str,
) -> dict[str, Any]:
    """Bind validated native executions to one authorized cycle and its consumer.

    Fail closed on stale proofs or schema/registry mismatches. Never grants
    model, scoring, weight, generation or freeze authority.
    """
    if phase not in ("PRE_FREEZE", "POST_FREEZE"):
        raise RuntimeError("invalid consumer execution phase")
    if (
        not isinstance(epoch_id, str) or not epoch_id.strip()
        or isinstance(target_contest, bool) or not isinstance(target_contest, int)
        or isinstance(cutoff_contest, bool) or not isinstance(cutoff_contest, int)
        or target_contest != cutoff_contest + 1
        or not isinstance(data_sha256, str) or len(data_sha256) != 64
        or any(char not in "0123456789abcdef" for char in data_sha256)
    ):
        raise RuntimeError("invalid consumer cycle identity")

    contract_path = Path(contract_file)
    if not contract_path.is_file() or contract_path.is_symlink():
        raise RuntimeError("execution contract not found or unsafe")
    expected_name = f"{phase}_TOTAL_INTEGRATION.json"
    proof_path = Path(proof_file)
    if (
        proof_path.is_symlink() or proof_path.name != expected_name
        or proof_path.resolve().parent != Path(epoch_dir).resolve()
    ):
        raise RuntimeError("orchestration proof belongs to another epoch or phase")
    raw_contract = contract_path.read_bytes()
    try:
        contract = json.loads(raw_contract)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("execution contract invalid JSON") from exc
    if not isinstance(contract, dict):
        raise RuntimeError("execution contract must be an object")
    observed = contract.get("sha256")
    if (
        not isinstance(observed, str)
        or observed != sha256_json({k: v for k, v in contract.items() if k != "sha256"})
        or contract.get("schema") != EXECUTION_CONTRACT_SCHEMA
        or observed != EXPECTED_EXECUTION_CONTRACT_SHA256
        or contract.get("status") != "ACTIVE_NON_PREDICTIVE"
        or contract.get("system", {}).get("phases") != ["PRE_FREEZE", "POST_FREEZE"]
        or contract.get("agents", {}).get("required_order") != list(ORDER)
        or contract.get("agents", {}).get("count") != 9
        or contract.get("skills", {}).get("registered_count") != 41
        or contract.get("skills", {}).get("native_probe_alias_invocations") != 37
        or contract.get("skills", {}).get("quarantined_noncallable") != 4
        or contract.get("consumer", {}).get("fail_closed") is not True
        or contract.get("consumer", {}).get("phase_proofs") != [
            "PRE_FREEZE_TOTAL_INTEGRATION.json", "POST_FREEZE_TOTAL_INTEGRATION.json"
        ]
        or contract.get("llm", {}).get("provider") is not None
        or contract.get("llm", {}).get("required") is not False
        or contract.get("llm", {}).get("external_network_calls") != 0
        or any(value is not False for key, value in contract.get("authority", {}).items()
               if key != "card_optimizer_unchanged")
        or contract.get("authority", {}).get("card_optimizer_unchanged") is not True
    ):
        raise RuntimeError("execution contract not authorized or hash mismatch")
    for role in ("agents", "skills", "consumer"):
        if role == "agents" and contract["agents"].get("allow_predictive_weight_mutation") is not False:
            raise RuntimeError("agent material authority forbidden")
        if role == "skills" and contract["skills"].get("external_skill_source_execution") is not False:
            raise RuntimeError("external skill execution forbidden")
        if role == "consumer" and contract["consumer"].get("required_gate_status") != "PASS":
            raise RuntimeError("consumer cannot accept failed gate")

    verified = verify_consumer_gate(gate, proof_path, phase=phase)
    agents = gate.get("agent_inventory", [])
    if [a.get("name") for a in agents] != list(ORDER):
        raise RuntimeError("agent execution order differs from contract")
    if gate.get("gates", {}).get("G5_INTEGRATION", {}).get("all_operational_handoffs_consumed_exactly_once") is not True:
        raise RuntimeError("handoff consumption is not exactly once")
    if gate.get("skill_adapter_registry_sha256") != verified["skill_adapter_registry_sha256"]:
        raise RuntimeError("skill registry changed during consumer validation")

    result = {
        "schema": CONSUMER_RECEIPT_SCHEMA,
        "status": "PASS",
        "phase": phase,
        "epoch_id": epoch_id,
        "target_contest": target_contest,
        "cutoff_contest": cutoff_contest,
        "data_sha256": data_sha256,
        "contract_schema": EXECUTION_CONTRACT_SCHEMA,
        "contract_self_sha256": observed,
        "contract_file_sha256": hashlib.sha256(raw_contract).hexdigest(),
        "gate_file": proof_path.name,
        "consumer": verified,
        "agents_executed": verified["agents_executed"],
        "skills_native_invoked": verified["skills_native_invoked"],
        "skills_quarantined": verified["skills_quarantined"],
        "handoffs_consumed": verified["handoffs_consumed"],
        "skill_adapter_registry_sha256": verified["skill_adapter_registry_sha256"],
        "llm_provider": None,
        "prediction_or_weight_influence": False,
        "freeze_mutation_authorized": False,
    }
    result["sha256"] = sha256_json(result)
    return result
