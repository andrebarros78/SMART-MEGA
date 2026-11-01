"""Contract tests for recovery batch and operator-only adjudication lineage."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from smart_operator_recovery_validation import (
    select_recovery_batch,
    verify_adjudication_lineage,
)


TARGET = 3079
FREEZE = "f" * 64
ACTUAL = [1, 2, 3, 4, 5, 6]


def test_optional_batch_is_none_without_io(tmp_path):
    assert select_recovery_batch(tmp_path, None) is None


def test_relative_batch_is_verified_and_returned(tmp_path):
    path = tmp_path / "official" / "batch.json"
    path.parent.mkdir()
    path.write_text("{}", encoding="utf-8")
    assert select_recovery_batch(tmp_path, "official/batch.json") == path


def test_exact_two_megabytes_is_accepted(tmp_path):
    p = tmp_path / "batch.json"
    p.write_bytes(b"x" * (2 * 1024 * 1024))
    assert select_recovery_batch(tmp_path, "batch.json") == p


@pytest.mark.parametrize("incoming", ["../batch.json", "official/../batch.json", "/", ".", ""])
def test_batch_rejects_traversal_absolute_and_empty_paths(tmp_path, incoming):
    with pytest.raises(ValueError, match="recovery official batch"):
        select_recovery_batch(tmp_path, incoming)


@pytest.mark.parametrize("kind", ["missing", "directory", "oversize"])
def test_batch_rejects_invalid_file(tmp_path, kind):
    p = tmp_path / "batch.json"
    if kind == "directory":
        p.mkdir()
    elif kind == "oversize":
        p.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="recovery official batch"):
        select_recovery_batch(tmp_path, "batch.json")


def test_batch_rejects_symlink_component(tmp_path):
    safe = tmp_path / "real"
    safe.mkdir()
    (safe / "batch.json").write_text("{}", encoding="utf-8")
    try:
        (tmp_path / "alias").symlink_to(safe, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unsupported by platform policy")
    with pytest.raises(ValueError, match="symbolic link"):
        select_recovery_batch(tmp_path, "alias/batch.json")


def test_batch_rejects_symlink_file(tmp_path):
    original = tmp_path / "real.json"
    original.write_text("{}", encoding="utf-8")
    try:
        (tmp_path / "alias.json").symlink_to(original)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unsupported by platform policy")
    with pytest.raises(ValueError, match="symbolic link"):
        select_recovery_batch(tmp_path, "alias.json")


def _lineage(tmp_path, *, active=None, observation=None, events=None, freeze=None, authority=None):
    p = tmp_path / "epoch" / "ledger.json"
    p.parent.mkdir()
    p.write_text("{}", encoding="utf-8")
    active = {"state_paths": {"ledger": "epoch/ledger.json"}} if active is None else active
    observation = {"result_input_authority": "OPERATOR", "actual_numbers": ACTUAL} if observation is None else observation
    events = [{"event_type": "ADJUDICATION", "target_contest": TARGET,
               "freeze_sha256": FREEZE, "retroactive_rewrite": False,
               "actual_numbers": ACTUAL}] if events is None else events
    freeze = {"freeze_sha256": FREEZE} if freeze is None else freeze
    authority = {"source": "OPERATOR", "actual_numbers": ACTUAL,
                 "predictive_weight_authorized": False} if authority is None else authority
    calls = []
    def read_ledger(path):
        calls.append(("ledger", path))
        return {"events": events}
    def active_freeze(ledger, target):
        calls.append(("freeze", target))
        return freeze
    def read_authority(root, target):
        calls.append(("authority", target))
        return authority
    def verify():
        return verify_adjudication_lineage(
            tmp_path, active, TARGET, FREEZE, observation,
            load_ledger=read_ledger,
            active_freeze=active_freeze,
            read_authority=read_authority,
        )
    return verify, calls


def test_valid_operator_recovery_has_exact_ledger_freeze_and_authority(tmp_path):
    check, calls = _lineage(tmp_path)
    assert check() is True
    assert [kind for kind, *_ in calls] == ["ledger", "freeze", "authority"]


@pytest.mark.parametrize("change", ["missing_paths", "missing_ledger", "absolute", "traversal", "symlink", "non_operator"])
def test_recovery_rejects_unsafe_inputs_before_reading_ledger(tmp_path, change):
    active = {"state_paths": {"ledger": "epoch/ledger.json"}}
    observation = {"result_input_authority": "OPERATOR", "actual_numbers": ACTUAL}
    check, calls = _lineage(tmp_path, active=active, observation=observation)
    p = tmp_path / "epoch" / "ledger.json"
    if change == "missing_paths":
        active.pop("state_paths")
    elif change == "missing_ledger":
        p.unlink()
    elif change == "absolute":
        active["state_paths"]["ledger"] = str(p.resolve())
    elif change == "traversal":
        active["state_paths"]["ledger"] = "../epoch/ledger.json"
    elif change == "symlink":
        (tmp_path / "epoch" / "real.json").write_text("{}", encoding="utf-8")
        p.unlink()
        try:
            p.symlink_to(tmp_path / "epoch" / "real.json")
        except (OSError, NotImplementedError):
            pytest.skip("symlink creation unsupported by platform policy")
    else:
        observation["result_input_authority"] = "UNVERIFIED"
    assert check() is False
    assert calls == []


@pytest.mark.parametrize("change", ["missing_freeze", "wrong_freeze", "no_adjudication", "two_adjudications",
                                      "wrong_target", "wrong_freeze_event", "retroactive", "wrong_numbers"])
def test_recovery_rejects_unbound_ledger_events(tmp_path, change):
    event = {"event_type": "ADJUDICATION", "target_contest": TARGET, "freeze_sha256": FREEZE,
             "retroactive_rewrite": False, "actual_numbers": ACTUAL}
    events = [event]
    freeze = {"freeze_sha256": FREEZE}
    if change == "missing_freeze":
        freeze = None
    elif change == "wrong_freeze":
        freeze["freeze_sha256"] = "e" * 64
    elif change == "no_adjudication":
        events = []
    elif change == "two_adjudications":
        events = [event, dict(event)]
    elif change == "wrong_target":
        event["target_contest"] = TARGET + 1
    elif change == "wrong_freeze_event":
        event["freeze_sha256"] = "e" * 64
    elif change == "retroactive":
        event["retroactive_rewrite"] = True
    else:
        event["actual_numbers"] = [2, 3, 4, 5, 6, 7]
    check, calls = _lineage(tmp_path, events=events, freeze=freeze)
    assert check() is False
    assert "authority" not in [kind for kind, *_ in calls]


@pytest.mark.parametrize("change", ["wrong_source", "different_numbers", "predictive_weight_enabled", "missing_weight_flag"])
def test_recovery_rejects_unverified_operator_authority(tmp_path, change):
    auth = {"source": "OPERATOR", "actual_numbers": ACTUAL, "predictive_weight_authorized": False}
    if change == "wrong_source":
        auth["source"] = "OTHER"
    elif change == "different_numbers":
        auth["actual_numbers"] = [7, 8, 9, 10, 11, 12]
    elif change == "predictive_weight_enabled":
        auth["predictive_weight_authorized"] = True
    else:
        auth.pop("predictive_weight_authorized")
    check, calls = _lineage(tmp_path, authority=auth)
    assert check() is False
    assert [kind for kind, *_ in calls] == ["ledger", "freeze", "authority"]
