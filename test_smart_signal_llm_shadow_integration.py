"""Causal, hash-bound LLM proposal is a real shadow consumer, never a production switch."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from smart_frontier_signal_lab import FrontierState, freeze_shadow, sha256_file, sha256_json
from smart_prospective_cycle import build_registration


def _proposal(path, data_path, *, target=3090, **changes):
    doc = {
        "schema": "SMART_LLM_SHADOW_PROPOSAL_1",
        "target_contest": target,
        "cutoff_contest": target - 1,
        "history_sha256": sha256_file(data_path),
        "generated_utc": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "provider_claim": "ChatGPT",
        "model_claim": "unverified-external-llm",
        "prompt_sha256": "a" * 64,
        "scores": {str(n): (1.0 if n in range(51, 57) else 0.1) for n in range(1, 61)},
        "result_used": False,
        "production_authority": False,
    }
    doc.update(changes)
    doc["sha256"] = sha256_json(doc)
    path.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    return doc


def _freeze(tmp_path, *, candidate=True):
    data = tmp_path / "history.bin"
    data.write_bytes(b"history strictly before target")
    report = tmp_path / "history-report.json"
    report.write_text("{}", encoding="utf-8")
    candidate_path = tmp_path / "SMART_LLM_SHADOW_CANDIDATE_3090.json"
    if candidate:
        _proposal(candidate_path, data)
    state = FrontierState()
    state.update(np.array([1, 2, 3, 4, 5, 6]), 0)
    frontier = freeze_shadow(
        state, data, 3090, "11/11/2026", report,
        tmp_path / "shadow-freeze.json", tmp_path / "registry.json",
        **({"llm_candidate_path": candidate_path} if candidate else {}),
    )
    return frontier


def test_llm_proposal_is_consumed_into_real_prospective_registry(tmp_path):
    frozen = _freeze(tmp_path)
    llm = frozen["candidate_predictions"]["llm_shadow_v1"]
    assert frozen["candidate_count"] == 6
    assert frozen["llm_shadow_input"]["provider_verified"] is False
    assert frozen["llm_shadow_input"]["input_file_sha256"] == sha256_file(
        tmp_path / "SMART_LLM_SHADOW_CANDIDATE_3090.json"
    )
    assert llm["top6"] == [51, 52, 53, 54, 55, 56]
    assert llm["production_authority"] is False
    assert llm["result_used"] is False
    assert llm["probability_sum"] == pytest.approx(6.0)
    assert frozen["material_weight"] == 0.0
    assert frozen["production_authority"] is False
    registry = json.loads((tmp_path / "registry.json").read_text(encoding="utf-8"))
    assert registry["candidate_count"] == 6
    assert registry["candidates"]["llm_shadow_v1"]["material_weight_cap"] == 0.0

    main = {"target_contest": 3090, "cutoff_contest": 3089,
            "champion": {"top6": [1, 2, 3, 4, 5, 6]},
            "challenger": {"top6": [7, 8, 9, 10, 11, 12]}}
    entry = build_registration(
        frozen, "shadow-freeze.json", "b" * 64,
        main, "main-freeze.json", "c" * 64,
    )
    assert entry["candidate_count"] == 6
    assert entry["candidate_predictions"]["llm_shadow_v1"]["top6"] == [51, 52, 53, 54, 55, 56]
    assert entry["llm_shadow"]["provider_verified"] is False
    assert entry["llm_shadow"]["overlap_with_champion"] == 0
    assert entry["llm_shadow"]["effect_on_production_card"] is False
    assert entry["production_switch_performed"] is False


def test_default_freeze_still_has_five_native_shadow_candidates(tmp_path):
    frozen = _freeze(tmp_path, candidate=False)
    assert frozen["candidate_count"] == 5
    assert "llm_shadow_v1" not in frozen["candidate_predictions"]
    assert "llm_shadow_input" not in frozen


@pytest.mark.parametrize("mutations", [
    {"target_contest": 3091},
    {"cutoff_contest": 3088},
    {"history_sha256": "b" * 64},
    {"generated_utc": "2999-01-01T00:00:00+00:00"},
    {"generated_utc": "2026-11-09T09:00:00"},
    {"result_used": True},
    {"production_authority": True},
    {"scores": {str(n): (True if n == 1 else 0.2) for n in range(1, 61)}},
    {"scores": {str(n): 0.2 for n in range(1, 60)}},
])
def test_invalid_or_leaky_llm_proposals_fail_closed_without_freeze(tmp_path, mutations):
    data = tmp_path / "history.bin"
    data.write_bytes(b"causal history")
    proposal_path = tmp_path / "SMART_LLM_SHADOW_CANDIDATE_3090.json"
    _proposal(proposal_path, data, **mutations)
    report = tmp_path / "report.json"
    report.write_text("{}", encoding="utf-8")
    with pytest.raises((ValueError, TypeError)):
        freeze_shadow(
            FrontierState(), data, 3090, "11/11/2026", report,
            tmp_path / "freeze.json", tmp_path / "registry.json",
            llm_candidate_path=proposal_path,
        )
    assert not (tmp_path / "freeze.json").exists()
    assert not (tmp_path / "registry.json").exists()


def test_tampered_self_hash_is_rejected(tmp_path):
    data = tmp_path / "history.bin"
    data.write_bytes(b"causal history")
    proposal_path = tmp_path / "SMART_LLM_SHADOW_CANDIDATE_3090.json"
    doc = _proposal(proposal_path, data)
    doc["scores"]["1"] = 0.9
    proposal_path.write_text(json.dumps(doc), encoding="utf-8")
    report = tmp_path / "report.json"
    report.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        freeze_shadow(
            FrontierState(), data, 3090, None, report,
            tmp_path / "freeze.json", tmp_path / "registry.json",
            llm_candidate_path=proposal_path,
        )



def test_llm_candidate_is_adjudicated_after_official_result_without_production_switch(tmp_path):
    import pandas as pd
    from smart_frontier_adjudicator import adjudicate_frontier

    freeze = _freeze(tmp_path)
    main = {
        "target_contest": 3090, "cutoff_contest": 3089,
        "champion": {"top6": [1, 2, 3, 4, 5, 6]},
    }
    main_path = tmp_path / "main-freeze.json"
    main_path.write_text(json.dumps(main), encoding="utf-8")
    pd.DataFrame([{"Concurso": 3090, **{f"Bola{n}": 50 + n for n in range(1, 7)}}]).to_excel(
        tmp_path / "official-result.xlsx", index=False,
    )
    result = adjudicate_frontier(
        tmp_path / "shadow-freeze.json", main_path,
        tmp_path / "official-result.xlsx", 3090,
        tmp_path / "registry.json", tmp_path / "adjudicated.json",
    )
    assert result["status"] == "FRONTIER_ADJUDICATED"
    assert result["candidate_hits"]["llm_shadow_v1"] == 6
    assert result["champion_hits"] == 0
    assert result["production_switch_performed"] is False
    ledger = json.loads((tmp_path / "adjudicated.json").read_text(encoding="utf-8"))
    evaluation = ledger["events"][0]["evaluations"]["llm_shadow_v1"]
    assert evaluation["delta_hits"] == 6
    assert evaluation["production_authority"] is False
    registry = json.loads((tmp_path / "registry.json").read_text(encoding="utf-8"))
    assert registry["candidates"]["llm_shadow_v1"]["total_oos"] == 1
    assert registry["candidates"]["llm_shadow_v1"]["material_weight_cap"] == 0.0
    with pytest.raises(ValueError, match="already adjudicated"):
        adjudicate_frontier(
            tmp_path / "shadow-freeze.json", main_path,
            tmp_path / "official-result.xlsx", 3090,
            tmp_path / "registry.json", tmp_path / "adjudicated.json",
        )
