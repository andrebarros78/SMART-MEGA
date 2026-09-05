from __future__ import annotations
import hashlib,json
from pathlib import Path
from typing import Any
from smart_agent_runtime import SmartAgentRuntime, sha256_json

SCHEMA='SMART_AGENT_SKILL_FUNCTIONAL_GATE_V1'

def evaluate(root:str|Path)->dict[str,Any]:
    root=Path(root)
    runtime=SmartAgentRuntime(root).run()
    matrix=[]
    for agent_name, execution in runtime['executions'].items():
        for capability in execution['capabilities']:
            matrix.append({
                'capability': capability,
                'agent_owner': agent_name,
                'native_targets': list(execution['native_targets']),
                'runtime_evidence': list(execution['artifacts']),
                'handoff_outputs': list(execution['produced_handoffs']),
                'status':'PASS',
            })
    capability_names=[row['capability'] for row in matrix]
    checks={
        'runtime_pass':runtime['status']=='PASS',
        'nine_agents':runtime['agent_count']==9,
        'forty_one_capabilities':runtime['capability_count']==41 and len(matrix)==41,
        'capabilities_unique':len(capability_names)==len(set(capability_names))==41,
        'every_capability_has_owner':all(row['agent_owner'] for row in matrix),
        'every_capability_has_realization':all(row['native_targets'] or (row['agent_owner']=='quarantine_curator' and row['handoff_outputs']) for row in matrix),
        'every_capability_has_runtime_evidence':all(row['runtime_evidence'] for row in matrix),
        'handoffs_complete':runtime['unacknowledged_handoffs']==[],
        'runtime_checks_all_true':all(runtime['checks'].values()),
    }
    doc={'schema':SCHEMA,'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'matrix':matrix,'runtime_proof':runtime}
    doc['sha256']=sha256_json(doc)
    return doc

def write(root:str|Path,out='SMART_AGENT_SKILL_FUNCTIONAL_INTEGRATION_PROOF.json'):
    root=Path(root); doc=evaluate(root); (root/out).write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); return doc

if __name__=='__main__':
    d=write(Path(__file__).resolve().parent); print(json.dumps({'status':d['status'],'checks':d['checks'],'matrix_rows':len(d['matrix'])},ensure_ascii=False,indent=2))
