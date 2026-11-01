"""Characterization tests for result-data helpers extracted from terminal engine.

These tests exercise format, validation and target binding; they do not create
or certify lottery predictions.
"""
from __future__ import annotations

import pandas as pd
import pytest

from smart_terminal_result_data import (
    contest_max,
    target_events,
    normalize_primary,
    payload_from_normalized,
    consensus_rank,
    draw_map,
)

BALL_COLUMNS = tuple(f"Bola{i}" for i in range(1, 7))


def test_contest_max_reads_excel_and_rejects_duplicate(tmp_path):
    path = tmp_path / "draws.xlsx"
    pd.DataFrame({"Concurso": [3071, 3072, 3073]}).to_excel(path, index=False)
    assert contest_max(path) == 3073
    pd.DataFrame({"Concurso": [3071, 3071]}).to_excel(path, index=False)
    with pytest.raises(ValueError, match="duplicate contests"):
        contest_max(path)


def test_contest_max_rejects_empty_excel(tmp_path):
    path = tmp_path / "draws.xlsx"
    pd.DataFrame({"Concurso": []}).to_excel(path, index=False)
    with pytest.raises(ValueError, match="result store is empty"):
        contest_max(path)


def test_target_events_filters_kind_and_dynamic_contest():
    ledger = {"events": [
        {"event_type": "FREEZE", "target_contest": 3078},
        {"event_type": "RESULT", "target_contest": 3078},
        {"event_type": "RESULT", "target_contest": 3077},
        {"event_type": "RESULT", "target_contest": 3078},
    ]}
    actual = target_events(ledger, "RESULT", 3078)
    assert len(actual) == 2
    assert all(x["target_contest"] == 3078 for x in actual)
    assert target_events({}, "RESULT", 3078) == []


def test_normalize_primary_uses_current_target_and_official_validator():
    calls = []
    def validate(payload, target):
        calls.append((payload, target))
        return {"draw_date_text": "01/11/2026", "numbers": [1, 4, 9, 18, 25, 60]}
    payload = {"numero": 3080}
    result = normalize_primary(payload, 3080, validate)
    assert result == {
        "target_contest": 3080, "draw_date": "01/11/2026",
        "numbers": [1, 4, 9, 18, 25, 60],
    }
    assert calls == [(payload, 3080)]


def test_payload_from_normalized_keeps_official_shape_and_zero_padding():
    result = payload_from_normalized(
        {"draw_date": "01/11/2026", "numbers": [1, 9, 10, 25, 48, 60]},
        3080,
    )
    assert result == {
        "numero": 3080, "dataApuracao": "01/11/2026",
        "listaDezenas": ["01", "09", "10", "25", "48", "60"],
        "acumulado": False,
    }


@pytest.mark.parametrize("value,expected", [(True, 2), (False, 1), (1, 1), (None, 1)])
def test_consensus_rank_requires_explicit_boolean_true(value, expected):
    assert consensus_rank({"terminal_source_corroboration_authorized": value}) == expected


def _write_draws(path, rows):
    pd.DataFrame(rows, columns=("Concurso", *BALL_COLUMNS)).to_excel(path, index=False)


def test_draw_map_sorts_dezenas_and_binds_each_concurso(tmp_path):
    path = tmp_path / "history.xlsx"
    _write_draws(path, [
        [3078, 60, 3, 40, 10, 20, 31],
        [3079, 1, 15, 22, 46, 34, 8],
    ])
    assert draw_map(path, BALL_COLUMNS) == {
        3078: (3, 10, 20, 31, 40, 60),
        3079: (1, 8, 15, 22, 34, 46),
    }


@pytest.mark.parametrize("rows,expected", [
    ([[3078, 1, 2, 3, 4, 5, 6], [3078, 7, 8, 9, 10, 11, 12]], "invalid result store draw sequence"),
    ([[3078, 1, 1, 3, 4, 5, 6]], "invalid result store draw sequence"),
])
def test_draw_map_rejects_repeated_contest_or_dezenas(tmp_path, rows, expected):
    path = tmp_path / "history.xlsx"
    _write_draws(path, rows)
    with pytest.raises(ValueError, match=expected):
        draw_map(path, BALL_COLUMNS)


def test_draw_map_rejects_missing_ball_columns(tmp_path):
    path = tmp_path / "history.xlsx"
    pd.DataFrame({"Concurso": [3078], "Bola1": [7]}).to_excel(path, index=False)
    with pytest.raises(ValueError, match="result store draw columns missing"):
        draw_map(path, BALL_COLUMNS)
