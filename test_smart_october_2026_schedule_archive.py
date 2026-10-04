from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from smart_target_schedule import extract_target_from_text, sha256_file

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "runtime" / "procedural_sources" / "cronogramas_caixa" / "2026-10.pdf"
EXPECTED_SHA256 = "d8820f270f264c1d5963e84dc5052eb7e9b46d6adaae51281b51d91312f4a26d"


def test_october_2026_caixa_schedule_archive_binds_target_3067() -> None:
    assert ARCHIVE.is_file()
    assert sha256_file(ARCHIVE) == EXPECTED_SHA256
    reader = PdfReader(str(ARCHIVE))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    row = extract_target_from_text(text, 3067)
    assert row["target_date"] == "06/10/2026"
