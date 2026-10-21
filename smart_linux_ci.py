"""SMART-MEGA regression on governed Linux without GitHub Actions or pip installs.

An isolated checkout is required. Reuses the repository's canonical
smart_regression_runner for the *full* gate; a focused gate is explicitly
non-certifying. All evidence is create-only and stored outside the worktree.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
import uuid
from typing import Any, Callable

SCHEMA = "SMART_LINUX_CI_EXECUTION_1"
REPOSITORY = "andrebarros78/SMART-MEGA"
EXPECTED_ORIGINS = {
    "https://github.com/andrebarros78/SMART-MEGA",
    "https://github.com/andrebarros78/SMART-MEGA.git",
    "git@github.com:andrebarros78/SMART-MEGA.git",
    "ssh://git@github.com/andrebarros78/SMART-MEGA.git",
}
FOCUSED_MODULES = (
    "test_smart_contingency_card",
    "test_smart_scoped_history_gate",
    "test_smart_frozen_terminal_recovery",
    "test_smart_terminal_pending_idempotency",
    "test_smart_operator_complete_result",
    "test_smart_terminal_degraded_audit_execution",
    "test_smart_linux_ci",
    "test_smart_linux_certification_provenance",
    "test_smart_frozen_card_reader",
    "test_smart_cycle_completion",
    "test_smart_cycle_wiring",
    "test_smart_portal_transcription_recovery",
    "test_smart_public_result_capture",
    "test_smart_result_transport_provenance",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_receipt(doc: dict[str, Any]) -> dict[str, Any]:
    signed = dict(doc)
    signed.pop("sha256", None)
    signed["sha256"] = _sha(_canonical(signed))
    return signed


def verify_receipt(doc: dict[str, Any]) -> bool:
    if not isinstance(doc, dict) or not isinstance(doc.get("sha256"), str):
        return False
    return sign_receipt(doc)["sha256"] == doc["sha256"]


def read_lock(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9][A-Za-z0-9_.+!-]*)", line)
        if match is None:
            raise ValueError("dependency not pinned in lock: " + line[:100])
        name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
        if name in result:
            raise ValueError("duplicate dependency in lock: " + name)
        result[name] = match.group(2)
    if not result:
        raise ValueError("locked dependencies missing")
    return result


def installed_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def missing_packages(dependencies: dict[str, str], *,
                     installed: Callable[[str], str | None] = installed_version) -> list[str]:
    return sorted(f"{name}=={version}" for name, version in dependencies.items()
                  if installed(name) != version)


def check_full_dependencies(root: Path, *,
                            installed: Callable[[str], str | None] = installed_version) -> dict[str, Any]:
    requirements = root / "requirements.lock.txt"
    expected = read_lock(requirements)
    missing = missing_packages(expected, installed=installed)
    return {
        "status": "BLOCKED_DEPENDENCIES" if missing else "PASS",
        "expected_count": len(expected),
        "lock_sha256": _sha(requirements.read_bytes()),
        "missing": missing,
        "installed_count": len(expected) - len(missing),
    }


def interpret_focused(returncode: int, text: str, *, min_tests: int = 42) -> dict[str, Any]:
    match = re.search(r"Ran ([0-9]+) tests? in ", text)
    tested = int(match.group(1)) if match else 0
    return {"status": "PASS" if returncode == 0 and tested >= min_tests and
            re.search(r"(?m)^OK(?:\s|$)", text) else "FAIL",
            "test_count": tested, "min_tests": min_tests, "return_code": returncode}


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          timeout=30, check=True).stdout.strip()


def _verified_identity(root: Path) -> dict[str, Any]:
    head = _git(root, "rev-parse", "HEAD")
    if not re.fullmatch("[0-9a-f]{40}", head):
        raise ValueError("git source HEAD invalid")
    origin = _git(root, "remote", "get-url", "origin")
    if origin not in EXPECTED_ORIGINS:
        raise ValueError("only canonical SMART-MEGA Git origin allowed")
    if _git(root, "status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("execution requires clean, isolated checkout")
    return {"source_commit": head, "source_origin": origin, "checkout_clean": True}


def _syntax_check(root: Path) -> dict[str, Any]:
    raw = subprocess.run(["git", "ls-files", "-z", "--", "*.py"], cwd=root,
                         capture_output=True, check=True, timeout=30).stdout
    names = [p.decode("utf-8") for p in raw.split(b"\0") if p]
    for name in names:
        p = root / name
        with p.open("rb") as file:
            ast.parse(file.read(), filename=name)
    return {"checked_files": len(names), "status": "PASS" if names else "FAIL"}


def write_receipt(directory: Path, receipt: dict[str, Any]) -> Path:
    if not verify_receipt(receipt) or receipt.get("schema") != SCHEMA:
        raise ValueError("invalid signed regression receipt")
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError("receipt directory cannot be a symlink")
    directory.mkdir(parents=True, exist_ok=True)
    key = uuid.uuid4().hex
    path = directory / f"SMART_LINUX_CI_{receipt.get('profile')}_{key}.json"
    with path.open("x", encoding="utf-8") as fd:
        json.dump(receipt, fd, ensure_ascii=False, indent=2, sort_keys=True)
        fd.write("\n")
    if not verify_receipt(json.loads(path.read_text(encoding="utf-8"))):
        raise RuntimeError("regression receipt write integrity failure")
    return path



def baseline_junit_counts(root: Path) -> dict[str, Any] | None:
    """Read the pre-execution JUnit from Git HEAD, never from a mutable path."""
    try:
        import xml.etree.ElementTree as ET
        tracked = subprocess.run(
            ["git", "show", "HEAD:SMART_AUDIT_JUNIT_CURRENT.xml"],
            cwd=root, capture_output=True, check=False, timeout=30,
        )
        if tracked.returncode != 0 or not (0 < len(tracked.stdout) <= 5_000_000):
            return None
        raw = tracked.stdout
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            return None
        root_xml = ET.fromstring(raw)
        if root_xml.tag == "testsuite":
            suites = [root_xml]
        elif root_xml.tag == "testsuites":
            suites = root_xml.findall("testsuite")
        else:
            return None
        if not suites:
            return None
        counts = {
            field: sum(int(suite.attrib.get(field, "0")) for suite in suites)
            for field in ("tests", "failures", "errors", "skipped")
        }
        if counts["tests"] <= 0 or counts["failures"] != 0 or counts["errors"] != 0:
            return None
        return {
            "tests": counts["tests"], "skipped": counts["skipped"],
            "sha256": _sha(raw), "git_revision": "HEAD",
        }
    except (OSError, ValueError, TypeError, TimeoutError, ET.ParseError):
        return None


def verify_full_junit(root: Path, report: dict[str, Any], *, minimum_tests: int = 1, maximum_skipped: int = 0) -> bool:
    """Require the real project's immutable candidate/current JUnit evidence."""
    if not isinstance(report, dict) or report.get("status") != "PASS" or report.get("promoted") is not True:
        return False
    if any(report.get(key) is not True for key in (
        "code_fingerprint_stable",
        "canonical_environment_stable",
        "isolated_python_environment",
        "exclusive_runner_lock",
        "current_preserved_during_test",
    )):
        return False
    candidate = root / "SMART_AUDIT_JUNIT_CANDIDATE.xml"
    current = root / "SMART_AUDIT_JUNIT_CURRENT.xml"
    if candidate.is_symlink() or current.is_symlink() or not candidate.is_file() or not current.is_file():
        return False
    try:
        # The repository's original parser uses defusedxml and checks test counts.
        from smart_regression_evidence import junit_summary
        generated = junit_summary(candidate)
        persisted = junit_summary(current)
    except Exception:
        # Invalid/unreadable third-party JUnit is a failed gate, never an exception-based escape.
        return False
    metadata = report.get("candidate")
    promoted = report.get("promotion")
    if not isinstance(metadata, dict) or not isinstance(promoted, dict):
        return False
    return (
        generated["status"] == "PASS"
        and persisted["status"] == "PASS"
        and generated == persisted
        and type(generated["tests"]) is int and generated["tests"] >= minimum_tests
        and type(generated["skipped"]) is int and generated["skipped"] <= maximum_skipped
        and generated["tests"] == metadata.get("tests")
        and generated["sha256"] == metadata.get("sha256")
        and generated["sha256"] == promoted.get("sha256")
        and generated["sha256"] == report.get("current_sha256")
        and generated["failures"] == 0 and generated["errors"] == 0
    )


def execute(root: Path, profile: str, *, evidence_dir: Path | None = None, certify: bool = False) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    if profile not in {"focused", "full"}:
        raise ValueError("unknown regression profile")
    if certify and profile != "full":
        raise ValueError("certification requires full regression profile")
    provenance = _verified_identity(root)
    evidence_dir = (evidence_dir or root.parent / "SMART-MEGA-V6-CI-ATTESTATIONS").resolve()
    if evidence_dir.is_relative_to(root):
        raise ValueError("receipts must stay outside Git checkout")
    base: dict[str, Any] = {
        "schema": SCHEMA, "profile": profile, "executor": "LMCP_LINUX_VPS",
        "host": socket.gethostname(), "utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0], **provenance,
        "github_actions_required": False, "full_regression_proven": False,
        "scientific_6of6_proven": False, "production_changed": False,
        "certification_requested": certify, "certification_proven": False,
    }
    if profile == "full":
        dependencies = check_full_dependencies(root)
        baseline = baseline_junit_counts(root) if dependencies["status"] == "PASS" else None
        if dependencies["status"] != "PASS":
            base.update({"status": "BLOCKED_DEPENDENCIES", "dependency_gate": dependencies,
                         "test_count": 0, "canonical_junit_promoted": False})
        elif baseline is None:
            base.update({"status": "BLOCKED_BASELINE_EVIDENCE",
                         "test_count": 0, "canonical_junit_promoted": False})
        else:
            base["historical_junit_baseline"] = baseline
            # Original project runner manages exclusive lock, immutable CURRENT
            # and JUnit candidate promotion. Never emulate its result.
            command = [sys.executable, "-E", "-c",
                "import json,sys; from pathlib import Path; from smart_regression_runner import run_regression; "
                "r=run_regression(Path.cwd(), ['-p','no:cacheprovider','--disable-warnings']); "
                "print(json.dumps(r,ensure_ascii=False)); sys.exit(0 if r['status']=='PASS' else 1)"]
            done = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                  timeout=5400, check=False, env={**os.environ,
                                      "PYTHONNOUSERSITE": "1", "PYTHONPATH": ""})
            try:
                summary = json.loads(done.stdout.strip().splitlines()[-1]) if done.stdout.strip() else {}
            except (ValueError, IndexError, TypeError):
                summary = {}
            if not isinstance(summary, dict):
                summary = {}
            passing = done.returncode == 0 and verify_full_junit(
                root, summary, minimum_tests=baseline["tests"],
                maximum_skipped=baseline["skipped"],
            )
            base.update({"status": "PASS" if passing else "FAIL",
                         "canonical_junit_promoted": passing,
                         "full_regression_proven": passing,
                         "test_count": int(summary.get("candidate", {}).get("tests", 0)),
                         "runner": summary,
                         "stderr_sha256": _sha(done.stderr.encode("utf-8")),
                         "stderr_tail": done.stderr[-1000:]})
            if passing and certify:
                # Existing certification routine validates actual JUnit, code
                # fingerprint, governance and global integrity. No mock proof.
                import uuid
                execution_id = str(uuid.uuid4())
                script = (
                    "import json,sys,socket; from pathlib import Path; "
                    "from smart_github_certify import refresh; "
                    "report=refresh(Path.cwd(), Path('SMART_AUDIT_JUNIT_CANDIDATE.xml'), "
                    "sys.argv[1], sys.argv[2], executor_host=socket.gethostname(), "
                    "executor_kind='EXTERNAL_GOVERNED_EXECUTOR'); print(json.dumps(report,ensure_ascii=False))"
                )
                certificate = subprocess.run(
                    [sys.executable, "-E", "-c", script,
                     provenance["source_commit"], execution_id],
                    cwd=root, capture_output=True, text=True, timeout=1800,
                    check=False, env={**os.environ, "PYTHONNOUSERSITE": "1", "PYTHONPATH": ""},
                )
                try:
                    certified = json.loads(certificate.stdout.strip().splitlines()[-1])
                except (json.JSONDecodeError, IndexError):
                    certified = {}
                verified = (certificate.returncode == 0
                            and certified.get("status") == "CONSTRUCTION_PROVEN"
                            and certified.get("source_commit") == provenance["source_commit"]
                            and certified.get("execution", {}).get("kind") == "EXTERNAL_GOVERNED_EXECUTOR"
                            and certified.get("tests") == base["test_count"])
                base.update({
                    "status": "PASS" if verified else "FAIL",
                    "certification_proven": verified,
                    "certification_evidence": certified,
                    "certification_stdout_sha256": _sha(certificate.stdout.encode("utf-8")),
                    "certification_stderr_sha256": _sha(certificate.stderr.encode("utf-8")),
                    "certification_stderr_tail": certificate.stderr[-1500:],
                })
    else:
        syntax = _syntax_check(root)
        command = [sys.executable, "-E", "-m", "unittest", "-q", *FOCUSED_MODULES]
        done = subprocess.run(command, cwd=root, capture_output=True, text=True,
                              timeout=180, check=False,
                              env={**os.environ, "PYTHONNOUSERSITE": "1", "PYTHONPATH": ""})
        result = interpret_focused(done.returncode, done.stderr + "\n" + done.stdout)
        base.update({"status": "PASS" if result["status"] == "PASS"
                     and syntax["status"] == "PASS" else "FAIL",
                     "focused_suite": result, "syntax": syntax,
                     "test_count": result["test_count"],
                     "canonical_junit_promoted": False,
                     "stdout_sha256": _sha(done.stdout.encode("utf-8")),
                     "stderr_sha256": _sha(done.stderr.encode("utf-8")),
                     "stderr_tail": done.stderr[-1000:]})
    signed = sign_receipt(base)
    path = write_receipt(evidence_dir, signed)
    return {"status": base["status"], "profile": profile, "test_count": base["test_count"],
            "receipt": str(path), "sha256": signed["sha256"],
            "full_regression_proven": base["full_regression_proven"]}


def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("--profile", required=True, choices=["focused", "full"])
    cli.add_argument("--root", type=Path, default=Path.cwd())
    cli.add_argument("--evidence-dir", type=Path)
    cli.add_argument("--certify", action="store_true", help="require full regression and complete Linux certification")
    args = cli.parse_args()
    result = execute(args.root, args.profile, evidence_dir=args.evidence_dir, certify=args.certify)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
