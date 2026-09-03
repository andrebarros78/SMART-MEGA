import pandas as pd
import pytest

from smart_data_quality_gate import audit_draw_file, enforce_draw_quality


def _frame():
    return pd.DataFrame(
        [
            {"Concurso": 1, "Bola1": 1, "Bola2": 2, "Bola3": 3, "Bola4": 4, "Bola5": 5, "Bola6": 6},
            {"Concurso": 2, "Bola1": 7, "Bola2": 8, "Bola3": 9, "Bola4": 10, "Bola5": 11, "Bola6": 12},
        ]
    )


def _save(tmp_path, frame):
    path = tmp_path / "draws.xlsx"
    frame.to_excel(path, index=False)
    return path


def test_valid_file_passes_with_hash(tmp_path):
    path = _save(tmp_path, _frame())
    report = enforce_draw_quality(path, expected_max_contest=2)
    assert report.status == "PASS"
    assert report.row_count == 2
    assert len(report.file_sha256) == 64
    assert all(report.checks.values())


def test_future_contest_is_reported(tmp_path):
    path = _save(tmp_path, _frame())
    report = audit_draw_file(path, expected_max_contest=1)
    assert report.status == "FAIL"
    assert report.future_contest_count == 1
    assert report.checks["cutoff_respected"] is False


def test_duplicate_draw_number_is_reported(tmp_path):
    frame = _frame()
    frame.loc[0, "Bola6"] = 5
    path = _save(tmp_path, frame)
    report = audit_draw_file(path)
    assert report.status == "FAIL"
    assert report.invalid_draw_count == 1
    with pytest.raises(ValueError):
        enforce_draw_quality(path)


def test_duplicate_contest_is_reported(tmp_path):
    frame = _frame()
    frame.loc[1, "Concurso"] = 1
    path = _save(tmp_path, frame)
    report = audit_draw_file(path)
    assert report.status == "FAIL"
    assert report.duplicate_contest_count == 2
    assert report.checks["unique_contests"] is False
