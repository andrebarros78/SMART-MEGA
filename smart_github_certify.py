"""Refresh GitHub-native construction certification from a tested Actions commit."""
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

ARTIFACTS = ("SMART_AUDIT_JUNIT_CURRENT.xml", "SMART_CANONICAL_ROOT.json", "SMART_PRODUCT_CERTIFICATION.json")


def refresh(root: Path, candidate: Path, source_commit: str, run_id: str) -> dict:
    root = root.resolve()
    if os.environ.get("GITHUB_REPOSITORY") != "andrebarros78/SMART-MEGA":
        raise PermissionError("certification requires canonical GitHub Actions repository")
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit) or not run_id.isdecimal() or int(run_id) <= 0:
        raise ValueError("invalid GitHub source commit/run identity")
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
        "authority_refresh_reason": "GITHUB_NATIVE_CI_PROVENANCE",
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
    return {"status": cert["status"], "tests": regression["tests"],
            "source_commit": source_commit, "ci_run_id": run_id,
            "junit_sha256": sha256_file(junit), "certification_sha256": cert["sha256"]}


if __name__ == "__main__":
    result = refresh(Path.cwd(), Path("SMART_AUDIT_JUNIT_GITHUB.xml"),
                     os.environ.get("GITHUB_SHA", ""), os.environ.get("GITHUB_RUN_ID", ""))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
