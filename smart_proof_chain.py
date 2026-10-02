from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

SCHEMA = "SMART_PROOF_CHAIN_CONTRACT_1"

CHAIN = (
    ("critical_code_manifest", "SMART_CRITICAL_CODE_MANIFEST.json", "smart_critical_code_manifest.write", "smart_critical_code_manifest.build"),
    ("regression_authority", "SMART_AUDIT_JUNIT_CURRENT.xml", "smart_regression_runner.run_regression", None),
    ("regression_code_binding", "SMART_AUDIT_JUNIT_CURRENT_PROOF.json", "smart_regression_runner.run_regression", "smart_product_certification.verify_current_regression_code_binding"),
    ("canonical_root", "SMART_CANONICAL_ROOT.json", "smart_canonical_root_authority.write", "smart_canonical_root_authority.verify"),
    ("product_certification", "SMART_PRODUCT_CERTIFICATION.json", "smart_product_certification.write", "smart_product_certification.verify_product_certification"),
    ("global_integrity", "SMART_GLOBAL_INTEGRITY_PROOF.json", "smart_global_integrity.build_global_integrity_proof", "smart_global_integrity.verify_global_integrity"),
    ("governance", "SMART_AGENT_ECOSYSTEM_GOVERNANCE.json", "smart_agent_ecosystem_governance.write", "smart_authority_freshness.verify_governance"),
    ("material_registry", "SMART_MATERIAL_DEFICIENCY_REGISTRY.json", "smart_material_deficiency_registry.write_registry", "smart_material_deficiency_registry.load_registry"),
    ("mission_status", "SMART_MISSION_STATUS.json", "smart_mission_status.write_mission_status", "smart_mission_status.load_mission_status"),
    ("continuity", "SMART_CONTINUITY.md", "smart_continuity_consolidator.write", "smart_continuity_consolidator.build"),
    ("release_attestation", "SMART_RELEASE_ATTESTATION.json", "smart_release_attestation.build", "smart_release_attestation.verify"),
)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
def contract() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "IMPLEMENTED_NOT_FINALIZED",
        "order": [name for name, _, _, _ in CHAIN],
        "stages": [
            {"name": name, "file": file, "generator": generator, "verifier": verifier}
            for name, file, generator, verifier in CHAIN
        ],
        "invalidation_rule": "ANY_UPSTREAM_CHANGE_INVALIDATES_ALL_DOWNSTREAM_STAGES",
        "final_proof_generation_allowed_in_p1": False,
    }


def inspect(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    stages = []
    for name, file, generator, verifier in CHAIN:
        path = root / file
        stages.append({
            "name": name,
            "file": file,
            "present": path.is_file(),
            "sha256": _sha(path) if path.is_file() else None,
            "generator": generator,
            "verifier": verifier,
        })
    return {
        "schema": SCHEMA,
        "status": "PLAN_READY",
        "stages": stages,
        "final_proof_emitted": False,
    }
def downstream(stage: str) -> list[str]:
    names = [name for name, _, _, _ in CHAIN]
    if stage not in names:
        raise ValueError(f"unknown proof-chain stage: {stage}")
    return names[names.index(stage) + 1:]


def invalidation_plan(changed_stage: str) -> dict[str, Any]:
    invalidated = downstream(changed_stage)
    return {
        "schema": SCHEMA,
        "changed_stage": changed_stage,
        "invalidate_downstream": invalidated,
        "automatic_deletion": False,
        "regeneration_required": bool(invalidated),
    }


def assert_order(previous_stage: str, next_stage: str) -> None:
    names = [name for name, _, _, _ in CHAIN]
    if names.index(next_stage) != names.index(previous_stage) + 1:
        raise RuntimeError(f"proof-chain order violation: {previous_stage} -> {next_stage}")
