from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any


class RepositoryIntegrityError(RuntimeError):
    pass


def _git_root() -> Path:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RepositoryIntegrityError(
            f"git top-level unavailable: {(proc.stderr or proc.stdout).strip()}"
        )
    return Path(proc.stdout.strip()).resolve()


ROOT = _git_root()


def _read_json(relative: str) -> dict[str, Any]:
    path = _safe_relative(relative)
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise RepositoryIntegrityError(f"invalid JSON {relative}: {exc}") from exc
    if not isinstance(value, dict):
        raise RepositoryIntegrityError(f"JSON root must be an object: {relative}")
    return value


def _safe_relative(relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise RepositoryIntegrityError(f"invalid relative path: {relative!r}")

    normalized = relative.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", normalized) or normalized.startswith(("/", "//")):
        raise RepositoryIntegrityError(f"absolute path forbidden in portable authority: {relative}")

    pure = PurePosixPath(normalized)
    if ".." in pure.parts:
        raise RepositoryIntegrityError(f"path traversal forbidden: {relative}")

    resolved = (ROOT.joinpath(*pure.parts)).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise RepositoryIntegrityError(f"path escapes repository: {relative}") from exc
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_hash(label: str, relative: str, expected: str) -> None:
    path = _safe_relative(relative)
    if not path.is_file():
        raise RepositoryIntegrityError(f"{label} missing: {relative}")
    expected = str(expected).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RepositoryIntegrityError(f"{label} invalid expected SHA-256: {expected!r}")
    observed = _sha256(path)
    if observed != expected:
        raise RepositoryIntegrityError(
            f"{label} SHA-256 mismatch: file={relative} expected={expected} observed={observed}"
        )


def _check_discovery_docs() -> None:
    required_files = (
        "README.md",
        "AGENTS.md",
        "AI_START_HERE.md",
        "SMART_AI_EXECUTION_ENTRYPOINT.md",
        "SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md",
    )
    required_markers = (
        "andrebarros78/SMART-MEGA",
        "SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md",
    )
    forbidden_directives = (
        "CANONICAL_ROOT=`C:\\SMART-MEGA`",
        "CANONICAL_HOST=`DESKTOP-4T6AS9K`",
        "Root canônica: `C:\\SMART-MEGA`",
        "Host canônico: `DESKTOP-4T6AS9K`",
        "Root canônica obrigatória: `C:\\SMART-MEGA`",
        "Host canônico operacional: DESKTOP-4T6AS9K",
    )

    for relative in required_files:
        path = _safe_relative(relative)
        if not path.is_file():
            raise RepositoryIntegrityError(f"discovery file missing: {relative}")
        text = path.read_text(encoding="utf-8-sig")
        for marker in required_markers:
            if marker not in text:
                raise RepositoryIntegrityError(
                    f"GitHub-native marker missing from {relative}: {marker}"
                )
        for directive in forbidden_directives:
            if directive in text:
                raise RepositoryIntegrityError(
                    f"legacy physical identity directive reintroduced in {relative}: {directive}"
                )


def _check_identity_module() -> None:
    from smart_canonical_identity import require_canonical_identity

    evidence = require_canonical_identity(
        ROOT,
        require_host=False,
        require_git=True,
        detect_competitors=False,
    )
    if evidence.get("status") != "PASS":
        raise RepositoryIntegrityError(f"canonical identity failed: {evidence}")
    if evidence.get("portable_identity") is not True:
        raise RepositoryIntegrityError("portable_identity is not true")
    if evidence.get("host_enforced") is not False:
        raise RepositoryIntegrityError("host_enforced must be false")
    git_identity = evidence.get("git_identity") or {}
    if Path(str(git_identity.get("repository_root", ""))).resolve() != ROOT:
        raise RepositoryIntegrityError("canonical identity does not resolve to Git top-level")


def _check_active_epoch() -> dict[str, Any]:
    epoch = _read_json("SMART_ACTIVE_EPOCH.json")

    if epoch.get("schema") != "SMART_ACTIVE_LEARNING_EPOCH_2":
        raise RepositoryIntegrityError(f"unexpected active epoch schema: {epoch.get('schema')}")
    if epoch.get("status") != "FROZEN":
        raise RepositoryIntegrityError(f"active epoch not FROZEN: {epoch.get('status')}")

    target = int(epoch["target_contest"])
    cutoff = int(epoch["cutoff_contest"])
    if target <= cutoff:
        raise RepositoryIntegrityError(f"non-monotonic target/cutoff: {target} <= {cutoff}")

    _require_hash(
        "product certification",
        str(epoch["product_certification_file"]),
        str(epoch["product_certification_sha256"]),
    )
    _require_hash("active dataset", str(epoch["data_file"]), str(epoch["data_sha256"]))

    state_paths = epoch.get("state_paths") or {}
    _require_hash("signal ledger", str(state_paths["ledger"]), str(epoch["ledger_sha256"]))

    freeze = epoch.get("freeze_authority") or {}
    _require_hash("freeze authority", str(freeze["file"]), str(freeze["sha256"]))
    if int(freeze["target_contest"]) != target or int(freeze["cutoff_contest"]) != cutoff:
        raise RepositoryIntegrityError("freeze authority target/cutoff mismatch")

    learning = epoch.get("learning_state_authority") or {}
    _require_hash("learning state", str(learning["file"]), str(learning["sha256"]))

    schedule = epoch.get("target_schedule") or {}
    _require_hash("schedule source", str(schedule["source_file"]), str(schedule["source_sha256"]))
    _require_hash(
        "draw-time policy",
        str(schedule["draw_time_policy_file"]),
        str(schedule["draw_time_policy_sha256"]),
    )
    if int(schedule["target_contest"]) != target:
        raise RepositoryIntegrityError("schedule target mismatch")
    if schedule.get("result_used") is not False:
        raise RepositoryIntegrityError("schedule must remain prospectively result-free")

    prospective = epoch.get("prospective_registration") or {}
    if prospective:
        for label, file_key, sha_key in (
            ("frontier report", "frontier_report_file", "frontier_report_sha256"),
            ("frontier freeze", "frontier_freeze_file", "frontier_freeze_sha256"),
            ("probability ledger", "probability_ledger_file", "probability_ledger_sha256"),
        ):
            if prospective.get(file_key) or prospective.get(sha_key):
                _require_hash(label, str(prospective[file_key]), str(prospective[sha_key]))
        if prospective.get("result_used") is not False:
            raise RepositoryIntegrityError("prospective registration must remain result-free")

    # activation_authority and expansion_registry are reserved lifecycle paths.
    # Their presence is not required merely because state_paths names them.

    return {
        "schema": epoch["schema"],
        "status": epoch["status"],
        "target_contest": target,
        "cutoff_contest": cutoff,
        "epoch_id": epoch.get("epoch_id"),
    }


def validate_repository() -> dict[str, Any]:
    _check_discovery_docs()
    _check_identity_module()
    epoch = _check_active_epoch()
    return {
        "status": "PASS",
        "repository_root": str(ROOT),
        "portable_identity": True,
        "epoch": epoch,
    }


def main() -> int:
    try:
        evidence = validate_repository()
    except Exception as exc:
        print(f"REPOSITORY_INTEGRITY=FAIL\nERROR={exc}")
        return 1

    print("REPOSITORY_INTEGRITY=PASS")
    print(f"ROOT={evidence['repository_root']}")
    print("PORTABLE_IDENTITY=PASS")
    print(f"ACTIVE_EPOCH={evidence['epoch']['epoch_id']}")
    print(f"TARGET={evidence['epoch']['target_contest']}")
    print(f"CUTOFF={evidence['epoch']['cutoff_contest']}")
    print("CANONICAL_RUNTIME_HASHES=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
