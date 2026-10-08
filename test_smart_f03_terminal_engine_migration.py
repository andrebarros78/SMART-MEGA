from pathlib import Path

import smart_terminal_executor
import smart_terminal_engine
from smart_component_reachability import build_registry

ROOT = Path(__file__).resolve().parent


def _component(registry, path):
    return next(c for c in registry["components"] if c["source_file"] == path)


def test_f03_canonical_terminal_wrapper_uses_generic_engine():
    assert smart_terminal_executor._engine is smart_terminal_engine


def test_f03_generic_engine_is_production_reachable_and_legacy_is_not():
    registry = build_registry(ROOT)
    debt = registry["known_debt_observations"]
    assert debt["generic_terminal_engine_reachable"] is True
    assert debt["legacy_3054_terminal_executor_reachable"] is False

    generic = _component(registry, "smart_terminal_engine.py")
    legacy = _component(registry, "smart_3054_terminal_executor.py")
    wrapper = _component(registry, "smart_terminal_executor.py")

    assert generic["role"] == "PRODUCTION"
    assert generic["production_reachable"] is True
    assert "smart_terminal_engine" in wrapper["producers"]
    assert "smart_3054_terminal_executor" not in wrapper["producers"]
    assert legacy["role"] != "PRODUCTION"
    assert legacy["reachable"] is False


def test_f03_generic_active_epoch_contract_is_preserved():
    assert callable(smart_terminal_engine.probe_active_epoch)
    assert callable(smart_terminal_engine.execute_active_epoch)
    assert callable(smart_terminal_engine.active_epoch_context)
