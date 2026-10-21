from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any

import pandas as pd

from smart_agent_runtime import sha256_file
from smart_champion_challenger import load_ledger
from smart_path_semantics import is_windows_absolute
from smart_sequential_prospective_proof import validate_target_sequence

SCHEMA = "SMART_CANONICAL_HISTORY_ADVANCE_1"
DRAW_COLUMNS = ["Concurso", *[f"Bola{i}" for i in range(1, 7)]]


def _under_root(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {path}") from exc
    return resolved


def _resolve_adjudication_result_evidence(
    root: Path, adjudication: dict[str, Any], epoch_dir: Path, target: int
) -> Path:
    raw = str(adjudication.get("result_data_file", ""))
    declared: Path | None = None
    if is_windows_absolute(raw):
        # A historical event can retain its Windows path while the same
        # immutable epoch workbook is now checked out on a GitHub runner.
        # Match the complete epoch-relative suffix and the committed hash.
        relative = epoch_dir.relative_to(root) / f"Mega-Sena_through_{target}.xlsx"
        suffix = tuple(part.casefold() for part in relative.parts)
        parts = tuple(part.casefold() for part in PureWindowsPath(raw).parts)
        if parts[-len(suffix):] == suffix:
            declared = _under_root(root, root / relative)
    else:
        declared = _under_root(root, root / raw)
    expected = str(adjudication.get("result_data_sha256") or "").lower()
    if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
        raise ValueError("adjudication result evidence missing or hash mismatch")
    if declared is not None and declared.is_file() and sha256_file(declared).lower() == expected:
        return declared

    # The adjudication hash is immutable, while an originally-declared canonical
    # workbook path may later advance. Permit recovery only from the project's
    # immutable archive and only when the archived bytes match the exact hash
    # already committed by the adjudication event. The ledger event itself is
    # never rewritten, preserving learning/proof hash chains.
    archive_root = root / "SMART_STATE_ARCHIVE"
    if archive_root.is_dir():
        candidates = sorted(
            (p for p in archive_root.rglob("*") if p.is_file() and expected in p.name.lower()),
            key=lambda p: str(p).casefold(),
        )
        for candidate in candidates:
            candidate = _under_root(root, candidate)
            if sha256_file(candidate).lower() == expected:
                return candidate
    raise ValueError("adjudication result evidence missing or hash mismatch")


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(fd)
    tmp = Path(raw)
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _contest_sequence(frame: pd.DataFrame) -> list[int]:
    if "Concurso" not in frame.columns:
        raise ValueError("canonical history lacks Concurso column")
    values = pd.to_numeric(frame["Concurso"], errors="raise").astype(int).tolist()
    if len(values) != len(set(values)):
        raise ValueError("history contains duplicate contests")
    if not values or values != list(range(values[0], values[-1] + 1)):
        raise ValueError("history contest sequence is not contiguous")
    return values


def _frames_value_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    left = left.reset_index(drop=True)
    right = right.reset_index(drop=True)
    if left.shape != right.shape or list(left.columns) != list(right.columns):
        return False
    for column in left.columns:
        a = left[column]
        b = right[column]
        if not ((a.eq(b)) | (a.isna() & b.isna())).all():
            return False
    return True


def _core_history_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    left = left.reset_index(drop=True)
    right = right.reset_index(drop=True)
    core = ["Concurso", "Data do Sorteio", *[f"Bola{i}" for i in range(1, 7)]]
    if any(c not in left.columns or c not in right.columns for c in core):
        return False
    if len(left) != len(right):
        return False
    # Normalize contest/balls numerically and draw dates to pandas timestamps.
    for column in ["Concurso", *[f"Bola{i}" for i in range(1, 7)]]:
        a = pd.to_numeric(left[column], errors="raise").astype(int)
        b = pd.to_numeric(right[column], errors="raise").astype(int)
        if not a.equals(b):
            return False
    a_date = pd.to_datetime(left["Data do Sorteio"], errors="raise", format="mixed", dayfirst=True).reset_index(drop=True)
    b_date = pd.to_datetime(right["Data do Sorteio"], errors="raise", format="mixed", dayfirst=True).reset_index(drop=True)
    return a_date.equals(b_date)


def _metadata_enrichment_only(canonical: pd.DataFrame, through: pd.DataFrame) -> bool:
    canonical = canonical.reset_index(drop=True)
    through = through.reset_index(drop=True)
    if canonical.shape != through.shape or list(canonical.columns) != list(through.columns):
        return False
    if not _core_history_equal(canonical, through):
        return False
    core = {"Concurso", "Data do Sorteio", *[f"Bola{i}" for i in range(1, 7)]}
    enriched = False
    for column in canonical.columns:
        if column in core:
            continue
        for current, prior in zip(canonical[column].tolist(), through[column].tolist()):
            current_na = bool(pd.isna(current))
            prior_na = bool(pd.isna(prior))
            if prior_na:
                if not current_na:
                    enriched = True
                continue
            if current_na or current != prior:
                return False
    return enriched


def _numbers(frame: pd.DataFrame, target: int) -> list[int]:
    missing = [c for c in DRAW_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"history missing draw columns: {missing}")
    rows = frame.loc[pd.to_numeric(frame["Concurso"], errors="raise").astype(int) == int(target)]
    if len(rows) != 1:
        raise ValueError(f"target contest {target} must occur exactly once in through-dataset")
    row = rows.iloc[0]
    values = sorted(int(row[f"Bola{i}"]) for i in range(1, 7))
    if len(set(values)) != 6 or values[0] < 1 or values[-1] > 60:
        raise ValueError("target draw numbers invalid")
    return values


def advance_completed_epoch(root: str | Path, active: dict[str, Any]) -> dict[str, Any]:
    root = Path(root).resolve()
    if not isinstance(active, dict) or active.get("project") != "SMART-MEGA":
        raise ValueError("active epoch authority invalid")
    target = int(active.get("target_contest", 0))
    if target <= 1:
        raise ValueError("active epoch target invalid")
    state_paths = active.get("state_paths")
    if not isinstance(state_paths, dict) or not state_paths.get("ledger"):
        raise ValueError("active epoch ledger path missing")
    ledger_path = _under_root(root, root / str(state_paths["ledger"]))
    ledger = load_ledger(ledger_path)
    validation = validate_target_sequence(
        ledger, target, require_learning=True, require_proof=True,
        verify_files=True, root=root,
    )
    if validation.get("valid") is not True or validation.get("adjudicated") is not True:
        raise ValueError("active epoch is not a completed prospective attempt")
    adjudications = [
        dict(ev) for ev in ledger.get("events", [])
        if ev.get("event_type") == "ADJUDICATION" and int(ev.get("target_contest", -1)) == target
    ]
    if len(adjudications) != 1:
        raise ValueError("completed epoch requires exactly one adjudication")
    adjudication = adjudications[0]
    actual = sorted(int(x) for x in adjudication.get("actual_numbers", []))
    if len(actual) != 6 or len(set(actual)) != 6 or actual[0] < 1 or actual[-1] > 60:
        raise ValueError("adjudication actual numbers invalid")

    expected_result_sha = str(adjudication.get("result_data_sha256") or "")
    epoch_dir = ledger_path.parent
    result_file = _resolve_adjudication_result_evidence(root, adjudication, epoch_dir, target)

    through = _under_root(root, epoch_dir / f"Mega-Sena_through_{target}.xlsx")
    if not through.is_file():
        raise FileNotFoundError(f"completed epoch through-dataset missing: {through}")
    canonical = root / "Mega-Sena.xlsx"
    if not canonical.is_file():
        raise FileNotFoundError(canonical)

    canonical_frame = pd.read_excel(canonical)
    through_frame = pd.read_excel(through)
    if list(canonical_frame.columns) != list(through_frame.columns):
        raise ValueError("canonical/through column schemas differ")
    canonical_seq = _contest_sequence(canonical_frame)
    through_seq = _contest_sequence(through_frame)
    if through_seq[-1] != target:
        raise ValueError("through-dataset does not end at completed target")
    if through_seq[:-1] != canonical_seq and canonical_seq[-1] != target:
        raise ValueError("canonical history is not the exact through-dataset prefix")
    if _numbers(through_frame, target) != actual:
        raise ValueError("through-dataset target numbers differ from adjudication")

    through_sha = sha256_file(through)
    proof_path = root / f"SMART_CANONICAL_HISTORY_ADVANCE_{target}.json"
    if canonical_seq[-1] == target:
        if canonical_seq != through_seq or not _core_history_equal(canonical_frame, through_frame):
            raise ValueError("already-advanced canonical core draw history differs from completed through-dataset")
        canonical_sha = sha256_file(canonical)
        metadata_enrichment = False
        if canonical_sha != through_sha:
            if not _metadata_enrichment_only(canonical_frame, through_frame):
                raise ValueError("already-advanced canonical history differs from completed through-dataset")
            metadata_enrichment = True
        proof = {
            "schema": SCHEMA,
            "status": "ALREADY_CURRENT",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "target_contest": target,
            "canonical_sha256": canonical_sha,
            "through_sha256": through_sha,
            "sequence_valid": True,
            "core_history_equal": True,
            "canonical_metadata_enrichment_preserved": metadata_enrichment,
            "completed_sequence_required": True,
            "sequence_sha256": validation.get("sequence_sha256"),
            "future_information_used": False,
            "retroactive_rewrite": False,
            "ready_for_next_target": target + 1,
        }
        canonical_doc = json.dumps(proof, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        proof["sha256"] = hashlib.sha256(canonical_doc).hexdigest()
        # The first PASS receipt is immutable: a resumed post-result / catch-up
        # pass may report ALREADY_CURRENT but must not rewrite original proof.
        if proof_path.exists():
            if proof_path.is_symlink() or not proof_path.is_file():
                raise ValueError("existing canonical history advance proof invalid")
            try:
                previous = json.loads(proof_path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError("existing canonical history advance proof invalid") from exc
            if not isinstance(previous, dict):
                raise ValueError("existing canonical history advance proof invalid")
            original_body = {key: value for key, value in previous.items() if key != "sha256"}
            original_sha = hashlib.sha256(json.dumps(
                original_body, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")).hexdigest()
            if (previous.get("sha256") != original_sha
                    or previous.get("schema") != SCHEMA
                    or previous.get("status") not in {"PASS", "ALREADY_CURRENT"}
                    or previous.get("target_contest") != target
                    or previous.get("through_sha256") != through_sha
                    or previous.get("sequence_sha256") != validation.get("sequence_sha256")
                    or previous.get("future_information_used") is not False
                    or previous.get("retroactive_rewrite") is not False
                    or (previous.get("status") == "PASS" and
                        previous.get("canonical_sha256_after") != through_sha)):
                raise ValueError("existing canonical history advance proof invalid")
            proof["existing_proof_preserved"] = True
            proof["persisted_proof_sha256"] = sha256_file(proof_path)
            return proof
        _atomic_json(proof_path, proof)
        return proof

    if not _frames_value_equal(canonical_frame, through_frame.iloc[:-1]):
        raise ValueError("canonical history rows differ from through-dataset prefix")

    before_sha = sha256_file(canonical)
    archive_dir = root / "SMART_STATE_ARCHIVE" / "canonical-result-store"
    archive_dir.mkdir(parents=True, exist_ok=True)
    backup = archive_dir / f"Mega-Sena.{before_sha}.xlsx"
    if not backup.exists():
        # Copy archival bytes independently of shutil.copyfile so backup creation
        # cannot be affected by test/runtime hooks that target the temporary
        # replacement copy below. The backup contract is byte identity, which is
        # verified immediately by SHA-256.
        with canonical.open("rb") as source, backup.open("xb") as backup_target:
            shutil.copyfileobj(source, backup_target)
    if sha256_file(backup) != before_sha:
        raise RuntimeError("canonical history backup hash mismatch")

    fd, raw = tempfile.mkstemp(prefix=f"Mega-Sena.{target}.", suffix=".tmp.xlsx", dir=root)
    os.close(fd)
    tmp = Path(raw)
    try:
        shutil.copyfile(through, tmp)
        # The through frame was already checked against the immutable
        # adjudication and exact canonical prefix. Byte identity proves
        # the temporary copy has the same schema, values and row order,
        # without an unnecessary second Excel parse.
        if sha256_file(tmp) != through_sha:
            raise RuntimeError("temporary canonical history hash mismatch")
        os.replace(tmp, canonical)
    finally:
        tmp.unlink(missing_ok=True)

    after_sha = sha256_file(canonical)
    if after_sha != through_sha:
        raise RuntimeError("canonical history advance hash mismatch")
    # Post-replacement SHA-256 identity to the validated through workbook
    # guarantees the same rows. Re-check the authoritative target without
    # reparsing an identical 3,000+-row Excel workbook.
    if through_seq[-1] != target or _numbers(through_frame, target) != actual:
        raise RuntimeError("canonical history advance postcondition failed")

    proof = {
        "schema": SCHEMA,
        "status": "PASS",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_contest": target,
        "canonical_sha256_before": before_sha,
        "canonical_sha256_after": after_sha,
        "through_file": str(through.relative_to(root)).replace("\\", "/"),
        "through_sha256": through_sha,
        "source_epoch_ledger": str(ledger_path.relative_to(root)).replace("\\", "/"),
        "source_epoch_ledger_sha256": sha256_file(ledger_path),
        "result_file": str(result_file.relative_to(root)).replace("\\", "/"),
        "result_file_sha256": expected_result_sha,
        "actual_numbers": actual,
        "canonical_backup": str(backup.relative_to(root)).replace("\\", "/"),
        "canonical_prefix_preserved": True,
        "completed_sequence_required": True,
        "sequence_sha256": validation.get("sequence_sha256"),
        "future_information_used": False,
        "retroactive_rewrite": False,
        "canonical_max_after": target,
        "ready_for_next_target": target + 1,
    }
    canonical_doc = json.dumps(proof, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    proof["sha256"] = hashlib.sha256(canonical_doc).hexdigest()
    _atomic_json(proof_path, proof)
    return proof


__all__ = ["SCHEMA", "advance_completed_epoch"]
