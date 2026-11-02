"""Scoped engine globals must restore exact baseline under every exit path."""
from __future__ import annotations

import pytest


def test_scoped_values_active_only_while_context_is_entered():
    from smart_terminal_epoch_context import scoped_epoch_globals
    baseline = object()
    state = {"TARGET": 3054, "SENTINEL": baseline}
    with scoped_epoch_globals(state, {"TARGET": 3080, "SENTINEL": "epoch"}):
        assert state == {"TARGET": 3080, "SENTINEL": "epoch"}
    assert state["TARGET"] == 3054
    assert state["SENTINEL"] is baseline


def test_nested_context_restores_outer_then_initial_authority():
    from smart_terminal_epoch_context import scoped_epoch_globals
    state = {"TARGET": 3054, "STATUS_FILE": "original.json"}
    with scoped_epoch_globals(state, {"TARGET": 3080, "STATUS_FILE": "outer.json"}):
        with scoped_epoch_globals(state, {"TARGET": 3081, "STATUS_FILE": "inner.json"}):
            assert state == {"TARGET": 3081, "STATUS_FILE": "inner.json"}
        assert state == {"TARGET": 3080, "STATUS_FILE": "outer.json"}
    assert state == {"TARGET": 3054, "STATUS_FILE": "original.json"}


def test_body_exception_restores_all_globals_and_propagates():
    from smart_terminal_epoch_context import scoped_epoch_globals
    state = {"SCHEMA": "v1", "TARGET": 3054}
    with pytest.raises(RuntimeError, match="execution failed"):
        with scoped_epoch_globals(state, {"SCHEMA": "v2", "TARGET": 3080}):
            assert state == {"SCHEMA": "v2", "TARGET": 3080}
            raise RuntimeError("execution failed")
    assert state == {"SCHEMA": "v1", "TARGET": 3054}


@pytest.mark.parametrize("overrides", [
    {"TARGET": 3080, "MISSING": 2},
    {"MISSING": "unexpected", "TARGET": 3080},
])
def test_unknown_global_raises_before_any_mutation(overrides):
    from smart_terminal_epoch_context import scoped_epoch_globals
    state = {"TARGET": 3054, "CUTOFF": 3053}
    with pytest.raises(KeyError, match="MISSING"):
        with scoped_epoch_globals(state, overrides):
            raise AssertionError("context must not become active")
    assert state == {"TARGET": 3054, "CUTOFF": 3053}


def test_explicit_modification_inside_scope_is_reverted():
    from smart_terminal_epoch_context import scoped_epoch_globals
    state = {"TARGET": 3054}
    with scoped_epoch_globals(state, {"TARGET": 3080}):
        state["TARGET"] = 9001
    assert state["TARGET"] == 3054


def test_no_overrides_is_noop():
    from smart_terminal_epoch_context import scoped_epoch_globals
    state = {"TARGET": 3054}
    with scoped_epoch_globals(state, {}):
        assert state["TARGET"] == 3054
    assert state == {"TARGET": 3054}


def test_override_map_not_changed():
    from smart_terminal_epoch_context import scoped_epoch_globals
    state = {"TARGET": 3054}
    overrides = {"TARGET": 3080}
    with scoped_epoch_globals(state, overrides):
        assert overrides == {"TARGET": 3080}
    assert overrides == {"TARGET": 3080}
