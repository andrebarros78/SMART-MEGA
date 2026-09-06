from pathlib import Path
from smart_total_integration_gate import evaluate,write
ROOT=Path(__file__).resolve().parent

def test_total_integration_gate():
 d=evaluate(ROOT)
 assert d['status']=='PASS'; assert d['health']=='HEALTHY'
 assert all(v for g in d['gates'].values() for v in g.values())
 assert len(d['agent_inventory'])==9; assert len(d['skill_inventory'])==41
 assert all(a['runtime']=='DETERMINISTIC_ROLE_EXECUTOR' and a['autonomous_ai_agent'] is False and a['llm_model'] is False for a in d['agent_inventory'])
 assert all(s['direct_named_skill_execution'] is False for s in d['skill_inventory'])
 assert d['gates']['G9_SEMANTIC_TRUTH']['agents_not_misrepresented_as_llm'] is True
 assert d['gates']['G9_SEMANTIC_TRUTH']['skills_not_misrepresented_as_direct_execution'] is True

def test_total_integration_roundtrip(tmp_path):
 d=write(ROOT,tmp_path/'proof.json'); assert d['status']=='PASS'; assert len(d['sha256'])==64
