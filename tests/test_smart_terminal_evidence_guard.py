"""Frozen-evidence guard: immutable source and no accidental promotion."""
from pathlib import Path
import pytest

from smart_terminal_evidence_guard import evaluate_verified_terminal_evidence


def _case(tmp_path, *, mode="ACTIVE_EPOCH", provided=True, relative=True):
    artifact = tmp_path / "freeze.json"
    artifact.write_text("frozen")
    binding = {"freeze_sha256": "abc", "freeze": artifact, "mode": mode}
    event = {"freeze_file": "freeze.json" if relative else str(artifact)}
    ledger = {"events": [event]}
    observed = []
    output = {"eligible_for_mission_proven": False}
    def record(name, value):
        observed.append((name, value))
        return value
    options = dict(
        target=3080, cutoff=3079,
        active_freeze=lambda doc, t: record("active", event),
        runtime_binding=lambda root: record("runtime", binding),
        sha256_file=lambda path: record("hash", "abc"),
        read_json=lambda path: record("read", {"frozen": True}),
        target_events=lambda doc, kind: record("events", [{"event_type": kind}]),
        evaluate_terminal_evidence=lambda **kw: record("evaluate", output),
    )
    def run():
        return evaluate_verified_terminal_evidence(
            tmp_path, ledger, {"status": "PASS"}, {"status": "PASS"},
            {"valid": True}, binding if provided else None, **options)
    return artifact, binding, event, options, observed, output, run


@pytest.mark.parametrize("relative,provided", [(True, True), (False, True), (True, False)])
def test_exact_delegation_and_read_order(tmp_path, relative, provided):
    artifact, binding, event, opts, trace, output, run = _case(
        tmp_path, relative=relative, provided=provided)
    assert run() is output
    assert [name for name, _ in trace] == [
        "active", *([] if provided else ["runtime"]),
        "hash", "read", "events", "evaluate"]
    assert trace[-2][1] == [{"event_type": "ADJUDICATION"}]
    assert artifact.read_text() == "frozen"


def test_missing_freeze_fails_closed(tmp_path):
    artifact, binding, event, opts, trace, output, run = _case(tmp_path)
    opts["active_freeze"] = lambda *args: None
    with pytest.raises(ValueError, match="active 3054 freeze is missing"):
        run()
    assert trace == []


@pytest.mark.parametrize("failure", ["missing", "hash"])
def test_missing_or_modified_artifact_blocks_evaluation(tmp_path, failure):
    artifact, binding, event, opts, trace, output, run = _case(tmp_path)
    if failure == "missing":
        artifact.unlink()
    else:
        opts["sha256_file"] = lambda path: "changed"
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        run()
    assert "evaluate" not in [name for name, _ in trace]


@pytest.mark.parametrize("mode,should_reject", [
    ("ACTIVE_EPOCH", True),
    ("LOCKED_PROSPECTIVE_AUTHORITY", False),
    ("ACTIVE_EPOCH_POST_ADJUDICATION_RECOVERY", False),
])
def test_epoch_path_contract_is_unchanged(tmp_path, mode, should_reject):
    artifact, binding, event, opts, trace, output, run = _case(tmp_path, mode=mode)
    binding["freeze"] = tmp_path / "another.json"
    if should_reject:
        with pytest.raises(ValueError, match="ledger freeze path differs"):
            run()
    else:
        assert run() is output


def test_missing_authority_raises_before_evaluation(tmp_path):
    artifact, binding, event, opts, trace, output, run = _case(tmp_path)
    binding.pop("freeze_sha256")
    with pytest.raises(KeyError):
        run()
    assert "evaluate" not in [name for name, _ in trace]


@pytest.mark.parametrize("dependency,error", [
    ("sha256_file", OSError("hash failed")),
    ("evaluate_terminal_evidence", RuntimeError("evaluation failed")),
])
def test_dependency_failures_propagate(tmp_path, dependency, error):
    artifact, binding, event, opts, trace, output, run = _case(tmp_path)
    def fail(*args, **kwargs):
        raise error
    opts[dependency] = fail
    with pytest.raises(type(error), match=str(error)):
        run()
