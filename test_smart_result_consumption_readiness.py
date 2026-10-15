from pathlib import Path

import pytest

import smart_operator as op
from smart_github_operator import READ_ONLY, command_args


def _setup(monkeypatch, tmp_path):
    from smart_operator_result import register
    import json
    supplied = tmp_path / "OPERATOR_RESULT_INPUT.json"
    supplied.write_text(json.dumps({"schema": "SMART_OPERATOR_RESULT_INPUT_1",
        "target_contest": 3068, "draw_date": "08/10/2026",
        "numbers": [1, 7, 13, 25, 41, 59]}))
    register(tmp_path, 3068, supplied)
    monkeypatch.setattr(op, "canonical_root", lambda root=None: tmp_path)
    monkeypatch.setattr(op, "reconcile_startup",
                        lambda *a, **k: {"status": "OK", "failed_checks": []})
    monkeypatch.setattr(op, "assert_lifecycle_state",
                        lambda *a, **k: {"state": "FROZEN", "sha256": "a" * 64})
    monkeypatch.setattr(op, "verify_active_epoch",
                        lambda *a, **k: {
                            "status": "FROZEN",
                            "target_contest": 3068,
                            "target_schedule": {"target_contest": 3068, "target_date": "08/10/2026"},
                        })
    monkeypatch.setattr(op, "_existing_frozen_freeze_summary",
                        lambda *a, **k: {"freeze_sha256": "b" * 64})


def _observation(**changes):
    return {
        "status": "OFFICIAL_RESULT_AVAILABLE",
        "target_contest": 3068,
        "official_result_available": True,
        "actual_numbers": [1, 7, 13, 25, 41, 59],
        "draw_date": "08/10/2026",
        "terminal_source_corroboration_authorized": True,
        "preflight_status": "PASS",
        "canonical_writes_performed": False,
        **changes,
    }


def test_result_preflight_is_readonly_and_bound_to_frozen_epoch(tmp_path, monkeypatch):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(op.terminal_executor, "probe", lambda root, target: _observation())
    before = list(tmp_path.rglob("*"))
    result = op.result_preflight_operation(tmp_path, 3068)
    assert result["status"] == "READY_TO_CONSUME"
    assert result["official_numbers"] == [1, 7, 13, 25, 41, 59]
    assert result["draw_date"] == "08/10/2026"
    assert result["dual_channel_corroborated"] is True
    assert result["freeze_sha256"] == "b" * 64
    assert result["next_mutating_operation"] == "terminal"
    assert result["result_used_for_learning"] is False
    assert result["canonical_writes_performed"] is False
    assert list(tmp_path.rglob("*")) == before


@pytest.mark.parametrize("change", [
    {"draw_date": "09/10/2026"},
    {"target_contest": 3067},
    {"canonical_writes_performed": True},
    {"actual_numbers": [1, 2, 3, 4, 5, 5]},
    {"preflight_status": "RECOVERY_REQUIRED"},
    {"status": "UNKNOWN"},
])
def test_result_preflight_fails_closed_on_bad_observation(tmp_path, monkeypatch, change):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(op.terminal_executor, "probe",
                        lambda root, target: _observation(**change))
    result = op.result_preflight_operation(tmp_path, 3068)
    assert result["status"] in {"BLOCKED_OFFICIAL_EVIDENCE", "BLOCKED_INTEGRITY"}
    assert result["canonical_writes_performed"] is False


def test_result_preflight_offline_waits_without_consuming(tmp_path, monkeypatch):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(op.terminal_executor, "probe",
                        lambda root, target: {
                            "target_contest": 3068,
                            "status": "WAITING_OFFICIAL_RESULT",
                            "canonical_writes_performed": False,
                            "error_type": "ConnectTimeout",
                        })
    result = op.result_preflight_operation(tmp_path, 3068)
    assert result["status"] == "WAITING_OFFICIAL_RESULT"
    assert result["result_used_for_learning"] is False


def test_result_preflight_frozen_authority_mismatch_blocks_network(tmp_path, monkeypatch):
    _setup(monkeypatch, tmp_path)
    def broken(*args, **kwargs):
        raise ValueError("wrong freeze digest")
    monkeypatch.setattr(op, "_existing_frozen_freeze_summary", broken)
    monkeypatch.setattr(op.terminal_executor, "probe",
                        lambda *a, **kw: pytest.fail("must never fetch before verified freeze"))
    result = op.result_preflight_operation(tmp_path, 3068)
    assert result["status"] == "BLOCKED_INTEGRITY"


def test_result_preflight_recovery_blocks_network(tmp_path, monkeypatch):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(op, "reconcile_startup",
                        lambda *a, **kw: {"status": "RECOVERY_REQUIRED",
                                         "failed_checks": ["lifecycle_documents_consistent"]})
    monkeypatch.setattr(op.terminal_executor, "probe",
                        lambda *a, **kw: pytest.fail("must not fetch when recovery is required"))
    result = op.result_preflight_operation(tmp_path, 3068)
    assert result["status"] == "RECOVERY_REQUIRED"
    assert result["failed_checks"] == ["lifecycle_documents_consistent"]


def test_result_preflight_github_dispatch_is_explicit_readonly_target():
    assert "result-preflight" in READ_ONLY
    assert command_args("result-preflight", "3068")[-4:] == [
        "smart_operator.py", "result-preflight", "--target", "3068"]
    with pytest.raises(ValueError, match="target"):
        command_args("result-preflight")
    assert op.contract()["result_preflight_is_read_only"] is True


def test_result_preflight_official_channel_disagreement_is_blocked(tmp_path, monkeypatch):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(op.terminal_executor, "probe",
                        lambda root, target: {
                            "target_contest": 3068,
                            "status": "WAITING_OFFICIAL_RESULT",
                            "canonical_writes_performed": False,
                            "error_type": "ValueError",
                        })
    result = op.result_preflight_operation(tmp_path, 3068)
    assert result["status"] == "BLOCKED_OFFICIAL_EVIDENCE"
    assert result["error_type"] == "ValueError"


def test_existing_github_preflight_dispatch_exposes_readonly_result_gate(tmp_path, monkeypatch):
    import json
    import subprocess
    import sys
    import smart_github_operator as runner

    root = tmp_path / "checkout"
    root.mkdir()
    subprocess.run(["git", "init", "--initial-branch=main", str(root)],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email",
                    "smart-test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "SMART test"],
                   check=True)
    (root / "README.md").write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "initial"],
                   check=True, capture_output=True)
    before = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"])

    def commands(operation, target="", payload=""):
        if operation == "preflight":
            result = {"status": "ALREADY_FROZEN", "target_contest": 3068}
        elif operation == "result-preflight":
            result = {"status": "READY_TO_CONSUME", "target_contest": 3068,
                      "canonical_writes_performed": False,
                      "result_used_for_learning": False}
        else:
            raise AssertionError("unexpected operation")
        return [sys.executable, "-c", "import json;print(json.dumps(" + repr(result) + "))"]

    monkeypatch.setattr(runner, "__file__", str(root / "smart_github_operator.py"))
    monkeypatch.setattr(runner, "command_args", commands)
    result = runner.execute("preflight", "3068")
    assert result["observation"]["status"] == "ALREADY_FROZEN"
    assert result["result_preflight"]["status"] == "READY_TO_CONSUME"
    assert result["commit"] is None
    assert subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"]) == before
    assert not subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"])



def test_operator_result_preflight_ignores_external_schedule_date(tmp_path, monkeypatch):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(op, "verify_active_epoch", lambda *a, **k: {
        "status": "FROZEN", "target_contest": 3068,
        "target_schedule": {"authority": "OPERATOR_SELECTED_TARGET",
                            "target_contest": 3068, "target_date": None}})
    monkeypatch.setattr(op.terminal_executor, "probe", lambda *a, **k: _observation(
        draw_date="09/10/2026", result_input_authority="OPERATOR",
        terminal_source_corroboration_authorized=False))
    result = op.result_preflight_operation(tmp_path, 3068)
    assert result["status"] == "READY_TO_CONSUME"
    assert result["result_input_authority"] == "OPERATOR"
    assert result["draw_date"] == "09/10/2026"
    assert result["primary_official_channel_validated"] is False
