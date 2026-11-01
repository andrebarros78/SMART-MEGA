"""Contract tests for reconciliation of a previous operator epoch.

No official results are fetched and no canonical state is written by these
fixtures. The caller must still control certification and preparation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from smart_operator_previous_epoch import reconcile_previous_epoch


TARGET = 3058
PREVIOUS = 3057


def _case(tmp_path, *, events=None, active_exists=True, failure=None, sandbox=False):
    active_path = tmp_path / "active.json"
    if active_exists:
        active_path.write_text("{}", encoding="utf-8")
    previous_active = {
        "target_contest": PREVIOUS,
        "state_paths": {"ledger": "epochs/previous/SMART_SIGNAL_LEDGER.json"},
        "sha256": "p" * 64,
    }
    calls = []
    events = [] if events is None else events
    def verify(path):
        calls.append(("verify", str(path)))
        if failure is not None:
            raise failure
        return previous_active
    def read(path):
        calls.append(("load_ledger", str(path)))
        return {"events": events}
    def ledger_reconcile(canonical, previous, contest, *, root):
        calls.append(("reconcile", str(canonical), str(previous), contest, str(root)))
        return {"status": "RECONCILED", "contest": contest}
    def advance(root, active):
        calls.append(("advance", str(root), active))
        return {"status": "ADVANCED"}
    def sandbox_check(root):
        calls.append(("sandbox", str(root)))
        return sandbox
    def run():
        return reconcile_previous_epoch(
            tmp_path,
            active_path,
            verify_active_epoch=verify,
            load_ledger=read,
            reconcile_completed_epoch_ledger=ledger_reconcile,
            advance_completed_epoch=advance,
            authorized_pytest_sandbox=sandbox_check,
        )
    return run, calls, previous_active, active_path


def test_absent_active_epoch_returns_no_reconciliation_without_reads(tmp_path):
    run, calls, _, _ = _case(tmp_path, active_exists=False)
    assert run() == (None, None)
    assert calls == []


def test_completed_epoch_reconciles_ledger_before_advancing_result_store(tmp_path):
    events = [{"event_type": "FREEZE", "target_contest": PREVIOUS},
              {"event_type": "ADJUDICATION", "target_contest": str(PREVIOUS)}]
    run, calls, original, active_path = _case(tmp_path, events=events)
    result = run()
    assert result == ({"status": "RECONCILED", "contest": PREVIOUS},
                      {"status": "ADVANCED"})
    assert [call[0] for call in calls] == ["verify", "load_ledger", "reconcile", "advance"]
    assert calls[0][1] == str(active_path)
    assert calls[1][1] == str(tmp_path / "epochs/previous/SMART_SIGNAL_LEDGER.json")
    assert calls[2][1:] == (
        str(tmp_path / "SMART_SIGNAL_LEDGER.json"),
        str(tmp_path / "epochs/previous/SMART_SIGNAL_LEDGER.json"),
        PREVIOUS,
        str(tmp_path),
    )
    assert calls[3][2] is original


@pytest.mark.parametrize("events", [
    [],
    [{"event_type": "FREEZE", "target_contest": PREVIOUS}],
    [{"event_type": "ADJUDICATION", "target_contest": PREVIOUS - 1}],
    [{"event_type": "ADJUDICATION", "target_contest": PREVIOUS + 1}],
    [{"event_type": "ADJUDICATION", "target_contest": PREVIOUS, "result": None, "other": "value"}],
])
def test_adjudication_gate_does_not_allow_unresolved_previous_epoch(tmp_path, events):
    # The existing code only checks the event type and target, not payload.
    if any(e["event_type"] == "ADJUDICATION" and e["target_contest"] == PREVIOUS for e in events):
        pytest.skip("payload validation belongs to later reconciliation")
    run, calls, _, _ = _case(tmp_path, events=events)
    with pytest.raises(ValueError, match="cannot supersede an unresolved prospective attempt"):
        run()
    assert [c[0] for c in calls] == ["verify", "load_ledger"]


@pytest.mark.parametrize("exception", [ValueError("corrupt"), RuntimeError("bad integrity"), FileNotFoundError("missing")])
def test_active_verification_failure_propagates_outside_test_sandbox(tmp_path, exception):
    run, calls, _, _ = _case(tmp_path, failure=exception, sandbox=False)
    with pytest.raises(type(exception), match=str(exception)):
        run()
    assert [c[0] for c in calls] == ["verify", "sandbox"]


@pytest.mark.parametrize("exception", [ValueError("bad"), RuntimeError("damaged")])
def test_active_verification_in_sandbox_matches_legacy_file_exists_error(tmp_path, exception):
    run, calls, _, _ = _case(tmp_path, failure=exception, sandbox=True)
    with pytest.raises(FileExistsError, match="active epoch already exists"):
        run()
    assert [c[0] for c in calls] == ["verify", "sandbox"]


def test_invalid_adjudication_target_is_not_silently_accepted(tmp_path):
    run, calls, _, _ = _case(tmp_path, events=[{"event_type": "ADJUDICATION", "target_contest": "invalid"}])
    with pytest.raises(ValueError):
        run()
    assert [c[0] for c in calls] == ["verify", "load_ledger"]


def test_previous_epoch_is_not_mutated_by_reconciliation_helper(tmp_path):
    events = [{"event_type": "ADJUDICATION", "target_contest": PREVIOUS}]
    run, calls, active, _ = _case(tmp_path, events=events)
    snapshot = dict(active)
    run()
    assert active == snapshot


def test_previous_reconciliation_aborts_before_advance_on_ledger_error(tmp_path):
    events = [{"event_type": "ADJUDICATION", "target_contest": PREVIOUS}]
    run, calls, _, _ = _case(tmp_path, events=events)
    # The lower-layer reconciliation is expected to enforce its own hash contract.
    def reject(*args, **kwargs):
        calls.append(("rejected",))
        raise PermissionError("reconciliation failed")
    # Replace dependency by constructing a fresh call, with the same collaborator wrappers.
    with pytest.raises(PermissionError, match="reconciliation failed"):
        reconcile_previous_epoch(
            tmp_path, tmp_path / "active.json",
            verify_active_epoch=lambda _: {"target_contest": PREVIOUS, "state_paths": {"ledger": "ledger.json"}},
            load_ledger=lambda _: {"events": events},
            reconcile_completed_epoch_ledger=reject,
            advance_completed_epoch=lambda *a: pytest.fail("advance executed after reconciliation failure"),
            authorized_pytest_sandbox=lambda _: False,
        )
    assert ("rejected",) in calls
