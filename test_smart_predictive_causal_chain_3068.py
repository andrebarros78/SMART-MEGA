"""Read-only forensic regression of an existing frozen, adjudicated prediction.

This test is not a forecast for 3068, a fitted model, or evidence of predictive
advantage: its outcome was already known when this diagnostic was written.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

import pytest

from smart_primary_card_selector import select_primary_card


ROOT = Path(__file__).resolve().parent
EPOCH = (ROOT / "SMART_STATE_ARCHIVE" / "adjudicated-epochs" / "3068"
         / "operator-3068-acc6a34c9e27-20261008T222652499219Z" / "epoch")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _document_sha(doc: dict) -> str:
    payload = {k: v for k, v in doc.items() if k != "sha256"}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _frozen() -> tuple[dict, dict, dict]:
    return (
        _read(EPOCH / "SMART_3068_CHAMPION_CHALLENGER_FREEZE.json"),
        _read(EPOCH / "SMART_3068_CHAMPION_CHALLENGER_FREEZE_PORTFOLIO.json"),
        _read(EPOCH / "SMART_3068_PRIMARY_CARD.json"),
    )


def test_frozen_signal_weights_are_actually_consumed_into_sixty_challenger_scores():
    freeze, _portfolio, _primary = _frozen()
    model = freeze["challenger"]
    assert freeze["target_contest"] == 3068 and freeze["cutoff_contest"] == 3067
    assert freeze["frozen_before_result"] is True and freeze["causal_cutoff"] is True
    weights = model["weights"]
    assert len(weights) == 12 and set(weights) == set(model["raw_signals"])
    assert math.isclose(sum(weights.values()), 1.0, rel_tol=0, abs_tol=1e-12)
    assert all(math.isfinite(w) and 0 < w < 1 for w in weights.values())
    for name, weight in weights.items():
        signal = model["raw_signals"][name]
        assert signal["cutoff_contest"] == 3067
        assert signal["target_contest"] == 3068
        assert signal["causal"] is True
        assert math.isclose(model["weight_components"][name]["final_weight"],
                            weight, rel_tol=0, abs_tol=1e-12)
        assert set(map(int, signal["values"])) == set(range(1, 61))

    reconstructed = {
        n: sum(weights[name] * float(signal["values"][str(n)])
               for name, signal in model["raw_signals"].items())
        for n in range(1, 61)
    }
    observed = {int(k): float(v) for k, v in model["aggregate_scores"].items()}
    assert set(observed) == set(reconstructed)
    assert max(abs(observed[n] - reconstructed[n]) for n in observed) < 1e-12
    ranking = sorted(range(1, 61), key=lambda n: (-reconstructed[n], n))
    assert ranking == model["ranking60"]
    assert model["top6"] == ranking[:6]


def test_champion_scores_replay_exact_frozen_card_without_result_or_promotion():
    freeze, portfolio, primary = _frozen()
    freeze_path = EPOCH / "SMART_3068_CHAMPION_CHALLENGER_FREEZE.json"
    portfolio_path = EPOCH / "SMART_3068_CHAMPION_CHALLENGER_FREEZE_PORTFOLIO.json"
    assert portfolio["freeze_sha256"] == _sha(freeze_path)
    assert primary["freeze_sha256"] == portfolio["freeze_sha256"]
    assert primary["portfolio_sha256"] == _sha(portfolio_path)
    assert primary["sha256"] == _document_sha(primary)
    assert primary["status"] == "FROZEN" and primary["result_used"] is False
    assert primary["product_role"] == "FINAL_SINGLE_CARD_PRODUCT"
    assert portfolio["product_role"] == "AUXILIARY_MULTICARD_PORTFOLIO"
    assert primary["confidence"]["calibrated"] is False
    assert primary["confidence"]["probability_six_hits"] is None
    assert freeze["champion_remains_active"] is True
    assert freeze["production_switch_performed"] is False

    scores = freeze["champion"]["aggregate_scores"]
    reconstructed = select_primary_card(scores)
    assert reconstructed["sha256"] == portfolio["primary_card_selector"]["sha256"]
    assert reconstructed["selected_numbers"] == primary["numbers"]
    assert reconstructed["selected_numbers"] == portfolio["primary_card"]["numbers"]
    assert set(primary["numbers"]) == {10, 11, 27, 35, 38, 53}
    assert primary["selector"]["result_used"] is False
    assert primary["false_negative_rescue"]["result_used"] is False
    assert primary["source_head"] == "champion"

    # Engineering-only sensitivity demonstration, not a retrospective selection.
    artificial_scores = dict(scores)
    artificial_scores["59"] = max(map(float, scores.values())) + 100.0
    alternative = select_primary_card(artificial_scores)
    assert alternative["selected_numbers"] != primary["numbers"]
    assert 59 in alternative["selected_numbers"]
    assert _sha(freeze_path) == portfolio["freeze_sha256"]  # immutable input


def test_result_reconciles_once_and_learning_follows_original_freeze():
    freeze, _portfolio, primary = _frozen()
    report = _read(ROOT / "SMART_POST_RESULT_REPORT_3068.json")
    ledger = _read(ROOT / "SMART_SIGNAL_LEDGER.json")
    learned = _read(EPOCH / "SMART_SIGNAL_STATE_3068_LEARNED.json")
    events = [(idx, e) for idx, e in enumerate(ledger["events"])
              if e.get("target_contest") == 3068]
    count = Counter(event["event_type"] for _, event in events)
    for kind in ("FREEZE", "ADJUDICATION", "LEARNING_UPDATE", "SEQUENTIAL_PROOF"):
        assert count[kind] == 1
    positions = {e["event_type"]: i for i, e in events}
    assert (positions["FREEZE"] < positions["ADJUDICATION"]
            < positions["LEARNING_UPDATE"] < positions["SEQUENTIAL_PROOF"])
    freeze_event = next(e for _, e in events if e["event_type"] == "FREEZE")
    adjudication = next(e for _, e in events if e["event_type"] == "ADJUDICATION")
    assert freeze_event["freeze_sha256"] == _sha(
        EPOCH / "SMART_3068_CHAMPION_CHALLENGER_FREEZE.json")
    assert freeze_event["primary_card"]["numbers"] == primary["numbers"]
    assert datetime.fromisoformat(freeze["frozen_utc"]) < datetime.fromisoformat(
        adjudication["created_utc"])
    actual = set(adjudication["actual_numbers"])
    assert actual == set(report["official_result"]) == {7, 10, 39, 40, 43, 57}
    assert set(report["generated_card"]) == set(primary["numbers"])
    assert len(actual & set(primary["numbers"])) == report["hit_count"] == 1
    assert learned["last_contest"] == learned["sequential_learning_target"] == 3068
    assert learned["learning_after_adjudication"] is True

    mission = _read(ROOT / "SMART_MISSION_STATUS.json")
    assert mission["scientific_predictive_status"] == "UNPROVEN"
    assert mission["terminal_6of6_proven"] is False
