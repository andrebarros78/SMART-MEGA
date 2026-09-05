from pathlib import Path
from smart_total_integration_gate import evaluate,write
ROOT=Path(__file__).resolve().parent

def test_total_integration_gate():
 d=evaluate(ROOT)
 assert d['status']=='PASS'; assert d['health']=='HEALTHY'
 assert all(v for g in d['gates'].values() for v in g.values())
 assert len(d['agent_inventory'])==9; assert len(d['skill_inventory'])==41

def test_total_integration_roundtrip(tmp_path):
 d=write(ROOT,tmp_path/'proof.json'); assert d['status']=='PASS'; assert len(d['sha256'])==64
