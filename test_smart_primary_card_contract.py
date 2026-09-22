from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from smart_portfolio_pipeline import build_portfolio_package


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
