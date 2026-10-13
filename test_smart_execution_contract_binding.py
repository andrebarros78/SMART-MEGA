from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from smart_agent_runtime import ORDER, sha256_json
from smart_agent_skill_consumer_contract import (
    EXPECTED_EXECUTION_CONTRACT_SHA256, bind_consumer_execution,
)
from smart_total_integration_gate import evaluate

ROOT = Path(__file__).resolve().parent
DATA_HASH = hashlib.sha256(b"immutable-history-cutoff").hexdigest()
EPOCH_ID = "epoch-isolated-contract-test"
TARGET = 3069
CUTOFF = 3068


@pytest.fixture(scope="module")
def synthetic_gate():
    # The builder executes real native agents, adapters and handoffs in BUILD.
    # Retagging the outer envelope exercises the PRE_FREEZE consumer contract
    # without pretending a historical result is a new prospective prediction.
    gate = copy.deepcopy(evaluate(ROOT, phase="BUILD"))
    assert gate["status"] == "PASS"
    gate["phase"] = "PRE_FREEZE"
    gate["sha256"] = sha256_json({k: v for k, v in gate.items() if k != "sha256"})
    return gate


def _file(tmp_path, gate):
    p = tmp_path / "PRE_FREEZE_TOTAL_INTEGRATION.json"
    p.write_text(json.dumps(gate, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def _bind(gate, proof, *, epoch=None, contract=None, target=TARGET, cutoff=CUTOFF):
    return bind_consumer_execution(
        gate, proof, contract_file=contract or ROOT/"SMART_AGENT_SKILL_EXECUTION_CONTRACT.json",
        epoch_dir=epoch or proof.parent, phase="PRE_FREEZE",
        epoch_id=EPOCH_ID, target_contest=target,
        cutoff_contest=cutoff, data_sha256=DATA_HASH,
    )


def test_execution_contract_has_pinned_hash_and_explicit_owners():
    p=ROOT/"SMART_AGENT_SKILL_EXECUTION_CONTRACT.json"
    obj=json.loads(p.read_text())
    digest=obj.pop("sha256")
    assert digest==sha256_json(obj)==EXPECTED_EXECUTION_CONTRACT_SHA256
    assert obj["agents"]["required_order"]==list(ORDER)
    assert obj["agents"]["count"]==9
    assert obj["skills"]["native_probe_alias_invocations"]==37
    assert obj["skills"]["quarantined_noncallable"]==4
    assert obj["llm"]["required"] is False
    assert obj["authority"]["consumer_can_change_weights"] is False


def test_current_epoch_consumes_agent_skill_proof(synthetic_gate,tmp_path):
    path=_file(tmp_path,synthetic_gate)
    receipt=_bind(synthetic_gate,path)
    assert receipt["status"]=="PASS"
    assert receipt["epoch_id"]==EPOCH_ID
    assert receipt["target_contest"]==TARGET
    assert receipt["cutoff_contest"]==CUTOFF
    assert receipt["agents_executed"]==9
    assert receipt["skills_native_invoked"]==37
    assert receipt["skills_quarantined"]==4
    assert receipt["handoffs_consumed"]>0
    assert receipt["llm_provider"] is None
    assert receipt["prediction_or_weight_influence"] is False
    assert receipt["sha256"]==sha256_json({k:v for k,v in receipt.items() if k!="sha256"})


def test_rejects_bogus_target_and_cross_epoch_proof(synthetic_gate,tmp_path):
    path=_file(tmp_path,synthetic_gate)
    with pytest.raises(RuntimeError,match="cycle"):
        _bind(synthetic_gate,path,target=3070,cutoff=3068)
    with pytest.raises(RuntimeError,match="another epoch"):
        _bind(synthetic_gate,path,epoch=tmp_path/"other")


def test_rejects_tampered_execution_contract_even_when_rehashed(synthetic_gate,tmp_path):
    path=_file(tmp_path,synthetic_gate)
    contract=json.loads((ROOT/"SMART_AGENT_SKILL_EXECUTION_CONTRACT.json").read_text())
    contract["consumer"]["fail_closed"]=False
    contract["sha256"]=sha256_json({k:v for k,v in contract.items() if k!="sha256"})
    forged=tmp_path/"forged-contract.json"
    forged.write_text(json.dumps(contract),encoding="utf-8")
    with pytest.raises(RuntimeError,match="not authorized"):
        _bind(synthetic_gate,path,contract=forged)


def test_rejects_missing_native_invocation_and_unconsumed_handoff(synthetic_gate,tmp_path):
    modified=copy.deepcopy(synthetic_gate)
    modified["native_invocations"].pop()
    modified["sha256"]=sha256_json({k:v for k,v in modified.items() if k!="sha256"})
    with pytest.raises(RuntimeError,match="incomplete"):
        _bind(modified,_file(tmp_path,modified))
    modified=copy.deepcopy(synthetic_gate)
    modified["operational_handoff_ledger"]["consumed_count"]-=1
    modified["sha256"]=sha256_json({k:v for k,v in modified.items() if k!="sha256"})
    with pytest.raises(RuntimeError,match="handoffs"):
        _bind(modified,_file(tmp_path,modified))


def test_pipeline_has_a_complete_ordered_consumer_contract():
    s=(ROOT/"smart_full_process_pipeline.py").read_text(encoding="utf-8-sig")
    assert s.count("bind_consumer_execution(")==2
    assert s.index("pre_consumer = bind_consumer_execution(")<s.index("freeze_champion_challenger(")
    assert s.index("post_consumer = bind_consumer_execution(")<s.index("primary_card_numbers =")
    assert '"agent_skill_consumer_bound_to_current_epoch"' in s
    assert '"agent_skill_consumer_receipts_match_gate_files"' in s
    assert '"execution_contract_sha256"' in s
    assert '"pre_freeze": pre_consumer' in s and '"post_freeze": post_consumer' in s
