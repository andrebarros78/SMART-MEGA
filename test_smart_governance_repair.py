import json, hashlib
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()

def test_terminal_authority_is_active_not_false_proven():
    s=json.loads(Path('SMART_MISSION_STATUS.json').read_text(encoding='utf-8'))
    assert s['status']=='MISSION_ACTIVE'; assert s['terminal_6of6_proven'] is False
    assert all(x['authority']=='HISTORICAL_ENGINEERING_ONLY' for x in s['supersedes_terminal_authority_of'])

def test_model_registry_matches_freeze_exactly():
    f=Path('SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json'); freeze=json.loads(f.read_text(encoding='utf-8'))
    reg=json.loads(Path('SMART_MODEL_REGISTRY.json').read_text(encoding='utf-8'))
    assert reg['source_sha256']==sha(f)
    assert reg['models'][0]['top6']==freeze['champion']['top6']
    assert reg['models'][1]['top6']==freeze['challenger']['top6']

def test_frontier_negative_learning_keeps_zero_weight():
    d=json.loads(Path('SMART_FRONTIER_LEARNING_DECISION.json').read_text(encoding='utf-8'))
    assert d['global_decision']=='NO_FRONTIER_CANDIDATE_PROMOTED'
    assert len(d['decisions'])==5
    assert all(v['material_weight']==0.0 for v in d['decisions'].values())
    assert all(v['historical_diagnostic_pass'] is False for v in d['decisions'].values())
