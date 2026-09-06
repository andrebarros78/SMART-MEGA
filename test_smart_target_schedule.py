from pathlib import Path

import pytest

from smart_target_schedule import extract_target_from_text, resolve_target_schedule

ROOT = Path(__file__).resolve().parent


def test_extract_target_schedule_requires_unique_dated_line():
    text = """
05/09/2026 sabado 999 1000
06/09/2026 domingo 06098-4 7111 2438 3054 1291 387
08/09/2026 terca-feira 7112 2439 3055 1292
"""
    row = extract_target_from_text(text, 3054)
    assert row["target_date"] == "06/09/2026"
    assert row["weekday"] == "domingo"
    with pytest.raises(ValueError):
        extract_target_from_text("06/09/2026 domingo 3054\n07/09/2026 segunda 3054", 3054)


def test_archived_caixa_cronogram_resolves_3054_to_sunday_06_09_2026():
    doc = resolve_target_schedule(ROOT, 3054)
    assert doc["target_date"] == "06/09/2026"
    assert doc["weekday"].casefold().startswith("domingo")
    assert doc["authority"] == "CAIXA_ARCHIVED_CRONOGRAM_PDF"
    assert doc["result_used"] is False
    assert len(doc["source_sha256"]) == 64
