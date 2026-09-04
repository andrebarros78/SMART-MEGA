from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from smart_official_result_ingest import build_extended_frame, validate_official_payload


def payload(contest=3053, numbers=None):
    return {
        "numero": contest,
        "dataApuracao": "03/09/2026",
        "listaDezenas": numbers or ["01", "13", "25", "35", "39", "51"],
        "acumulado": True,
    }


def source_file(tmp_path, last=3052):
    path = tmp_path / "source.xlsx"
    pd.DataFrame([
        {
            "Concurso": last,
            "Data do Sorteio": datetime(2026, 9, 1),
            "Bola1": 16,
            "Bola2": 30,
            "Bola3": 40,
            "Bola4": 47,
            "Bola5": 48,
            "Bola6": 60,
            "Observação": None,
        }
    ]).to_excel(path, index=False)
    return path


def test_validate_official_payload_normalizes_numbers():
    result = validate_official_payload(payload(), 3053)
    assert result["contest"] == 3053
    assert result["numbers"] == [1, 13, 25, 35, 39, 51]
    assert result["draw_date_text"] == "03/09/2026"


@pytest.mark.parametrize("bad", [
    payload(contest=3054),
    payload(numbers=["01", "01", "25", "35", "39", "51"]),
    payload(numbers=["00", "13", "25", "35", "39", "51"]),
    payload(numbers=["01", "13", "25", "35", "39", "61"]),
])
def test_validate_official_payload_rejects_invalid_result(bad):
    with pytest.raises(ValueError):
        validate_official_payload(bad, 3053)


def test_build_extended_frame_appends_exact_target(tmp_path):
    official = validate_official_payload(payload(), 3053)
    frame = build_extended_frame(source_file(tmp_path), 3053, official)
    assert frame["Concurso"].tolist() == [3052, 3053]
    assert frame.iloc[-1][list(f"Bola{i}" for i in range(1, 7))].tolist() == [1, 13, 25, 35, 39, 51]


def test_build_extended_frame_requires_consecutive_cutoff(tmp_path):
    official = validate_official_payload(payload(), 3053)
    with pytest.raises(ValueError, match="target-1"):
        build_extended_frame(source_file(tmp_path, last=3051), 3053, official)


def test_payload_structure_and_integer_validation():
    with pytest.raises(ValueError, match="object"):
        validate_official_payload([], 3053)
    with pytest.raises(ValueError, match="integer"):
        validate_official_payload(payload(contest=True), 3053)
    with pytest.raises(ValueError, match="integer"):
        validate_official_payload(payload(numbers=["1.5", "13", "25", "35", "39", "51"]), 3053)
    malformed = payload()
    malformed["listaDezenas"] = ["1", "2"]
    with pytest.raises(ValueError, match="exactly six"):
        validate_official_payload(malformed, 3053)
    malformed = payload()
    malformed["dataApuracao"] = "2026-09-03"
    with pytest.raises(ValueError, match="DD/MM/YYYY"):
        validate_official_payload(malformed, 3053)


def test_build_extended_frame_rejects_bad_sources(tmp_path):
    official = validate_official_payload(payload(), 3053)
    with pytest.raises(ValueError, match="missing"):
        build_extended_frame(tmp_path / "absent.xlsx", 3053, official)

    missing = tmp_path / "missing.xlsx"
    pd.DataFrame([{"Concurso": 3052}]).to_excel(missing, index=False)
    with pytest.raises(ValueError, match="missing columns"):
        build_extended_frame(missing, 3053, official)

    unordered = tmp_path / "unordered.xlsx"
    rows = []
    for contest in (3052, 3051):
        row = {"Concurso": contest, "Data do Sorteio": datetime(2026, 9, 1)}
        row.update({f"Bola{i}": i for i in range(1, 7)})
        rows.append(row)
    pd.DataFrame(rows).to_excel(unordered, index=False)
    with pytest.raises(ValueError, match="strictly ordered"):
        build_extended_frame(unordered, 3053, official)


def test_fetch_official_payload_uses_validated_response(monkeypatch):
    import smart_official_result_ingest as module

    class Response:
        def raise_for_status(self):
            self.checked = True

        def json(self):
            return payload()

    monkeypatch.setattr(module.requests, "get", lambda *args, **kwargs: Response())
    observed, endpoint = module.fetch_official_payload(3053, timeout=1)
    assert observed["numero"] == 3053
    assert endpoint.endswith("/3053")


def test_ingest_is_atomic_and_refuses_overwrite(tmp_path):
    import json
    from smart_official_result_ingest import ingest

    source = source_file(tmp_path)
    output = tmp_path / "extended.xlsx"
    proof = tmp_path / "proof.json"
    result = ingest(source, output, proof, 3053, payload())
    assert result["row_count"] == 2
    assert result["official_payload_validated"] is True
    assert json.loads(proof.read_text(encoding="utf-8"))["sha256"] == result["sha256"]
    with pytest.raises(FileExistsError, match="proof"):
        ingest(source, tmp_path / "again.xlsx", proof, 3053, payload())

    another_proof = tmp_path / "another.json"
    with pytest.raises(FileExistsError, match="dataset"):
        ingest(source, output, another_proof, 3053, payload())


def test_ingest_fetches_when_payload_is_omitted(tmp_path, monkeypatch):
    import smart_official_result_ingest as module

    monkeypatch.setattr(module, "fetch_official_payload", lambda target: (payload(target), "https://official/test"))
    result = module.ingest(source_file(tmp_path), tmp_path / "out.xlsx", tmp_path / "proof.json", 3053)
    assert result["official_endpoint"] == "https://official/test"


def test_ingest_main_cli(tmp_path, monkeypatch, capsys):
    import json
    import smart_official_result_ingest as module

    monkeypatch.setattr(module, "fetch_official_payload", lambda target: (payload(target), "https://official/test"))
    source = source_file(tmp_path)
    output = tmp_path / "cli.xlsx"
    proof = tmp_path / "cli.json"
    monkeypatch.setattr("sys.argv", ["prog", "--source", str(source), "--target", "3053", "--out", str(output), "--proof", str(proof)])
    module.main()
    assert json.loads(capsys.readouterr().out)["target_contest"] == 3053
