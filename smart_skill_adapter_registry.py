from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from smart_source_identity import sha256_source_file

from smart_agent_skill_orchestration import AGENTS, LANES

SCHEMA = "SMART_SKILL_ADAPTER_REGISTRY_V1"
STATES = (
    "REFERENCE_ONLY", "QUARANTINED_SOURCE", "NATIVE_ADAPTER",
    "ACTIVE_NATIVE", "REJECTED", "RETIRED",
)
MANIFEST_NAME = "SMART_EXTERNAL_SKILLS_QUARANTINE_MANIFEST.json"


def sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def sha256_file(path: Path) -> str:
    """Normalize Python source EOL only; preserve forensic evidence byte hashes."""
    return (sha256_source_file(path) if path.suffix == ".py"
            else hashlib.sha256(path.read_bytes()).hexdigest())


def build_registry(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    source_path = root / MANIFEST_NAME
    manifest = json.loads(source_path.read_text(encoding="utf-8-sig"))
    items = manifest.get("items")
    errors: list[str] = []
    if not isinstance(items, list):
        raise ValueError("external skill quarantine manifest items must be a list")
    if (
        manifest.get("acquired_items") != 21
        or manifest.get("external_code_auto_execute") is not False
        or manifest.get("source_payload_required_at_runtime") is not False
    ):
        errors.append("external source quarantine manifest policy violated")
    names = [item.get("name") for item in items if isinstance(item, dict)]
    if len(names) != 21 or len(set(names)) != 21:
        errors.append("external source manifest must contain 21 unique named sources")

    source_rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            errors.append("external source manifest item invalid")
            continue
        name = item.get("name")
        checksum = item.get("skill_md_sha256")
        if (
            not isinstance(name, str) or not name
            or item.get("status") != "ACQUIRED_VERIFIED"
            or item.get("execution_policy") != "SOURCE_ONLY_QUARANTINE"
            or not isinstance(checksum, str) or len(checksum) != 64
        ):
            errors.append(f"external skill source invalid: {name}")
        source_rows.append({
            "source_name": name,
            "state": "QUARANTINED_SOURCE",
            "source_repo": item.get("source_repo"),
            "source_path": item.get("source_path"),
            "source_branch": item.get("source_branch"),
            "skill_md_sha256": checksum,
            "runtime_source_code_executed": False,
            "runtime_payload_required": False,
            "promotion_authorized": False,
        })

    by_name = {row["source_name"]: row for row in source_rows}
    adapters: list[dict[str, Any]] = []
    seen: set[str] = set()
    for agent, config in sorted(AGENTS.items()):
        lane_name = config.get("lane")
        if lane_name is None:
            continue
        lane = LANES[lane_name]
        for capability in lane["capabilities"]:
            if capability in seen:
                errors.append(f"duplicate capability mapping: {capability}")
            seen.add(capability)
            targets = []
            for rel in lane["native_targets"]:
                target = (root / rel).resolve()
                try:
                    target.relative_to(root)
                except ValueError:
                    errors.append(f"native adapter target escapes repository: {capability}")
                    continue
                if not target.exists():
                    errors.append(f"native adapter target missing: {rel}")
                targets.append({
                    "path": str(rel).replace("\\", "/"),
                    "sha256": sha256_file(target) if target.is_file() else None,
                    "type": "file" if target.is_file() else "directory",
                })
            reference_only = lane_name == "retained_quarantine_no_current_lane"
            if not reference_only and not targets:
                errors.append(f"native capability has no executable evidence targets: {capability}")
            row = {
                "capability_id": capability,
                "agent_owner": agent,
                "lane": lane_name,
                "state": "REFERENCE_ONLY" if reference_only else "NATIVE_ADAPTER",
                "execution_mode": "SOURCE_ONLY_QUARANTINE" if reference_only else "BOUNDED_NATIVE_ADAPTER",
                "adapter_kind": "NONE" if reference_only else "METHODOLOGY_ALIAS_TO_NATIVE_ROLE_PROBE",
                "callable": not reference_only,
                "native_targets": targets,
                "external_source": capability if capability in by_name else None,
                "external_source_state": "QUARANTINED_SOURCE" if capability in by_name else None,
                "direct_named_skill_execution": False,
                "external_source_code_executed": False,
                "decision_effect": "NONE" if reference_only else "READ_ONLY_VALIDATION_EVIDENCE",
                "predictive_weight_authorized": False,
                "freeze_mutation_authorized": False,
                "active_native_promotion_authorized": False,
                "evidence_gate": "NATIVE_ROLE_PROBE_PASS_REQUIRED" if not reference_only else "NO_RUNTIME_EXECUTION",
            }
            row["binding_sha256"] = sha256_json(row)
            adapters.append(row)
    adapters.sort(key=lambda row: row["capability_id"])
    if len(adapters) != 41 or len(seen) != 41:
        errors.append("41 unique capability adapters required")
    native = [row for row in adapters if row["state"] == "NATIVE_ADAPTER"]
    references = [row for row in adapters if row["state"] == "REFERENCE_ONLY"]
    if len(native) != 37 or len(references) != 4:
        errors.append("37 native probe adapters and four reference-only capabilities required")
    if any(row["state"] not in STATES for row in adapters):
        errors.append("unsupported capability state")
    if any(row["state"] == "ACTIVE_NATIVE" for row in adapters):
        errors.append("unproved direct ACTIVE_NATIVE promotion forbidden")
    if any(row["external_source_code_executed"] or row["direct_named_skill_execution"] for row in adapters):
        errors.append("direct external skill execution forbidden")
    if any(row["external_source"] and row["external_source"] not in by_name for row in adapters):
        errors.append("source binding missing from quarantine manifest")
    if any(row["external_source"] and row["external_source_state"] != "QUARANTINED_SOURCE" for row in adapters):
        errors.append("capability alias may not promote quarantined external source")

    result = {
        "schema": SCHEMA,
        "state_model": list(STATES),
        "claim_boundary": "NATIVE_ADAPTER means a bounded alias invoking the named owner's native probe. It does NOT mean the named external skill/library code is executed. ACTIVE_NATIVE requires separate per-skill proof and is not granted here.",
        "external_manifest_file": MANIFEST_NAME,
        "external_manifest_sha256": sha256_file(source_path),
        "policy": {
            "external_code_auto_execute": False,
            "external_skill_direct_execution": False,
            "all_native_adapters_validation_only": True,
            "predictive_weight_authority": False,
            "freeze_mutation_authority": False,
            "active_native_requires_separate_proof": True,
        },
        "summary": {
            "capabilities": len(adapters),
            "native_adapters": len(native),
            "reference_only": len(references),
            "external_quarantined_sources": len(source_rows),
            "active_native": 0,
            "external_executions": 0,
        },
        "external_sources": sorted(source_rows, key=lambda row: row["source_name"] or ""),
        "adapters": adapters,
        "gate": {"status": "FAIL" if errors else "PASS", "errors": errors},
    }
    result["registry_sha256"] = sha256_json(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and check the canonical skill/adapter registry")
    parser.add_argument("--write", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    reg = build_registry(root)
    raw = json.dumps(reg, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        target = args.write if args.write.is_absolute() else root / args.write
        target.write_text(raw, encoding="utf-8")
    if args.check:
        target = args.check if args.check.is_absolute() else root / args.check
        if not target.is_file() or target.read_text(encoding="utf-8") != raw:
            raise SystemExit("skill adapter registry stale/missing")
    print(json.dumps({"summary": reg["summary"], "gate": reg["gate"]}, ensure_ascii=False))
    return 0 if reg["gate"]["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
