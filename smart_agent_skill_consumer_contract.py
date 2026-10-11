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
