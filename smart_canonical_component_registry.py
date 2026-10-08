from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from smart_component_reachability import build_registry as build_reachability_registry

SCHEMA = "SMART_CANONICAL_COMPONENT_REGISTRY_V1"
ALLOWED_STATES = {
    "ACTIVE",
    "SHADOW",
    "DIAGNOSTIC",
    "VALIDATION_ONLY",
    "QUARANTINED",
    "DEPRECATED",
    "ARCHIVED",
}

STATE_BY_ROLE = {
    "PRODUCTION": "ACTIVE",
    "SHADOW": "SHADOW",
    "DIAGNOSTIC": "DIAGNOSTIC",
    "VALIDATION": "VALIDATION_ONLY",
    "TEST": "DIAGNOSTIC",
    "ARCHIVE": "ARCHIVED",
    "QUARANTINE": "QUARANTINED",
}

DEPRECATED_FILES = {
    "smart_3054_terminal_executor.py",
}

AUTHORITY_OVERRIDES: dict[str, dict[str, str]] = {
    "smart_signal_agent.py": {
        "decision_effect": "DIRECT_SIGNAL_SCORING_AND_RANKING",
        "predictive_authority": "DIRECT_PREDICTIVE_SCORING",
        "weight_authority": "DIRECT_DYNAMIC_WEIGHT_COMPUTATION",
        "freeze_authority": "NONE",
        "evidence_gate": "CAUSAL_BACKTEST_AND_PRE_FREEZE_RUNTIME",
    },
    "smart_ai_fine_tuning.py": {
        "decision_effect": "BOUNDED_HYPERPARAMETER_SELECTION",
        "predictive_authority": "INDIRECT_BOUNDED_HYPERPARAMETER_EFFECT",
        "weight_authority": "INDIRECT_BOUNDED_HYPERPARAMETER_GOVERNANCE",
        "freeze_authority": "NONE",
        "evidence_gate": "F04_CAUSAL_PARTITION_AND_NON_REGRESSION_GATE",
    },
    "smart_fine_tuning_lifecycle.py": {
        "decision_effect": "PRE_FREEZE_HYPERPARAMETER_AUTHORITY_BINDING",
        "predictive_authority": "INDIRECT_BOUNDED_HYPERPARAMETER_EFFECT",
        "weight_authority": "INDIRECT_BOUNDED_HYPERPARAMETER_GOVERNANCE",
        "freeze_authority": "NONE",
        "evidence_gate": "F04_EPOCH_TARGET_CUTOFF_DATA_HASH_BINDING",
    },
    "smart_champion_challenger.py": {
        "decision_effect": "PREDICTION_PACKAGE_AND_PRE_RESULT_FREEZE",
        "predictive_authority": "DIRECT_CHAMPION_CHALLENGER_SELECTION",
        "weight_authority": "CONSUMES_SIGNAL_WEIGHT_AUTHORITY",
        "freeze_authority": "PRE_RESULT_FREEZE_WRITER",
        "evidence_gate": "TEMPORAL_GUARD_CAUSAL_CUTOFF_AND_FREEZE_LEDGER",
    },
    "smart_portfolio_pipeline.py": {
        "decision_effect": "FINAL_SINGLE_CARD_SELECTION_FROM_FROZEN_SCORES",
        "predictive_authority": "POST_SCORING_CARD_SELECTION",
        "weight_authority": "NONE",
        "freeze_authority": "NONE",
        "evidence_gate": "FROZEN_SCORE_ONLY_RESULT_UNUSED",
    },
    "smart_primary_card_selector.py": {
        "decision_effect": "FINAL_SINGLE_CARD_COMBINATORIAL_SELECTOR",
        "predictive_authority": "POST_SCORING_CARD_SELECTION",
        "weight_authority": "NONE",
        "freeze_authority": "NONE",
        "evidence_gate": "PURE_FROZEN_SCORE_SELECTOR_RESULT_UNUSED",
    },
    "smart_full_process_pipeline.py": {
        "decision_effect": "OPERATIONAL_PRE_FREEZE_ORCHESTRATION",
        "predictive_authority": "ORCHESTRATION_ONLY",
        "weight_authority": "NONE",
        "freeze_authority": "ORCHESTRATES_AUTHORIZED_FREEZE",
        "evidence_gate": "FULL_PROCESS_PRE_AND_POST_INTEGRATION_GATES",
    },
}

DEFAULT_AUTHORITY = {
    "decision_effect": "NONE_ESTABLISHED",
    "predictive_authority": "NONE",
    "weight_authority": "NONE",
    "freeze_authority": "NONE",
    "evidence_gate": "STATIC_REACHABILITY_AND_STATE_CLASSIFICATION_ONLY",
}


def _sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _state(component: dict[str, Any]) -> str:
    source = str(component["source_file"])
    if source in DEPRECATED_FILES:
        return "DEPRECATED"
    role = str(component["role"])
    if role not in STATE_BY_ROLE:
        raise ValueError(f"canonical registry cannot classify reachability role: {role}")
    return STATE_BY_ROLE[role]


def _execution_mode(component: dict[str, Any], state: str) -> str:
    if state == "ACTIVE":
        return "CANONICAL_STATIC_REACHABLE"
    if state == "SHADOW":
        return "SHADOW_NON_AUTHORITATIVE"
    if state == "VALIDATION_ONLY":
        return "VALIDATION_ONLY"
    if state == "QUARANTINED":
        return "SOURCE_ONLY_QUARANTINE"
    if state == "ARCHIVED":
        return "ARCHIVED_NON_RUNTIME"
    if state == "DEPRECATED":
        return "DEPRECATED_COMPATIBILITY_ONLY"
    return "DIAGNOSTIC_NON_AUTHORITATIVE"


def build_registry(root: str | Path = ".") -> dict[str, Any]:
    root = Path(root).resolve()
    reach = build_reachability_registry(root)
    if reach["gate"]["status"] != "PASS":
        raise RuntimeError("canonical component registry requires passing reachability registry")

    components = []
    ids = set()
    errors = []
    for component in reach["components"]:
        component_id = str(component["component_id"])
        source = str(component["source_file"])
        if component_id in ids:
            errors.append(f"duplicate component_id: {component_id}")
        ids.add(component_id)

        state = _state(component)
        authority = dict(DEFAULT_AUTHORITY)
        authority.update(AUTHORITY_OVERRIDES.get(source, {}))
        if state != "ACTIVE" and any(
            authority[key] != DEFAULT_AUTHORITY[key]
            for key in ("predictive_authority", "weight_authority", "freeze_authority")
        ):
            errors.append(f"non-ACTIVE component has material authority: {source}")

        producers = list(component.get("producers") or [])
        consumers = list(component.get("consumers") or [])
        entrypoints = list(component.get("entrypoints") or [])
        implementation_hash = str(component.get("sha256") or "")
        if len(implementation_hash) != 64:
            errors.append(f"missing implementation hash: {source}")

        row = {
            "component_id": component_id,
            "type": "PYTHON_COMPONENT",
            "implementation": source,
            "implementation_sha256": implementation_hash,
            "role": str(component["role"]),
            "state": state,
            "producers": producers,
            "consumers": consumers,
            "entrypoints": entrypoints,
            "execution_mode": _execution_mode(component, state),
            "decision_effect": authority["decision_effect"],
            "predictive_authority": authority["predictive_authority"],
            "weight_authority": authority["weight_authority"],
            "freeze_authority": authority["freeze_authority"],
            "external_dependency": "NOT_DECLARED_BY_F05_STATIC_REGISTRY",
            "evidence_gate": authority["evidence_gate"],
            "retirement_status": (
                "RETIRED_FROM_CANONICAL_RUNTIME"
                if state in {"ARCHIVED", "DEPRECATED"}
                else "NOT_RETIRED"
            ),
            "reachable": bool(component.get("reachable")),
            "production_reachable": bool(component.get("production_reachable")),
        }
        if state == "ACTIVE" and not row["production_reachable"]:
            errors.append(f"ACTIVE component is not production reachable: {source}")
        if state != "ACTIVE" and row["production_reachable"]:
            errors.append(f"non-ACTIVE component is production reachable: {source}")
        components.append(row)

    active_sources = {c["implementation"] for c in components if c["state"] == "ACTIVE"}
    for source in AUTHORITY_OVERRIDES:
        if source not in active_sources:
            errors.append(f"authority allowlist component is not ACTIVE: {source}")

    authority_components = [
        c for c in components
        if c["predictive_authority"] != "NONE"
        or c["weight_authority"] != "NONE"
        or c["freeze_authority"] != "NONE"
    ]
    summary = {
        "component_count": len(components),
        "active": sum(c["state"] == "ACTIVE" for c in components),
        "shadow": sum(c["state"] == "SHADOW" for c in components),
        "diagnostic": sum(c["state"] == "DIAGNOSTIC" for c in components),
        "validation_only": sum(c["state"] == "VALIDATION_ONLY" for c in components),
        "quarantined": sum(c["state"] == "QUARANTINED" for c in components),
        "deprecated": sum(c["state"] == "DEPRECATED" for c in components),
        "archived": sum(c["state"] == "ARCHIVED" for c in components),
        "material_authority_components": len(authority_components),
    }
    payload = {
        "schema": SCHEMA,
        "source_reachability_schema": reach["schema"],
        "source_reachability_inventory_sha256": reach["inventory_sha256"],
        "state_model": sorted(ALLOWED_STATES),
        "authority_policy": {
            "default": DEFAULT_AUTHORITY,
            "explicit_allowlist_required": True,
            "non_active_material_authority_forbidden": True,
            "static_registry_does_not_prove_predictive_advantage": True,
        },
        "summary": summary,
        "gate": {
            "status": "PASS" if not errors else "FAIL",
            "errors": errors,
        },
        "components": components,
    }
    payload["registry_sha256"] = _sha256_json(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/check SMART-MEGA canonical component registry.")
    parser.add_argument("--write", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    registry = build_registry(root)
    payload = json.dumps(registry, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        target = args.write if args.write.is_absolute() else root / args.write
        target.write_text(payload, encoding="utf-8")
    if args.check:
        target = args.check if args.check.is_absolute() else root / args.check
        if not target.is_file() or target.read_text(encoding="utf-8") != payload:
            raise SystemExit("canonical component registry is stale or missing")
    if registry["gate"]["status"] != "PASS":
        print(json.dumps(registry["gate"], ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({"schema": registry["schema"], "summary": registry["summary"], "gate": "PASS"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
