from __future__ import annotations

import hashlib
import json
from typing import Any

HANDOFF_SCHEMA = "SMART_AGENT_HANDOFF_V1"
LEDGER_SCHEMA = "SMART_AGENT_OPERATIONAL_HANDOFF_LEDGER_V1"
DECISION_EFFECT = "EVIDENCE_GATE_INPUT_ONLY"


def _sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def create_handoff(
    *,
    producer: str,
    consumer: str,
    producer_sequence: int,
    probe_id: str,
    probe_result: dict[str, Any],
    evidence_artifacts: list[dict[str, str]],
    payload_sha256: str,
) -> dict[str, Any]:
    artifact_payload = {
        "producer": str(producer),
        "consumer": str(consumer),
        "probe_id": str(probe_id),
        "probe_result_sha256": _sha256_json(probe_result),
        "evidence_artifacts": list(evidence_artifacts),
        "source_payload_sha256": str(payload_sha256),
        "decision_effect": DECISION_EFFECT,
        "predictive_weight_authorized": False,
        "freeze_mutation_authorized": False,
    }
    artifact_sha = _sha256_json(artifact_payload)
    return {
        "schema": HANDOFF_SCHEMA,
        "handoff_id": f"{producer}->{consumer}:{artifact_sha[:16]}",
        "producer": str(producer),
        "consumer": str(consumer),
        "artifact": artifact_payload,
        "artifact_sha256": artifact_sha,
        "created_sequence": int(producer_sequence),
        "consumed": False,
        "consumption_result": None,
        "decision_effect": DECISION_EFFECT,
    }


def consume_handoff(
    handoff: dict[str, Any],
    *,
    consumer: str,
    consumer_sequence: int,
) -> dict[str, Any]:
    if handoff.get("schema") != HANDOFF_SCHEMA:
        raise ValueError("agent handoff schema invalid")
    if handoff.get("consumer") != consumer:
        raise ValueError("agent handoff consumer route mismatch")
    artifact = handoff.get("artifact")
    if not isinstance(artifact, dict):
        raise ValueError("agent handoff artifact missing")
    observed = handoff.get("artifact_sha256")
    if not isinstance(observed, str) or observed != _sha256_json(artifact):
        raise ValueError("agent handoff artifact hash mismatch")
    if artifact.get("producer") != handoff.get("producer") or artifact.get("consumer") != consumer:
        raise ValueError("agent handoff artifact route mismatch")
    if artifact.get("decision_effect") != DECISION_EFFECT:
        raise ValueError("agent handoff decision effect invalid")
    if artifact.get("predictive_weight_authorized") is not False or artifact.get("freeze_mutation_authorized") is not False:
        raise ValueError("agent handoff cannot carry predictive or freeze authority")
    if int(consumer_sequence) <= int(handoff.get("created_sequence", 0)):
        raise ValueError("agent handoff must be consumed after production")
    result = {
        "status": "CONSUMED",
        "validation": "SCHEMA_HASH_ROUTE_AUTHORITY_VALID",
        "consumer": str(consumer),
        "consumed_sequence": int(consumer_sequence),
        "artifact_sha256": observed,
        "decision_effect": DECISION_EFFECT,
    }
    return {
        **handoff,
        "consumed": True,
        "consumption_result": result,
    }


def build_operational_handoff_ledger(executions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    produced: dict[str, dict[str, Any]] = {}
    receipts: dict[str, list[dict[str, Any]]] = {}
    errors: list[str] = []

    for name, execution in executions.items():
        for handoff in execution.get("produced_handoffs", []):
            handoff_id = str(handoff.get("handoff_id") or "")
            if not handoff_id or handoff_id in produced:
                errors.append(f"invalid or duplicate produced handoff: {handoff_id}")
                continue
            produced[handoff_id] = handoff
        for receipt in execution.get("consumed_handoffs", []):
            handoff_id = str(receipt.get("handoff_id") or "")
            receipts.setdefault(handoff_id, []).append(receipt)

    records = []
    for handoff_id, original in sorted(produced.items()):
        rows = receipts.get(handoff_id, [])
        if len(rows) != 1:
            errors.append(f"handoff must be consumed exactly once: {handoff_id} count={len(rows)}")
            records.append({**original, "status": "UNCONSUMED" if not rows else "AMBIGUOUS_CONSUMPTION"})
            continue
        receipt = rows[0]
        if receipt.get("consumed") is not True:
            errors.append(f"handoff receipt not consumed: {handoff_id}")
        if receipt.get("artifact_sha256") != original.get("artifact_sha256"):
            errors.append(f"handoff receipt artifact mismatch: {handoff_id}")
        result = receipt.get("consumption_result")
        if not isinstance(result, dict) or result.get("status") != "CONSUMED":
            errors.append(f"handoff consumption result invalid: {handoff_id}")
        records.append({
            "schema": HANDOFF_SCHEMA,
            "handoff_id": handoff_id,
            "producer": original["producer"],
            "consumer": original["consumer"],
            "artifact": original["artifact"],
            "artifact_sha256": original["artifact_sha256"],
            "created_sequence": original["created_sequence"],
            "consumed": True,
            "consumption_result": result,
            "decision_effect": DECISION_EFFECT,
            "status": "CONSUMED",
        })

    orphan_receipts = sorted(set(receipts) - set(produced))
    if orphan_receipts:
        errors.extend(f"orphan handoff receipt: {handoff_id}" for handoff_id in orphan_receipts)

    checks = {
        "all_produced_have_artifact": all(isinstance(r.get("artifact"), dict) and len(str(r.get("artifact_sha256") or "")) == 64 for r in records),
        "all_consumed_exactly_once": len(records) == len(produced) and all(r.get("status") == "CONSUMED" for r in records),
        "no_orphan_receipts": not orphan_receipts,
        "no_predictive_or_freeze_authority": all(
            r["artifact"].get("predictive_weight_authorized") is False
            and r["artifact"].get("freeze_mutation_authorized") is False
            for r in records
        ),
        "decision_effect_evidence_only": all(r.get("decision_effect") == DECISION_EFFECT for r in records),
    }
    document = {
        "schema": LEDGER_SCHEMA,
        "status": "PASS" if not errors and all(checks.values()) else "FAIL",
        "execution_model": "DETERMINISTIC_ROLE_HANDOFF_CONSUMPTION",
        "autonomous_ai_agents": False,
        "llm_agents": False,
        "records": records,
        "checks": checks,
        "errors": errors,
        "produced_count": len(produced),
        "consumed_count": sum(1 for r in records if r.get("status") == "CONSUMED"),
    }
    document["sha256"] = _sha256_json(document)
    return document
