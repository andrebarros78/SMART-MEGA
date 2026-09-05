from pathlib import Path
import json
from smart_agent_skill_functional_gate import evaluate,write


def root(): return Path(__file__).resolve().parent


def test_functional_gate_proves_full_matrix():
    d=evaluate(root()); assert d['status']=='PASS'; assert all(d['checks'].values()); assert len(d['matrix'])==41
    assert len({r['capability'] for r in d['matrix']})==41


def test_every_pertinent_capability_is_executable_through_owner_contract():
    d=evaluate(root())
    pertinent=[r for r in d['matrix'] if r['pertinent']]
    quarantined=[r for r in d['matrix'] if not r['pertinent']]
    assert len(pertinent)==37 and len(quarantined)==4
    for row in pertinent:
        assert row['agent_owner']; assert row['native_targets']; assert row['runtime_evidence']; assert row['status']=='PASS'
        assert row['callable'] is True; assert row['individual_invocation']['status']=='PASS'
    for row in quarantined:
        assert row['agent_owner']=='quarantine_curator'; assert row['callable'] is False
        assert row['execution_mode']=='SOURCE_ONLY_QUARANTINE'; assert row['status']=='PASS'


def test_functional_proof_roundtrip(tmp_path):
    out=tmp_path/'proof.json'; d=write(root(),str(out)); loaded=json.loads(out.read_text(encoding='utf-8')); assert loaded['sha256']==d['sha256']; assert loaded['status']=='PASS'
