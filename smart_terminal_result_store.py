"""Byte-preserving canonical result store advancement for legacy terminal.

The canonical prefix and through-dataset are checked before any replacement.
The trusted terminal engine owns contest identity, hashing, and proof writes.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def dispatch_result_store(root: Path, binding: dict[str, Any], *, epoch_advance: Callable, canonical_advance: Callable) -> dict[str, Any]:
    """Route to the existing epoch or canonical persistence authority."""
    if binding.get("mode") == "ACTIVE_EPOCH":
        return epoch_advance(root, binding["active"])
    return canonical_advance(root)


def _pending_paths(root: Path, target: int) -> tuple[Path, Path]:
    return (
        root / f".Mega-Sena.{target}.advance-before.xlsx",
        root / f".Mega-Sena.{target}.advance-intent.json",
    )


def _verify_pending(
    *, root: Path, target: int, cutoff: int, canonical: Path, through: Path,
    proof_path: Path, backup: Path, intent_path: Path,
    draw_map: Callable, sha256_file: Callable, read_json: Callable,
) -> dict[str, Any]:
    """Permit recovery only with a verified original and immutable through bytes."""
    if not backup.is_file() or not intent_path.is_file():
        raise ValueError("pending canonical transaction files incomplete or conflicting")
    try:
        record = read_json(intent_path)
        proof = record["proof"]
        before = sha256_file(backup)
        after = sha256_file(through)
        current = sha256_file(canonical)
        if (record.get("schema") != "SMART_CANONICAL_ADVANCE_INTENT_1"
                or record.get("target_contest") != target
                or record.get("cutoff_contest") != cutoff
                or record.get("canonical_sha256_before") != before
                or record.get("official_through_sha256") != after
                or proof.get("target_contest") != target
                or proof.get("canonical_sha256_before") != before
                or proof.get("canonical_sha256_after") != after
                or proof.get("official_through_sha256") != after
                or proof.get("official_through_file") != through.name
                or proof.get("schema") != "SMART_CANONICAL_RESULT_STORE_ADVANCE_1"
                or proof.get("status") != "PASS"
                or proof.get("prefix_preserved") is not True
                or proof.get("retroactive_rewrite") is not False
                or proof.get("canonical_max_after") != target):
            raise ValueError("invalid pending canonical transaction declaration")
        original_draws = draw_map(backup)
        current_draws = draw_map(canonical)
        through_draws = draw_map(through)
        if (not original_draws or max(original_draws) != cutoff
                or not through_draws or max(through_draws) != target
                or any(through_draws.get(k) != v for k, v in original_draws.items())
                or current not in {before, after}
                or (current == before and current_draws != original_draws)
                or (current == after and current_draws != through_draws)):
            raise ValueError("pending canonical transaction sources do not match")
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise ValueError("pending canonical transaction evidence invalid") from exc
    return proof


def advance_canonical_result_store(
    root: Path, *, target: int, cutoff: int,
    result_data: str, result_store_proof: str,
    draw_map: Callable, sha256_file: Callable,
    read_json: Callable, atomic_write_json: Callable,
) -> dict[str, Any]:
    canonical = root / "Mega-Sena.xlsx"
    through = root / result_data
    proof_path = root / result_store_proof
    backup, intent_path = _pending_paths(root, target)
    pending = backup.exists() or intent_path.exists()
    if pending and proof_path.is_file():
        # A crash may occur after proof publication during two-file cleanup.
        # The committed proof and all remaining evidence must still agree.
        proof = read_json(proof_path)
        try:
            if (proof.get("schema") != "SMART_CANONICAL_RESULT_STORE_ADVANCE_1"
                    or proof.get("target_contest") != target
                    or proof.get("status") != "PASS"
                    or proof.get("canonical_sha256_after") != sha256_file(canonical)
                    or proof.get("official_through_sha256") != sha256_file(through)
                    or proof.get("official_through_file") != through.name
                    or proof.get("retroactive_rewrite") is not False
                    or (backup.exists() and (
                        sha256_file(backup) != proof.get("canonical_sha256_before")
                        or any(draw_map(through).get(k) != v
                               for k, v in draw_map(backup).items())
                    ))
                    or (intent_path.exists() and
                        read_json(intent_path).get("proof") != proof)):
                raise ValueError("pending canonical transaction committed cleanup invalid")
        except (KeyError, TypeError, ValueError, OSError) as exc:
            raise ValueError("pending canonical transaction committed cleanup invalid") from exc
        if intent_path.exists():
            intent_path.unlink()
        if backup.exists():
            backup.unlink()
        return proof
    if backup.is_file() and not intent_path.exists() and not proof_path.exists():
        # An interruption before journal publication cannot have replaced the
        # canonical store. Recheck the original bytes before retrying.
        if (sha256_file(backup) != sha256_file(canonical)
                or max(draw_map(canonical)) != cutoff):
            raise ValueError("pending canonical transaction pre-intent backup invalid")
        backup.unlink()
        pending = False

    # A durable, hash-bound pre-advance copy allows restart after process death
    # between the canonical swap and its separate atomic proof write.
    if pending:
        proof = _verify_pending(
            root=root, target=target, cutoff=cutoff, canonical=canonical,
            through=through, proof_path=proof_path, backup=backup,
            intent_path=intent_path, draw_map=draw_map,
            sha256_file=sha256_file, read_json=read_json,
        )
        if sha256_file(canonical) == proof["canonical_sha256_after"]:
            if proof_path.exists():
                if read_json(proof_path) != proof:
                    raise ValueError("pending canonical transaction committed proof differs")
            else:
                atomic_write_json(proof_path, proof)
            intent_path.unlink()
            backup.unlink()
            return proof
        if proof_path.exists():
            raise ValueError("pending canonical transaction has proof without advanced store")
        # The process stopped before replacement. Reuse the verified intent.
    else:
        canonical_draws = draw_map(canonical)
        through_draws = draw_map(through)
        max_current = max(canonical_draws)
        if max(through_draws) != target:
            raise ValueError("official through-dataset does not end at 3054")
        for contest, numbers in canonical_draws.items():
            if through_draws.get(contest) != numbers:
                raise ValueError(f"canonical result prefix mismatch at contest {contest}")
        if max_current == target:
            if canonical_draws != through_draws:
                raise ValueError("already-advanced canonical result store differs from official through-dataset")
            if proof_path.exists():
                return read_json(proof_path)
            raise ValueError("canonical store already advanced without its proof")
        if max_current != cutoff:
            raise ValueError("canonical result store is not at expected pre-advance cutoff")
        before_sha = sha256_file(canonical)
        after_sha = sha256_file(through)
        proof = {
            "schema": "SMART_CANONICAL_RESULT_STORE_ADVANCE_1",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "target_contest": target,
            "canonical_sha256_before": before_sha,
            "canonical_sha256_after": after_sha,
            "official_through_file": through.name,
            "official_through_sha256": after_sha,
            "prefix_preserved": True,
            "canonical_max_after": target,
            "draw_fields_authoritative": True,
            "auxiliary_non_signal_fields_may_be_null_until_later_official_reconciliation": True,
            "retroactive_rewrite": False,
            "status": "PASS",
        }
        # Verify the pre-advance copy before saving the durable intention.
        shutil.copyfile(canonical, backup)
        if sha256_file(backup) != before_sha:
            raise RuntimeError("canonical pre-advance backup verification failed")
        atomic_write_json(intent_path, {
            "schema": "SMART_CANONICAL_ADVANCE_INTENT_1",
            "target_contest": target,
            "cutoff_contest": cutoff,
            "canonical_sha256_before": before_sha,
            "official_through_sha256": after_sha,
            "proof": proof,
        })

    fd, temporary = tempfile.mkstemp(
        prefix=f"Mega-Sena.{target}.", suffix=".tmp.xlsx", dir=root
    )
    os.close(fd)
    temp = Path(temporary)
    try:
        shutil.copyfile(through, temp)
        if (sha256_file(temp) != proof["canonical_sha256_after"]
                or draw_map(temp) != draw_map(through)):
            raise RuntimeError("temporary canonical result store verification failed")
        os.replace(temp, canonical)
    finally:
        if temp.exists():
            temp.unlink()

    atomic_write_json(proof_path, proof)
    intent_path.unlink()
    backup.unlink()
    return proof