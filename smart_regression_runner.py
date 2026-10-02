from __future__ import annotations
from smart_canonical_identity import canonical_root

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from smart_platform_lock import lock_nonblocking, unlock

import smart_regression_evidence as evidence

SCHEMA = "SMART_REGRESSION_RUNNER_V3"
CANDIDATE = "SMART_AUDIT_JUNIT_CANDIDATE.xml"
CURRENT = "SMART_AUDIT_JUNIT_CURRENT.xml"
CURRENT_PROOF = "SMART_AUDIT_JUNIT_CURRENT_PROOF.json"
REGRESSION_PROOF_SCHEMA = "SMART_REGRESSION_CODE_BINDING_V1"
LOCK_FILE = ".smart_regression.lock"
CANONICAL_AUTHORITY = "SMART_CANONICAL_ROOT.json"
CRITICAL_NON_SMART_CODE_FILES = ("freeze_next_research.py", "adjudicate_signal_challenger.py")
AUXILIARY_CODE_FILES = ("p14_coverage_plugin.py",)
METADATA_FILES = (
    "requirements.txt",
    "requirements.lock.txt",
    "smart_python.cmd",
    "pytest.ini",
    "SMART_DATA_CONTRACT.md",
)


class _RegressionLockError(RuntimeError):
    """Raised when the canonical regression lock cannot be acquired safely."""


class _RegressionLock:
    def __init__(self, root: Path):
        self.path = root / LOCK_FILE
        self.handle = None

    def __enter__(self):
        self.handle = self.path.open("a+b")
        self.handle.seek(0, os.SEEK_END)
        if self.handle.tell() == 0:
            self.handle.write(b"0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            lock_nonblocking(self.handle)
        except OSError as exc:
            self.handle.close()
            self.handle = None
            raise _RegressionLockError("another SMART regression runner already holds the exclusive lock") from exc
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.handle is not None:
            try:
                self.handle.seek(0)
                unlock(self.handle)
            finally:
                self.handle.close()
                self.handle = None
        return False


def _hash_if_present(path: Path) -> str | None:
    return evidence.sha256_file(path) if path.is_file() else None


def _code_files(root: Path) -> list[Path]:
    files = set(root.glob("smart_*.py")) | set(root.glob("test_*.py"))
    for name in CRITICAL_NON_SMART_CODE_FILES + AUXILIARY_CODE_FILES + METADATA_FILES:
        path = root / name
        if path.is_file():
            files.add(path)
    return sorted((path for path in files if path.is_file()), key=lambda path: path.name.casefold())


def code_fingerprint(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    rows = [{"path": path.name, "sha256": evidence.sha256_file(path)} for path in _code_files(root)]
    raw = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"file_count": len(rows), "files": rows, "sha256": hashlib.sha256(raw).hexdigest()}


def _regression_proof(root: Path, junit_path: Path, regression: dict[str, Any], fingerprint: dict[str, Any]) -> dict[str, Any]:
    doc = {
        "schema": REGRESSION_PROOF_SCHEMA,
        "status": "PASS",
        "junit_file": junit_path.name,
        "junit_sha256": evidence.sha256_file(junit_path),
        "tests": int(regression.get("tests", 0)),
        "failures": int(regression.get("failures", 0)),
        "errors": int(regression.get("errors", 0)),
        "skipped": int(regression.get("skipped", 0)),
        "code_fingerprint": fingerprint,
    }
    raw = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    doc["sha256"] = hashlib.sha256(raw).hexdigest()
    return doc


def _write_regression_proof(root: Path, junit_path: Path, regression: dict[str, Any], fingerprint: dict[str, Any]) -> dict[str, Any]:
    proof = _regression_proof(root, junit_path, regression, fingerprint)
    target = root / CURRENT_PROOF
    temp = root / f".{CURRENT_PROOF}.tmp"
    temp.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, target)
    return proof


def canonical_environment_snapshot(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    authority_path = root / CANONICAL_AUTHORITY
    if not authority_path.is_file():
        return {
            "enforced": False, "ok": True, "authority_present": False,
            "authority_sha256": None, "root_matches": False,
            "legacy_alias": None, "legacy_alias_exists": None,
            "declared_canonical_only": None,
        }
    try:
        authority = json.loads(authority_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {
            "enforced": True, "ok": False, "authority_present": True,
            "authority_sha256": _hash_if_present(authority_path), "root_matches": False,
            "legacy_alias": None, "legacy_alias_exists": None,
            "declared_canonical_only": False,
        }
    declared_root = authority.get("canonical_root")
    try:
        root_matches = isinstance(declared_root, str) and Path(declared_root).resolve() == root
    except Exception:
        root_matches = False
    legacy_alias = authority.get("legacy_alias")
    legacy_exists = None
    if root_matches and isinstance(legacy_alias, str) and legacy_alias:
        try:
            legacy_exists = Path(legacy_alias).exists()
        except OSError:
            legacy_exists = True
    declared_canonical_only = (
        authority.get("canonical_state") == "CANONICAL_ONLY"
        and authority.get("legacy_alias_present") is False
        and authority.get("legacy_alias_type") == "REMOVED"
    )
    enforced = bool(root_matches)
    ok = (not enforced) or (declared_canonical_only and legacy_exists is False)
    return {
        "enforced": enforced, "ok": bool(ok), "authority_present": True,
        "authority_sha256": _hash_if_present(authority_path), "root_matches": bool(root_matches),
        "legacy_alias": legacy_alias, "legacy_alias_exists": legacy_exists,
        "declared_canonical_only": bool(declared_canonical_only),
    }


def _run_regression_locked(root: Path, pytest_args: Sequence[str] | None = None) -> dict[str, Any]:
    candidate = root / CANDIDATE
    current = root / CURRENT
    current_before = _hash_if_present(current)
    code_before = code_fingerprint(root)
    environment_before = canonical_environment_snapshot(root)
    if environment_before.get("enforced") and not environment_before.get("ok"):
        return {
            "schema": SCHEMA, "status": "FAIL",
            "reason": "CANONICAL_ENVIRONMENT_INVALID_BEFORE_REGRESSION",
            "candidate_present": candidate.is_file(), "current_preserved": True,
            "current_sha256": current_before, "code_fingerprint": code_before,
            "canonical_environment_before": environment_before, "promoted": False,
        }

    if candidate.exists():
        candidate.unlink()

    env = os.environ.copy()
    env["PYTHONPATH"] = ""
    env["PYTHONNOUSERSITE"] = "1"
    env["SMART_PYTEST_SANDBOX_ROOTS"] = "1"
    command = [
        sys.executable,
        "-E",
        "-m",
        "pytest",
        "-q",
        f"--junitxml={candidate.name}",
        *(list(pytest_args) if pytest_args is not None else []),
    ]
    completed = subprocess.run(command, cwd=root, check=False, env=env)

    current_after_test = _hash_if_present(current)
    if current_after_test != current_before:
        raise RuntimeError("canonical CURRENT regression evidence changed during candidate execution")

    environment_after = canonical_environment_snapshot(root)
    if environment_after != environment_before or (environment_after.get("enforced") and not environment_after.get("ok")):
        return {
            "schema": SCHEMA, "status": "FAIL",
            "reason": "CANONICAL_ENVIRONMENT_CHANGED_DURING_REGRESSION",
            "pytest_returncode": int(completed.returncode),
            "candidate_present": candidate.is_file(),
            "current_preserved": _hash_if_present(current) == current_before,
            "current_sha256": current_before,
            "code_fingerprint_before": code_before,
            "canonical_environment_before": environment_before,
            "canonical_environment_after": environment_after,
            "promoted": False,
        }

    code_after = code_fingerprint(root)
    code_stable = code_after == code_before
    if not code_stable:
        return {
            "schema": SCHEMA,
            "status": "FAIL",
            "reason": "CODE_CHANGED_DURING_REGRESSION",
            "pytest_returncode": int(completed.returncode),
            "candidate_present": candidate.is_file(),
            "current_preserved": _hash_if_present(current) == current_before,
            "current_sha256": current_before,
            "code_fingerprint_before": code_before,
            "code_fingerprint_after": code_after,
            "promoted": False,
        }

    if not candidate.is_file():
        return {
            "schema": SCHEMA,
            "status": "FAIL",
            "reason": "CANDIDATE_MISSING",
            "pytest_returncode": int(completed.returncode),
            "candidate_present": False,
            "current_preserved": True,
            "current_sha256": current_before,
            "code_fingerprint": code_before,
            "promoted": False,
        }

    candidate_summary = evidence.junit_summary(candidate)
    if completed.returncode != 0 or candidate_summary["status"] != "PASS":
        return {
            "schema": SCHEMA,
            "status": "FAIL",
            "reason": "TEST_FAILURE",
            "pytest_returncode": int(completed.returncode),
            "candidate_present": True,
            "candidate": candidate_summary,
            "current_preserved": _hash_if_present(current) == current_before,
            "current_sha256": current_before,
            "code_fingerprint": code_before,
            "promoted": False,
        }

    promoted = evidence.promote(candidate, current)
    if evidence.sha256_file(current) != promoted["sha256"]:
        raise RuntimeError("promoted CURRENT regression evidence hash mismatch")
    current_summary = evidence.junit_summary(current)
    proof = _write_regression_proof(root, current, current_summary, code_before)

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "pytest_returncode": int(completed.returncode),
        "candidate_present": True,
        "candidate": candidate_summary,
        "current_preserved_during_test": current_after_test == current_before,
        "code_fingerprint_stable": True,
        "code_fingerprint": code_before,
        "canonical_environment_stable": True,
        "canonical_environment": environment_after,
        "isolated_python_environment": True,
        "exclusive_runner_lock": True,
        "promoted": True,
        "promotion": promoted,
        "current_sha256": promoted["sha256"],
        "current_proof_file": CURRENT_PROOF,
        "current_proof_sha256": proof["sha256"],
    }


def run_regression(root: str | Path, pytest_args: Sequence[str] | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    try:
        with _RegressionLock(root):
            return _run_regression_locked(root, pytest_args)
    except _RegressionLockError:
        return {
            "schema": SCHEMA,
            "status": "FAIL",
            "reason": "REGRESSION_ALREADY_RUNNING",
            "candidate_present": (root / CANDIDATE).is_file(),
            "promoted": False,
        }


def main() -> None:
    result = run_regression(canonical_root(), sys.argv[1:])
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
