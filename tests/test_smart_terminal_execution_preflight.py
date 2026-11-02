"""Execution preflight checks active freeze authority before official fetch."""
from __future__ import annotations
import hashlib
from pathlib import Path
import pytest

from smart_terminal_execution_preflight import validate_execution_preflight


def _case(tmp_path):
    freeze = tmp_path / "frozen.json"
    freeze.write_bytes(b"frozen-authority")
    digest = hashlib.sha256(freeze.read_bytes()).hexdigest()
    binding={"freeze":freeze,"freeze_sha256":digest,
             "ledger":tmp_path/"ledger.json","mode":"LEGACY"}
    state={"events":[],"readiness":"PASS",
           "scope":None,"actions":[]}
    def sha(path):
        state["actions"].append(("hash",Path(path)))
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def load(path):
        state["actions"].append(("load",Path(path)))
        return {"events":state["events"]}
    def events(ledger,kind):
        state["actions"].append(("events",kind))
        return [e for e in ledger["events"] if e.get("event_type")==kind]
    def historical(root,ledger,*,allow_unverified_history,current_sha256):
        state["actions"].append(("history",allow_unverified_history,current_sha256))
        return state["scope"]
    def preflight(root,authority):
        state["actions"].append(("preflight",root,authority))
        return {"readiness_status":state["readiness"]}
    opts=dict(sha256_file=sha,load_ledger=load,target_events=events,
              historical_precheck=historical,preflight_readiness=preflight)
    def run():
        return validate_execution_preflight(tmp_path,binding,**opts)
    return freeze,binding,state,opts,run


def test_valid_freeze_and_no_adjudication_runs_preflight_before_result(tmp_path):
    freeze,binding,state,opts,run=_case(tmp_path)
    adjudications,scope=run()
    assert adjudications==[] and scope is None
    assert [x[0] for x in state["actions"]]==["hash","load","events","history","preflight"]


def test_existing_adjudication_skips_preflight_without_skipping_history(tmp_path):
    freeze,binding,state,opts,run=_case(tmp_path)
    state["events"]=[{"event_type":"ADJUDICATION","target_contest":3080}]
    state["readiness"]="WAITING"
    adjudications,scope=run()
    assert len(adjudications)==1 and scope is None
    assert [x[0] for x in state["actions"]]==["hash","load","events","history"]


@pytest.mark.parametrize("reason",["absent","tampered"])
def test_invalid_active_freeze_rejected_before_ledger_access(tmp_path,reason):
    freeze,binding,state,opts,run=_case(tmp_path)
    if reason=="absent":freeze.unlink()
    else:freeze.write_bytes(b"tampered")
    with pytest.raises(ValueError,match="active epoch freeze hash differs from immutable authority"):
        run()
    assert not [x for x in state["actions"] if x[0] in {"load","events","history","preflight"}]


def test_duplicate_adjudications_rejected_before_historical_precheck(tmp_path):
    freeze,binding,state,opts,run=_case(tmp_path)
    state["events"]=[{"event_type":"ADJUDICATION"}]*2
    with pytest.raises(ValueError,match="multiple 3054 adjudications"):
        run()
    assert [x[0] for x in state["actions"]]==["hash","load","events"]


@pytest.mark.parametrize("mode,expected",[
    ("ACTIVE_EPOCH",True),
    ("ACTIVE_EPOCH_POST_ADJUDICATION_RECOVERY",True),
    ("LEGACY",False),
    ("OTHER",False),
    (None,False),
])
def test_scoped_history_option_is_derived_exactly_from_authority_mode(tmp_path,mode,expected):
    freeze,binding,state,opts,run=_case(tmp_path)
    binding["mode"]=mode
    state["scope"]={"unverified_contests":[3000],"promotion_authority":False}
    _,scope=run()
    assert scope is state["scope"]
    assert ("history",expected,binding["freeze_sha256"]) in state["actions"]


def test_history_precheck_failure_blocks_preflight(tmp_path):
    freeze,binding,state,opts,run=_case(tmp_path)
    def reject(*a,**kw):raise ValueError("active freeze evidence unbound")
    opts["historical_precheck"]=reject
    with pytest.raises(ValueError,match="active freeze evidence unbound"):
        run()
    assert not [x for x in state["actions"] if x[0]=="preflight"]


def test_preflight_nonpass_remains_fatal_before_adding_official_result(tmp_path):
    freeze,binding,state,opts,run=_case(tmp_path)
    state["readiness"]="WAITING"
    with pytest.raises(RuntimeError,match="3054 preflight is not PASS"):
        run()


def test_preflight_status_requires_literal_pass(tmp_path):
    freeze,binding,state,opts,run=_case(tmp_path)
    state["readiness"]=True
    with pytest.raises(RuntimeError,match="3054 preflight is not PASS"):
        run()


def test_hash_reader_exception_propagates_without_ledger_or_preflight(tmp_path):
    freeze,binding,state,opts,run=_case(tmp_path)
    opts["sha256_file"]=lambda path:(_ for _ in ()).throw(OSError("frozen disk offline"))
    with pytest.raises(OSError,match="frozen disk offline"):
        run()
    assert state["actions"]==[]


def test_ledger_loading_exception_propagates_without_history_or_preflight(tmp_path):
    freeze,binding,state,opts,run=_case(tmp_path)
    opts["load_ledger"]=lambda path:(_ for _ in ()).throw(ValueError("ledger malformed"))
    with pytest.raises(ValueError,match="ledger malformed"):
        run()
    assert [x[0] for x in state["actions"]]==["hash"]


def test_preflight_does_not_write_any_file(tmp_path):
    freeze,binding,state,opts,run=_case(tmp_path)
    names={f.name for f in tmp_path.iterdir()}
    run()
    assert {f.name for f in tmp_path.iterdir()}==names

def test_active_epoch_readiness_preserves_frozen_proof(tmp_path):
    from smart_terminal_execution_preflight import build_execution_readiness
    binding = {
        "mode": "ACTIVE_EPOCH",
        "current": {"generation_proof_valid": True},
        "freeze_sha256": "frozen-digest",
    }
    original = dict(binding)
    observed = build_execution_readiness(
        tmp_path, binding, target=3080, cutoff=3079,
        legacy_preflight=lambda root: (_ for _ in ()).throw(AssertionError("legacy called")),
    )
    assert observed == {
        "readiness_status": "PASS",
        "target_contest": 3080,
        "cutoff_contest": 3079,
        "generation_proof_valid": True,
        "freeze_sha256": "frozen-digest",
        "result_used": False,
    }
    assert binding == original


@pytest.mark.parametrize("current,expected", [
    ({"generation_proof_valid": False}, False),
    ({"generation_proof_valid": 1}, False),
    ({}, False),
])
def test_active_epoch_readiness_requires_literal_generation_proof(tmp_path, current, expected):
    from smart_terminal_execution_preflight import build_execution_readiness
    result = build_execution_readiness(
        tmp_path, {"mode": "ACTIVE_EPOCH", "current": current},
        target=3080, cutoff=3079,
        legacy_preflight=lambda root: None,
    )
    assert result["generation_proof_valid"] is expected
    assert result["result_used"] is False


@pytest.mark.parametrize("mode", ["LEGACY", "ACTIVE_EPOCH_POST_ADJUDICATION_RECOVERY", None])
def test_non_active_readiness_delegates_to_unchanged_legacy_builder(tmp_path, mode):
    from smart_terminal_execution_preflight import build_execution_readiness
    calls = []
    def legacy(root):
        calls.append(root)
        return {"readiness_status": "WAITING", "source": "legacy"}
    result = build_execution_readiness(
        tmp_path, {"mode": mode}, target=3080, cutoff=3079,
        legacy_preflight=legacy,
    )
    assert result == {"readiness_status": "WAITING", "source": "legacy"}
    assert calls == [tmp_path]


def test_legacy_readiness_exception_is_never_suppressed(tmp_path):
    from smart_terminal_execution_preflight import build_execution_readiness
    def failing(root):
        raise ValueError("untrusted preflight")
    with pytest.raises(ValueError, match="untrusted preflight"):
        build_execution_readiness(
            tmp_path, {"mode": "LEGACY"}, target=3080, cutoff=3079,
            legacy_preflight=failing,
        )
