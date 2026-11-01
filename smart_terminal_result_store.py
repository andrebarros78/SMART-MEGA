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


def advance_canonical_result_store(
    root: Path, *, target: int, cutoff: int,
    result_data: str, result_store_proof: str,
    draw_map: Callable, sha256_file: Callable,
    read_json: Callable, atomic_write_json: Callable,
) -> dict[str, Any]:
    canonical = root / "Mega-Sena.xlsx"
    through = root / result_data
    proof_path = root / result_store_proof
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
    fd, temporary = tempfile.mkstemp(prefix="Mega-Sena.3054.", suffix=".tmp.xlsx", dir=root)
    os.close(fd)
    temp = Path(temporary)
    try:
        shutil.copyfile(through, temp)
        if draw_map(temp) != through_draws:
            raise RuntimeError("temporary canonical result store verification failed")
        os.replace(temp, canonical)
    finally:
        if temp.exists():
            temp.unlink()
    proof = {
        "schema": "SMART_CANONICAL_RESULT_STORE_ADVANCE_1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_contest": target,
        "canonical_sha256_before": before_sha,
        "canonical_sha256_after": sha256_file(canonical),
        "official_through_file": through.name,
        "official_through_sha256": sha256_file(through),
        "prefix_preserved": True,
        "canonical_max_after": target,
        "draw_fields_authoritative": True,
        "auxiliary_non_signal_fields_may_be_null_until_later_official_reconciliation": True,
        "retroactive_rewrite": False,
        "status": "PASS",
    }
    atomic_write_json(proof_path, proof)
    return proof