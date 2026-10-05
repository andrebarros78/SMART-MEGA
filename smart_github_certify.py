"""Refresh GitHub-native construction certification from a tested Actions commit."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import socket
import uuid
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

ARTIFACTS = (
    "SMART_AUDIT_JUNIT_CURRENT.xml", "SMART_CANONICAL_ROOT.json",
    "SMART_PRODUCT_CERTIFICATION.json", "SMART_AGENT_ECOSYSTEM_GOVERNANCE.json",
    "SMART_GLOBAL_INTEGRITY_PROOF.json", "SMART_3052_IMPLEMENTATION_GATE.json",
    "SMART_P09_RED_TEAM_LATEST.json", "SMART_AGENT_ECOSYSTEM_ACQUISITIONS_20260915.json",
)


def execution_provenance(root: Path, source_commit: str, run_id: str, executor_host: str | None = None) -> dict:
    """Identify the real executor without impersonating a GitHub Actions run."""
    if not isinstance(source_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("invalid tested source commit")
    if executor_host is None:
        if os.environ.get("GITHUB_REPOSITORY") != "andrebarros78/SMART-MEGA":
            raise PermissionError("certification requires canonical GitHub repository")
        if not isinstance(run_id, str) or not run_id.isdecimal() or int(run_id) <= 0:
            raise ValueError("invalid GitHub run identity")
        return {"kind": "GITHUB_ACTIONS", "run_id": run_id}
    if not isinstance(executor_host, str) or executor_host != socket.gethostname():
        raise PermissionError("federated executor hostname does not match this machine")
    try:
        execution_id = str(uuid.UUID(run_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("federated execution requires a UUID") from exc
    if execution_id != run_id:
        raise ValueError("federated execution UUID must be canonical")
    origin = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root,
                            capture_output=True, text=True, check=True, timeout=30).stdout.strip()
    if origin not in {
        "https://github.com/andrebarros78/SMART-MEGA",
        "https://github.com/andrebarros78/SMART-MEGA.git",
        "git@github.com:andrebarros78/SMART-MEGA.git",
        "ssh://git@github.com/andrebarros78/SMART-MEGA.git",
    }:
        raise PermissionError("federated certification requires canonical Git origin")
    return {"kind": "FEDERATED_PC", "execution_id": execution_id, "hostname": executor_host}


def refresh(root: Path, candidate: Path, source_commit: str, run_id: str, *,
            executor_host: str | None = None) -> dict:
    root = root.resolve()
    execution = execution_provenance(root, source_commit, run_id, executor_host)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()
    if head != source_commit:
        raise ValueError("certification source differs from checked-out commit")
    if not candidate.is_file() or candidate.resolve() == (root / ARTIFACTS[0]).resolve():
        raise ValueError("CI JUnit candidate missing or not independent of current proof")

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
        "authority_refresh_reason": "GITHUB_NATIVE_CI_PROVENANCE" if executor_host is None else "FEDERATED_EXECUTION_PROVENANCE",
        "certified_execution": execution,
        "certified_source_commit": source_commit,
        "certified_ci_run_id": run_id if executor_host is None else None,
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
            "source_commit": source_commit, "ci_run_id": run_id if executor_host is None else None,
            "execution": execution,
            "junit_sha256": sha256_file(junit), "certification_sha256": cert["sha256"],
            "governance_sha256": governance["sha256"],
            "global_integrity_sha256": global_proof["sha256"],
            "operator_startup": startup["status"]}


if __name__ == "__main__":
    result = refresh(Path.cwd(), Path("SMART_AUDIT_JUNIT_GITHUB.xml"),
                     os.environ.get("GITHUB_SHA", ""), os.environ.get("GITHUB_RUN_ID", ""))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
