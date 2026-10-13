"""Preserve P14 as scientific proof while allowing certified operational freeze."""
import json
from pathlib import Path

import pytest
import smart_champion_challenger as cc


def _gate():
    return {
        "schema": cc.PRE_3052_GATE_SCHEMA,
        "freeze_allowed": True,
        "items": [
            {"priority": i, "id": f"P{i:02d}", "status": "PROVEN", "evidence": ["proof"]}
            for i in range(1, 16)
        ],
    }


def _setup(monkeypatch, root):
    gate = root / "SMART_3052_IMPLEMENTATION_GATE.json"
    gate.write_text(json.dumps(_gate()), encoding="utf-8")
    monkeypatch.setattr(cc, "PRE_3052_GATE_PATH", gate)
    calls = []
    monkeypatch.setattr("smart_continuous_red_team.verify_latest_report",
                        lambda **kw: calls.append("red") or {"status": "PASS"})
    def global_check(**kwargs):
        calls.append("global")
        raise ValueError("stale P14 scientific proof")
    monkeypatch.setattr("smart_global_integrity.verify_global_integrity", global_check)
    def cert_check(path, *, root, require_current_code):
        calls.append("cert")
        assert path == gate.parent / "SMART_PRODUCT_CERTIFICATION.json"
        assert require_current_code is True
        return {"status": "CONSTRUCTION_PROVEN"}
    monkeypatch.setattr("smart_product_certification.verify_product_certification", cert_check)
    return gate, calls


def test_default_scientific_gate_still_requires_global_proof(monkeypatch, tmp_path):
    gate, calls = _setup(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="P14"):
        cc.require_pre_3052_gate(3052, gate)
    assert calls == ["red", "global"]


def test_operator_certification_replaces_only_historical_global_check(monkeypatch, tmp_path):
    gate, calls = _setup(monkeypatch, tmp_path)
    certificate = tmp_path / "SMART_PRODUCT_CERTIFICATION.json"
    result = cc.require_pre_3052_gate(3052, gate, operational_certification_path=certificate)
    assert result["freeze_allowed"] is True
    assert calls == ["red", "cert"]


def test_operator_certification_wrong_path_is_rejected(monkeypatch, tmp_path):
    gate, calls = _setup(monkeypatch, tmp_path)
    with pytest.raises(PermissionError, match="root-bound"):
        cc.require_pre_3052_gate(3052, gate, operational_certification_path=tmp_path / "other.json")
    assert calls == ["red"]


def test_noncanonical_gate_cannot_bypass_historical_global_check(monkeypatch, tmp_path):
    gate, calls = _setup(monkeypatch, tmp_path)
    other = tmp_path / "other_gate.json"
    other.write_text(json.dumps(_gate()), encoding="utf-8")
    with pytest.raises(PermissionError, match="canonical implementation gate"):
        cc.require_pre_3052_gate(3052, other, operational_certification_path=tmp_path / "SMART_PRODUCT_CERTIFICATION.json")
    assert calls == []


def test_operator_certification_invalid_fails_closed(monkeypatch, tmp_path):
    gate, calls = _setup(monkeypatch, tmp_path)
    def invalid(*args, **kwargs):
        raise ValueError("stale operational source certification")
    monkeypatch.setattr("smart_product_certification.verify_product_certification", invalid)
    with pytest.raises(ValueError, match="stale operational source"):
        cc.require_pre_3052_gate(3052, gate, operational_certification_path=tmp_path / "SMART_PRODUCT_CERTIFICATION.json")
    assert calls == ["red"]


def test_operator_certification_requires_proven_status(monkeypatch, tmp_path):
    gate, calls = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr("smart_product_certification.verify_product_certification",
                        lambda *a, **kw: {"status": "CONSTRUCTION_BLOCKED"})
    with pytest.raises(PermissionError, match="not proven"):
        cc.require_pre_3052_gate(3052, gate, operational_certification_path=tmp_path / "SMART_PRODUCT_CERTIFICATION.json")
    assert calls == ["red"]
