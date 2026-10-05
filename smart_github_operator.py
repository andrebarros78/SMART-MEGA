"""Execute one SMART-MEGA operator action on a GitHub-hosted runner.

The repository on main is the only durable operational state. A failed action
never publishes its runner-local changes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

REPOSITORY = "andrebarros78/SMART-MEGA"
READ_ONLY = {"status", "preflight"}
TARGET_ACTIONS = {
    "preflight", "prepare", "withdraw", "recover-missed", "catch-up",
    "authorize-next-cycle", "authorize-generation", "freeze", "adjudicate",
    "post-result-report", "review", "hold", "terminal",
}
ACTIONS = READ_ONLY | TARGET_ACTIONS
PAYLOAD_REQUIRED = {"adjudicate", "review"}
PAYLOAD_OPTION = {
    "adjudicate": "--result-data",
    "review": "--review-file",
    "catch-up": "--payload-file",
}
SUFFIXES = {".json", ".md", ".xml", ".txt", ".xlsx", ".csv", ".pdf", ".log"}
TRANSIENT_IGNORED = (
    "runtime/locks/",
)


def command_args(operation: str, target: str = "", payload: str = "") -> list[str]:
    if operation not in ACTIONS:
        raise ValueError(f"unsupported operation: {operation!r}")
    if operation in TARGET_ACTIONS:
        if not re.fullmatch(r"[1-9][0-9]*", target or ""):
            raise ValueError("a positive integer target is required")
    elif target:
        raise ValueError(f"{operation} does not accept a target")
    if operation in PAYLOAD_REQUIRED and not payload:
        raise ValueError(f"{operation} requires a repository payload path")
    if payload and operation not in PAYLOAD_OPTION:
        raise ValueError(f"{operation} does not accept a payload")
    args = [sys.executable, "smart_operator.py", operation]
    if operation in TARGET_ACTIONS:
        args += ["--through" if operation == "catch-up" else "--target", target]
    if payload:
        args += [PAYLOAD_OPTION[operation], payload]
    return args


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=True, timeout=60
    )
    return result.stdout.strip()


def _git_paths(root: Path, *args: str) -> set[str]:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, check=True, timeout=60
    )
    return {p.decode("utf-8", "surrogateescape") for p in result.stdout.split(b"\0") if p}


def _tracked_payload(root: Path, payload: str) -> None:
    supplied = root / payload
    if supplied.is_symlink():
        raise ValueError("payload must be a regular file in this repository")
    candidate = supplied.resolve()
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("payload must be inside this repository") from exc
    if not candidate.is_file():
        raise ValueError("payload must be a regular file in this repository")
    _git(root, "ls-files", "--error-unmatch", "--", relative.as_posix())


def allowed_artifact(raw: str) -> bool:
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return False
    if len(path.parts) == 1:
        if raw == "Mega-Sena.xlsx":
            return True
        return path.name.startswith("SMART_") and path.suffix.lower() in SUFFIXES
    if path.parts[0] == "SMART_STATE_ARCHIVE":
        return path.suffix.lower() in SUFFIXES | {".bak", ".pre", ".before", ".applied", ".archived", ".retired", ".pre-optimized", ".pre-strict", ".pre-strict-split", ".pre-d018", ".py"}
    return path.parts[0] in {"runtime", "artifacts"} and path.suffix.lower() in SUFFIXES


def _changes(root: Path) -> list[str]:
    paths = _git_paths(root, "diff", "--name-only", "--no-renames", "-z", "HEAD")
    paths |= _git_paths(root, "ls-files", "--others", "--exclude-standard", "-z")
    return sorted(paths)


def _require_no_unpersisted_state(root: Path) -> None:
    ignored = _git_paths(
        root, "ls-files", "--others", "--ignored", "--exclude-standard",
        "-z", "--", "runtime", "SMART_STATE_ARCHIVE",
    )
    material = sorted(
        path for path in ignored
        if not path.startswith(TRANSIENT_IGNORED)
        and not path.endswith((".log", ".pid", ".exit", ".out", ".err", ".tmp"))
    )
    if material:
        raise RuntimeError(f"operator generated ignored state: {material[:20]}")


def _verified_freeze_publication(root: Path, observation: dict, changes: list[str],
                                 target: str) -> dict:
    """Allow a frozen card into main only while its pre-draw window is open."""
    from smart_target_schedule import assert_pre_draw_window

    proof = observation.get("proof")
    if not isinstance(proof, dict) or proof.get("status") != "PASS" or proof.get("result_used") is not False:
        raise ValueError("freeze lacks a valid prospective full-process proof")
    if proof.get("target_contest") != int(target):
        raise ValueError("freeze proof target mismatch")
    card_file = proof.get("primary_card_file")
    if not isinstance(card_file, str) or not allowed_artifact(card_file) or card_file not in changes:
        raise ValueError("frozen primary card is not a new persistent artifact")
    path = (root / card_file).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
        raise ValueError("frozen primary card path is unsafe")
    raw = path.read_bytes()
    file_sha = hashlib.sha256(raw).hexdigest()
    if file_sha != proof.get("primary_card_sha256"):
        raise ValueError("frozen primary card file hash mismatch")
    card = json.loads(raw)
    embedded = dict(card)
    declared = embedded.pop("sha256", None)
    embedded_sha = hashlib.sha256(
        json.dumps(embedded, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if (card != proof.get("primary_card") or declared != embedded_sha
            or card.get("result_used") is not False or card.get("status") != "FROZEN"
            or card.get("freeze_sha256") != proof.get("freeze_sha256")
            or card.get("target_contest") != int(target)
            or card.get("product_role") != "FINAL_SINGLE_CARD_PRODUCT"):
        raise ValueError("frozen primary card/proof binding invalid")
    run_id = card.get("run_id")
    confidence = card.get("confidence")
    if (not isinstance(run_id, str) or not run_id or run_id != run_id.strip()
            or run_id != proof.get("epoch_id")):
        raise ValueError("frozen primary card execution identifier is missing or mismatched")
    if confidence != {"status": "UNPROVEN_PROSPECTIVE", "level": "LOW", "calibrated": False, "probability_six_hits": None, "guaranteed": False}:
        raise ValueError("frozen primary card must expose its unproven joint confidence")
    numbers = card.get("numbers")
    if (not isinstance(numbers, list) or len(numbers) != 6
            or any(type(number) is not int or not 1 <= number <= 60 for number in numbers)
            or len(set(numbers)) != 6):
        raise ValueError("frozen primary card must contain six distinct numbers")
    schedule = proof.get("target_schedule")
    assert_pre_draw_window(schedule)
    return {"numbers": numbers, "file": card_file, "sha256": file_sha, "schedule": schedule,
            "run_id": run_id, "confidence": confidence}


def _pin_artifact_bytes(root: Path, changes: list[str]) -> bool:
    """Keep generated hash-bound files byte-identical after future checkouts."""
    attributes = root / ".gitattributes"
    previous = attributes.read_text(encoding="utf-8") if attributes.is_file() else ""
    lines = previous.splitlines()
    for path in changes:
        candidate = root / path
        if not candidate.is_file():
            continue
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", path):
            raise ValueError(f"artifact cannot be pinned with a safe Git attribute: {path}")
        rule = f"/{path} -text"
        if rule not in lines:
            lines.append(rule)
    updated = ("\n".join(lines) + "\n") if lines else ""
    if updated == previous.replace("\r\n", "\n"):
        return False
    attributes.write_text(updated, encoding="utf-8")
    for path in changes:
        if (root / path).is_file() and not _git(root, "check-attr", "text", "--", path).endswith("text: unset"):
            raise RuntimeError(f"Git is still converting artifact bytes: {path}")
    return True


def _verify_staged_bytes(root: Path, changes: list[str]) -> None:
    for path in changes:
        candidate = root / path
        if not candidate.is_file():
            continue
        staged = subprocess.run(
            ["git", "show", f":{path}"], cwd=root, capture_output=True, check=True, timeout=60
        ).stdout
        if staged != candidate.read_bytes():
            raise RuntimeError(f"staged artifact bytes differ from the hashed file: {path}")


def execute(operation: str, target: str = "", payload: str = "") -> dict:
    root = Path(__file__).resolve().parent
    if Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise RuntimeError("operator must run at the Git top-level")
    if operation not in READ_ONLY and (
        os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
    ):
        raise PermissionError("mutations require explicit dispatch on canonical GitHub main")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise RuntimeError("checkout is dirty before operator action")
    if payload:
        _tracked_payload(root, payload)
    args = command_args(operation, target, payload)
    result = subprocess.run(args, cwd=root, text=True, capture_output=True, check=False, timeout=4800)
    if result.returncode != 0:
        raise RuntimeError(f"operator failed ({result.returncode}): {result.stderr[-3000:]} {result.stdout[-3000:]}")
    try:
        observation = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("operator did not return one JSON document") from exc
    changes = _changes(root)
    _require_no_unpersisted_state(root)
    if operation in READ_ONLY:
        if changes:
            raise RuntimeError(f"read-only operation changed canonical files: {changes[:20]}")
        return {"operation": operation, "target": target or None, "observation": observation, "commit": None}
    if not changes:
        raise RuntimeError("mutating operation returned without any persistent change")
    frozen_card = _verified_freeze_publication(root, observation, changes, target) if operation == "freeze" else None
    rejected = [path for path in changes if not allowed_artifact(path)]
    if rejected:
        raise RuntimeError(f"operator changed non-operational files: {rejected[:20]}")
    for path in changes:
        candidate = root / path
        if candidate.is_symlink() or (candidate.exists() and not candidate.resolve().is_relative_to(root)):
            raise RuntimeError(f"unsafe artifact path: {path}")
    attributes_changed = _pin_artifact_bytes(root, changes)
    staged_expected = set(changes) | ({".gitattributes"} if attributes_changed else set())
    subprocess.run(["git", "add", "--all", "--", *sorted(staged_expected)], cwd=root, check=True)
    # Archived Windows evidence is hash-bound and must retain its CRLF bytes.
    # Accept CR as the line terminator while still rejecting real trailing spaces.
    subprocess.run(
        ["git", "-c", "core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol",
         "diff", "--cached", "--check"], cwd=root, check=True
    )
    staged = _git_paths(root, "diff", "--cached", "--name-only", "--no-renames", "-z")
    if staged != staged_expected:
        raise RuntimeError(f"staged artifact set differs from observed changes: {sorted(staged ^ staged_expected)}")
    _verify_staged_bytes(root, changes)
    commit_msg = f"operation: {operation} contest {target}"
    _git(root, "-c", "user.name=SMART-MEGA GitHub Operator",
         "-c", "user.email=smart-mega-operator@users.noreply.github.com",
         "commit", "-m", commit_msg)
    commit = _git(root, "rev-parse", "HEAD")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise RuntimeError("checkout still contains uncommitted state")
    if frozen_card is not None:
        from smart_target_schedule import assert_pre_draw_window
        assert_pre_draw_window(frozen_card["schedule"])
    _git(root, "push", "origin", "HEAD:main")
    remote = _git(root, "ls-remote", "origin", "refs/heads/main").split()[0]
    if remote != commit:
        raise RuntimeError("remote main does not match the operation commit")
    nested_proof = observation.get("proof")
    observed_status = nested_proof.get("status") if isinstance(nested_proof, dict) else observation.get("status")
    return {"operation": operation, "target": target, "changed_files": sorted(staged_expected),
            "observation_status": observed_status,
            "run_id": frozen_card["run_id"] if frozen_card else observation.get("epoch_id"),
            "primary_card": {key: frozen_card[key] for key in ("numbers", "file", "sha256", "run_id", "confidence")} if frozen_card else None,
            "commit": commit}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", required=True, choices=sorted(ACTIONS))
    parser.add_argument("--target", default="")
    parser.add_argument("--payload", default="")
    args = parser.parse_args()
    try:
        proof = execute(args.operation, args.target, args.payload)
    except Exception as exc:
        error = {
            "erro": "OPERACAO_SMART_MEGA_FALHOU",
            "causa": f"{type(exc).__name__}: {exc}",
            "acao_sugerida": (
                "Consulte o status e corrija a causa antes de repetir a mesma operacao; "
                "nao gere cartao retrospectivo nem altere evidencia historica."
            ),
        }
        print(json.dumps(error, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1
    if args.operation in READ_ONLY:
        observation = proof.pop("observation")
        proof["observation_status"] = observation.get("status")
        proof["active_target"] = (observation.get("active_operation") or {}).get("target_contest")
        proof["reconciled_state"] = (observation.get("reconciled_state") or {}).get("status")
    print(json.dumps(proof, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
