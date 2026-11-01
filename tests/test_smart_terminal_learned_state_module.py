"""Frozen learning policy and after-result replay remain fail-closed."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from smart_terminal_learned_state import (
    agent_from_prestate, verify_existing_learned_policy, ensure_learned_state,
)


TARGET=3070
CUTOFF=3069


def _prestate():
    return {
        "last_contest":CUTOFF,"start_index":30,"eta":0.2,
        "meta_strength":0.1,"redundancy_consensus_threshold":0.85,
        "calibration_strength":0.0,
        "architecture_profile":"DIVERSITY_HARDENED_V1",
        "online_learning_max_abs_step":0.75,
        "bounded_online_learning":{
            "expert":{"clipped_update_count":10},
            "family":{"clipped_update_count":20}},
        "meta_governor":{"selected_cumulative_hits":30},
        "training_rows":100,
    }


class FakeAgent:
    initialized=[]
    def __init__(self, **kwargs):
        self.initialized.append(kwargs)
        self.redundancy_threshold=kwargs["redundancy_threshold"]
        self.architecture_profile="DIVERSITY_HARDENED_V1"
        self.online_max_abs_step=0.75
        self.profile=None
        self.replay_calls=[]
    def _configure_target_profile(self, target):self.profile=target
    def _reset_states(self):pass
    def replay_history(self,draws,contests):
        self.replay_calls.append((draws,contests,Path.cwd()))
    def state_document(self,**kwargs):
        return {"last_contest":TARGET,**kwargs}


def _learned():
    frozen=_prestate()
    return {
        "last_contest":TARGET,
        "architecture_profile":frozen["architecture_profile"],
        "online_learning_max_abs_step":0.75,
        "redundancy_consensus_threshold":0.85,
        "calibration_strength":0.0,
        "training_rows":101,
        "bounded_online_learning":{
            "expert":{"max_abs_step":0.75,"clipped_update_count":11},
            "family":{"max_abs_step":0.75,"clipped_update_count":21}},
        "meta_governor":{"selected_cumulative_hits":31},
    }


def _create(frozen=None):
    return agent_from_prestate(frozen or _prestate(),target_contest=TARGET,
                               agent_factory=FakeAgent)


def test_agent_is_rebuilt_with_frozen_noncalibrated_policy():
    FakeAgent.initialized.clear()
    agent=_create()
    assert agent.profile==TARGET
    assert FakeAgent.initialized[0]["calibration_strength"]==0.0
    assert FakeAgent.initialized[0]["redundancy_threshold"]==0.85


@pytest.mark.parametrize("property,value,match",[
    ("last_contest",3068,"cutoff mismatch"),
    ("calibration_strength",0.2,"independent promotion authority"),
    ("architecture_profile","LEGACY_COMPATIBLE","profile mismatch"),
    ("online_learning_max_abs_step",2.5,"profile mismatch"),
])
def test_invalid_prestate_rejected(property,value,match):
    frozen=_prestate()
    frozen[property]=value
    with pytest.raises(ValueError,match=match):
        _create(frozen)


def test_existing_learned_state_policy_matches_all_guards():
    verify_existing_learned_policy(_prestate(),_learned(),TARGET,
                                   agent_from_prestate=lambda state,target_contest:_create(state))


@pytest.mark.parametrize("mutation,match",[
    ("profile","policy differs"),
    ("cap","guard cap mismatch"),
    ("counter","counter regression"),
    ("governor","governor counter anomaly"),
    ("rows","training-row count mismatch"),
])
def test_learned_policy_mutation_is_not_reused(mutation,match):
    learned=_learned()
    if mutation=="profile":learned["architecture_profile"]="LEGACY_COMPATIBLE"
    elif mutation=="cap":learned["bounded_online_learning"]["expert"]["max_abs_step"]=2.5
    elif mutation=="counter":learned["bounded_online_learning"]["family"]["clipped_update_count"]=19
    elif mutation=="governor":learned["meta_governor"]["selected_cumulative_hits"]=37
    elif mutation=="rows":learned["training_rows"]=99
    with pytest.raises(ValueError,match=match):
        verify_existing_learned_policy(_prestate(),learned,TARGET,
                                       agent_from_prestate=lambda state,target_contest:_create(state))


def _state_case(root):
    frozen=_prestate()
    predata=root/"old.xlsx";through=root/"official.xlsx";prestate=root/"prestate.json";learned=root/"learned.json"
    predata.write_bytes(b"historical");through.write_bytes(b"historical and official")
    frozen["data_sha256"]=hashlib.sha256(predata.read_bytes()).hexdigest()
    prestate.write_text(json.dumps(frozen),encoding="utf-8")
    binding={"state":prestate,"learned":learned,"data":predata,
             "freeze_sha256":"f"*64,"mode":"ACTIVE_EPOCH"}
    writes=[];replays=[]
    def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def factory(state,target_contest):
        return _create(state)
    def save(path,doc):writes.append((path,doc))
    options=dict(
        target=TARGET,cutoff=CUTOFF,result_data="official.xlsx",
        sha256_file=sha,read_json=lambda path:json.loads(Path(path).read_text()),
        load_draws=lambda path:([[1,2,3,4,5,6]],[TARGET]),
        agent_from_prestate=factory,
        verify_existing_learned_policy=lambda state,learned,target:
          verify_existing_learned_policy(state,learned,target,agent_from_prestate=factory),
        atomic_write_json=save,
    )
    def run():return ensure_learned_state(root,binding,**options)
    return frozen,binding,options,writes,run


def test_first_replay_is_bound_to_frozen_epoch_and_persisted(tmp_path):
    frozen,binding,options,writes,run=_state_case(tmp_path)
    before=Path.cwd()
    result=run()
    assert result["last_contest"]==TARGET
    assert result["learning_after_adjudication"] is True
    assert result["retroactive_rewrite"] is False
    assert result["source_freeze_sha256"]=="f"*64
    assert result["authority_mode"]=="ACTIVE_EPOCH"
    assert result["source_prestate_sha256"]==options["sha256_file"](binding["state"])
    assert writes==[(binding["learned"],result)]
    assert Path.cwd()==before


def test_existing_valid_learned_state_is_returned_without_replaying(tmp_path):
    frozen,binding,options,writes,run=_state_case(tmp_path)
    learned=_learned()
    learned["data_sha256"]=options["sha256_file"](tmp_path/"official.xlsx")
    binding["learned"].write_text(json.dumps(learned),encoding="utf-8")
    assert run()==learned
    assert writes==[]


@pytest.mark.parametrize("reason,match",[
    ("cutoff","does not end at cutoff"),
    ("pre_hash","prestate data hash mismatch"),
    ("target_result","result data does not end at target"),
])
def test_replay_rejects_wrong_preconditions_without_writing(tmp_path,reason,match):
    frozen,binding,options,writes,run=_state_case(tmp_path)
    if reason=="cutoff":
        frozen["last_contest"]=CUTOFF-1
        binding["state"].write_text(json.dumps(frozen),encoding="utf-8")
    elif reason=="pre_hash":
        binding["data"].write_bytes(b"changed pre-history")
    else:
        options["load_draws"]=lambda path:([[1,2,3,4,5,6]],[CUTOFF])
    with pytest.raises(ValueError,match=match):run()
    assert writes==[]


def test_existing_wrong_result_hash_never_replays_or_mutates(tmp_path):
    frozen,binding,options,writes,run=_state_case(tmp_path)
    binding["learned"].write_text(json.dumps({**_learned(),"data_sha256":"0"*64}),encoding="utf-8")
    with pytest.raises(ValueError,match="not bound to official target data"):
        run()
    assert writes==[]