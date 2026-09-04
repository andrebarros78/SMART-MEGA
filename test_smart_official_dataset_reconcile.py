from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from smart_official_dataset_reconcile import reconcile


def make_source(tmp_path: Path, numbers=None) -> Path:
    values = numbers or [2, 6, 27, 39, 44, 50]
    path = tmp_path / "source.xlsx"
    row = {"Concurso": 3048, "Data do Sorteio": None}
    row.update({f"Bola{i}": value for i, value in enumerate(values, 1)})
    pd.DataFrame([row]).to_excel(path, index=False)
    return path


def fetcher(contest: int):
    return ({
        "numero": contest,
        "dataApuracao": "23/08/2026",
        "listaDezenas": ["02", "06", "27", "39", "44", "50"],
        "acumulado": False,
    }, f"https://official/{contest}")


def test_reconcile_fills_date_and_preserves_numbers(tmp_path):
    output = tmp_path / "out.xlsx"
    proof = tmp_path / "proof.json"
    result = reconcile(make_source(tmp_path), output, proof, fetcher)
    frame = pd.read_excel(output)
    assert result["repaired_count"] == 1
    assert result["remaining_missing_dates"] == 0
    assert pd.to_datetime(frame.iloc[0]["Data do Sorteio"]).strftime("%d/%m/%Y") == "23/08/2026"
    assert frame.iloc[0][[f"Bola{i}" for i in range(1, 7)]].tolist() == [2, 6, 27, 39, 44, 50]


def test_reconcile_rejects_official_number_mismatch(tmp_path):
    with pytest.raises(ValueError, match="official numbers differ"):
        reconcile(make_source(tmp_path, [1, 6, 27, 39, 44, 50]), tmp_path / "out.xlsx", tmp_path / "proof.json", fetcher)


def test_reconcile_refuses_dataset_without_missing_dates(tmp_path):
    source = make_source(tmp_path)
    frame = pd.read_excel(source)
    frame["Data do Sorteio"] = "23/08/2026"
    frame.to_excel(source, index=False)
    with pytest.raises(ValueError, match="no missing"):
        reconcile(source, tmp_path / "out.xlsx", tmp_path / "proof.json", fetcher)


def test_reconcile_input_guards(tmp_path):
    with pytest.raises(ValueError, match="missing"):
        reconcile(tmp_path / "absent.xlsx", tmp_path / "out.xlsx", tmp_path / "proof.json", fetcher)

    source = make_source(tmp_path)
    proof = tmp_path / "exists.json"
    proof.write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError, match="proof"):
        reconcile(source, tmp_path / "out.xlsx", proof, fetcher)

    bad = tmp_path / "bad.xlsx"
    pd.DataFrame([{"Concurso": 3048, "Data do Sorteio": None}]).to_excel(bad, index=False)
    with pytest.raises(ValueError, match="missing columns"):
        reconcile(bad, tmp_path / "out2.xlsx", tmp_path / "proof2.json", fetcher)


def test_reconcile_refuses_output_overwrite(tmp_path):
    source = make_source(tmp_path)
    output = tmp_path / "out.xlsx"
    output.write_text("occupied", encoding="utf-8")
    with pytest.raises(FileExistsError, match="overwrite"):
        reconcile(source, output, tmp_path / "proof.json", fetcher)


def test_reconcile_repairs_multiple_rows(tmp_path):
    source = tmp_path / "source.xlsx"
    rows = []
    for contest in (3048, 3049):
        row = {"Concurso": contest, "Data do Sorteio": None}
        row.update({f"Bola{i}": value for i, value in enumerate([2, 6, 27, 39, 44, 50], 1)})
        rows.append(row)
    pd.DataFrame(rows).to_excel(source, index=False)
    output = tmp_path / "out.xlsx"
    result = reconcile(source, output, tmp_path / "proof.json", fetcher)
    assert result["repaired_count"] == 2
    assert [row["contest"] for row in result["repairs"]] == [3048, 3049]


def test_reconcile_main_cli(tmp_path, monkeypatch, capsys):
    import json
    import smart_official_dataset_reconcile as module

    source = make_source(tmp_path)
    output = tmp_path / "cli.xlsx"
    proof = tmp_path / "cli.json"
    monkeypatch.setattr(module, "fetch_official_payload", fetcher)
    monkeypatch.setattr("sys.argv", ["prog", "--source", str(source), "--out", str(output), "--proof", str(proof)])
    module.main()
    assert json.loads(capsys.readouterr().out)["repaired_count"] == 1
