from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from smart_critical_code_manifest import build as build_critical_code_manifest


PRODUCT_CERTIFICATION = "SMART_PRODUCT_CERTIFICATION.json"
CANONICAL_ROOT = "SMART_CANONICAL_ROOT.json"
GOVERNANCE = "SMART_AGENT_ECOSYSTEM_GOVERNANCE.json"
REGRESSION_PROOF = "SMART_AUDIT_JUNIT_CURRENT_PROOF.json"
REGRESSION_PROOF_SCHEMA = "SMART_REGRESSION_CODE_BINDING_V1"

# Keep this file-selection contract aligned with smart_product_certification._code_files.
# CRITICAL_SOURCE_FILES contributes only these non-smart_*.py paths beyond the glob set.
CRITICAL_NON_SMART_CODE_FILES = (
    "freeze_next_research.py",
    "adjudicate_signal_challenger.py",
)
AUXILIARY_CODE_FILES = ("p14_coverage_plugin.py",)
METADATA_FILES = (
    "requirements.txt",
    "requirements.lock.txt",
    "smart_python.cmd",
    "pytest.ini",
    "SMART_DATA_CONTRACT.md",
)


def _sha_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path.name}")
    return value


def _self_hash_valid(doc: dict[str, Any]) -> bool:
    observed = doc.get("sha256")
    canonical = dict(doc)
    canonical.pop("sha256", None)
    return isinstance(observed, str) and observed == _sha_json(canonical)


def _code_files(root: Path) -> list[Path]:
    files = set(root.glob("smart_*.py")) | set(root.glob("test_*.py"))
    for name in CRITICAL_NON_SMART_CODE_FILES + AUXILIARY_CODE_FILES + METADATA_FILES:
        path = root / name
        if path.is_file():
            files.add(path)
    return sorted((path for path in files if path.is_file()), key=lambda path: path.name.casefold())


def code_fingerprint(root: str | Path) -> dict[str, Any]:
    root_path = Path(root).resolve()
    rows = [{"path": path.name, "sha256": _sha256_file(path)} for path in _code_files(root_path)]
    return {"file_count": len(rows), "files": rows, "sha256": _sha_json(rows)}


def junit_summary(path: str | Path) -> dict[str, Any]:
    junit_path = Path(path)
    raw = junit_path.read_bytes()
    upper = raw.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("DTD/ENTITY is forbidden in CI JUnit evidence")
    root = ET.fromstring(raw)
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if root.tag == "testsuites" and root.attrib.get("tests") is not None:
        tests = int(root.attrib.get("tests", 0))
        failures = int(root.attrib.get("failures", 0))
        errors = int(root.attrib.get("errors", 0))
        skipped = int(root.attrib.get("skipped", 0))
    else:
        tests = sum(int(suite.attrib.get("tests", 0)) for suite in suites)
        failures = sum(int(suite.attrib.get("failures", 0)) for suite in suites)
        errors = sum(int(suite.attrib.get("errors", 0)) for suite in suites)
        skipped = sum(int(suite.attrib.get("skipped", 0)) for suite in suites)
    return {
        "tests": tests,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "status": "PASS" if failures == 0 and errors == 0 and tests > 0 else "FAIL",
        "sha256": _sha256_file(junit_path),
    }


def _regression_signature(regression: dict[str, Any]) -> dict[str, Any]:
    tests = int(regression.get("tests", 0))
    failures = int(regression.get("failures", 0))
    errors = int(regression.get("errors", 0))
    skipped = int(regression.get("skipped", 0))
    return {
        "tests": tests,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "status": regression.get("status"),
    }


def _same_counts(candidate: dict[str, Any] | None, live: dict[str, Any]) -> bool:
    if not isinstance(candidate, dict):
        return False
    return (
        candidate.get("tests") == live.get("tests")
        and candidate.get("failures") == live.get("failures")
        and candidate.get("errors") == live.get("errors")
        and candidate.get("skipped", 0) == live.get("skipped", 0)
    )


def binding_checks(
    *,
    certification: dict[str, Any],
    canonical_root: dict[str, Any],
    governance: dict[str, Any],
    regression_proof: dict[str, Any],
    regression_proof_file_sha256: str,
    live_regression: dict[str, Any],
    current_code_fingerprint: dict[str, Any],
    current_critical_manifest: Any,
) -> dict[str, bool]:
    live = _regression_signature(live_regression)
    cert_regression = certification.get("regression")
    cert_authority = certification.get("canonical_root_authority")
    canonical_nested = canonical_root.get("certified_regression")
    cert_binding = certification.get("regression_code_binding")
    proof_junit_sha = regression_proof.get("junit_sha256")

    return {
        "live_regression_green": live["status"] == "PASS" and live["failures"] == 0 and live["errors"] == 0,
        "product_certification_self_hash_valid": _self_hash_valid(certification),
        "product_certification_live_pass": (
            certification.get("schema") == "SMART_PRODUCT_CERTIFICATION_V1"
            and certification.get("status") == "CONSTRUCTION_PROVEN"
            and bool(certification.get("checks"))
            and all(value is True for value in certification.get("checks", {}).values())
        ),
        "product_certification_code_fingerprint_current": certification.get("code_fingerprint") == current_code_fingerprint,
        "product_certification_critical_manifest_current": certification.get("critical_code_manifest") == current_critical_manifest,
        "product_certification_regression_counts_current": _same_counts(cert_regression, live),
        "product_certification_canonical_authority_counts_current": _same_counts(cert_authority, live),
        "regression_proof_self_hash_valid": _self_hash_valid(regression_proof),
        "regression_proof_live_pass": regression_proof.get("schema") == REGRESSION_PROOF_SCHEMA and regression_proof.get("status") == "PASS",
        "regression_proof_code_fingerprint_current": regression_proof.get("code_fingerprint") == current_code_fingerprint,
        "regression_proof_counts_current": _same_counts(regression_proof, live),
        "product_certification_regression_binding_current": (
            isinstance(cert_binding, dict)
            and cert_binding.get("status") == "PASS"
            and cert_binding.get("file") == REGRESSION_PROOF
            and cert_binding.get("file_sha256") == regression_proof_file_sha256
            and cert_binding.get("proof_sha256") == regression_proof.get("sha256")
            and cert_binding.get("junit_file") == regression_proof.get("junit_file")
            and cert_binding.get("junit_sha256") == proof_junit_sha
            and cert_binding.get("code_fingerprint_sha256") == current_code_fingerprint.get("sha256")
            and bool(cert_binding.get("checks"))
            and all(value is True for value in cert_binding.get("checks", {}).values())
        ),
        "canonical_root_self_hash_valid": _self_hash_valid(canonical_root),
        "canonical_root_live_state": (
            canonical_root.get("schema") == "SMART_CANONICAL_ROOT_V1"
            and canonical_root.get("project") == "SMART-MEGA"
            and canonical_root.get("canonical_state") == "CANONICAL_ONLY"
            and canonical_root.get("legacy_alias_present") is False
        ),
        "canonical_root_regression_counts_current": (
            canonical_root.get("certified_regression_tests") == live["tests"]
            and canonical_root.get("certified_regression_failures") == live["failures"]
            and canonical_root.get("certified_regression_errors") == live["errors"]
            and canonical_root.get("certified_regression_skipped", 0) == live["skipped"]
        ),
        "canonical_root_nested_regression_counts_current": _same_counts(canonical_nested, live),
        "canonical_root_regression_proof_hash_bound": (
            canonical_root.get("certified_regression_junit") == regression_proof.get("junit_file")
            and canonical_root.get("certified_regression_junit_sha256") == proof_junit_sha
            and isinstance(canonical_nested, dict)
            and canonical_nested.get("junit_file") == regression_proof.get("junit_file")
            and canonical_nested.get("junit_sha256") == proof_junit_sha
        ),
        "governance_self_hash_valid": _self_hash_valid(governance),
        "governance_live_pass": (
            governance.get("status") == "PASS"
            and bool(governance.get("checks"))
            and all(value is True for value in governance.get("checks", {}).values())
        ),
        "governance_critical_manifest_current": governance.get("critical_code_manifest") == current_critical_manifest,
    }


def audit_ci(root: str | Path = ".", junit: str | Path = "SMART_AUDIT_JUNIT_GITHUB.xml") -> dict[str, Any]:
    root_path = Path(root).resolve()
    junit_path = Path(junit)
    if not junit_path.is_absolute():
        junit_path = root_path / junit_path

    certification = _read_json(root_path / PRODUCT_CERTIFICATION)
    canonical = _read_json(root_path / CANONICAL_ROOT)
    governance = _read_json(root_path / GOVERNANCE)
    regression_proof_path = root_path / REGRESSION_PROOF
    regression_proof = _read_json(regression_proof_path)
    regression_proof_file_sha256 = _sha256_file(regression_proof_path)
    live_regression = junit_summary(junit_path)
    current_fingerprint = code_fingerprint(root_path)
    current_manifest = build_critical_code_manifest(root_path)

    checks = binding_checks(
        certification=certification,
        canonical_root=canonical,
        governance=governance,
        regression_proof=regression_proof,
        regression_proof_file_sha256=regression_proof_file_sha256,
        live_regression=live_regression,
        current_code_fingerprint=current_fingerprint,
        current_critical_manifest=current_manifest,
    )
    failed = sorted(name for name, value in checks.items() if value is not True)
    return {
        "schema": "SMART_CI_AUTHORITY_GATE_V1",
        "status": "PASS" if not failed else "FAIL",
        "junit": junit_path.name,
        "live_regression": _regression_signature(live_regression),
        "code_fingerprint_sha256": current_fingerprint.get("sha256"),
        "checks": checks,
        "failed_checks": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed GitHub CI authority freshness gate.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--junit", default="SMART_AUDIT_JUNIT_GITHUB.xml")
    args = parser.parse_args()

    try:
        result = audit_ci(args.root, args.junit)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema": "SMART_CI_AUTHORITY_GATE_V1",
                    "status": "FAIL",
                    "error": f"{type(exc).__name__}: {exc}",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
