from pathlib import Path
import json
from smart_agent_skill_functional_gate import evaluate,write

def root(): return Path(__file__).resolve().parent

def test_functional_gate_proves_full_matrix():
    d=evaluate(root()); assert d['status']=='PASS'; assert all(d['checks'].values()); assert len(d['matrix'])==41
    assert len({r['capability'] for r in d['matrix']})==41

def test_every_capability_is_executable_through_owner_contract():
    d=evaluate(root())
    for row in d['matrix']:
        assert row['agent_owner']; assert (row['native_targets'] or (row['agent_owner']=='quarantine_curator' and row['handoff_outputs'])); assert row['runtime_evidence']; assert row['status']=='PASS'

def test_functional_proof_roundtrip(tmp_path):
    out=tmp_path/'proof.json'; d=write(root(),str(out)); loaded=json.loads(out.read_text(encoding='utf-8')); assert loaded['sha256']==d['sha256']; assert loaded['status']=='PASS'
