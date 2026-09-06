from pathlib import Path
import json
from smart_agent_runtime import SmartAgentRuntime, write_runtime

def root(): return Path(__file__).resolve().parent

def test_runtime_executes_all_agents_and_capabilities():
 d=SmartAgentRuntime(root()).run()
 assert d['status']=='PASS'; assert d['agent_count']==9; assert d['capability_count']==41
 assert all(d['checks'].values())

def test_every_declared_handoff_is_acknowledged():
 d=SmartAgentRuntime(root()).run(); assert d['unacknowledged_handoffs']==[]
 for n,e in d['executions'].items():
  assert e['status']=='PASS'

def test_runtime_evidence_is_real_and_hashed():
 d=SmartAgentRuntime(root()).run()
 for n,e in d['executions'].items():
  if n!='mission_governor': assert e['artifacts']
  for a in e['artifacts']:
   p=root()/a['path']; assert p.is_file(); assert len(a['sha256'])==64

def test_runtime_proof_roundtrip(tmp_path):
 d=write_runtime(root(),str(tmp_path/'proof.json'))
 loaded=json.loads((tmp_path/'proof.json').read_text(encoding='utf-8'))
 assert loaded['runtime_sha256']==d['runtime_sha256']; assert loaded['status']=='PASS'

def test_red_team_runtime_evidence_is_independent_of_current_junit():
 import smart_agent_runtime as ar
 hints=ar.ARTIFACT_HINTS['robustness_red_team']
 assert 'SMART_AUDIT_JUNIT_CURRENT.xml' not in hints
 assert 'SMART_P09_RED_TEAM_LATEST.json' in hints
 d=ar.SmartAgentRuntime(root()).run()
 assert d['executions']['robustness_red_team']['probe_result']['pass'] is True
