"""Durable CAIXA official discovery -> observer integration regressions."""
import json
from pathlib import Path

import pytest

from smart_video_official_catalog import CHANNEL, URL, ingest, enrich
from smart_video_official_queue import (
    _read_state, _checkpoint_proof, run_official_queue,
)
from smart_video_learning import get_visual_features
from smart_video_observation import ObservationConfig

def official(tmp_path, n=3, *, duplicate=False):
    cat=tmp_path/"catalog"
    rows=[
        {"id":f"v{i:010d}", "title":f"Loterias da CAIXA {i}"}
        for i in range(1, n+1)
    ]
    inp={"channel_id":CHANNEL,"source_url":URL,"entries":rows}
    ingest(inp,cat,max_items=max(n,1))
    details=[
        {"id":row["id"],"channel_id":CHANNEL,
         "description":f"Sorteio da Mega-Sena concurso {4500+i}"}
        for i,row in enumerate(rows,1)
    ]
    if duplicate and n>=2:
        details[1]["description"]=details[0]["description"]
    enrich(details,cat)
    return cat

def options(tmp_path, cat):
    return dict(catalog_dir=cat,checkpoint_dir=tmp_path/"checkpoints",
                queue_dir=tmp_path/"queue",batch_workers=2,workers=1)

def resolver(url,timeout):
    return {"source_url":url,"stream_url":url,"video_id":url,"duration_s":120.0,
            "format_id":"low","height":320,"width":420,"resolver":"fake","protocol":"https"}

def sampler(spec,timeout):
    start=float(spec["start_s"])
    if spec["duration_s"]<=3:
        score=0.05 if 30<start<90 else 0.001
        grid=[0.01]*12
        return {"status":"OK","start_s":start,"duration_s":spec["duration_s"],
                "mean_motion":score,"median_motion":score,"max_motion":score,
                "motion_scores":[score]*8,"sample_times":[start+i*.2 for i in range(8)],
                "grid_energy":grid,"grid_energy_alt":[0.01]*16,
                "global_motion_fraction":0.0}
    scores=[0.01,0.012,.08,.011,.09,.012,.085,.01]
    grid=[0.001]*12;grid[5]=.08
    alt=[0.001]*16;alt[6]=.08
    return {"status":"OK","start_s":start,"duration_s":spec["duration_s"],
            "mean_motion":sum(scores)/len(scores),"median_motion":.012,
            "max_motion":.09,"motion_scores":scores,
            "sample_times":[start+i*.5 for i in range(8)],
            "grid_energy":grid,"grid_energy_alt":alt,"global_motion_fraction":0.0}

def bad(*args,**kwargs):
    raise AssertionError("OFFICIAL_VIDEO_MUST_NOT_REOPEN")

def test_only_official_unambiguous_contests_enter_queue(tmp_path):
    cat=official(tmp_path,3,duplicate=True)
    report=run_official_queue(**options(tmp_path,cat),dry_run=True)
    assert report["catalog_broadcasts"]==3
    assert report["ambiguous_contests_blocked"]==1
    assert report["eligible_unique_contests"]==1
    assert report["attempted_this_run"]==0
    assert not (tmp_path/"queue").exists()
    assert not (tmp_path/"checkpoints").exists()

def test_real_observer_produces_checkpoints_and_idempotent_reuse(tmp_path):
    cat=official(tmp_path,4)
    opts=options(tmp_path,cat)
    r=run_official_queue(**opts,max_items=4,resolver=resolver,sampler=sampler)
    assert r["attempted_this_run"]==4
    assert r["verified_checkpoints"]==4
    assert r["waves_this_run"]==2
    before={p.name:p.read_bytes() for p in opts["checkpoint_dir"].glob("contest_*.json")}
    snapshot=_read_state(opts["queue_dir"])
    memory=(opts["checkpoint_dir"]/"SMART_VISUAL_LEARNING_STATE.json")
    assert memory.is_file()
    assert get_visual_features("4505","2026-10-20T00:00:00Z",opts["checkpoint_dir"])["predictive_weight"]==0
    again=run_official_queue(**opts,resolver=bad,sampler=bad)
    after=_read_state(opts["queue_dir"])
    assert again["attempted_this_run"]==0
    assert again["verified_checkpoints"]==4
    assert after["sha256"]==snapshot["sha256"]
    assert before=={p.name:p.read_bytes() for p in opts["checkpoint_dir"].glob("contest_*.json")}

def test_interrupted_after_completed_wave_recovers_without_fetch(tmp_path,monkeypatch):
    cat=official(tmp_path,2)
    opts=options(tmp_path,cat)
    import smart_video_official_queue as bridge
    underlying=bridge.observe_batch
    def crash(*a,**k):
        underlying(*a,**k)
        (opts["checkpoint_dir"]/"SMART_VISUAL_LEARNING_STATE.json").unlink()
        raise KeyboardInterrupt("simulated host death after checkpoints")
    monkeypatch.setattr(bridge,"observe_batch",crash)
    with pytest.raises(KeyboardInterrupt):
        run_official_queue(**opts,max_items=2,resolver=resolver,sampler=sampler)
    state=_read_state(opts["queue_dir"])
    assert all(r["state"]=="RUNNING" for r in state["records"].values())
    monkeypatch.setattr(bridge,"observe_batch",underlying)
    after=run_official_queue(**opts,resolver=bad,sampler=bad)
    assert after["attempted_this_run"]==0
    assert after["verified_checkpoints"]==2
    assert (opts["checkpoint_dir"]/"SMART_VISUAL_LEARNING_STATE.json").is_file()

def test_checkpoint_tamper_detected_without_reprocessing(tmp_path):
    cat=official(tmp_path,1)
    opts=options(tmp_path,cat)
    run_official_queue(**opts,resolver=resolver,sampler=sampler)
    cp=next(opts["checkpoint_dir"].glob("contest_*.json"))
    data=json.loads(cp.read_text())
    data["checkpoint_fingerprint"]="corrupted"
    cp.write_text(json.dumps(data),encoding="utf-8")
    with pytest.raises(ValueError,match="COMPLETED_CHECKPOINT_LOST_OR_CHANGED"):
        run_official_queue(**opts,resolver=bad,sampler=bad)

def test_preexisting_invalid_completed_checkpoint_quarantined(tmp_path):
    cat=official(tmp_path,1)
    opts=options(tmp_path,cat)
    opts["checkpoint_dir"].mkdir()
    (opts["checkpoint_dir"]/"contest_4501.json").write_text(
        '{"schema":"smart.video_observation.v1","status":"CANDIDATE","contest_id":"4501"}'
    )
    output=run_official_queue(**opts,resolver=bad,sampler=bad)
    assert output["quarantined"]==1 and output["attempted_this_run"]==0

def test_recoverable_failures_retry_on_future_run_only(tmp_path):
    cat=official(tmp_path,2)
    opts=options(tmp_path,cat)
    def fail_resolver(url,timeout):
        raise ConnectionError("network denied")
    r1=run_official_queue(**opts,max_attempts=2,resolver=fail_resolver,sampler=sampler)
    assert r1["attempted_this_run"]==2
    assert r1["verified_checkpoints"]==0
    assert all(r["attempts"]==1 for r in _read_state(opts["queue_dir"])["records"].values())
    r2=run_official_queue(**opts,max_attempts=2,resolver=fail_resolver,sampler=sampler)
    assert r2["attempted_this_run"]==2
    assert r2["exhausted"]==2
    r3=run_official_queue(**opts,max_attempts=2,resolver=bad,sampler=bad)
    assert r3["attempted_this_run"]==0

def test_source_identity_revision_fails_closed(tmp_path):
    cat=official(tmp_path,1)
    opts=options(tmp_path,cat)
    run_official_queue(**opts,dry_run=False,resolver=resolver,sampler=sampler)
    enrich([{"id":"v0000000001","channel_id":CHANNEL,
             "description":"Mega-Sena concurso 4501, transmissão revisada"}],cat)
    with pytest.raises(ValueError,match="QUEUE_SOURCE_IDENTITY_DRIFT"):
        run_official_queue(**opts,resolver=bad,sampler=bad)

def test_500_catalogued_broadcasts_are_not_500_learned(tmp_path):
    cat=official(tmp_path,500)
    opts=options(tmp_path,cat)
    report=run_official_queue(**opts,dry_run=True,max_items=500)
    assert report["catalog_broadcasts"]==500
    assert report["eligible_unique_contests"]==500
    assert report["verified_checkpoints"]==0
    assert report["real_media_verified"] is False
    assert not opts["queue_dir"].exists()

def test_reject_wrong_resource_budget_and_same_path(tmp_path):
    cat=official(tmp_path,1)
    opts=options(tmp_path,cat)
    with pytest.raises(ValueError,match="RESOURCE_BUDGET"):
        run_official_queue(**{**opts, 'batch_workers':8,'workers':2})
    with pytest.raises(ValueError,match="MUST_DIFFER"):
        run_official_queue(cat,tmp_path/"same",tmp_path/"same",dry_run=True)

def test_queue_state_pointer_tamper_stops(tmp_path):
    cat=official(tmp_path,1)
    opts=options(tmp_path,cat)
    run_official_queue(**opts,resolver=resolver,sampler=sampler)
    p=opts["queue_dir"]/"SMART_CAIXA_VISUAL_QUEUE_CURRENT.json"
    row=json.loads(p.read_text());row["records"]["4501"]["attempts"]=44
    p.write_text(json.dumps(row),encoding="utf-8")
    with pytest.raises(ValueError,match="QUEUE_CHECKSUM"):
        run_official_queue(**opts,resolver=bad,sampler=bad)


def test_sync_only_persists_all_entries_without_video(tmp_path):
    cat=official(tmp_path,500)
    opts=options(tmp_path,cat)
    one=run_official_queue(**opts,sync_only=True,resolver=bad,sampler=bad)
    assert one["sync_only"] is True
    assert one["eligible_unique_contests"]==500
    assert one["attempted_this_run"]==0
    assert one["pending"]==500
    assert not opts["checkpoint_dir"].exists()
    saved=_read_state(opts["queue_dir"])
    assert saved["catalog_sha256"] and len(saved["records"])==500
    assert set(row["state"] for row in saved["records"].values())=={"PENDING"}
    again=run_official_queue(**opts,sync_only=True,resolver=bad,sampler=bad)
    assert one["queue_state_sha256"]==again["queue_state_sha256"]
    assert len(list((opts["queue_dir"]/"queue_history").glob("*.json")))==1


def test_conflicting_dry_and_sync_modes_denied(tmp_path):
    cat=official(tmp_path,1)
    with pytest.raises(ValueError,match="CONFLICT"):
        run_official_queue(**options(tmp_path,cat),dry_run=True,sync_only=True)
