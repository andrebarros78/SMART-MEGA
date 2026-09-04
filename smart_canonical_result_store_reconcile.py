from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from smart_v2_engine import load_draws

SCHEMA = "SMART_CANONICAL_RESULT_STORE_RECONCILIATION_V1"
DRAW_COLUMNS = ["Concurso", *[f"Bola{i}" for i in range(1, 7)]]
EXPECTED_SOURCE_SHA256 = "287afcdb89ba822c6e4acc848a80583a17653d646581d2a582cad3abc1947c60"
EXPECTED_FREEZE_SHA256 = "503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816"
EXPECTED_CUTOFF = 3053


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalized_draws(df: pd.DataFrame) -> dict[int, tuple[int, ...]]:
    missing = [column for column in DRAW_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"missing draw columns: {missing}")
    out: dict[int, tuple[int, ...]] = {}
    for _, row in df[DRAW_COLUMNS].iterrows():
        contest = int(row["Concurso"])
        if contest in out:
            raise ValueError(f"duplicate contest {contest}")
        numbers = tuple(sorted(int(row[f"Bola{i}"]) for i in range(1, 7)))
        if len(set(numbers)) != 6 or numbers[0] < 1 or numbers[-1] > 60:
            raise ValueError(f"invalid draw at contest {contest}")
        out[contest] = numbers
    return out


def build_plan(canonical_path: Path, source_path: Path, cutoff: int = EXPECTED_CUTOFF) -> dict[str, Any]:
    canonical_path = Path(canonical_path)
    source_path = Path(source_path)
    canonical = pd.read_excel(canonical_path)
    source = pd.read_excel(source_path)
    if list(canonical.columns) != list(source.columns):
        raise ValueError("canonical/source column schemas differ")

    canonical_draws = _normalized_draws(canonical)
    source_draws = _normalized_draws(source)
    if not canonical_draws or not source_draws:
        raise ValueError("empty canonical/source dataset")
    current_max = max(canonical_draws)
    source_max = max(source_draws)
    if source_max != int(cutoff):
        raise ValueError("source dataset does not end exactly at requested cutoff")
    if sorted(canonical_draws) != list(range(min(canonical_draws), current_max + 1)):
        raise ValueError("canonical contest sequence already contains gaps")
    if sorted(source_draws) != list(range(min(source_draws), source_max + 1)):
        raise ValueError("source contest sequence contains gaps")
    if min(canonical_draws) != min(source_draws):
        raise ValueError("canonical/source starting contests differ")
    if current_max > cutoff:
        raise ValueError("canonical dataset contains future contest beyond requested cutoff")

    mismatches = [
        contest for contest in canonical_draws
        if source_draws.get(contest) != canonical_draws[contest]
    ]
    if mismatches:
        raise ValueError(f"canonical/source draw prefix mismatch at contests {mismatches[:10]}")

    missing = list(range(current_max + 1, cutoff + 1))
    if any(contest not in source_draws for contest in missing):
        raise ValueError("source does not contain every required missing contest")

    return {
        "schema": SCHEMA,
        "canonical_file": canonical_path.name,
        "source_file": source_path.name,
        "canonical_sha256_before": sha256_file(canonical_path),
        "source_sha256": sha256_file(source_path),
        "canonical_rows_before": len(canonical),
        "canonical_max_before": current_max,
        "source_rows": len(source),
        "source_max": source_max,
        "cutoff": int(cutoff),
        "prefix_draw_mismatch_count": 0,
        "missing_contests": missing,
        "append_count": len(missing),
        "status": "READY" if missing else "ALREADY_CURRENT",
    }


def reconcile(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    canonical_path = root / "Mega-Sena.xlsx"
    source_path = root / "Mega-Sena_through_3053_v2.xlsx"
    freeze_path = root / "SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json"
    official_proof_path = root / "SMART_DATASET_RECONCILIATION_3053_PROOF.json"
    proof_path = root / "SMART_CANONICAL_RESULT_STORE_RECONCILIATION_3053.json"

    source_sha = sha256_file(source_path)
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise ValueError("scientific source hash differs from reconciled 3053 authority")
    freeze_before = sha256_file(freeze_path)
    if freeze_before != EXPECTED_FREEZE_SHA256:
        raise ValueError("3054 freeze hash differs from immutable authority")
    official_proof = json.loads(official_proof_path.read_text(encoding="utf-8-sig"))
    if official_proof.get("output_sha256") != source_sha or official_proof.get("official_numbers_cross_checked") is not True:
        raise ValueError("3053 reconciliation proof does not authorize the source dataset")

    plan = build_plan(canonical_path, source_path, EXPECTED_CUTOFF)
    canonical_before_sha = plan["canonical_sha256_before"]
    if plan["status"] == "READY":
        canonical = pd.read_excel(canonical_path)
        source = pd.read_excel(source_path)
        additions = source[source["Concurso"].astype(int).isin(plan["missing_contests"])].copy()
        additions = additions.sort_values("Concurso")
        merged = pd.concat([canonical, additions], ignore_index=True)
        merged = merged.sort_values("Concurso").reset_index(drop=True)

        temp_path = canonical_path.with_suffix(".reconcile.tmp.xlsx")
        backup_path = canonical_path.with_suffix(".reconcile.backup.xlsx")
        try:
            shutil.copy2(canonical_path, backup_path)
            merged.to_excel(temp_path, index=False)
            _, contests = load_draws(temp_path)
            contests_list = [int(x) for x in contests]
            if contests_list[-1] != EXPECTED_CUTOFF:
                raise ValueError("reconciled canonical data does not end at cutoff")
            if contests_list != list(range(contests_list[0], EXPECTED_CUTOFF + 1)):
                raise ValueError("reconciled canonical data is not contiguous")
            os.replace(temp_path, canonical_path)
        except Exception:
            if backup_path.exists():
                os.replace(backup_path, canonical_path)
            if temp_path.exists():
                temp_path.unlink()
            raise
        else:
            if backup_path.exists():
                backup_path.unlink()
            if temp_path.exists():
                temp_path.unlink()

    _, contests_after = load_draws(canonical_path)
    contests_after_list = [int(x) for x in contests_after]
    freeze_after = sha256_file(freeze_path)
    if freeze_after != freeze_before:
        raise RuntimeError("3054 freeze changed during canonical result-store reconciliation")

    proof = {
        **plan,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "official_source_proof": official_proof_path.name,
        "official_source_proof_sha256": sha256_file(official_proof_path),
        "canonical_sha256_after": sha256_file(canonical_path),
        "canonical_rows_after": len(contests_after_list),
        "canonical_max_after": max(contests_after_list),
        "canonical_contiguous_through_cutoff": contests_after_list == list(range(contests_after_list[0], EXPECTED_CUTOFF + 1)),
        "freeze_3054_sha256_before": freeze_before,
        "freeze_3054_sha256_after": freeze_after,
        "freeze_3054_unchanged": freeze_after == freeze_before,
        "result_store_ready_for_next_contest": max(contests_after_list) == EXPECTED_CUTOFF,
        "canonical_before_preserved_as_prefix": True,
        "future_information_used": False,
        "terminal_6of6_proven": False,
        "final_status": "PASS",
    }
    if canonical_before_sha == proof["canonical_sha256_after"] and plan["append_count"]:
        raise RuntimeError("expected reconciliation changed no bytes")
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return proof


if __name__ == "__main__":
    import sys

    project_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    result = reconcile(project_root)
    print(json.dumps({
        "status": result["final_status"],
        "before": result["canonical_max_before"],
        "after": result["canonical_max_after"],
        "appended": result["append_count"],
        "freeze_unchanged": result["freeze_3054_unchanged"],
    }, ensure_ascii=False))
