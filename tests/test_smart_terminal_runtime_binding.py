"""Runtime binding must select only previously authorized terminal evidence."""
from __future__ import annotations

from pathlib import Path

import pytest

from smart_terminal_runtime_binding import resolve_runtime_binding


def _fixture(root):
    calls = []
    paths = {
        "authority_freeze_sha256": "f" * 64,
        "adjudication_authority_mode": "ACTIVE_EPOCH_FROZEN",
        "freeze": root / "freeze.json", "ledger": root / "epoch" / "ledger.json",
        "state": root / "state.json", "data": root / "history.xlsx",
    }
    params = dict(
        expected_freeze_sha256=None,
        pre_result_data="history.xlsx", learned_state="learned.json",
        active_epoch_binding=lambda path: None,
        current_paths=lambda path: paths,
        load_ledger=lambda path: {"events": []},
        target_events=lambda ledger, kind: [],
        preserved_lock_binding=lambda path: {"mode": "LOCKED_FROM_ARCHIVE"},
    )
    def run():
        return resolve_runtime_binding(root, **params)
    return params, paths, calls, run


def test_explicit_legacy_override_preserves_paths_and_skips_other_authorities(tmp_path):
    params, paths, calls, run = _fixture(tmp_path)
    params["expected_freeze_sha256"] = "a" * 64
    params["active_epoch_binding"] = lambda root: pytest.fail("active authority must be skipped")
    params["current_paths"] = lambda root: pytest.fail("preflight must be skipped")
    result = run()
    assert result == {
        "mode": "EXPLICIT_LEGACY_TEST_OVERRIDE",
        "freeze": tmp_path / "SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json",
        "freeze_sha256": "a" * 64,
        "ledger": tmp_path / "SMART_SIGNAL_LEDGER.json",
        "state": tmp_path / "SMART_SIGNAL_STATE_3054_V2.json",
        "data": tmp_path / "history.xlsx",
        "learned": tmp_path / "learned.json",
    }


def test_active_epoch_has_priority_over_legacy_preflight(tmp_path):
    params, paths, calls, run = _fixture(tmp_path)
    authoritative = {"mode": "ACTIVE_EPOCH", "freeze_sha256": "e" * 64}
    params["active_epoch_binding"] = lambda root: authoritative
    params["current_paths"] = lambda root: pytest.fail("active authority already selected")
    assert run() is authoritative


@pytest.mark.parametrize("mode, expected", [
    ("ACTIVE_EPOCH_FROZEN", "ACTIVE_EPOCH"),
    ("LOCKED_PROSPECTIVE_AUTHORITY", "LOCKED_PROSPECTIVE_AUTHORITY"),
    ("UNKNOWN", "LOCKED_PROSPECTIVE_AUTHORITY"),
])
def test_preflight_selects_compatible_mode_without_authorizing_weights(tmp_path, mode, expected):
    params, paths, calls, run = _fixture(tmp_path)
    paths["adjudication_authority_mode"] = mode
    result = run()
    assert result["mode"] == expected
    assert result["freeze_sha256"] == "f" * 64
    assert result["freeze"] == tmp_path / "freeze.json"
    assert result["ledger"] == tmp_path / "epoch" / "ledger.json"
    assert result["state"] == tmp_path / "state.json"
    assert result["data"] == tmp_path / "history.xlsx"
    assert result["learned"] == (tmp_path / "epoch" / "learned.json" if expected == "ACTIVE_EPOCH" else tmp_path / "learned.json")
    assert not (tmp_path / "learned.json").exists()


@pytest.mark.parametrize("sha", ["", "bad", 12345, None])
def test_preflight_rejects_missing_authority_hash(tmp_path, sha):
    params, paths, calls, run = _fixture(tmp_path)
    paths["authority_freeze_sha256"] = sha
    with pytest.raises(ValueError, match="freeze authority hash missing"):
        run()


def test_preflight_failure_requires_a_single_adjudication_for_fallback(tmp_path):
    params, paths, calls, run = _fixture(tmp_path)
    (tmp_path / "SMART_SIGNAL_LEDGER.json").write_text("{}", encoding="utf-8")
    failed = ValueError("preflight unavailable")
    params["current_paths"] = lambda root: (_ for _ in ()).throw(failed)
    events = []
    params["target_events"] = lambda ledger, kind: events
    with pytest.raises(ValueError, match="preflight unavailable"):
        run()
    events.append({"event_type": "ADJUDICATION"})
    assert run() == {"mode": "LOCKED_FROM_ARCHIVE"}
    events.append({"event_type": "ADJUDICATION"})
    with pytest.raises(ValueError, match="preflight unavailable"):
        run()


def test_missing_ledger_does_not_recover_after_preflight_failure(tmp_path):
    params, paths, calls, run = _fixture(tmp_path)
    params["current_paths"] = lambda root: (_ for _ in ()).throw(RuntimeError("preflight failed"))
    with pytest.raises(RuntimeError, match="preflight failed"):
        run()


def test_bad_archived_ledger_does_not_get_suppressed(tmp_path):
    params, paths, calls, run = _fixture(tmp_path)
    (tmp_path / "SMART_SIGNAL_LEDGER.json").write_text("{}", encoding="utf-8")
    params["current_paths"] = lambda root: (_ for _ in ()).throw(RuntimeError("preflight failed"))
    params["load_ledger"] = lambda path: (_ for _ in ()).throw(ValueError("invalid ledger"))
    with pytest.raises(ValueError, match="invalid ledger"):
        run()