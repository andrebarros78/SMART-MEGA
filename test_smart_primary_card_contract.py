from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from smart_portfolio_pipeline import build_portfolio_package
from smart_full_process_pipeline import _verified_primary_card


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256_json(value: dict) -> str:
    payload = dict(value)
    payload.pop("sha256", None)
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def test_portfolio_pipeline_marks_multicard_as_auxiliary_not_card():
    freeze_path = Path(__file__).with_name("SMART_3053_CHAMPION_CHALLENGER_FREEZE.json")
    artifact = build_portfolio_package(freeze_path)

    primary = artifact["primary_card"]
    assert artifact["product_role"] == "AUXILIARY_MULTICARD_PORTFOLIO"
    assert artifact["primary_card_role"] == "FINAL_SINGLE_CARD_PRODUCT"
    assert artifact["champion_top6_role"] == "PRIMARY_SINGLE_CARD_SOURCE"
    assert primary["optimization_objective"] == "MAXIMIZE_SIX_HIT_SINGLE_CARD"
    assert primary["product_role"] == "FINAL_SINGLE_CARD_PRODUCT"
    assert primary["numbers"] == sorted(artifact["champion_top6"])
    assert len(primary["numbers"]) == 6
    assert len(set(primary["numbers"])) == 6
    assert artifact["contract"]["primary_output_is_single_card"] is True
    assert artifact["contract"]["portfolio_requires_explicit_multicard_request"] is True


def test_3061_generation_proof_has_single_primary_card_contract():
    proof_path = Path(__file__).with_name("SMART_3061_GENERATION_PROOF.json")
    if not proof_path.exists():
        pytest.skip("3061 generation proof not present in this checkout")
    proof = _load(proof_path)

    assert proof["status"] == "FROZEN"
    assert proof["card_contract"]["primary_output"] == "SINGLE_CARD"
    assert proof["card_contract"]["numbers_per_card"] == 6
    assert proof["card_contract"]["objective"] == "MAXIMIZE_SIX_HIT_SINGLE_CARD"
    assert proof["card_contract"]["portfolio_is_auxiliary"] is True
    assert proof["card_contract"]["portfolio_must_not_replace_primary_card"] is True
    assert proof["card_contract"]["multicard_requires_explicit_request"] is True
    assert proof["portfolio_role"] == "AUXILIARY_MULTICARD_PORTFOLIO"
    assert proof["card"] == proof["primary_card"]["numbers"]
    assert proof["primary_card"]["product_role"] == "FINAL_SINGLE_CARD_PRODUCT"
    assert proof["primary_card"]["optimization_objective"] == "MAXIMIZE_SIX_HIT_SINGLE_CARD"
    assert proof["card"] == sorted(proof["champion_top6"])
    assert len(proof["card"]) == 6
    assert len(set(proof["card"])) == 6
    assert proof["sha256"] == _sha256_json(proof)


def test_primary_card_flow_uses_frozen_portfolio_selection(tmp_path: Path):
    selector = {"status": "PASS", "result_used": False, "selected_numbers": [1, 2, 3, 7, 8, 9]}
    selector["sha256"] = _sha256_json(selector)
    rescue = {"status": "PASS", "result_used": False, "nonzero_deltas": {}}
    rescue["sha256"] = _sha256_json(rescue)
    card = {
        "schema": "SMART_PRIMARY_SINGLE_CARD_2", "target_contest": 3067,
        "cutoff_contest": 3066, "numbers": [1, 2, 3, 7, 8, 9],
        "source_top6_ordered": [1, 2, 3, 4, 5, 6],
        "freeze_sha256": "a" * 64, "product_role": "FINAL_SINGLE_CARD_PRODUCT",
        "optimization_objective": "MAXIMIZE_SIX_HIT_SINGLE_CARD",
        "selector": selector, "false_negative_rescue": rescue,
    }
    package = {
        "status": "PASS", "target_contest": 3067, "cutoff_contest": 3066,
        "source_data_sha256": "b" * 64, "freeze_sha256": "a" * 64,
        "product_role": "AUXILIARY_MULTICARD_PORTFOLIO",
        "primary_card": card, "primary_card_selector": selector,
        "false_negative_rescue": rescue,
    }
    portfolio = tmp_path / "portfolio.json"
    portfolio.write_text(json.dumps(package), encoding="utf-8")
    frozen_sha = hashlib.sha256(portfolio.read_bytes()).hexdigest()
    freeze_result = {
        "portfolio_file": "portfolio.json", "portfolio_sha256": frozen_sha,
        "freeze_sha256": "a" * 64,
    }
    event = {"primary_card": card, "portfolio_sha256": frozen_sha}
    selected, _, observed = _verified_primary_card(
        tmp_path, freeze_result, event, 3067, 3066, [1, 2, 3, 4, 5, 6], "b" * 64
    )
    assert selected["numbers"] == [1, 2, 3, 7, 8, 9]
    assert selected["numbers"] != sorted(selected["source_top6_ordered"])
    assert observed == frozen_sha

    with pytest.raises(ValueError, match="ledger"):
        _verified_primary_card(
            tmp_path, freeze_result, {**event, "primary_card": {**card, "numbers": [1, 2, 3, 4, 5, 6]}},
            3067, 3066, [1, 2, 3, 4, 5, 6], "b" * 64,
        )
    with pytest.raises(ValueError, match="hash"):
        _verified_primary_card(
            tmp_path, {**freeze_result, "portfolio_sha256": "0" * 64}, event,
            3067, 3066, [1, 2, 3, 4, 5, 6], "b" * 64,
        )
