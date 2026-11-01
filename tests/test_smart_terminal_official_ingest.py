"""Characterization: official ingest and adjudication are fail-closed."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import pytest

from smart_terminal_official_ingest import ensure_ingest, ensure_adjudication


def _ingest_case(tmp_path):
    payload = {"numbers": [1,2,3,4,5,6], "draw_date": "2026-11-01"}
    events=[]
    through = tmp_path / "official.xlsx"
    proof_path = tmp_path / "ingest.json"
    proof = {"target_contest":3080,"actual_numbers":payload["numbers"],"output_sha256":""}
    state={"cutoff":3079,"last":3080,"calls":[]}
    def fingerprint(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def write_existing():
        through.write_bytes(b"official")
        proof["output_sha256"]=fingerprint(through)
        proof_path.write_text(json.dumps(proof),encoding="utf-8")
    config=dict(target=3080,cutoff=3079,result_data="official.xlsx",ingest_proof="ingest.json",
        normalize_primary=lambda raw:{"numbers":raw["numbers"]},
        read_json=lambda path:json.loads(Path(path).read_text()),
        sha256_file=fingerprint,
        load_draws=lambda path:([],[3079,state["last"]]),
        runtime_binding=lambda root: (_ for _ in ()).throw(AssertionError("must not resolve runtime authority on existing evidence")),
        contest_max=lambda path:state["cutoff"],
        ingest=lambda source, output, proof_file, target, data: state["calls"].append((source,output,proof_file,target,data)) or {"status":"INGESTED"})
    def run(binding=None):
        return ensure_ingest(tmp_path,payload,binding=binding,**config)
    return payload,config,state,proof,through,proof_path,write_existing,run


def test_existing_ingest_verified_and_no_runtime_dependency(tmp_path):
    payload, cfg, state, proof, through, path, setup, run=_ingest_case(tmp_path)
    setup()
    assert run()==proof
    assert state["calls"]==[]


@pytest.mark.parametrize("invalid, message",[
    ("missing_proof","partially present"),
    ("missing_file","partially present"),
    ("wrong_target","proof conflicts"),
    ("wrong_numbers","proof conflicts"),
    ("wrong_hash","hash mismatch"),
    ("wrong_last","does not end at target"),
])
def test_existing_ingest_rejects_unverified_content(tmp_path,invalid,message):
    payload, cfg, state, proof, through, path, setup, run=_ingest_case(tmp_path)
    setup()
    if invalid=="missing_proof": path.unlink()
    elif invalid=="missing_file": through.unlink()
    elif invalid=="wrong_target": proof["target_contest"]=3079
    elif invalid=="wrong_numbers": proof["actual_numbers"]=[1,2,3,4,5,7]
    elif invalid=="wrong_hash": proof["output_sha256"]="0"*64
    elif invalid=="wrong_last": state["last"]=3079
    if invalid in {"wrong_target","wrong_numbers","wrong_hash"}:
        path.write_text(json.dumps(proof),encoding="utf-8")
    with pytest.raises(ValueError,match=message):
        run()
    assert state["calls"]==[]


def test_first_ingest_requires_cutoff_and_passes_identity(tmp_path):
    payload, cfg, state, proof, through, path, setup, run=_ingest_case(tmp_path)
    source=tmp_path/"previous.xlsx"
    result=run(binding={"data":source})
    assert result=={"status":"INGESTED"}
    assert state["calls"]==[(source,through,path,3080,payload)]


def test_first_ingest_fails_when_cutoff_is_wrong(tmp_path):
    payload,cfg,state,proof,through,path,setup,run=_ingest_case(tmp_path)
    state["cutoff"]=3078
    with pytest.raises(ValueError,match="must end at cutoff"):
        run(binding={"data":tmp_path/"previous.xlsx"})
    assert state["calls"]==[]


def _adjudication_case(tmp_path):
    root=tmp_path
    recorded={"events":[]}
    calls=[]
    binding={"ledger":root/"ledger.json","freeze_sha256":"a"*64}
    config=dict(target=3080,result_data="official.xlsx",
        runtime_binding=lambda path:binding,
        load_ledger=lambda path:recorded,
        target_events=lambda ledger,kind:[e for e in ledger["events"] if e["event_type"]==kind],
        adjudicate=lambda path,target,ledger:calls.append((path,target,ledger,Path.cwd())) or {"champion_hits":0})
    def run(nums=None, binding_override=None):
        return ensure_adjudication(root,nums or [1,2,3,4,5,6],
                                   binding=binding_override,**config)
    event={"event_type":"ADJUDICATION","actual_numbers":[6,5,4,3,2,1],
           "freeze_sha256":"a"*64,"champion_hits":"3","challenger_hits":"1","e_value_after":"1.5"}
    return binding,recorded,calls,config,event,run


def test_existing_adjudication_idempotent_and_read_only(tmp_path):
    binding,recorded,calls,cfg,event,run=_adjudication_case(tmp_path)
    recorded["events"].append(event)
    result=run()
    assert result=={"status":"ALREADY_ADJUDICATED_EVENT_PRESERVED",
                    "target_contest":3080,"actual_numbers":event["actual_numbers"],
                    "champion_hits":3,"challenger_hits":1,"e_value_after":1.5}
    assert calls==[]


@pytest.mark.parametrize("reason, match",[
    ("duplicate","multiple 3054 adjudications"),
    ("numbers","conflicts with official result"),
    ("freeze","outside the active epoch"),
])
def test_bad_adjudication_refuses_repeat_or_mismatched_authority(tmp_path,reason,match):
    binding,recorded,calls,cfg,event,run=_adjudication_case(tmp_path)
    recorded["events"].append(event)
    if reason=="duplicate": recorded["events"].append(dict(event))
    elif reason=="numbers": event["actual_numbers"]=[1,2,3,4,5,7]
    elif reason=="freeze": event["freeze_sha256"]="b"*64
    with pytest.raises(ValueError,match=match):
        run()
    assert calls==[]


def test_new_adjudication_executes_at_project_root_and_restores_cwd(tmp_path):
    binding,recorded,calls,cfg,event,run=_adjudication_case(tmp_path)
    before=Path.cwd()
    result=run()
    assert result=={"champion_hits":0,"status":"ADJUDICATED"}
    assert calls==[(tmp_path/"official.xlsx",3080,tmp_path/"ledger.json",tmp_path)]
    assert Path.cwd()==before


def test_failed_adjudication_restores_cwd_and_propagates(tmp_path):
    binding,recorded,calls,cfg,event,run=_adjudication_case(tmp_path)
    cfg["adjudicate"]=lambda *args: (_ for _ in ()).throw(RuntimeError("ledger failed"))
    before=Path.cwd()
    with pytest.raises(RuntimeError,match="ledger failed"):
        run()
    assert Path.cwd()==before