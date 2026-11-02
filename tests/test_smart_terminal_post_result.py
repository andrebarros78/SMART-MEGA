"""Post-result coordination must preserve ordering and fail-closed promotion."""
from __future__ import annotations

import copy
from pathlib import Path
import pytest


def _case(tmp_path, *, eligible=False, allow=True):
    from smart_terminal_post_result import finalize_terminal_result
    root = tmp_path
    ledger = {"events": ["frozen"]}
    binding = {"ledger": root / "ledger.json", "mode": "ACTIVE_EPOCH"}
    consensus = {"status": "CORROBORATED"}
    evaluation = {"status": "NOT_PROVEN", "eligible_for_mission_proven": eligible}
    original_mission = {"status": "MISSION_ACTIVE", "terminal_6of6_proven": False}
    promoted = {"status": "MISSION_PROVEN", "terminal_6of6_proven": True}
    docs = dict(normalized={"numbers": [1, 2, 3, 4, 5, 6]}, ingest={"schema": "INGEST"},
                adjudication={"champion_hits": 2, "challenger_hits": 1},
                learned={"last_contest": 3080}, sequence_validation={"valid": True},
                audit={"status": "PASS"}, result_store={"status": "PASS"})
    events = []
    def load_ledger(path):
        events.append(("ledger", path))
        return ledger
    def read_json(path):
        events.append(("consensus", path))
        return consensus
    def evaluate(root_, ledger_, consensus_, audit, seq, binding=None):
        events.append(("evaluate", root_, ledger_, consensus_, audit, seq, binding))
        return evaluation
    def load_mission(path, *, root):
        events.append(("mission_read", path, root))
        return original_mission
    def promote(root_, evaluation_, consensus_, audit, seq, *, binding):
        events.append(("promote", root_, evaluation_, consensus_, audit, seq, binding))
        return promoted
    def now():
        events.append(("clock",))
        return "2026-11-02T13:00:00+00:00"
    def projection(**args):
        events.append(("projection", args))
        return {"status": args["evaluation"]["status"], "mission": args["mission"]}
    def writer(path, report):
        events.append(("write", path, report))
    opts = dict(
        schema="TERMINAL_1", target=3080, status_file="terminal-status.json",
        consensus_file="consensus.json", allow_terminal_write=allow,
        load_ledger=load_ledger, read_json=read_json, evaluate_terminal_rule=evaluate,
        load_mission_status=load_mission, promote_terminal_mission=promote,
        build_terminal_execution_status=projection, atomic_write_json=writer,
        current_time_utc=now,
    )
    def run():
        return finalize_terminal_result(root, binding, **docs, **opts)
    return root, binding, docs, opts, events, original_mission, promoted, run


def test_unproven_path_evaluates_then_projects_then_persists(tmp_path):
    root, binding, docs, opts, events, original, promoted, run = _case(tmp_path)
    result = run()
    assert [event[0] for event in events] == [
        "ledger", "consensus", "evaluate", "mission_read", "clock", "projection", "write"
    ]
    assert events[0][1] == binding["ledger"]
    assert events[1][1] == root / "consensus.json"
    assert events[2][2] == {"events": ["frozen"]}
    assert events[2][6] is binding
    projection = events[5][1]
    assert projection["schema"] == "TERMINAL_1"
    assert projection["target"] == 3080
    assert projection["created_at_utc"] == "2026-11-02T13:00:00+00:00"
    assert projection["mission"] is original
    for name, document in docs.items():
        assert projection[name] is document
    assert events[6] == ("write", root / "terminal-status.json", result)


@pytest.mark.parametrize("allow", [False, True])
def test_eligible_promotion_respects_terminal_write_permission(tmp_path, allow):
    root, binding, docs, opts, events, original, promoted, run = _case(tmp_path, eligible=True, allow=allow)
    result = run()
    calls = [event[0] for event in events]
    assert ("promote" in calls) is allow
    assert result["mission"] is (promoted if allow else original)
    assert calls[-2:] == ["projection", "write"]
    if allow:
        assert calls.index("mission_read") < calls.index("promote") < calls.index("clock")
        assert events[4][1] is root
        assert events[4][2]["eligible_for_mission_proven"] is True
        assert events[4][-1] is binding


def test_missing_eligibility_field_fails_before_promotion_or_status_write(tmp_path):
    root, binding, docs, opts, events, original, promoted, run = _case(tmp_path)
    opts["evaluate_terminal_rule"] = lambda *args, **kwargs: {"status": "INCOMPLETE"}
    with pytest.raises(KeyError, match="eligible_for_mission_proven"):
        run()
    assert not any(row[0] in ("promote", "clock", "projection", "write") for row in events)


@pytest.mark.parametrize("stage", ["ledger", "consensus", "evaluation", "mission", "promotion", "projection", "writer"])
def test_failure_propagates_without_subsequent_status_write(tmp_path, stage):
    root, binding, docs, opts, events, original, promoted, run = _case(tmp_path, eligible=True)
    callbacks = {
        "ledger": "load_ledger", "consensus": "read_json",
        "evaluation": "evaluate_terminal_rule", "mission": "load_mission_status",
        "promotion": "promote_terminal_mission",
        "projection": "build_terminal_execution_status", "writer": "atomic_write_json",
    }
    def fail(*args, **kwargs):
        raise OSError("stage " + stage + " failed")
    opts[callbacks[stage]] = fail
    with pytest.raises(OSError, match="stage " + stage + " failed"):
        run()
    if stage != "writer":
        assert not any(row[0] == "write" for row in events)


def test_injected_inputs_remain_unchanged(tmp_path):
    root, binding, docs, opts, events, original, promoted, run = _case(tmp_path)
    previous = copy.deepcopy((binding, docs, original))
    run()
    assert (binding, docs, original) == previous
