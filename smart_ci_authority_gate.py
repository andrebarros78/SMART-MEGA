from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from smart_critical_code_manifest import build as build_critical_code_manifest
from smart_product_certification import code_fingerprint
from smart_regression_evidence import junit_summary


PRODUCT_CERTIFICATION = "SMART_PRODUCT_CERTIFICATION.json"
CANONICAL_ROOT = "SMART_CANONICAL_ROOT.json"
GOVERNANCE = "SMART_AGENT_ECOSYSTEM_GOVERNANCE.json"


def _sha_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _self_hash_valid(doc: dict[str, Any]) -> bool:
    observed = doc.get("sha256")
    canonical = dict(doc)
    canonical.pop("sha256", None)
    return isinstance(observed, str) and observed == _sha_json(canonical)


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
    live_regression: dict[str, Any],
    current_code_fingerprint: dict[str, Any],
    current_critical_manifest: Any,
) -> dict[str, bool]:
    live = _regression_signature(live_regression)
    cert_regression = certification.get("regression")
    cert_authority = certification.get("canonical_root_authority")
    canonical_nested = canonical_root.get("certified_regression")

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
    live_regression = junit_summary(junit_path)
    current_fingerprint = code_fingerprint(root_path)
    current_manifest = build_critical_code_manifest(root_path)

    checks = binding_checks(
        certification=certification,
        canonical_root=canonical,
        governance=governance,
        live_regression=live_regression,
        current_code_fingerprint=current_fingerprint,
        current_critical_manifest=current_manifest,
    )
    failed = sorted(name for name, value in checks.items() if value is not True)
    result = {
        "schema": "SMART_CI_AUTHORITY_GATE_V1",
        "status": "PASS" if not failed else "FAIL",
        "junit": junit_path.name,
        "live_regression": _regression_signature(live_regression),
        "code_fingerprint_sha256": current_fingerprint.get("sha256"),
        "checks": checks,
        "failed_checks": failed,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed GitHub CI authority freshness gate.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--junit", default="SMART_AUDIT_JUNIT_GITHUB.xml")
    args = parser.parse_args()

    try:
        result = audit_ci(args.root, args.junit)
    except Exception as exc:
        print(json.dumps({"schema": "SMART_CI_AUTHORITY_GATE_V1", "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
