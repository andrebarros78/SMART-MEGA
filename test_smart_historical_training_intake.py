from pathlib import Path
import pandas as pd
import pytest

from smart_historical_training_intake import validate


def _good_frame():
    return pd.DataFrame([
        {"Concurso": 1, "Bola1": 1, "Bola2": 2, "Bola3": 3, "Bola4": 4, "Bola5": 5, "Bola6": 6},
        {"Concurso": 2, "Bola1": 7, "Bola2": 8, "Bola3": 9, "Bola4": 10, "Bola5": 11, "Bola6": 12},
    ])


def test_valid_csv(tmp_path: Path):
    path = tmp_path / "mega.csv"
    _good_frame().to_csv(path, index=False)
    result = validate(path)
    assert result["status"] == "PASS"
    assert result["ready_for_shadow_replay"] is True
    assert result["contest_min"] == 1
    assert result["contest_max"] == 2


def test_reject_duplicate_contest(tmp_path: Path):
    df = _good_frame()
    df.loc[1, "Concurso"] = 1
    path = tmp_path / "dup.csv"
    df.to_csv(path, index=False)
    with pytest.raises(ValueError, match="duplicados"):
        validate(path)


def test_reject_repeated_ball(tmp_path: Path):
    df = _good_frame()
    df.loc[0, "Bola6"] = 5
    path = tmp_path / "repeat.csv"
    df.to_csv(path, index=False)
    with pytest.raises(ValueError, match="repetidas"):
        validate(path)


def test_reject_out_of_range(tmp_path: Path):
    df = _good_frame()
    df.loc[0, "Bola6"] = 61
    path = tmp_path / "range.csv"
    df.to_csv(path, index=False)
    with pytest.raises(ValueError, match="fora de 1..60"):
        validate(path)
