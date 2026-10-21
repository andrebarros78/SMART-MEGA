"""Refresh construction certification from externally tested canonical GitHub code."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import subprocess

from smart_agent_runtime import sha256_file
from smart_product_certification import (
    _sha256_json, code_fingerprint, junit_summary, verify_product_certification, write,
)
from smart_agent_ecosystem_governance import evaluate as evaluate_governance, write_acquisition_manifest
from smart_authority_freshness import audit as audit_authority_freshness, verify_governance
from smart_global_integrity import build_global_integrity_proof, verify_global_integrity
from smart_continuous_red_team import run_suite as run_red_team_suite, verify_latest_report, write_report as write_red_team_report
from smart_startup_reconciler import reconcile as reconcile_startup
from smart_source_identity import sha256_source_file

ARTIFACTS = (
    "SMART_AUDIT_JUNIT_CURRENT.xml", "SMART_CANONICAL_ROOT.json",
    "SMART_PRODUCT_CERTIFICATION.json", "SMART_AGENT_ECOSYSTEM_GOVERNANCE.json",
    "SMART_GLOBAL_INTEGRITY_PROOF.json", "SMART_3052_IMPLEMENTATION_GATE.json",
    "SMART_P09_RED_TEAM_LATEST.json", "SMART_AGENT_ECOSYSTEM_ACQUISITIONS_20260915.json",
)


def require_current_coverage_sources(root: Path) -> None:
    """Reject historical coverage before updating any operational authority."""
    from smart_global_integrity import REQUIRED_GLOBAL_COVERAGE_SOURCES

    root = Path(root).resolve()
    proof = json.loads((root / "SMART_GLOBAL_INTEGRITY_PROOF.json").read_text(encoding="utf-8-sig"))
    rows = proof.get("coverage")
    expected = set(REQUIRED_GLOBAL_COVERAGE_SOURCES)
    if (not isinstance(rows, list) or len(rows) != len(expected)
            or any(not isinstance(row, dict) for row in rows)
            or {row.get("source_key") for row in rows} != expected):
        raise ValueError("current source-bound coverage inventory required")
    reports = {}
    for row in rows:
        relative = row.get("report_file")
        if not isinstance(relative, str):
            raise ValueError("current source-bound coverage report required")
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError("current source-bound coverage report is unsafe or missing")
        if relative not in reports:
            reports[relative] = json.loads(path.read_text(encoding="utf-8-sig"))
        source = row["source_key"]
        entry = reports[relative].get("files", {}).get(source, {})
        if entry.get("source_sha256") != sha256_source_file(root / source):
            raise ValueError(f"current source-bound coverage required: {source}")


def execution_provenance(root: Path, source_commit: str, run_id: str,
                         executor_host: str | None = None, *,
                         executor_kind: str = "EXTERNAL_GOVERNED_EXECUTOR") -> dict:
    """Record approved, source-bound external verification, never Actions.

    GitHub is canonical for source, not an execution environment. This binding
    is an integrity/authorization check, not a cryptographic host signature.
    """
    import socket
    if (os.environ.get("GITHUB_ACTIONS", "").lower() in {"true", "1"}
            or os.environ.get("GITHUB_EVENT_NAME")):
        raise PermissionError("GitHub Actions are prohibited for certification")
    if executor_kind != "EXTERNAL_GOVERNED_EXECUTOR":
        raise PermissionError("retired or GitHub Actions certification authority")
    if not isinstance(source_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("invalid tested source commit")
    if (not isinstance(run_id, str) or re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            run_id) is None):
        raise ValueError("external execution identity must be UUIDv4")
    if (not isinstance(executor_host, str) or not executor_host
            or executor_host != socket.gethostname()):
        raise PermissionError("executor host identity mismatch")
    if os.environ.get("SMART_MEGA_CERTIFICATION_APPROVAL") != source_commit:
        raise PermissionError("GitHub canonical source requires explicit certification approval")
    root = Path(root).resolve()
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, capture_output=True,
                              text=True, check=True, timeout=45).stdout.strip()
    if Path(git("rev-parse", "--show-toplevel")).resolve() != root:
        raise PermissionError("certification checkout is not the canonical Git root")
    if git("rev-parse", "HEAD") != source_commit:
        raise PermissionError("checked-out Git source differs from approved SHA")
    origin = git("remote", "get-url", "origin")
    if origin not in {
        "https://github.com/andrebarros78/SMART-MEGA.git",
        "https://github.com/andrebarros78/SMART-MEGA",
        "git@github.com:andrebarros78/SMART-MEGA.git",
        "ssh://git@github.com/andrebarros78/SMART-MEGA.git",
    }:
        raise PermissionError("certification Git origin is not canonical")
    return {
        "kind": "EXTERNAL_GOVERNED_EXECUTOR", "execution_id": run_id,
        "hostname": executor_host, "source_commit": source_commit, "origin": origin,
    }

def refresh(root: Path, candidate: Path, source_commit: str, run_id: str, *,
            executor_host: str | None = None, executor_kind: str = "EXTERNAL_GOVERNED_EXECUTOR") -> dict:
    root = root.resolve()
    execution = execution_provenance(root, source_commit, run_id, executor_host, executor_kind=executor_kind)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()
    if head != source_commit:
        raise ValueError("certification source differs from checked-out commit")
    if (not candidate.is_file() or candidate.is_symlink()
            or candidate.resolve() == (root / ARTIFACTS[0]).resolve()):
        raise ValueError("regression JUnit candidate missing or not independent of current proof")

    # Validate the external result BEFORE changing any tracked authority.
    # Use the immutable source-commit baseline, never the mutable checkout file.
    from smart_linux_ci import baseline_junit_counts
    baseline = baseline_junit_counts(root)
    if baseline is None:
        raise ValueError("immutable Git JUnit baseline unavailable")
    observed = junit_summary(candidate)
    if (observed.get("status") != "PASS"
            or observed.get("tests", 0) < baseline["tests"]
            or observed.get("failures") != 0 or observed.get("errors") != 0
            or observed.get("skipped") != 0):
        raise ValueError("regression coverage below immutable baseline or skipped tests")

    require_current_coverage_sources(root)

    attributes = root / ".gitattributes"
    lines = attributes.read_text(encoding="utf-8").splitlines() if attributes.is_file() else []
    for name in ARTIFACTS:
        rule = f"/{name} -text"
        if rule not in lines:
            lines.append(rule)
    attributes.write_text("\n".join(lines) + "\n", encoding="utf-8")

    junit = root / ARTIFACTS[0]
    shutil.copyfile(candidate, junit)
    regression = junit_summary(junit)
    if regression["status"] != "PASS" or regression["tests"] <= 0:
        raise ValueError("full CI regression did not pass")
    fp = code_fingerprint(root)
    authority_path = root / ARTIFACTS[1]
    authority = json.loads(authority_path.read_text(encoding="utf-8-sig"))
    authority.pop("sha256", None)
    authority.update({
        "git_ref_sha": source_commit,
        "git_head": f"commit: {source_commit}",
        "authority_refreshed_at": datetime.now(timezone.utc).isoformat(),
        "authority_refresh_reason": "GITHUB_CANONICAL_EXTERNAL_REGRESSION_PROVENANCE",
        "certified_execution": execution,
        "certified_source_commit": source_commit,
        "certified_ci_run_id": run_id,
        "certified_source_code_fingerprint_sha256": fp["sha256"],
        "certified_regression_junit": junit.name,
        "certified_regression_junit_sha256": sha256_file(junit),
        "certified_regression_tests": regression["tests"],
        "certified_regression_failures": regression["failures"],
        "certified_regression_errors": regression["errors"],
        "certified_regression_skipped": regression["skipped"],
        "certified_regression": {
            "junit_file": junit.name, "junit_sha256": sha256_file(junit),
            "tests": regression["tests"], "failures": regression["failures"],
            "errors": regression["errors"], "skipped": regression["skipped"],
            "status": regression["status"],
        },
    })
    authority["sha256"] = _sha256_json(authority)
    authority_path.write_text(json.dumps(authority, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cert = write(root)
    verify_product_certification(root / ARTIFACTS[2], root=root, require_current_code=True)

    write_acquisition_manifest(root)
    governance = evaluate_governance(root)
    if governance.get("status") != "PASS":
        raise RuntimeError(f"supervisory agent governance failed: {governance.get('checks')}")
    (root / ARTIFACTS[3]).write_text(json.dumps(governance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verify_governance(root)

    red_team_path = root / ARTIFACTS[6]
    try:
        verify_latest_report(red_team_path, root)
    except ValueError:
        report = run_red_team_suite(root)
        if report["status"] != "PASS":
            raise RuntimeError(f"continuous Red Team scenarios failed: {report['failed']}")
        write_red_team_report(report, red_team_path)
        verify_latest_report(red_team_path, root)

    proof_path = root / ARTIFACTS[4]
    previous_proof = json.loads(proof_path.read_text(encoding="utf-8-sig"))
    coverage_specs = [(row["report_file"], row["source_key"]) for row in previous_proof["coverage"]]
    gate_path = root / ARTIFACTS[5]
    gate = json.loads(gate_path.read_text(encoding="utf-8-sig"))
    global_proof = build_global_integrity_proof(root, gate, junit, coverage_specs)
    proof_path.write_text(json.dumps(global_proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gate["global_integrity"] = {"file": proof_path.name, "sha256": sha256_file(proof_path)}
    gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verify_global_integrity(root, gate_path, proof_path)

    freshness = audit_authority_freshness(root)
    if freshness["status"] != "PASS":
        raise RuntimeError(f"current operational authorities are stale: {freshness['authorities']}")
    startup = reconcile_startup(root, include_authority_freshness=True)
    if startup["status"] != "OK":
        raise RuntimeError(f"operator startup requires recovery: {startup['failed_checks']}")
    return {"status": cert["status"], "tests": regression["tests"],
            "source_commit": source_commit, "ci_run_id": run_id,
            "execution": execution,
            "junit_sha256": sha256_file(junit), "certification_sha256": cert["sha256"],
            "governance_sha256": governance["sha256"],
            "global_integrity_sha256": global_proof["sha256"],
            "operator_startup": startup["status"]}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--execution-id", required=True)
    args = parser.parse_args()
    import socket
    result = refresh(Path.cwd(), args.candidate, args.source_commit,
                     args.execution_id, executor_host=socket.gethostname(),
                     executor_kind="EXTERNAL_GOVERNED_EXECUTOR")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
