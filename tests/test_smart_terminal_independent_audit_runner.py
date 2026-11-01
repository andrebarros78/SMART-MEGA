"""Independent P14 report dispatch must preserve evidence and restore cwd."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from smart_terminal_stale_coverage import run_terminal_independent_audit


def _case(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    binding = {"ledger": root / "ledger.json", "data": root / "cutoff.xlsx"}
    observed = {"audit_calls": [], "degraded_calls": [], "writes": []}
    def full_audit(repo, ledger, files, data, target, start=0):
        observed["audit_calls"].append((repo, ledger, files, data, target, start, Path.cwd()))
        return {"status": "PASS", "independent": True}
    def degraded(repo, state, files):
        observed["degraded_calls"].append((repo, state, files, Path.cwd()))
        return {"status": "DEGRADED_P14_COVERAGE_STALE", "terminal_promotion_permitted": False}
    def write(path, document):
        observed["writes"].append((path, document, Path.cwd()))
    options = dict(
        target=3080, audit_filename="AUDIT.json",
        coverage_bindings=("coverage_one.json", "coverage_two.json"),
        invoke_independent_audit=full_audit, degraded_result_audit=degraded,
        atomic_write_json=write,
    )
    def run():
        return run_terminal_independent_audit(root, binding, **options)
    return root, binding, options, observed, run


def test_passed_audit_is_written_with_expected_target_and_root(tmp_path):
    root, binding, options, obs, run = _case(tmp_path)
    before = Path.cwd()
    result = run()
    assert result == {"status": "PASS", "independent": True}
    assert len(obs["audit_calls"]) == 1
    args = obs["audit_calls"][0]
    assert args == (root, binding["ledger"],
                    [root/"coverage_one.json", root/"coverage_two.json"],
                    binding["data"], 3080, 1000, root)
    assert obs["degraded_calls"] == []
    assert obs["writes"] == [(root / "AUDIT.json", result, before)]
    assert Path.cwd() == before


def test_exact_stale_source_error_uses_audited_degraded_path(tmp_path):
    root, binding, options, obs, run = _case(tmp_path)
    def stale(*args, **kwargs):
        raise ValueError("coverage binding source hash mismatch")
    options["invoke_independent_audit"] = stale
    result = run()
    assert result["status"] == "DEGRADED_P14_COVERAGE_STALE"
    assert result["terminal_promotion_permitted"] is False
    assert obs["degraded_calls"] == [
        (root, binding, [root/"coverage_one.json", root/"coverage_two.json"], root)
    ]
    assert obs["writes"][0][:2] == (root / "AUDIT.json", result)


@pytest.mark.parametrize("message", ["source hash mismatch", "prospective ledger hash mismatch",
                                      "coverage binding source hash mismatch: other"])
def test_unrelated_audit_errors_are_not_downgraded(tmp_path, message):
    root, binding, options, obs, run = _case(tmp_path)
    options["invoke_independent_audit"] = lambda *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
    before = Path.cwd()
    with pytest.raises(ValueError, match="mismatch"):
        run()
    assert obs["degraded_calls"] == []
    assert obs["writes"] == []
    assert Path.cwd() == before


@pytest.mark.parametrize("status", ["FAIL", "WAITING", "ERROR", None])
def test_nonpassing_report_is_not_persisted(tmp_path, status):
    root, binding, options, obs, run = _case(tmp_path)
    options["invoke_independent_audit"] = lambda *args, **kwargs: {"status": status}
    with pytest.raises(RuntimeError, match="independent audit did not pass"):
        run()
    assert obs["writes"] == []


def test_unexpected_audit_exception_always_restores_directory(tmp_path):
    root, binding, options, obs, run = _case(tmp_path)
    options["invoke_independent_audit"] = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("audit crashed"))
    before = Path.cwd()
    with pytest.raises(RuntimeError, match="audit crashed"):
        run()
    assert Path.cwd() == before
    assert obs["writes"] == []


def test_degraded_audit_failure_propagates_without_persisting(tmp_path):
    root, binding, options, obs, run = _case(tmp_path)
    options["invoke_independent_audit"] = lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("coverage binding source hash mismatch"))
    options["degraded_result_audit"] = lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("tampered P14 report"))
    before = Path.cwd()
    with pytest.raises(ValueError, match="tampered P14 report"):
        run()
    assert Path.cwd() == before
    assert obs["writes"] == []


def test_atomic_writer_failure_is_not_hidden(tmp_path):
    root, binding, options, obs, run = _case(tmp_path)
    options["atomic_write_json"] = lambda *args, **kwargs: (_ for _ in ()).throw(OSError("storage failed"))
    before = Path.cwd()
    with pytest.raises(OSError, match="storage failed"):
        run()
    assert Path.cwd() == before