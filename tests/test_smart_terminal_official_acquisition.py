"""Official acquisition is fail-closed and never invents result authority."""
from __future__ import annotations
from pathlib import Path
import pytest
from smart_terminal_official_evidence import acquire_official_result


def _scenario(tmp_path):
    calls=[]
    payload={"numbers":[1,2,3,4,5,6],"draw_date":"2026-11-01"}
    consensus={"status":"PRIMARY_VALIDATED","primary":{"validated":True}}
    persisted=(dict(payload),dict(consensus))
    state={"existing":None,"failure":None,"adjudications":[]}
    def load(root):
        calls.append("load")
        return state["existing"]
    def fetch(target):
        calls.append(("fetch",target))
        if state["failure"] is not None:raise state["failure"]
        return payload,consensus
    def primary(root,raw):
        calls.append(("primary",raw))
        return raw
    def corrob(root,raw):
        calls.append(("consensus",raw))
        return raw
    def invoke():
        return acquire_official_result(
            tmp_path,fetch,state["adjudications"],
            target=3080,schema="SMART_TERMINAL_EXECUTOR_ACTIVE_EPOCH_1",
            load_existing=load,ensure_primary=primary,ensure_consensus=corrob,
        )
    return calls,payload,consensus,persisted,state,invoke


def test_first_official_result_applies_immutable_payload_before_consensus(tmp_path):
    calls,payload,consensus,persisted,state,run=_scenario(tmp_path)
    actual,document,wait=run()
    assert actual is payload and document is consensus and wait is None
    assert calls==["load",("fetch",3080),("primary",payload),("consensus",consensus)]


def test_no_result_yet_requires_no_evidence_and_no_adjudication(tmp_path):
    calls,payload,consensus,persisted,state,run=_scenario(tmp_path)
    state["failure"]=OSError("provider unavailable")
    actual,document,wait=run()
    assert actual is None and document is None
    assert wait=={
       "schema":"SMART_TERMINAL_EXECUTOR_ACTIVE_EPOCH_1",
       "target_contest":3080,"status":"WAITING_OFFICIAL_RESULT",
       "preflight_status":"PASS","official_result_available":False,
       "canonical_writes_performed":False,"error_type":"OSError",
       "terminal_6of6_proven":False,
    }
    assert calls==["load",("fetch",3080)]
    assert list(tmp_path.iterdir())==[]


def test_existing_result_survives_provider_failure_without_rewrite(tmp_path):
    calls,payload,consensus,persisted,state,run=_scenario(tmp_path)
    state["existing"]=persisted
    state["failure"]=TimeoutError("refresh unavailable")
    assert run()==(*persisted,None)
    assert calls==["load",("fetch",3080)]


def test_adjudicated_result_without_persisted_evidence_propagates_failure(tmp_path):
    calls,payload,consensus,persisted,state,run=_scenario(tmp_path)
    state["adjudications"]=[{"event_type":"ADJUDICATION"}]
    state["failure"]=RuntimeError("official provider down")
    with pytest.raises(RuntimeError,match="official provider down"):
        run()
    assert calls==["load",("fetch",3080)]


def test_refresh_success_uses_preservation_guards_even_if_existing(tmp_path):
    calls,payload,consensus,persisted,state,run=_scenario(tmp_path)
    state["existing"]=persisted
    a,b,wait=run()
    assert a is payload and b is consensus and wait is None
    assert calls==["load",("fetch",3080),("primary",payload),("consensus",consensus)]


@pytest.mark.parametrize("step",["load","fetch","primary","consensus"])
def test_failures_are_not_converted_to_fake_success_or_suppressed(tmp_path,step):
    calls,payload,consensus,persisted,state,run=_scenario(tmp_path)
    error=ValueError("untrusted "+step)
    if step=="load":
        fn=lambda root: (_ for _ in ()).throw(error)
    elif step=="primary":
        fn=lambda root,payload: (_ for _ in ()).throw(error)
    elif step=="consensus":
        fn=lambda root,payload: (_ for _ in ()).throw(error)
    else:
        state["adjudications"]=[{"event_type":"ADJUDICATION"}]
        state["failure"]=error
        fn=None
    kwargs=dict(target=3080,schema="schema",load_existing=lambda root:None,
        ensure_primary=lambda root,payload:payload,
        ensure_consensus=lambda root,payload:payload)
    if step=="load":kwargs["load_existing"]=fn
    elif step=="primary":kwargs["ensure_primary"]=fn
    elif step=="consensus":kwargs["ensure_consensus"]=fn
    with pytest.raises(ValueError,match="untrusted "+step):
        acquire_official_result(tmp_path,
            lambda target:(payload,consensus) if step!="fetch" else (_ for _ in ()).throw(error),
            state["adjudications"],**kwargs)


def test_exception_type_is_recorded_without_leaking_provider_text(tmp_path):
    calls,payload,consensus,persisted,state,run=_scenario(tmp_path)
    state["failure"]=ConnectionError("secret provider detail")
    wait=run()[2]
    assert wait["error_type"]=="ConnectionError"
    assert "secret provider detail" not in str(wait)


def test_status_does_not_claim_proof_when_fetch_is_unavailable(tmp_path):
    calls,payload,consensus,persisted,state,run=_scenario(tmp_path)
    state["failure"]=TimeoutError("unavailable")
    wait=run()[2]
    assert wait["terminal_6of6_proven"] is False
    assert wait["canonical_writes_performed"] is False
