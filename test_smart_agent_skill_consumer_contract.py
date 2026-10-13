from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from smart_agent_runtime import sha256_json
from smart_agent_skill_consumer_contract import verify_consumer_gate
from smart_total_integration_gate import evaluate

ROOT = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def real_gate():
    proof = evaluate(ROOT, phase="BUILD")
    assert proof["status"] == "PASS"
    return proof


def _write(tmp_path: Path, doc: dict) -> Path:
    path = tmp_path / "gate.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _rehashed(doc: dict) -> dict:
    copy_doc = copy.deepcopy(doc)
    copy_doc["sha256"] = sha256_json({k: v for k, v in copy_doc.items() if k != "sha256"})
    return copy_doc


def test_consumer_uses_all_real_executions_and_no_llm(real_gate, tmp_path):
    summary = verify_consumer_gate(real_gate, _write(tmp_path, real_gate), phase="BUILD")
    assert summary["status"] == "PASS"
    assert summary["agents_executed"] == 9
    assert summary["skills_native_invoked"] == 37
    assert summary["skills_quarantined"] == 4
    assert summary["handoffs_consumed"] >= 1
    assert summary["llm_provider"] is None
    assert summary["prediction_or_weight_influence"] is False


def test_consumer_rejects_phase_and_file_mismatch(real_gate, tmp_path):
    path = _write(tmp_path, real_gate)
    with pytest.raises(RuntimeError, match="phase"):
        verify_consumer_gate(real_gate, path, phase="PRE_FREEZE")
    edited = copy.deepcopy(real_gate)
    edited["health"] = "UNHEALTHY"
    with pytest.raises(RuntimeError, match="file/returned"):
        verify_consumer_gate(edited, path, phase="BUILD")


def test_consumer_rejects_missing_native_skill_even_with_rehashed_gate(real_gate, tmp_path):
    edited = copy.deepcopy(real_gate)
    edited["native_invocations"].pop()
    edited = _rehashed(edited)
    with pytest.raises(RuntimeError, match="incomplete"):
        verify_consumer_gate(edited, _write(tmp_path, edited), phase="BUILD")


def test_consumer_rejects_tampered_skill_execution_even_with_rehashed_gate(real_gate, tmp_path):
    edited = copy.deepcopy(real_gate)
    edited["native_invocations"][0]["status"] = "PASS"
    edited["native_invocations"][0]["adapter_state"] = "ACTIVE_NATIVE"
    candidate = edited["native_invocations"][0]["capability"]
    next(row for row in edited["skill_inventory"] if row["capability"] == candidate)["alias_invocation"] = edited["native_invocations"][0]
    edited = _rehashed(edited)
    with pytest.raises(RuntimeError, match="not consumed"):
        verify_consumer_gate(edited, _write(tmp_path, edited), phase="BUILD")


def test_consumer_rejects_orphan_handoff_and_llm_injection(real_gate, tmp_path):
    edited = copy.deepcopy(real_gate)
    edited["operational_handoff_ledger"]["consumed_count"] -= 1
    edited = _rehashed(edited)
    with pytest.raises(RuntimeError, match="handoffs"):
        verify_consumer_gate(edited, _write(tmp_path, edited), phase="BUILD")

    edited = copy.deepcopy(real_gate)
    edited["sdk_llm_selection"]["provider"] = "unauthorized"
    edited = _rehashed(edited)
    with pytest.raises(RuntimeError, match="provider"):
        verify_consumer_gate(edited, _write(tmp_path, edited), phase="BUILD")


def test_full_process_consumes_pre_and_post_gate_and_binds_to_proof():
    text = (ROOT / "smart_full_process_pipeline.py").read_text(encoding="utf-8-sig")
    assert text.count("bind_consumer_execution(") == 2
    assert text.index('pre_consumer = bind_consumer_execution(') < text.index('freeze_champion_challenger(')
    assert text.index('post_consumer = bind_consumer_execution(') < text.index('primary_card_numbers =')
    assert '"agent_skill_consumer": {' in text
    assert '"pre_freeze": pre_consumer' in text
    assert '"post_freeze": post_consumer' in text
