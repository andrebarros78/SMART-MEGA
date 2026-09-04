import copy
import json

import pytest

import smart_prospective_cycle as pc


def fixtures():
    probabilities = {str(number): 0.1 for number in range(1, 61)}
    freeze = {
        "schema": "SMART_FRONTIER_SHADOW_FREEZE_1",
        "target_contest": 4000,
        "target_date": "10/09/2026",
        "cutoff_contest": 3999,
        "status": "FROZEN_SHADOW_ONLY",
        "frozen_utc": "2026-09-09T10:00:00+00:00",
        "result_used": False,
        "production_authority": False,
        "material_weight": 0.0,
        "candidate_predictions": {
            "candidate": {
                "family": "test",
                "top6": [1, 2, 3, 4, 5, 6],
                "probabilities": probabilities,
            }
        },
    }
    freeze["sha256"] = pc.sha256_json(freeze)
    main = {
        "target_contest": 4000,
        "cutoff_contest": 3999,
        "champion": {"top6": [7, 8, 9, 10, 11, 12]},
        "challenger": {"top6": [13, 14, 15, 16, 17, 18]},
    }
    return freeze, main


def test_registration_retains_all_probabilities_and_hash():
    freeze, main = fixtures()
    entry = pc.build_registration(
        freeze,
        "frontier.json",
        "a" * 64,
        main,
        "main.json",
        "b" * 64,
        registered_at_utc="2026-09-09T11:00:00+00:00",
    )
    assert entry["candidate_count"] == 1
    assert entry["all_60_probabilities_retained"] is True
    assert len(entry["candidate_predictions"]["candidate"]["probabilities"]) == 60
    assert entry["result_used"] is False
    canonical = dict(entry)
    digest = canonical.pop("entry_sha256")
    assert digest == pc.sha256_json(canonical)


def test_registration_rejects_result_use():
    freeze, main = fixtures()
    freeze["result_used"] = True
    freeze["sha256"] = pc.sha256_json(
        {key: value for key, value in freeze.items() if key != "sha256"}
    )
    with pytest.raises(ValueError, match="used target result"):
        pc.build_registration(freeze, "f.json", "a" * 64, main, "m.json", "b" * 64)


def test_registration_rejects_bad_probability_sum():
    freeze, main = fixtures()
    freeze["candidate_predictions"]["candidate"]["probabilities"]["1"] = 0.2
    freeze["sha256"] = pc.sha256_json(
        {key: value for key, value in freeze.items() if key != "sha256"}
    )
    with pytest.raises(ValueError, match="sum to six"):
        pc.build_registration(freeze, "f.json", "a" * 64, main, "m.json", "b" * 64)


def test_register_is_idempotent(tmp_path):
    freeze, main = fixtures()
    frontier_path = tmp_path / "frontier.json"
    main_path = tmp_path / "main.json"
    ledger_path = tmp_path / "ledger.json"
    frontier_path.write_text(json.dumps(freeze), encoding="utf-8")
    main_path.write_text(json.dumps(main), encoding="utf-8")
    first = pc.register(frontier_path, main_path, ledger_path)
    second = pc.register(frontier_path, main_path, ledger_path)
    assert first["entry_sha256"] == second["entry_sha256"]
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert len(ledger["entries"]) == 1
