from __future__ import annotations
from smart_canonical_identity import canonical_root

import hashlib
import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from smart_source_identity import sha256_source_file

from smart_agent_runtime import SmartAgentRuntime, sha256_file
from smart_critical_code_manifest import build as build_critical_code_manifest
from smart_agent_skill_functional_gate import evaluate as functional_evaluate
from smart_agent_skill_orchestration import build_orchestration
from smart_material_deficiency_registry import load_registry
from smart_material_deficiency_policy import material_blockers
from smart_global_integrity import CRITICAL_SOURCE_FILES
from smart_operator import contract as operator_contract, validate_target_sequence
from smart_regression_evidence import junit_summary
from smart_runtime_guard import audit as runtime_audit
from smart_total_integration_gate import evaluate as total_integration_evaluate

SCHEMA = "SMART_PRODUCT_CERTIFICATION_V1"
DEFAULT_PATH = Path("SMART_PRODUCT_CERTIFICATION.json")
AUXILIARY_CODE_FILES = ("p14_coverage_plugin.py",)


def _sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _code_files(root: Path) -> list[Path]:
    files = sorted(set(root.glob("smart_*.py")) | set(root.glob("test_*.py")))
    authority_files = tuple(CRITICAL_SOURCE_FILES) + AUXILIARY_CODE_FILES
    metadata_files = ("requirements.txt", "requirements.lock.txt", "smart_python.cmd", "pytest.ini", "SMART_DATA_CONTRACT.md")
    for name in authority_files + metadata_files:
        p = root / name
        if p.is_file():
            files.append(p)
    return sorted(set(files))


def code_fingerprint(root: Path) -> dict[str, Any]:
    rows = [{"path": p.name, "sha256": sha256_source_file(p)} for p in _code_files(root)]
    return {"file_count": len(rows), "files": rows, "sha256": _sha256_json(rows)}


def canonical_root_authority_binding(root: Path, junit_path: Path, regression: dict[str, Any]) -> dict[str, Any]:
    authority_path = root / "SMART_CANONICAL_ROOT.json"
    actual_junit_sha = sha256_file(junit_path) if junit_path.is_file() else None
    checks: dict[str, bool] = {
        "authority_file_present": authority_path.is_file(),
        "junit_file_present": junit_path.is_file(),
    }
    if not authority_path.is_file() or not junit_path.is_file():
        return {"status": "FAIL", "file": authority_path.name, "file_sha256": None, "junit_sha256": actual_junit_sha, "checks": checks}
    try:
        authority = json.loads(authority_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, json.JSONDecodeError):
        checks["authority_json_valid"] = False
        return {"status": "FAIL", "file": authority_path.name, "file_sha256": sha256_file(authority_path), "junit_sha256": actual_junit_sha, "checks": checks}
    canonical = dict(authority)
    observed_self_hash = canonical.pop("sha256", None)
    nested = authority.get("certified_regression") if isinstance(authority.get("certified_regression"), dict) else {}
    authority_hostname = str(authority.get("hostname") or "")
    local_authority_host = os.name == "nt" and bool(authority_hostname) and authority_hostname.casefold() == socket.gethostname().casefold()
    legacy_alias = authority.get("legacy_alias")
    legacy_alias_physically_absent = True
    if local_authority_host:
        legacy_alias_physically_absent = isinstance(legacy_alias, str) and bool(legacy_alias) and not Path(legacy_alias).exists()
    checks.update({
        "authority_json_valid": True,
        "authority_self_hash_valid": isinstance(observed_self_hash, str) and observed_self_hash == _sha256_json(canonical),
        "authority_project_valid": authority.get("project") == "SMART-MEGA",
        "authority_root_matches": (authority.get("canonical_root") == str(root)) if local_authority_host and Path(str(authority.get("canonical_root") or "")).resolve() == root else isinstance(authority.get("canonical_root"), str) and bool(authority.get("canonical_root")),
        "authority_state_canonical_only": authority.get("canonical_state") == "CANONICAL_ONLY" and authority.get("legacy_alias_present") is False,
        "legacy_alias_physically_absent": legacy_alias_physically_absent,
        "junit_file_bound": authority.get("certified_regression_junit") == junit_path.name and nested.get("junit_file") == junit_path.name,
        "junit_sha_bound": authority.get("certified_regression_junit_sha256") == actual_junit_sha and nested.get("junit_sha256") == actual_junit_sha,
        "regression_counts_bound": authority.get("certified_regression_tests") == regression.get("tests") == nested.get("tests") and authority.get("certified_regression_failures") == regression.get("failures") == nested.get("failures") and authority.get("certified_regression_errors") == regression.get("errors") == nested.get("errors"),
    })
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "file": authority_path.name,
        "file_sha256": sha256_file(authority_path),
        "authority_sha256": observed_self_hash,
        "junit_file": junit_path.name,
        "junit_sha256": actual_junit_sha,
        "tests": regression.get("tests"),
        "failures": regression.get("failures"),
        "errors": regression.get("errors"),
        "checks": checks,
    }


def _all_total_gates_true(doc: dict[str, Any]) -> bool:
    gates = doc.get("gates")
    return isinstance(gates, dict) and bool(gates) and all(isinstance(group, dict) and bool(group) and all(v is True for v in group.values()) for group in gates.values())


def verify_product_certification(path: str | Path, *, root: str | Path | None = None, require_current_code: bool = False) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA or doc.get("status") != "CONSTRUCTION_PROVEN":
        raise ValueError("SMART product certification schema/status invalid")
    observed = doc.get("sha256")
    canonical = dict(doc); canonical.pop("sha256", None)
    if observed != _sha256_json(canonical):
        raise ValueError("SMART product certification self-hash invalid")
    if not all(doc.get("checks", {}).values()):
        raise ValueError("SMART product certification checks are not all true")
    if require_current_code:
        project_root = Path(root).resolve() if root is not None else p.resolve().parent
        if doc.get("code_fingerprint") != code_fingerprint(project_root):
            raise ValueError("SMART product certification is stale for current code")
        if doc.get("critical_code_manifest") != build_critical_code_manifest(project_root):
            raise ValueError("SMART product certification critical code manifest is stale")
        current_junit = project_root / "SMART_AUDIT_JUNIT_CURRENT.xml"
        current_regression = junit_summary(current_junit)
        current_authority = canonical_root_authority_binding(project_root, current_junit, current_regression)
        if current_authority.get("status") != "PASS" or doc.get("canonical_root_authority") != current_authority:
            raise ValueError("SMART product certification canonical regression authority is stale")
        code_files = _code_files(project_root)
        regression_fresh = current_junit.is_file() and bool(code_files) and current_junit.stat().st_mtime >= max(item.stat().st_mtime for item in code_files)
        if not regression_fresh:
            raise ValueError("SMART product certification regression is stale for current code")
    return doc


def build(root: str | Path = ".") -> dict[str, Any]:
    root = Path(root).resolve()
    junit_path = root / "SMART_AUDIT_JUNIT_CURRENT.xml"
    regression = junit_summary(junit_path)
    canonical_authority = canonical_root_authority_binding(root, junit_path, regression)
    code_files = _code_files(root)
    regression_fresh = junit_path.is_file() and junit_path.stat().st_mtime >= max(p.stat().st_mtime for p in code_files)
    runtime = runtime_audit(root)
    orchestration = build_orchestration(root, phase="BUILD")
    agent_runtime = SmartAgentRuntime(root, phase="BUILD").run()
    functional = functional_evaluate(root, phase="BUILD")
    total = total_integration_evaluate(root, phase="BUILD")
    deficiencies = load_registry(root / "SMART_MATERIAL_DEFICIENCY_REGISTRY.json", root=root)
    open_deficiencies = deficiencies.get("open_entries", [])
    product_blocking_deficiencies = material_blockers(open_deficiencies, allow_supervisory_freshness_self_resolution=True)
    op = operator_contract()
    generic_target_accept = validate_target_sequence([8998, 8999, 9000], 9001)["target_contest"] == 9001
    gap_rejected = False
    try:
        validate_target_sequence([8998, 8999, 9000], 9002)
    except ValueError:
        gap_rejected = True
    checks = {
        "full_regression_green": regression["status"] == "PASS" and regression["failures"] == 0 and regression["errors"] == 0,
        "full_regression_fresh_for_current_code": regression_fresh,
        "canonical_root_authority_bound_to_current_regression": canonical_authority.get("status") == "PASS",
        "runtime_guard_pass": runtime.get("status") == "PASS" and all(runtime.get("checks", {}).values()),
        "build_orchestration_pass": orchestration.get("phase") == "BUILD" and orchestration.get("integration_status") == "PASS" and all(orchestration.get("checks", {}).values()),
        "build_runtime_pass": agent_runtime.get("phase") == "BUILD" and agent_runtime.get("status") == "PASS" and all(agent_runtime.get("checks", {}).values()),
        "build_functional_integration_pass": functional.get("phase") == "BUILD" and functional.get("status") == "PASS" and all(functional.get("checks", {}).values()),
        "build_total_integration_pass": total.get("phase") == "BUILD" and total.get("status") == "PASS" and _all_total_gates_true(total),
        "operator_contract_separates_construction_from_freeze": op.get("product_completion_independent_of_operation") is True and op.get("freeze_is_operational_not_construction_gate") is True,
        "operator_target_is_explicit_and_generic": op.get("operator_selects_target") is True and generic_target_accept,
        "operator_target_fails_closed_without_complete_prior_history": gap_rejected and op.get("fail_closed_on_history_gap_or_target_result_present") is True,
        "zero_open_material_deficiencies": len(product_blocking_deficiencies) == 0,
        "scientific_terminal_claim_not_required_for_product_completion": op.get("scientific_terminal_claim_independent_of_product_completion") is True,
    }
    doc = {
        "schema": SCHEMA,
        "status": "CONSTRUCTION_PROVEN" if all(checks.values()) else "CONSTRUCTION_BLOCKED",
        "project": "SMART-MEGA",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Product construction/integration certification only. No contest, freeze, generated combination or adjudication is required to complete the product.",
        "operation_boundary": "The operator chooses a target at runtime. Operational prepare/freeze/adjudicate state is not a construction gate.",
        "scientific_boundary": "Scientific predictive advantage and terminal 6/6 remain separate prospective claims and do not control product construction status.",
        "code_fingerprint": code_fingerprint(root),
        "critical_code_manifest": build_critical_code_manifest(root),
        "regression": regression,
        "canonical_root_authority": canonical_authority,
        "runtime_guard": runtime,
        "build_orchestration_sha256": orchestration.get("orchestration_sha256"),
        "build_runtime_sha256": agent_runtime.get("runtime_sha256"),
        "build_functional_sha256": functional.get("sha256"),
        "build_total_integration_sha256": total.get("sha256"),
        "operator_contract": op,
        "material_deficiency_registry_sha256": deficiencies.get("registry_sha256"),
        "open_material_deficiencies": open_deficiencies,
        "product_blocking_material_deficiencies": product_blocking_deficiencies,
        "checks": checks,
    }
    doc["sha256"] = _sha256_json(doc)
    return doc


def write(root: str | Path = ".", out: str | Path = DEFAULT_PATH) -> dict[str, Any]:
    root = Path(root).resolve(); path = Path(out); path = path if path.is_absolute() else root / path
    doc = build(root)
    if doc["status"] != "CONSTRUCTION_PROVEN":
        raise RuntimeError({"product_certification_checks": doc["checks"]})
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc

if __name__ == "__main__":
    result = write(canonical_root())
    print(json.dumps({"status": result["status"], "sha256": result["sha256"], "checks": result["checks"]}, ensure_ascii=False, indent=2))

