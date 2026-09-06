from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pypdf import PdfReader

SCHEMA = "SMART_TARGET_SCHEDULE_AUTHORITY_3"
DEFAULT_ARCHIVE = Path("runtime/procedural_sources/cronogramas_caixa")
_DATE_LINE = re.compile(r"^\s*(\d{2}/\d{2}/\d{4})\s+([^\r\n]+)$")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_target_from_text(text: str, target_contest: int) -> dict[str, str]:
    target = str(int(target_contest))
    token = re.compile(rf"(?<!\d){re.escape(target)}(?!\d)")
    matches: list[dict[str, str]] = []
    for raw in str(text).splitlines():
        line = " ".join(raw.split())
        match = _DATE_LINE.match(line)
        if not match or not token.search(line):
            continue
        date_text = match.group(1)
        rest = match.group(2)
        weekday = rest.split()[0] if rest.split() else ""
        matches.append({"target_date": date_text, "weekday": weekday, "source_line": line})
    unique = {(row["target_date"], row["source_line"]): row for row in matches}
    if len(unique) != 1:
        raise ValueError(f"target contest {target_contest} must resolve to exactly one dated cronogram line; matches={len(unique)}")
    return next(iter(unique.values()))


def _previous_contest_date(root: Path, target_contest: int) -> datetime:
    data = root / "Mega-Sena.xlsx"
    if not data.is_file():
        raise FileNotFoundError("canonical Mega-Sena.xlsx is required to bind target schedule to modality sequence")
    frame = pd.read_excel(data)
    required = {"Concurso", "Data do Sorteio"}
    if not required.issubset(frame.columns):
        raise ValueError("canonical Mega-Sena.xlsx lacks Concurso/Data do Sorteio columns")
    contests = pd.to_numeric(frame["Concurso"], errors="raise").astype(int)
    previous = int(target_contest) - 1
    rows = frame.loc[contests == previous, "Data do Sorteio"]
    if len(rows) != 1:
        raise ValueError(f"canonical Mega-Sena previous contest {previous} must occur exactly once")
    value = pd.to_datetime(rows.iloc[0], dayfirst=True, errors="raise")
    return value.to_pydatetime().replace(tzinfo=None)


def resolve_target_schedule(
    root: str | Path,
    target_contest: int,
    archive: str | Path = DEFAULT_ARCHIVE,
) -> dict[str, Any]:
    root = Path(root).resolve()
    archive_path = Path(archive)
    if not archive_path.is_absolute():
        archive_path = (root / archive_path).resolve()
    if not archive_path.is_dir():
        raise FileNotFoundError(f"CAIXA cronogram archive missing: {archive_path}")

    previous_date = _previous_contest_date(root, int(target_contest))
    candidates: list[tuple[Path, dict[str, str], datetime]] = []
    rejected_before_cutoff: list[dict[str, str]] = []
    for pdf in sorted(archive_path.glob("*.pdf"), reverse=True):
        reader = PdfReader(str(pdf))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        try:
            row = extract_target_from_text(text, int(target_contest))
        except ValueError as exc:
            if "matches=0" in str(exc):
                continue
            raise
        row_date = datetime.strptime(row["target_date"], "%d/%m/%Y")
        if row_date <= previous_date:
            rejected_before_cutoff.append({
                "file": str(pdf.relative_to(root)).replace("\\", "/"),
                "target_date": row["target_date"],
                "reason": "NOT_AFTER_PREVIOUS_MEGA_SENA_CONTEST",
            })
            continue
        candidates.append((pdf, row, row_date))

    if not candidates:
        raise ValueError(f"target contest {target_contest} has no archived CAIXA cronogram occurrence after previous Mega-Sena contest date")

    nearest_date = min(row_date for _, _, row_date in candidates)
    nearest = [(pdf, row) for pdf, row, row_date in candidates if row_date == nearest_date]
    schedule_keys = {(row["target_date"], row["weekday"].casefold()) for _, row in nearest}
    if len(schedule_keys) != 1:
        details = [
            {
                "file": str(pdf.relative_to(root)).replace("\\", "/"),
                "target_date": row["target_date"],
                "weekday": row["weekday"],
            }
            for pdf, row in nearest
        ]
        raise ValueError(f"conflicting nearest CAIXA cronogram occurrences for target {target_contest}: {details}")

    pdf, row = nearest[0]
    sources = [
        {
            "file": str(source_pdf.relative_to(root)).replace("\\", "/"),
            "sha256": sha256_file(source_pdf),
            "source_line": source_row["source_line"],
        }
        for source_pdf, source_row in nearest
    ]
    return {
        "schema": SCHEMA,
        "target_contest": int(target_contest),
        "previous_contest": int(target_contest) - 1,
        "previous_contest_date": previous_date.strftime("%d/%m/%Y"),
        "target_date": row["target_date"],
        "weekday": row["weekday"],
        "source_file": sources[0]["file"],
        "source_sha256": sources[0]["sha256"],
        "source_line": row["source_line"],
        "source_count": len(sources),
        "sources": sources,
        "rejected_occurrences_before_cutoff": rejected_before_cutoff,
        "modality_binding": "MEGA_SENA_PREVIOUS_CONTEST_SEQUENCE",
        "schedule_consensus": True,
        "authority": "CAIXA_ARCHIVED_CRONOGRAM_PDF",
        "result_used": False,
    }


__all__ = ["SCHEMA", "DEFAULT_ARCHIVE", "extract_target_from_text", "resolve_target_schedule", "sha256_file"]
