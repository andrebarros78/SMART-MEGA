"""Regression guard for malformed operator adjudication ledger records."""
from __future__ import annotations

import pytest

from smart_operator_recovery_validation import verify_adjudication_lineage


@pytest.mark.parametrize("bad_target", ["not-an-integer", None, {}, []])
def test_malformed_adjudication_target_fails_closed(tmp_path, bad_target):
    ledger_file = tmp_path / "ledger.json"
    ledger_file.write_text("{}", encoding="utf-8")
    calls = []

    def load_ledger(path):
        return {"events": [{"event_type": "ADJUDICATION",
                            "target_contest": bad_target,
                            "actual_numbers": [1, 2, 3, 4, 5, 6]}]}

    def read_authority(root, target):
        calls.append((root, target))
        return {"source": "OPERATOR",
                "actual_numbers": [1, 2, 3, 4, 5, 6],
                "predictive_weight_authorized": False}

    verified = verify_adjudication_lineage(
        tmp_path, {"state_paths": {"ledger": "ledger.json"}},
        3080, "abc",
        {"result_input_authority": "OPERATOR",
         "actual_numbers": [1, 2, 3, 4, 5, 6]},
        load_ledger=load_ledger,
        active_freeze=lambda ledger, target: {"freeze_sha256": "abc"},
        read_authority=read_authority,
    )
    assert verified is False
    assert calls == []


def test_valid_adjudication_lineage_stays_accepted(tmp_path):
    (tmp_path / "ledger.json").write_text("{}", encoding="utf-8")
    observed = {"result_input_authority": "OPERATOR", "actual_numbers": [1, 2, 3, 4, 5, 6]}
    assert verify_adjudication_lineage(
        tmp_path, {"state_paths": {"ledger": "ledger.json"}},
        3080, "frozen",
        observed,
        load_ledger=lambda path: {"events": [
            {"event_type": "ADJUDICATION", "target_contest": "3080",
             "freeze_sha256": "frozen", "retroactive_rewrite": False,
             "actual_numbers": [1, 2, 3, 4, 5, 6]}]},
        active_freeze=lambda ledger, target: {"freeze_sha256": "frozen"},
        read_authority=lambda root, target: {
            "source": "OPERATOR", "actual_numbers": [1, 2, 3, 4, 5, 6],
            "predictive_weight_authorized": False},
    ) is True



def test_corrupt_adjudication_cannot_be_ignored_beside_valid_event(tmp_path):
    (tmp_path / "ledger.json").write_text("{}", encoding="utf-8")
    records = [
        {"event_type": "ADJUDICATION", "target_contest": "3080",
         "freeze_sha256": "frozen", "retroactive_rewrite": False,
         "actual_numbers": [1, 2, 3, 4, 5, 6]},
        {"event_type": "ADJUDICATION", "target_contest": "invalid"},
    ]
    assert verify_adjudication_lineage(
        tmp_path, {"state_paths": {"ledger": "ledger.json"}},
        3080, "frozen",
        {"result_input_authority": "OPERATOR", "actual_numbers": [1, 2, 3, 4, 5, 6]},
        load_ledger=lambda path: {"events": records},
        active_freeze=lambda ledger, target: {"freeze_sha256": "frozen"},
        read_authority=lambda root, target: pytest.fail("authority must not be read"),
    ) is False
