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
        timeout=30,
    )
    if proc.returncode != 0:
        raise RepositoryIntegrityError(
            f"git top-level unavailable: {(proc.stderr or proc.stdout).strip()}"
        )
    return Path(proc.stdout.strip()).resolve()


ROOT = _git_root()


def _safe_relative(relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise RepositoryIntegrityError(f"invalid relative path: {relative!r}")

    normalized = relative.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", normalized) or normalized.startswith(("/", "//")):
        raise RepositoryIntegrityError(f"absolute path forbidden in portable authority: {relative}")

    pure = PurePosixPath(normalized)
    if ".." in pure.parts:
        raise RepositoryIntegrityError(f"path traversal forbidden: {relative}")

    resolved = ROOT.joinpath(*pure.parts).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise RepositoryIntegrityError(f"path escapes repository: {relative}") from exc
    return resolved


def _read_json(relative: str) -> dict[str, Any]:
    path = _safe_relative(relative)
    if not path.is_file():
        raise RepositoryIntegrityError(f"JSON authority missing: {relative}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise RepositoryIntegrityError(f"invalid JSON {relative}: {exc}") from exc
    if not isinstance(value, dict):
        raise RepositoryIntegrityError(f"JSON root must be an object: {relative}")
    return value


def _require_file(label: str, relative: str) -> Path:
    path = _safe_relative(relative)
    if not path.is_file():
        raise RepositoryIntegrityError(f"{label} missing: {relative}")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_raw_hash(label: str, relative: str, expected: str) -> None:
    path = _require_file(label, relative)
    expected = str(expected).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RepositoryIntegrityError(f"{label} invalid expected SHA-256: {expected!r}")
    observed = _sha256(path)
    if observed != expected:
        raise RepositoryIntegrityError(
            f"{label} SHA-256 mismatch: file={relative} expected={expected} observed={observed}"
        )


def _require_frozen_schedule_source(schedule: dict[str, Any], target: int) -> None:
    relative = str(schedule["source_file"])
    expected = str(schedule["source_sha256"]).lower()
    try:
        _require_raw_hash("schedule source", relative, expected)
        return
    except RepositoryIntegrityError as raw_failure:
        # Only the operator's snapshotted AUTHORIZED authority can remain pinned
        # after the same document advances through RESERVED to CONSUMED.
        if relative != "SMART_NEXT_CYCLE_AUTHORITY.json" or schedule.get("authority") != "OPERATOR_SELECTED_TARGET":
            raise raw_failure
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RepositoryIntegrityError("operator schedule source has invalid pinned hash")
    current = _read_json(relative)
    body = {k: v for k, v in current.items() if k != "sha256"}
    actual = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode("utf-8")).hexdigest()
    if (current.get("schema") != "SMART_NEXT_CYCLE_AUTHORITY_1"
            or current.get("sha256") != actual
            or current.get("status") != "CONSUMED"
            or current.get("consumed") is not True
            or current.get("authority_sha256_before_reservation") != expected
            or int(current.get("target_contest", -1)) != target
            or current.get("authorized_by") != "USER_EXPLICIT_APPLY_OR_GENERATE"
            or not current.get("consumption_transaction_id")
            or not current.get("prepared_epoch_id")):
        raise RepositoryIntegrityError("operator schedule consumed-authority lineage invalid")
    receipts = ROOT / "runtime" / "idempotency" / "AUTHORIZE"
    if not receipts.is_dir():
        raise RepositoryIntegrityError("operator schedule authorized receipt archive missing")
    for path in sorted(receipts.glob("*.json")):
        receipt = _read_json(str(path.relative_to(ROOT)))
        if (receipt.get("schema") != "SMART_IDEMPOTENCY_1"
                or receipt.get("operation") != "AUTHORIZE"
                or receipt.get("idempotency_key") != path.stem
                or receipt.get("target") != target):
            continue
        snapshot = receipt.get("result")
        if not isinstance(snapshot, dict) or snapshot.get("sha256") != expected:
            continue
        # operational_lifecycle is receipt metadata, not part of the original
        # authorization's self-hashed bytes.
        signed = {k: v for k, v in snapshot.items() if k not in {"sha256", "operational_lifecycle"}}
        computed = hashlib.sha256(json.dumps(signed, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode("utf-8")).hexdigest()
        if (computed == expected
                and snapshot.get("status") == "AUTHORIZED"
                and snapshot.get("consumed") is False
                and snapshot.get("authorized_by") == current.get("authorized_by")
                and int(snapshot.get("target_contest", -1)) == target
                and all(snapshot.get(k) == current.get(k) for k in
                        ("completed_contest", "review_file", "review_file_sha256", "review_sha256",
                         "canonical_sha256", "authorized_utc"))
                and int(current.get("revision", 0)) > int(snapshot.get("revision", 0))):
            return
    raise RepositoryIntegrityError("operator schedule original authorized snapshot not proven")


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
        path = _require_file("discovery file", relative)
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

    certification_rel = str(epoch["product_certification_file"])
    certification = _read_json(certification_rel)
    if certification.get("project") != "SMART-MEGA":
        raise RepositoryIntegrityError("product certification project mismatch")

    _require_raw_hash("active dataset", str(epoch["data_file"]), str(epoch["data_sha256"]))

    state_paths = epoch.get("state_paths") or {}
    ledger_rel = str(state_paths["ledger"])
    ledger = _read_json(ledger_rel)
    events = ledger.get("events")
    if not isinstance(events, list):
        raise RepositoryIntegrityError("signal ledger events missing")

    freeze = epoch.get("freeze_authority") or {}
    freeze_rel = str(freeze["file"])
    freeze_sha = str(freeze["sha256"]).lower()
    _require_raw_hash("freeze authority", freeze_rel, freeze_sha)
    if int(freeze["target_contest"]) != target or int(freeze["cutoff_contest"]) != cutoff:
        raise RepositoryIntegrityError("freeze authority target/cutoff mismatch")

    freeze_events = [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("event_type") == "FREEZE"
        and int(event.get("target_contest", -1)) == target
    ]
    if not freeze_events:
        raise RepositoryIntegrityError("signal ledger has no FREEZE event for active target")
    if not any(
        not event.get("freeze_sha256")
        or str(event.get("freeze_sha256")).lower() == freeze_sha
        for event in freeze_events
    ):
        raise RepositoryIntegrityError("signal ledger FREEZE event is not bound to active freeze")

    learning = epoch.get("learning_state_authority") or {}
    _require_raw_hash("learning state", str(learning["file"]), str(learning["sha256"]))

    schedule = epoch.get("target_schedule") or {}
    _require_frozen_schedule_source(schedule, target)
    if schedule.get("draw_time_policy_file"):
        _require_file("draw-time policy", str(schedule["draw_time_policy_file"]))
    elif schedule.get("authority") != "OPERATOR_SELECTED_TARGET":
        raise RepositoryIntegrityError("verified schedule missing draw-time policy file")
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
                _require_raw_hash(label, str(prospective[file_key]), str(prospective[sha_key]))
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



def _check_operational_state() -> dict[str, Any]:
    from smart_startup_reconciler import reconcile
    from smart_learning_epoch_reset import verify_active_epoch

    reconciliation = reconcile(ROOT, include_authority_freshness=False)
    if reconciliation["status"] != "OK":
        raise RepositoryIntegrityError(
            f"operational state requires recovery: {reconciliation['failed_checks']}"
        )
    lifecycle = reconciliation["details"]["lifecycle_valid"]
    active_path = ROOT / "SMART_ACTIVE_EPOCH.json"
    if not active_path.is_file():
        return {"schema": lifecycle["schema"],
                "status": f"NO_ACTIVE_EPOCH_{lifecycle['state']}",
                "target_contest": lifecycle.get("target_contest"),
                "cutoff_contest": lifecycle.get("completed_contest"),
                "epoch_id": None}
    epoch = verify_active_epoch(active_path)
    if epoch["status"] == "FROZEN":
        return _check_active_epoch()
    _require_raw_hash("active dataset", str(epoch["data_file"]), str(epoch["data_sha256"]))
    return {key: epoch.get(key) for key in
            ("schema", "status", "target_contest", "cutoff_contest", "epoch_id")}

def validate_repository() -> dict[str, Any]:
    _check_discovery_docs()
    _check_identity_module()
    epoch = _check_operational_state()
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
