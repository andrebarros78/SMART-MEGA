from __future__ import annotations

import json

import pandas as pd
import pytest

from smart_frontier_adjudicator import adjudicate_frontier
from smart_frontier_signal_lab import CANDIDATES, FREEZE_SCHEMA, sha256_json
from smart_signal_agent import SIGNAL_NAMES
from smart_signal_expansion_governance import SignalExpansionGovernance, write_registry


def fixture_files(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    registry = tmp_path / "registry.json"
    governance = SignalExpansionGovernance(tuple(SIGNAL_NAMES))
    predictions = {}
    for index, (name, family) in enumerate(CANDIDATES.items()):
        governance.register(name, family, 9)
        top6 = [1 + index, 10 + index, 20 + index, 30 + index, 40 + index, 50 + index]
        probabilities = {str(i): 0.1 for i in range(1, 61)}
        predictions[name] = {
            "family": family,
            "top6": top6,
            "probabilities": probabilities,
            "production_authority": False,
        }
    write_registry(registry, governance)

    frontier = {
        "schema": FREEZE_SCHEMA,
        "target_contest": 10,
        "cutoff_contest": 9,
        "candidate_predictions": predictions,
        "production_authority": False,
        "material_weight": 0.0,
        "result_used": False,
    }
    frontier["sha256"] = sha256_json(frontier)
    frontier_path = tmp_path / "frontier.json"
    frontier_path.write_text(json.dumps(frontier), encoding="utf-8")

    main = {
        "target_contest": 10,
        "cutoff_contest": 9,
        "champion": {"top6": [1, 2, 3, 4, 5, 6]},
    }
    main_path = tmp_path / "main.json"
    main_path.write_text(json.dumps(main), encoding="utf-8")

    result = pd.DataFrame([{
        "Concurso": 10,
        "Bola1": 1,
        "Bola2": 10,
        "Bola3": 20,
        "Bola4": 30,
        "Bola5": 40,
        "Bola6": 50,
    }])
    result_path = tmp_path / "result.xlsx"
    result.to_excel(result_path, index=False)
    return frontier_path, main_path, result_path, registry, tmp_path / "ledger.json"


def test_frontier_adjudication_updates_every_candidate_once(tmp_path):
    frontier, main, result, registry, ledger = fixture_files(tmp_path)
    output = adjudicate_frontier(frontier, main, result, 10, registry, ledger)
    assert output["status"] == "FRONTIER_ADJUDICATED"
    assert set(output["candidate_hits"]) == set(CANDIDATES)
    document = json.loads(registry.read_text(encoding="utf-8"))
    assert all(row["total_oos"] == 1 for row in document["candidates"].values())
    assert output["production_switch_performed"] is False


def test_frontier_adjudication_rejects_duplicate(tmp_path):
    frontier, main, result, registry, ledger = fixture_files(tmp_path)
    adjudicate_frontier(frontier, main, result, 10, registry, ledger)
    with pytest.raises(ValueError, match="already adjudicated"):
        adjudicate_frontier(frontier, main, result, 10, registry, ledger)


def rewrite_frontier(path, mutate):
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    document["sha256"] = sha256_json({key: value for key, value in document.items() if key != "sha256"})
    path.write_text(json.dumps(document), encoding="utf-8")


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda d: d.update(schema="bad"), "schema"),
        (lambda d: d.update(target_contest=11), "target/cutoff"),
        (lambda d: d.update(production_authority=True), "shadow-only"),
        (lambda d: d.update(candidate_predictions={}), "candidate set"),
    ],
)
def test_frontier_adjudication_rejects_invalid_freeze(tmp_path, mutate, message):
    frontier, main, result, registry, ledger = fixture_files(tmp_path)
    rewrite_frontier(frontier, mutate)
    with pytest.raises(ValueError, match=message):
        adjudicate_frontier(frontier, main, result, 10, registry, ledger)


def test_frontier_adjudication_rejects_embedded_hash_tamper(tmp_path):
    frontier, main, result, registry, ledger = fixture_files(tmp_path)
    document = json.loads(frontier.read_text(encoding="utf-8"))
    document["target_contest"] = 99
    frontier.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        adjudicate_frontier(frontier, main, result, 10, registry, ledger)


def test_frontier_adjudication_rejects_main_and_result_mismatch(tmp_path):
    frontier, main, result, registry, ledger = fixture_files(tmp_path)
    document = json.loads(main.read_text(encoding="utf-8"))
    document["target_contest"] = 11
    main.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="main freeze"):
        adjudicate_frontier(frontier, main, result, 10, registry, ledger)

    frontier, main, result, registry, ledger = fixture_files(tmp_path / "second")
    frame = pd.read_excel(result)
    frame["Concurso"] = 11
    frame.to_excel(result, index=False)
    with pytest.raises(ValueError, match="exactly once"):
        adjudicate_frontier(frontier, main, result, 10, registry, ledger)


def test_frontier_adjudication_validates_predictions(tmp_path):
    frontier, main, result, registry, ledger = fixture_files(tmp_path)
    name = next(iter(CANDIDATES))
    rewrite_frontier(frontier, lambda d: d["candidate_predictions"][name].update(top6=[1, 1, 2, 3, 4, 5]))
    with pytest.raises(ValueError, match="six unique"):
        adjudicate_frontier(frontier, main, result, 10, registry, ledger)

    frontier, main, result, registry, ledger = fixture_files(tmp_path / "prob")
    rewrite_frontier(frontier, lambda d: d["candidate_predictions"][name].update(probabilities={"1": 0.1}))
    with pytest.raises(ValueError, match="probabilities invalid"):
        adjudicate_frontier(frontier, main, result, 10, registry, ledger)

    frontier, main, result, registry, ledger = fixture_files(tmp_path / "sum")
    probabilities = {str(i): 0.0 for i in range(1, 61)}
    rewrite_frontier(frontier, lambda d: d["candidate_predictions"][name].update(probabilities=probabilities))
    with pytest.raises(ValueError, match="sum to six"):
        adjudicate_frontier(frontier, main, result, 10, registry, ledger)


def test_frontier_ledger_validation_and_cli(tmp_path, monkeypatch, capsys):
    import smart_frontier_adjudicator as module

    frontier, main, result, registry, ledger = fixture_files(tmp_path)
    ledger.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="ledger is invalid"):
        adjudicate_frontier(frontier, main, result, 10, registry, ledger)

    frontier, main, result, registry, ledger = fixture_files(tmp_path / "cli")
    monkeypatch.setattr("sys.argv", [
        "prog", "--freeze", str(frontier), "--main-freeze", str(main),
        "--result-data", str(result), "--target", "10",
        "--registry", str(registry), "--ledger", str(ledger),
    ])
    module.main()
    assert json.loads(capsys.readouterr().out)["status"] == "FRONTIER_ADJUDICATED"
