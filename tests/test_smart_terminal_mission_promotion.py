"""Terminal MISSION_PROVEN requires eligibility and persistent hash-bound proof."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from smart_terminal_mission_promotion import promote_terminal_mission


def _case(root):
    state={"status":"MISSION_ACTIVE","terminal_6of6_proven":False,"terminal_rule":"6of6"}
    for name in ("freeze.json","ledger.json","consensus.json","audit.json"):
        (root/name).write_text(name,encoding="utf-8")
    binding={"freeze":root/"freeze.json","ledger":root/"ledger.json","mode":"ACTIVE_EPOCH",
             "freeze_sha256":hashlib.sha256((root/"freeze.json").read_bytes()).hexdigest()}
    evaluations={"eligible_for_mission_proven":True,"frozen_top6":[1,2,3,4,5,6],
                 "actual_numbers":[1,2,3,4,5,6],"checks":{"all_attempts_counted":True}}
    consensus={"terminal_source_corroboration_authorized":True}
    audit={"status":"PASS"}
    sequence={"sequence_sha256":"a"*64}
    writes=[]
    def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def save(path,document):
        path=Path(path)
        path.write_text(json.dumps(document,sort_keys=True),encoding="utf-8")
        writes.append((path,document))
    def load(path,root):
        return state.copy()
    def mission_write(path,mission,root):
        writes.append(("mission",mission))
        state.clear();state.update(mission)
    def canonical(doc):
        return hashlib.sha256(json.dumps(doc,sort_keys=True).encode("utf-8")).hexdigest()
    opts=dict(
        target=3080,terminal_proof="proof.json",
        consensus_file="consensus.json",independent_audit_file="audit.json",
        load_mission_status=load,write_mission_status=mission_write,
        runtime_binding=lambda root:binding,
        sha256_file=sha,mission_sha256_json=canonical,atomic_write_json=save,
    )
    def run(binding_override=None):
        return promote_terminal_mission(root,evaluations,consensus,audit,sequence,
                                        binding=binding_override,**opts)
    return state,binding,evaluations,consensus,audit,sequence,opts,writes,run


def test_ineligible_evaluation_never_reads_mission_or_writes(tmp_path):
    state,binding,evaluation,consensus,audit,seq,opts,writes,run=_case(tmp_path)
    evaluation["eligible_for_mission_proven"]=False
    opts["load_mission_status"]=lambda *args,**kwargs: pytest.fail("eligibility must gate all operations")
    with pytest.raises(ValueError,match="fully eligible evaluation"):
        run()
    assert writes==[]


@pytest.mark.parametrize("eligible", [None, 0, "true"])
def test_only_boolean_true_is_eligible(tmp_path,eligible):
    state,binding,evaluation,consensus,audit,seq,opts,writes,run=_case(tmp_path)
    evaluation["eligible_for_mission_proven"]=eligible
    with pytest.raises(ValueError,match="fully eligible evaluation"):
        run()
    assert writes==[]


def test_existing_verified_mission_is_returned_unchanged_without_writing(tmp_path):
    state,binding,evaluation,consensus,audit,seq,opts,writes,run=_case(tmp_path)
    state.update({"status":"MISSION_PROVEN","terminal_6of6_proven":True,"receipt":"existing"})
    assert run() == state
    assert writes==[]


@pytest.mark.parametrize("status",["WAITING", "MISSION_PROVEN","UNKNOWN"])
def test_unexpected_nonproven_mission_status_does_not_promote(tmp_path,status):
    state,binding,evaluation,consensus,audit,seq,opts,writes,run=_case(tmp_path)
    state["status"]=status
    with pytest.raises(ValueError,match="unexpected mission state"):
        run()
    assert writes==[]


def test_eligible_promotion_persists_proof_before_mission_status(tmp_path):
    state,binding,evaluation,consensus,audit,seq,opts,writes,run=_case(tmp_path)
    result=run(binding_override=binding)
    proof_path=tmp_path/"proof.json"
    proof=json.loads(proof_path.read_text())
    assert [x[0] for x in writes]==[proof_path,"mission"]
    assert proof["schema"]=="SMART_TERMINAL_6OF6_PROOF_1"
    assert proof["freeze_file"]=="freeze.json"
    assert proof["signal_ledger_file"]=="ledger.json"
    assert proof["freeze_sha256"]==binding["freeze_sha256"]
    assert proof["target_contest"]==3080
    assert proof["retroactive_selection_prohibited"] is True
    assert proof["status"]=="MISSION_PROVEN"
    assert result["terminal_6of6_proven"] is True
    assert result["terminal_proof_sha256"]==opts["sha256_file"](proof_path)
    assert result["proven_top6"]==[1,2,3,4,5,6]


def test_failed_mission_commit_removes_new_proof_and_does_not_claim_completion(tmp_path):
    state,binding,evaluation,consensus,audit,seq,opts,writes,run=_case(tmp_path)
    def fail(*args,**kwargs):
        raise OSError("mission file unavailable")
    opts["write_mission_status"]=fail
    with pytest.raises(OSError,match="mission file unavailable"):
        run(binding_override=binding)
    assert not (tmp_path/"proof.json").exists()
    assert state["terminal_6of6_proven"] is False


def test_failed_proof_writer_never_commits_mission(tmp_path):
    state,binding,evaluation,consensus,audit,seq,opts,writes,run=_case(tmp_path)
    opts["atomic_write_json"]=lambda *args: (_ for _ in ()).throw(OSError("proof disk unavailable"))
    with pytest.raises(OSError,match="proof disk unavailable"):
        run(binding_override=binding)
    assert writes==[]
    assert state["terminal_6of6_proven"] is False


def test_outside_root_freeze_cannot_be_used_for_provenance(tmp_path):
    state,binding,evaluation,consensus,audit,seq,opts,writes,run=_case(tmp_path)
    outside=tmp_path.parent/"foreign-freeze.json"
    binding["freeze"]=outside
    with pytest.raises(ValueError):
        run(binding_override=binding)
    assert writes==[]


def test_runtime_binding_is_deferred_until_eligibility_confirmed(tmp_path):
    state,binding,evaluation,consensus,audit,seq,opts,writes,run=_case(tmp_path)
    evaluation["eligible_for_mission_proven"]=False
    opts["runtime_binding"]=lambda *args:pytest.fail("runtime authority must not be touched")
    with pytest.raises(ValueError,match="fully eligible evaluation"):
        run()
    assert writes==[]