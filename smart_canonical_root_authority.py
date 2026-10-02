from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from smart_regression_evidence import junit_summary, sha256_file

SCHEMA = "SMART_CANONICAL_ROOT_V1"
AUTHORITY_FILE = "SMART_CANONICAL_ROOT.json"
JUNIT_FILE = "SMART_AUDIT_JUNIT_CURRENT.xml"
BINDING_MODE = "CONTENT_HASH_NO_GIT_SHA_CIRCULARITY"
REFRESH_REASON = "CONTENT_BOUND_REGRESSION_REFRESH"


def _sha_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_authority(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA or doc.get("project") != "SMART-MEGA":
        raise ValueError("canonical root authority schema/project invalid")
    observed = doc.get("sha256")
    body = dict(doc)
    body.pop("sha256", None)
    if not isinstance(observed, str) or observed != _sha_json(body):
        raise ValueError("canonical root authority self-hash invalid")
    if doc.get("canonical_state") != "CANONICAL_ONLY" or doc.get("legacy_alias_present") is not False:
        raise ValueError("canonical root authority state is not canonical-only")
    return doc


def _current_binding(root: Path) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    from smart_product_certification import code_fingerprint, regression_code_binding

    junit = root / JUNIT_FILE
    if not junit.is_file():
        raise FileNotFoundError(junit)
    regression = junit_summary(junit)
    if regression.get("status") != "PASS" or regression.get("failures") != 0 or regression.get("errors") != 0:
        raise ValueError("canonical root refresh requires green current regression")
    fingerprint = code_fingerprint(root)
    binding = regression_code_binding(root, junit, regression, fingerprint)
    if binding.get("status") != "PASS" or not all(binding.get("checks", {}).values()):
        raise ValueError("canonical root refresh requires current regression/code binding")
    return junit, regression, fingerprint, binding


def build(root: str | Path = ".") -> dict[str, Any]:
    root = Path(root).resolve()
    authority_path = root / AUTHORITY_FILE
    doc = _read_authority(authority_path)
    junit, regression, fingerprint, binding = _current_binding(root)
    junit_sha = sha256_file(junit)

    refreshed = dict(doc)
    refreshed.pop("sha256", None)
    refreshed.update({
        "authority_refreshed_at": datetime.now(timezone.utc).isoformat(),
        "authority_refresh_reason": REFRESH_REASON,
        "authority_binding_mode": BINDING_MODE,
        "git_reference_authoritative": False,
        "git_reference_note": "git_head/git_ref_sha are historical provenance only; current authority is bound by content hashes to the tested code and JUnit evidence.",
        "certified_regression_tests": int(regression["tests"]),
        "certified_regression_failures": int(regression["failures"]),
        "certified_regression_errors": int(regression["errors"]),
        "certified_regression_skipped": int(regression.get("skipped", 0)),
        "certified_regression_junit": junit.name,
        "certified_regression_junit_sha256": junit_sha,
        "certified_regression": {
            "junit_file": junit.name,
            "junit_sha256": junit_sha,
            "tests": int(regression["tests"]),
            "failures": int(regression["failures"]),
            "errors": int(regression["errors"]),
            "skipped": int(regression.get("skipped", 0)),
            "status": "PASS",
        },
        "certified_code_fingerprint_sha256": fingerprint["sha256"],
        "certified_regression_binding_file": binding["file"],
        "certified_regression_binding_sha256": binding["file_sha256"],
        "certified_regression_proof_sha256": binding["proof_sha256"],
    })
    refreshed["sha256"] = _sha_json(refreshed)
    return refreshed


def verify(root: str | Path = ".", path: str | Path = AUTHORITY_FILE) -> dict[str, Any]:
    root = Path(root).resolve()
    authority_path = Path(path)
    if not authority_path.is_absolute():
        authority_path = root / authority_path
    doc = _read_authority(authority_path)
    junit, regression, fingerprint, binding = _current_binding(root)
    junit_sha = sha256_file(junit)
    nested = doc.get("certified_regression") if isinstance(doc.get("certified_regression"), dict) else {}
    checks = {
        "binding_mode_content_hash": doc.get("authority_binding_mode") == BINDING_MODE,
        "git_reference_non_authoritative": doc.get("git_reference_authoritative") is False,
        "junit_file_current": doc.get("certified_regression_junit") == junit.name and nested.get("junit_file") == junit.name,
        "junit_hash_current": doc.get("certified_regression_junit_sha256") == junit_sha and nested.get("junit_sha256") == junit_sha,
        "regression_counts_current": (
            doc.get("certified_regression_tests") == regression.get("tests") == nested.get("tests")
            and doc.get("certified_regression_failures") == regression.get("failures") == nested.get("failures") == 0
            and doc.get("certified_regression_errors") == regression.get("errors") == nested.get("errors") == 0
            and doc.get("certified_regression_skipped", 0) == regression.get("skipped", 0) == nested.get("skipped", 0)
        ),
        "code_fingerprint_current": doc.get("certified_code_fingerprint_sha256") == fingerprint.get("sha256"),
        "regression_binding_file_current": doc.get("certified_regression_binding_file") == binding.get("file"),
        "regression_binding_hash_current": doc.get("certified_regression_binding_sha256") == binding.get("file_sha256"),
        "regression_proof_hash_current": doc.get("certified_regression_proof_sha256") == binding.get("proof_sha256"),
        "historical_git_ref_preserved_as_provenance": isinstance(doc.get("git_ref_sha"), str) and bool(doc.get("git_ref_sha")),
    }
    failed = sorted(name for name, ok in checks.items() if ok is not True)
    if failed:
        raise ValueError(f"canonical root authority stale: {failed}")
    return {
        "status": "PASS",
        "file": authority_path.name,
        "file_sha256": sha256_file(authority_path),
        "authority_sha256": doc["sha256"],
        "code_fingerprint_sha256": fingerprint["sha256"],
        "junit_sha256": junit_sha,
        "regression_binding_sha256": binding["file_sha256"],
        "checks": checks,
    }


def write(root: str | Path = ".", path: str | Path = AUTHORITY_FILE) -> dict[str, Any]:
    root = Path(root).resolve()
    authority_path = Path(path)
    if not authority_path.is_absolute():
        authority_path = root / authority_path
    original = authority_path.read_bytes()
    newline = "\r\n" if b"\r\n" in original else "\n"
    bom = original.startswith(b"\xef\xbb\xbf")
    doc = build(root)
    text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if newline == "\r\n":
        text = text.replace("\n", "\r\n")
    payload = text.encode("utf-8")
    if bom:
        payload = b"\xef\xbb\xbf" + payload
    temp = authority_path.with_name(authority_path.name + ".tmp-authority-refresh")
    temp.write_bytes(payload)
    os.replace(temp, authority_path)
    verify(root, authority_path)
    return doc


if __name__ == "__main__":
    result = write(Path(__file__).resolve().parent)
    print(json.dumps({"status": "PASS", "sha256": result["sha256"], "binding_mode": result["authority_binding_mode"]}, ensure_ascii=False))
