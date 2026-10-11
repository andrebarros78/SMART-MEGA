import json
import threading
import time

import pytest
from smart_video_observation import ObservationConfig, _observation_fingerprint, EXTRACTOR_VERSION
from smart_video_learning import get_visual_features, observe_batch


def resolver(url, timeout):
    return {"source_url":url,"stream_url":url,"video_id":url,"duration_s":120.0,
            "format_id":"low","height":320,"width":420,"resolver":"fake","protocol":"https"}


def sampler(spec, timeout):
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
            "grid_energy":grid,"grid_energy_alt":alt,
            "global_motion_fraction":0.0}


def records():
    return [{"contest_id":str(x),"source_url":f"https://example.org/video{x}.mp4"}
            for x in (4501,4502,4503,4504)]


def test_batch_concurrency_and_idempotent_shared_memory(tmp_path):
    lock=threading.Lock()
    active=[0];peak=[0]
    def slow_resolver(url,timeout):
        with lock:
            active[0]+=1;peak[0]=max(peak[0],active[0])
        time.sleep(.035)
        with lock:active[0]-=1
        return resolver(url,timeout)
    cfg=ObservationConfig(coarse_points=8,workers=2)
    first=observe_batch(records(),tmp_path,cfg,batch_workers=2,
                        resolver=slow_resolver,sampler=sampler)
    assert peak[0]>=2
    assert first["processed"]==4
    assert first["reused"]==0
    assert first["learning_training_observations"]==4
    assert first["consumer_features"]["status"]=="ACTIVE"
    assert first["consumer_features"]["predictive_weight"]==0.0
    assert first["consumer_features"]["source_contests"]==[4501,4502,4503,4504]
    assert len(list((tmp_path/"learning_history").glob("*.json")))==1
    checkpoint_bytes={p.name:p.read_bytes() for p in tmp_path.glob("contest_*.json")}
    def fail_resolver(*args):raise AssertionError("stream should not be reopened")
    again=observe_batch(records(),tmp_path,cfg,batch_workers=2,
                        resolver=fail_resolver,sampler=sampler)
    assert again["reused"]==4
    assert again["learning_state_sha256"]==first["learning_state_sha256"]
    assert len(list((tmp_path/"learning_history").glob("*.json")))==1
    assert all(p.read_bytes()==checkpoint_bytes[p.name] for p in tmp_path.glob("contest_*.json"))


def test_consumer_cutoff_and_target_exclusion(tmp_path):
    cfg=ObservationConfig()
    for n in (4601,4602,4603,4604):
        url=f"https://example.org/v{n}.mp4"
        cp={"schema":"smart.video_observation.v1","contest_id":str(n),
            "source":url,"extractor_version":EXTRACTOR_VERSION,"hypothesis_id":None,
            "main_params":vars(cfg),"status":"CANDIDATE",
            "predictive_evidence":"NOT_ESTABLISHED",
            "spatial_consensus":{"recurrent":True},
            "analysis_scope":{"start_s":0.0,"end_s":100.0,"segment_guard_passed":True},
            "event_timestamps_s":[40.0,50.0,60.0],
            "created_at_utc":"2026-10-11T12:00:00Z" if n<4604 else "2026-10-12T12:00:00Z",
            "checkpoint_fingerprint":_observation_fingerprint(str(n),url,cfg,None)}
        (tmp_path/f"contest_{n}.json").write_text(json.dumps(cp),encoding="utf-8")
    value=get_visual_features("4605","2026-10-11T13:00:00+00:00",tmp_path)
    assert value["source_contests"]==[4601,4602,4603]
    assert value["quality"]["consensus_active"] is True
    assert value["predictive_weight_authorized"] is False
    assert get_visual_features("4602","2026-10-11T13:00:00Z",tmp_path)["source_contests"]==[4601]
    assert get_visual_features("4605","2026-10-10T12:00:00Z",tmp_path)["source_contests"]==[]
    with pytest.raises(ValueError,match="timezone"):
        get_visual_features("4605","2026-10-11",tmp_path)
    assert not (tmp_path/"SMART_VISUAL_LEARNING_STATE.json").exists()


def test_invalid_batch_never_writes(tmp_path):
    items=records()
    with pytest.raises(ValueError,match="duplicate"):
        observe_batch([items[0],items[0]],tmp_path)
    with pytest.raises(ValueError,match="follow"):
        observe_batch(items[:1],tmp_path,next_contest="4501")
    with pytest.raises(ValueError,match="between"):
        observe_batch(items[:1],tmp_path,batch_workers=5)
    assert list(tmp_path.iterdir())==[]


def test_batch_failure_isolated_without_fake_learning(tmp_path):
    def one_blocked(url,timeout):
        if "4501" in url:raise RuntimeError("blocked")
        return resolver(url,timeout)
    result=observe_batch(records()[:2],tmp_path,
            ObservationConfig(coarse_points=8),batch_workers=2,
            resolver=one_blocked,sampler=sampler)
    assert result["status"]=="PARTIAL"
    assert result["statuses"]==["STREAM_FAILED","CANDIDATE"]
    assert result["learning_training_observations"]==1
    assert result["consumer_features"]["predictive_weight_authorized"] is False
    assert (tmp_path/"contest_4501.json").exists()
