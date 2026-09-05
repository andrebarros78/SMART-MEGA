import json, hashlib, time, traceback
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from smart_agent_runtime import SmartAgentRuntime
from smart_agent_skill_functional_gate import evaluate
from smart_signal_agent import SmartSignalAgent

ROOT=Path(r'C:\New Projet\SMART-MEGA')
FILES=['SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json','SMART_3054_SHADOW_V3_FREEZE.json','SMART_SIGNAL_STATE.json','SMART_SIGNAL_STATE_3054_V2.json']

def sha(p):
    h=hashlib.sha256();
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1<<20),b''): h.update(c)
    return h.hexdigest()

before={f:sha(ROOT/f) for f in FILES}
rows=[]
for cycle in range(1,51):
    t0=time.time(); ok=True; errors=[]
    try:
        rt=SmartAgentRuntime(ROOT).run()
        fg=evaluate(ROOT)
        if rt['status']!='PASS': raise AssertionError('runtime not PASS')
        if fg['status']!='PASS': raise AssertionError('functional gate not PASS')
        if rt['agent_count']!=9 or rt['capability_count']!=41: raise AssertionError('agent/capability count')
        if rt['unacknowledged_handoffs']: raise AssertionError('unacked handoffs')
        if not all(rt['checks'].values()): raise AssertionError('runtime checks')
        if not all(fg['checks'].values()): raise AssertionError('functional checks')

        rng=np.random.default_rng(20260905+cycle)
        draws=np.array([np.sort(rng.choice(np.arange(1,61),size=6,replace=False)) for _ in range(75)],dtype=int)
        contests=np.arange(1,76,dtype=int)
        a=SmartSignalAgent(start=35)
        pred,back=a.predict_next(draws,contests,target_contest=76)
        if pred.cutoff_contest!=75 or pred.target_contest!=76: raise AssertionError('causal cutoff')
        if len(pred.top6)!=6 or len(set(pred.top6))!=6 or min(pred.top6)<1 or max(pred.top6)>60: raise AssertionError('invalid top6')
        if abs(sum(pred.weights.values())-1.0)>1e-9: raise AssertionError('weights not normalized')
        if len(back['rows'])!=40: raise AssertionError('unexpected replay rows')
        # determinism check on identical input
        b=SmartSignalAgent(start=35)
        pred2,back2=b.predict_next(draws,contests,target_contest=76)
        if pred.top6!=pred2.top6 or pred.ranking60!=pred2.ranking60: raise AssertionError('nondeterministic prediction')
        if back['total_hits']!=back2['total_hits']: raise AssertionError('nondeterministic replay')
    except Exception as e:
        ok=False; errors.append(f'{type(e).__name__}: {e}')
    rows.append({'cycle':cycle,'status':'PASS' if ok else 'FAIL','seconds':round(time.time()-t0,4),'errors':errors})
    if cycle%10==0:
        print(f'cycle {cycle}/50 pass={sum(r["status"]=="PASS" for r in rows)} fail={sum(r["status"]=="FAIL" for r in rows)}',flush=True)

after={f:sha(ROOT/f) for f in FILES}
summary={
 'schema':'SMART_50_CYCLE_SANDBOX_V1',
 'cycles':50,
 'passed':sum(r['status']=='PASS' for r in rows),
 'failed':sum(r['status']=='FAIL' for r in rows),
 'all_passed':all(r['status']=='PASS' for r in rows),
 'production_hashes_unchanged':before==after,
 'production_hashes_before':before,
 'production_hashes_after':after,
 'rows':rows,
}
out=ROOT/'runtime'/'SMART_50_CYCLE_SANDBOX_2026-09-05.json'
out.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:summary[k] for k in ['cycles','passed','failed','all_passed','production_hashes_unchanged']},ensure_ascii=False,indent=2))
