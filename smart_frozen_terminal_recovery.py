"""Fail-closed restart gate for terminal history committed before lifecycle advance.

This is NOT permission to skip adjudication or publish a scientific result.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable


def _hash(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def _inside(root: Path, text: Any) -> Path:
    if not isinstance(text, str) or not text or Path(text).is_absolute():
        raise ValueError("recovery evidence path invalid")
    item = root / text
    if item.is_symlink() or not item.resolve().is_relative_to(root):
        raise ValueError("recovery evidence path unsafe")
    return item.resolve()


def verified_frozen_terminal_recovery(
    root: str | Path,
    lifecycle: dict[str, Any],
    active: dict[str, Any] | None,
    *,
    load_ledger: Callable | None = None,
    validate_sequence: Callable | None = None,
) -> bool:
    """Allow exactly FROZEN -> ADJUDICATED resume after committed target data.

    Requires a verified current frozen artifact, complete adjudication+learning
    sequence, exact through-dataset bytes, and a hash-bound result. Does not
    create any authority or relax future contest preparation.
    """
    root = Path(root).resolve()
    if not isinstance(active, dict) or lifecycle.get("state") != "FROZEN":
        return False
    try:
        target = lifecycle.get("target_contest")
        if (type(target) is not int or target <= 1
                or active.get("status") != "FROZEN"
                or active.get("target_contest") != target
                or active.get("cutoff_contest") != target - 1
                or active.get("result_used") is not False):
            return False
        freeze_authority = active.get("freeze_authority") or {}
        freeze_path = _inside(root, freeze_authority.get("file"))
        if (freeze_authority.get("target_contest") != target
                or freeze_authority.get("cutoff_contest") != target - 1
                or not freeze_path.is_file()
                or _hash(freeze_path) != freeze_authority.get("sha256")):
            return False
        state_paths = active.get("state_paths") or {}
        ledger_path = _inside(root, state_paths.get("ledger"))
        through_path = ledger_path.parent / f"Mega-Sena_through_{target}.xlsx"
        canonical = root / "Mega-Sena.xlsx"
        if (canonical.is_symlink() or through_path.is_symlink()
                or not canonical.is_file() or not through_path.is_file()):
            return False
        through_sha = _hash(through_path)
        if _hash(canonical) != through_sha:
            return False
        if load_ledger is None:
            from smart_champion_challenger import load_ledger as load_ledger
        if validate_sequence is None:
            from smart_sequential_prospective_proof import validate_target_sequence as validate_sequence
        ledger = load_ledger(ledger_path)
        sequence = validate_sequence(
            ledger, target, require_learning=True, require_proof=True,
            verify_files=True, root=root,
        )
        if (sequence.get("valid") is not True
                or sequence.get("adjudicated") is not True
                or sequence.get("proof_recorded") is not True
                or sequence.get("active_freeze_sha256") != freeze_authority["sha256"]):
            return False
        events = ledger.get("events", [])
        records = [event for event in events
                   if isinstance(event, dict)
                   and event.get("event_type") == "ADJUDICATION"
                   and event.get("target_contest") == target]
        if len(records) != 1 or records[0].get("result_data_sha256") != through_sha:
            return False
        actual = records[0].get("actual_numbers")
        if (not isinstance(actual, list) or len(actual) != 6
                or any(type(n) is not int or n < 1 or n > 60 for n in actual)
                or len(set(actual)) != 6):
            return False
        receipt = root / f"SMART_CANONICAL_HISTORY_ADVANCE_{target}.json"
        if receipt.exists():
            if receipt.is_symlink() or not receipt.is_file():
                return False
            doc = json.loads(receipt.read_text(encoding="utf-8-sig"))
            body = {k: v for k, v in doc.items() if k != "sha256"}
            signed = hashlib.sha256(json.dumps(
                body, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")).hexdigest()
            if (signed != doc.get("sha256")
                    or doc.get("schema") != "SMART_CANONICAL_HISTORY_ADVANCE_1"
                    or doc.get("target_contest") != target
                    or doc.get("status") not in {"PASS", "ALREADY_CURRENT"}
                    or doc.get("sequence_sha256") != sequence.get("sequence_sha256")
                    or doc.get("retroactive_rewrite") is not False
                    or doc.get("ready_for_next_target") != target + 1):
                return False
            expected = (doc.get("canonical_sha256_after")
                        if doc.get("status") == "PASS"
                        else doc.get("canonical_sha256"))
            if expected != through_sha or doc.get("through_sha256") != through_sha:
                return False
        return True
    except (OSError, ValueError, TypeError, KeyError, AttributeError, json.JSONDecodeError):
        return False
