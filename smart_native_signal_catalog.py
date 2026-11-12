"""Single authoritative inventory of skill roles and actual native producer bindings."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from smart_agent_skill_orchestration import AGENTS
from smart_skill_adapter_registry import build_registry
from smart_native_signal_research import SIGNAL_SCHEMA, canonical_hash, hash_document, NATIVE_ALIAS_TO_PRODUCER

ROLE_BY_LANE = {
    "data_quality_and_contracts": "QUALITY_GATE",
    "experiment_design_and_falsification": "EVALUATION_TOOL",
    "time_series_regime_and_structure": "EVALUATION_TOOL",
    "combinatorial_and_formal": "OPTIMIZER",
    "testing_and_robustness": "EVALUATION_TOOL",
    "learning_calibration_and_drift": "WEIGHT_CALIBRATOR",
    "multi_expert_research": "RESEARCH_REFERENCE",
    "retained_quarantine_no_current_lane": "QUARANTINED",
}
# These are methodology aliases to a *native Python function*, not external library invocations.
ALIAS_TO_PRODUCER = NATIVE_ALIAS_TO_PRODUCER


def classify_capabilities(root: str | Path) -> dict[str, Any]:
    registry = build_registry(root)
    if registry["gate"]["status"] != "PASS":
        raise ValueError("source skill registry fails its own gate")
    rows = []
    for entry in registry["adapters"]:
        lane = entry["lane"]
        role = ROLE_BY_LANE[lane]
        producer = ALIAS_TO_PRODUCER.get(entry["capability_id"])
        if producer is not None and lane != "time_series_regime_and_structure":
            raise ValueError("source methodology alias mapped outside native Frontier lane")
        if entry["state"] == "REFERENCE_ONLY" and role != "QUARANTINED":
            raise ValueError("non-pertinent reference cannot gain an active role")
        if entry["state"] == "NATIVE_ADAPTER" and role == "QUARANTINED":
            raise ValueError("quarantined capability incorrectly active")
        rows.append({
            "capability_id": entry["capability_id"],
            "lane": lane,
            "agent_owner": entry["agent_owner"],
            "role": "SIGNAL_PRODUCER" if producer else role,
            "producer_id": producer,
            "actual_callable": (
                "smart_frontier_signal_lab.FrontierState.predict"
                if producer else None
            ),
            "implementation_kind": (
                "NATIVE_FRONTIER_NOT_NAMED_EXTERNAL_SKILL"
                if producer else "NATIVE_VALIDATION_OR_REFERENCE"
            ),
            "output_schema": SIGNAL_SCHEMA if producer else None,
            "consumer_id": "smart_native_signal_research.build_research_challenger" if producer else None,
            "evidence_hash": entry["binding_sha256"],
            "direct_external_code_executed": False,
            "production_authority": False,
        })
    roles = {role: sum(row["role"] == role for row in rows)
             for role in set(ROLE_BY_LANE.values()) | {"SIGNAL_PRODUCER"}}
    active = [entry for entry in registry["adapters"] if entry["state"] == "NATIVE_ADAPTER"]
    if len(rows) != 41 or len(active) != 37 or len(AGENTS) != 9:
        raise ValueError("41/37/9 expected count mismatch")
    if sum(row["role"] == "QUARANTINED" for row in rows) != 4:
        raise ValueError("quarantine count mismatch")
    if len({row["producer_id"] for row in rows if row["producer_id"]}) != 5:
        raise ValueError("five native producer bindings required")
    return hash_document({
        "schema": "SMART_NATIVE_CAPABILITY_CLASSIFICATION_V1",
        "source_adapter_registry_sha256": registry["registry_sha256"],
        "capabilities": rows,
        "counts": {
            "registered": 41,
            "probe_adapters": 37,
            "quarantined": 4,
            "agent_roles": 9,
            "functional_probe_groups": 7,
            "native_producer_bindings": 5,
        },
        "role_counts": roles,
        "skill_alias_is_not_independent_model": True,
        "external_skill_source_executed": False,
        "research_only": True,
    })
