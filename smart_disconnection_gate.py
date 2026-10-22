from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from smart_component_reachability import build_registry as build_reachability
from smart_canonical_component_registry import build_registry as build_canonical
from smart_skill_adapter_registry import build_registry as build_skills

SCHEMA = "SMART_F10_DISCONNECTION_GATE_V1"

# Contractual edges observed in the existing canonical production route, not
# arbitrary imports inferred from the existence of a Python file.
REQUIRED_EDGES: dict[str, tuple[str, ...]] = {
    "smart_github_operator.py": ("smart_operator",),
    "smart_operator.py": ("smart_full_process_pipeline", "smart_terminal_executor"),
    "smart_full_process_pipeline.py": (
        "smart_fine_tuning_lifecycle",
        "smart_champion_challenger",
        "smart_total_integration_gate",
    ),
    "smart_fine_tuning_lifecycle.py": ("smart_ai_fine_tuning",),
    "smart_terminal_executor.py": ("smart_terminal_engine",),
    "smart_agent_runtime.py": ("smart_agent_handoff_runtime",),
    "smart_skill_runtime.py": ("smart_skill_adapter_registry", "smart_agent_runtime"),
    "smart_total_integration_gate.py": ("smart_agent_skill_functional_gate",),
}
RETIRED_RUNTIME_FILE = "smart_3054_terminal_executor.py"
PROHIBITED_PRODUCTION_EDGES = {
    "smart_terminal_executor.py": ("smart_3054_terminal_executor",),
    "smart_full_process_pipeline.py": ("smart_operator",),
}
MATERIAL_KEYS = ("predictive_authority", "weight_authority", "freeze_authority")
NON_EXECUTABLE_SKILL_STATES = {"REFERENCE_ONLY"}


def _hash_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def audit_disconnections(
    root: str | Path,
    *,
    reachability: dict[str, Any] | None = None,
    canonical: dict[str, Any] | None = None,
    skills: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check runtime *wiring* against separately generated static registries.

    Snapshot overrides permit negative mutation testing without editing any
    productive code, workflow, or persisted artifact.
    """
    root = Path(root).resolve()
    reach = build_reachability(root) if reachability is None else reachability
    components = build_canonical(root) if canonical is None else canonical
    adapters = build_skills(root) if skills is None else skills
    errors: list[str] = []
    checks: dict[str, bool] = {}
    by_path = {row["source_file"]: row for row in reach["components"]}
    canon_by_path = {row["implementation"]: row for row in components["components"]}
    adapter_rows = list(adapters["adapters"])

    def check(name: str, condition: bool, description: str) -> None:
        checks[name] = bool(condition)
        if not condition:
            errors.append(description)

    # Reconcile to the current main's explicit multi-entrypoint external
    # executor contract. These are *static roots*, not a dynamic run receipt.
    from smart_component_reachability import (
        EXTERNAL_EXECUTION_ENTRYPOINTS, EXTERNAL_EXECUTION_POLICY,
    )
    from smart_github_native_policy import POLICY_ID, PolicyViolation, verify
    expected_external = {
        path: ["EXTERNAL_EXECUTOR:" + EXTERNAL_EXECUTION_POLICY]
        for path in EXTERNAL_EXECUTION_ENTRYPOINTS
        if path in by_path
    }
    try:
        policy = verify(root)
    except (OSError, UnicodeError, PolicyViolation):
        policy = {}
    provenance = {
        "policy_id": POLICY_ID,
        "authority_kind": "GITHUB_CANONICAL_EXTERNAL_EXECUTOR_STATIC_CONTRACT",
        "runtime_executed": bool(
            reach.get("classification_policy", {}).get("runtime_execution_claimed")
        ),
        "github_actions_authorized": policy.get("github_actions_authorized"),
        "root_contract_valid": (
            reach.get("workflow_entrypoints") == expected_external
            and reach.get("entrypoint_authority") == EXTERNAL_EXECUTION_POLICY
            and "smart_github_operator.py" in expected_external
            and "smart_fast_result_ingest.py" in expected_external
            and by_path.get("smart_github_operator.py", {}).get("production_reachable") is True
            and by_path.get("smart_fast_result_ingest.py", {}).get("production_reachable") is True
            and policy.get("status") == "PASS"
            and policy.get("external_executors_authorized") is True
            and policy.get("github_actions_authorized") is False
            and reach.get("classification_policy", {}).get("runtime_execution_claimed") is False
        ),
    }
    check(
        "external_governed_entrypoint_bound",
        provenance["root_contract_valid"],
        "canonical externally governed entrypoints missing, unauthorized, or falsely claim execution",
    )

    check("source_registries_pass",
          reach["gate"]["status"] == components["gate"]["status"] == adapters["gate"]["status"] == "PASS",
          "upstream canonical/skill/reachability gate is not PASS")
    check("registry_component_identity",
          set(by_path) == set(canon_by_path) and len(by_path) == len(reach["components"])
          and len(canon_by_path) == len(components["components"]),
          "component disconnected or duplicated across registries")
    check("registry_source_inventory_bound",
          components.get("source_reachability_inventory_sha256") == reach["inventory_sha256"],
          "canonical registry is not bound to source reachability inventory")
    check("registry_self_hashes_valid",
          components.get("registry_sha256") == _hash_json({k: v for k, v in components.items() if k != "registry_sha256"})
          and adapters.get("registry_sha256") == _hash_json({k: v for k, v in adapters.items() if k != "registry_sha256"}),
          "registry data or authority modified without a valid self hash")
    check("active_labels_match_reachability",
          all(
              canon_by_path.get(path, {}).get("production_reachable") is row["production_reachable"]
              and canon_by_path.get(path, {}).get("state") == (
                  "ACTIVE" if row["production_reachable"] else canon_by_path[path]["state"]
              )
              and (canon_by_path[path]["state"] == "ACTIVE") == row["production_reachable"]
              for path, row in by_path.items() if path in canon_by_path
          ),
          "false ACTIVE label or mismatched runtime reachability")
    check("no_non_active_material_authority",
          all(
              row["state"] == "ACTIVE" or all(row[key] == "NONE" for key in MATERIAL_KEYS)
              for row in components["components"]
          ),
          "non-ACTIVE component was assigned predictive/weight/freeze authority")
    check("required_production_edges_connected",
          all(
              path in by_path and by_path[path]["production_reachable"] is True
              and all(target in by_path[path]["producers"] for target in edges)
              for path, edges in REQUIRED_EDGES.items()
          ),
          "canonical production edge missing, including fine-tuning, generic terminal, or agent SDK consumption")
    check("legacy_executor_disconnected",
          RETIRED_RUNTIME_FILE in by_path
          and by_path[RETIRED_RUNTIME_FILE]["production_reachable"] is False
          and canon_by_path.get(RETIRED_RUNTIME_FILE, {}).get("state") == "DEPRECATED"
          and reach["known_debt_observations"]["legacy_3054_terminal_executor_reachable"] is False,
          "historical 3054 terminal executor was reconnected to production")
    check("forbidden_reverse_edges_absent",
          all(
              path in by_path and not (set(by_path[path]["producers"]) & set(edges))
              for path, edges in PROHIBITED_PRODUCTION_EDGES.items()
          ),
          "known prohibited reverse or historical executor import returned")
    check("no_unproved_active_skills",
          adapters["summary"]["active_native"] == 0
          and all(row["state"] in {"NATIVE_ADAPTER", "REFERENCE_ONLY"} for row in adapter_rows)
          and all(row["direct_named_skill_execution"] is False
                  and row["external_source_code_executed"] is False
                  and row["predictive_weight_authorized"] is False
                  and row["freeze_mutation_authorized"] is False for row in adapter_rows),
          "skill alias was promoted to unproved ACTIVE_NATIVE or external source execution")
    check("capability_aliases_match_owners_and_permissions",
          len(adapter_rows) == 41
          and len({row["capability_id"] for row in adapter_rows}) == 41
          and sum(row["state"] == "NATIVE_ADAPTER" and row["callable"] is True for row in adapter_rows) == 37
          and sum(row["state"] == "REFERENCE_ONLY" and row["callable"] is False for row in adapter_rows) == 4
          and all(
              row["binding_sha256"] == _hash_json({k: v for k, v in row.items() if k != "binding_sha256"})
              and (row["state"] not in NON_EXECUTABLE_SKILL_STATES or row["callable"] is False)
              for row in adapter_rows
          ),
          "alias binding, ownership, callable permission, or capability count is inconsistent")

    doc = {
        "schema": SCHEMA,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "claim_boundary": "Proves static route integrity and fail-closed disconnection mutations. Dynamic execution is validated separately by F06/F07/F09 integration tests; static ACTIVE alone is not dynamic-execution evidence.",
        "checks": checks,
        "errors": sorted(errors),
        "external_entrypoint_provenance": provenance,
        "required_edges": {k: list(v) for k, v in REQUIRED_EDGES.items()},
        "prohibited_edges": {k: list(v) for k, v in PROHIBITED_PRODUCTION_EDGES.items()},
        "reachability_inventory_sha256": reach["inventory_sha256"],
        "canonical_registry_sha256": components["registry_sha256"],
        "skill_registry_sha256": adapters["registry_sha256"],
    }
    doc["sha256"] = _hash_json(doc)
    return doc


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed F10 disconnection gate")
    parser.add_argument("--write", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    result = audit_disconnections(root)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        path = args.write if args.write.is_absolute() else root / args.write
        path.write_text(encoded, encoding="utf-8")
    if args.check:
        path = args.check if args.check.is_absolute() else root / args.check
        if not path.is_file() or path.read_text(encoding="utf-8") != encoded:
            raise SystemExit("F10 disconnection gate evidence is stale or missing")
    print(json.dumps({"status": result["status"], "checks": result["checks"], "errors": result["errors"]},
                     ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
