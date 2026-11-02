"""Characterize the active epoch authorization-to-filename boundary."""
from __future__ import annotations

import copy
from pathlib import Path
import pytest


def _case(tmp_path, *, selected=3080, requested=3080):
    from smart_terminal_epoch_context import authorize_epoch_runtime
    active = {"target_contest": selected, "state_paths": {"ledger": "ledger.json"}}
    overrides = {"TARGET": 3080, "CUTOFF": 3079}
    events = []

    def verify(path):
        events.append(("verify", path))
        return active

    def derive(doc, target):
        events.append(("derive", doc, target))
        return overrides

    def invoke():
        return authorize_epoch_runtime(
            tmp_path, requested, verify_active_epoch=verify,
            derive_runtime_names=derive,
        )
    return active, overrides, events, invoke


@pytest.mark.parametrize("requested,selected", [(3080,3080), ("3080","3080"), (3080,"3080")])
def test_authorized_epoch_checks_identity_and_preserves_payload(tmp_path, requested, selected):
    active, overrides, events, invoke = _case(tmp_path, selected=selected, requested=requested)
    before = copy.deepcopy(active)
    epoch, names = invoke()
    assert epoch is active and names is overrides
    assert events == [
        ("verify", tmp_path / "SMART_ACTIVE_EPOCH.json"),
        ("derive", active, 3080),
    ]
    assert active == before


@pytest.mark.parametrize("requested,selected", [(3081,3080), (3080,3079)])
def test_mismatched_epoch_refuses_name_derivation(tmp_path, requested, selected):
    active, overrides, events, invoke = _case(tmp_path, selected=selected, requested=requested)
    with pytest.raises(ValueError, match="requested terminal target differs from active epoch"):
        invoke()
    assert [name for name, _ in events] == ["verify"]


def test_null_epoch_target_preserves_existing_type_error(tmp_path):
    active, overrides, events, invoke = _case(tmp_path, selected=None)
    with pytest.raises(TypeError):
        invoke()
    assert [x[0] for x in events] == ["verify"]


def test_missing_epoch_target_is_rejected_before_derivation(tmp_path):
    active, overrides, events, invoke = _case(tmp_path)
    active.pop("target_contest")
    with pytest.raises(ValueError, match="requested terminal target differs from active epoch"):
        invoke()
    assert [x[0] for x in events] == ["verify"]


def test_incompatible_target_propagates_value_error(tmp_path):
    active, overrides, events, invoke = _case(tmp_path, requested="invalid")
    with pytest.raises(ValueError):
        invoke()
    assert [x[0] for x in events] == ["verify"]


def test_untrusted_epoch_document_raises_without_derivation(tmp_path):
    from smart_terminal_epoch_context import authorize_epoch_runtime
    calls = []
    with pytest.raises(OSError, match="epoch authority unavailable"):
        authorize_epoch_runtime(
            tmp_path, 3080,
            verify_active_epoch=lambda path: (_ for _ in ()).throw(OSError("epoch authority unavailable")),
            derive_runtime_names=lambda *args: calls.append(args),
        )
    assert calls == []


def test_derivation_error_propagates_and_does_not_mutate_epoch(tmp_path):
    from smart_terminal_epoch_context import authorize_epoch_runtime
    doc = {"target_contest": 3080}
    before = copy.deepcopy(doc)
    def reject(active, selected):
        raise ValueError("active epoch ledger path missing")
    with pytest.raises(ValueError, match="active epoch ledger path missing"):
        authorize_epoch_runtime(
            tmp_path, 3080, verify_active_epoch=lambda path: doc,
            derive_runtime_names=reject,
        )
    assert doc == before
