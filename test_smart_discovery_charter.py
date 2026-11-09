"""Independent tests for the owner's anti-dogma discovery charter.

The exact principle is anchored here separately from the runtime validator.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from smart_discovery_charter import (
    CHARTER_FILE,
    EXPECTED_PRINCIPLE,
    _sha256_json,
    verify_discovery_charter,
)

ROOT = Path(__file__).resolve().parent
OWNER_PRINCIPLE = (
    "O SMART-MEGA V6 não deve ser construído para confirmar que os conhecimentos atuais "
    "estão certos. Deve ser construído para descobrir se existe alguma informação ou "
    "método capaz de produzir previsões melhores, inclusive quando isso contrariar expectativas"
)


def _write_policy(tmp_path: Path, document: dict) -> None:
    (tmp_path / CHARTER_FILE).write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )


def test_exact_owner_discovery_principle_is_fixed_without_prediction_prejudgment():
    assert EXPECTED_PRINCIPLE == OWNER_PRINCIPLE
    charter = verify_discovery_charter(ROOT)
    assert charter["canonical_principle"] == OWNER_PRINCIPLE
    assert charter["method"]["allow_unconventional_hypotheses"] is True
    assert charter["method"]["no_a_priori_predictive_impossibility_verdict"] is True
    assert charter["method"]["no_a_priori_predictive_superiority_verdict"] is True
    assert charter["method"]["evaluate_out_of_sample_and_prospectively"] is True
    assert charter["method"]["adopt_better_validated_methods"] is True
    assert charter["method"]["reject_false_learning_and_leakage"] is True
    assert charter["change_control"]["ai_chat_unilateral_edit_permitted"] is False
    assert charter["change_control"]["explicit_owner_approval_required"] is True


def test_modification_with_recomputed_self_hash_is_rejected(tmp_path):
    doc = verify_discovery_charter(ROOT).copy()
    doc["canonical_principle"] = "Nenhum metodo pode superar o modelo atual"
    doc["sha256"] = _sha256_json({k: v for k, v in doc.items() if k != "sha256"})
    _write_policy(tmp_path, doc)
    with pytest.raises(ValueError, match="protected charter"):
        verify_discovery_charter(tmp_path)


def test_mutation_of_method_or_change_authority_is_rejected(tmp_path):
    doc = verify_discovery_charter(ROOT)
    for changed in (
        ("method", "allow_unconventional_hypotheses", False),
        ("method", "no_a_priori_predictive_superiority_verdict", False),
        ("change_control", "ai_chat_unilateral_edit_permitted", True),
    ):
        attempt = json.loads(json.dumps(doc))
        attempt[changed[0]][changed[1]] = changed[2]
        attempt["sha256"] = _sha256_json({k: v for k, v in attempt.items() if k != "sha256"})
        _write_policy(tmp_path, attempt)
        with pytest.raises(ValueError, match="protected charter"):
            verify_discovery_charter(tmp_path)


def test_missing_duplicate_or_corrupted_policy_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="missing"):
        verify_discovery_charter(tmp_path)
    original = (ROOT / CHARTER_FILE).read_text(encoding="utf-8")
    (tmp_path / CHARTER_FILE).write_text(original + original, encoding="utf-8")
    with pytest.raises(ValueError):
        verify_discovery_charter(tmp_path)
    (tmp_path / CHARTER_FILE).write_text(original.replace('"project": "SMART-MEGA"', '"project": "other"'), encoding="utf-8")
    with pytest.raises(ValueError):
        verify_discovery_charter(tmp_path)


def test_main_gate_and_freeze_entrypoint_require_charter_verification(monkeypatch):
    import smart_total_integration_gate as gate
    import smart_full_process_pipeline as pipeline

    class CharterRejected(Exception):
        pass

    def reject(_root):
        raise CharterRejected("guard executed")

    monkeypatch.setattr(gate, "verify_discovery_charter", reject)
    with pytest.raises(CharterRejected, match="guard executed"):
        gate.evaluate(ROOT, phase="BUILD")

    monkeypatch.setattr(pipeline, "verify_discovery_charter", reject)
    with pytest.raises(CharterRejected, match="guard executed"):
        pipeline.run_full_process(ROOT, manual_generation_authorized=False)


def test_agent_and_repository_rules_identify_owner_control():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    ownership = (ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8")
    assert "SMART_DISCOVERY_CHARTER.json" in agents
    assert "smart_discovery_charter.py" in agents
    assert "aprovação explícita" in agents.lower()
    assert "/SMART_DISCOVERY_CHARTER.json @andrebarros78" in ownership
    assert "/smart_discovery_charter.py @andrebarros78" in ownership
