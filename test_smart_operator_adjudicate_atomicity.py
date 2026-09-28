from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

import smart_operator


def _raw_adjudicate_operation():
    fn = smart_operator.adjudicate_operation
    seen = set()
    while hasattr(fn, "__wrapped__") and id(fn) not in seen:
        seen.add(id(fn))
        fn = fn.__wrapped__
    return fn


def test_adjudicate_operation_rolls_back_ledger_lifecycle_and_report_on_report_failure(tmp_path, monkeypatch):
    root = tmp_path
    ledger = root / "ledger.json"
    lifecycle = root / "SMART_OPERATIONAL_LIFECYCLE.json"
    report_json = root / "SMART_POST_RESULT_REPORT_999.json"
    report_md = root / "SMART_POST_RESULT_REPORT_999.md"
    result_file = root / "result.xlsx"
    ledger.write_text("LEDGER_BEFORE", encoding="utf-8")
    lifecycle.write_text("LIFECYCLE_BEFORE", encoding="utf-8")
    result_file.write_text("result", encoding="utf-8")

    active = {"target_contest": 999, "state_paths": {"ledger": "ledger.json", "freeze": "freeze.json"}}
    monkeypatch.setattr(smart_operator, "canonical_root", lambda value: Path(value))
    monkeypatch.setattr(smart_operator, "assert_lifecycle_state", lambda *a, **k: {"state": "FROZEN"})
    monkeypatch.setattr(smart_operator, "verify_active_epoch", lambda path: active)
    monkeypatch.setattr(smart_operator, "resolve_current_epoch", lambda root: {"status": "FROZEN", "freeze_authority_present": True, "target_contest": 999, "generation_proof_valid": True, "freeze_sha256": "FREEZE"})
    monkeypatch.setattr(smart_operator, "load_ledger", lambda path: {"events": []})
    monkeypatch.setattr(smart_operator, "active_freeze", lambda ledger_obj, target: {"freeze_sha256": "FREEZE"})

    def fake_adjudicate(result_data, target, ledger_path):
        Path(ledger_path).write_text("LEDGER_MUTATED", encoding="utf-8")
        return {"actual_numbers": [1, 2, 3, 4, 5, 6]}

    def fake_transition(root, expected, new_state, **kwargs):
        (Path(root) / "SMART_OPERATIONAL_LIFECYCLE.json").write_text("LIFECYCLE_MUTATED", encoding="utf-8")
        return {"state": new_state}

    module = types.ModuleType("smart_post_result_report")
    def fail_report(*args, **kwargs):
        report_json.write_text("REPORT_MUTATED", encoding="utf-8")
        report_md.write_text("REPORT_MD_MUTATED", encoding="utf-8")
        raise RuntimeError("forced report failure")
    module.emit_post_result_report = fail_report
    monkeypatch.setitem(sys.modules, "smart_post_result_report", module)
    monkeypatch.setattr(smart_operator, "adjudicate", fake_adjudicate)
    monkeypatch.setattr(smart_operator, "transition_lifecycle", fake_transition)

    with pytest.raises(RuntimeError, match="forced report failure"):
        _raw_adjudicate_operation()(root, 999, result_file)

    assert ledger.read_text(encoding="utf-8") == "LEDGER_BEFORE"
    assert lifecycle.read_text(encoding="utf-8") == "LIFECYCLE_BEFORE"
    assert not report_json.exists()
    assert not report_md.exists()
