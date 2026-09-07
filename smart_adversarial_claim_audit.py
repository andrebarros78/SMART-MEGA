from __future__ import annotations
import copy, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import smart_v2_engine as e
from smart_signal_agent import SmartSignalAgent, SIGNAL_NAMES
from smart_signal_weights import dynamic_weights

SCHEMA='SMART_ADVERSARIAL_CLAIM_AUDIT_1'

def sha256_file(p: Path) -> str:
    h=hashlib.sha256();
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def run(root: str|Path='.', data_name='Mega-Sena.xlsx', target: int|None=None) -> dict:
    root=Path(root).resolve(); data=root/data_name
    draws, contests=e.load_draws(data)
    cutoff=int(contests[-1])
    if target is None: target=cutoff+1
    target=int(target)
    if cutoff != target-1: raise ValueError('causal cutoff mismatch')
    agent=SmartSignalAgent(start=1000)
    pred, back=agent.predict_next(draws, contests, target_contest=target)
    policies=pred.multi_challengers['policies']
    policy_top6={k:list(v['top6']) for k,v in policies.items()}
    distinct_sets={tuple(sorted(v)) for v in policy_top6.values()}
    weights={k:float(v) for k,v in pred.weights.items()}
    # Causal sensitivity: destroy measured utility/quality/confidence of the current heaviest signal.
    heaviest=max(weights,key=weights.get)
    degraded=copy.deepcopy(pred.quality_metrics)
    for factor in ('utility','quality','confidence'):
        degraded[heaviest][factor]=0.0
    families={name:e.family_of(name) for name in SIGNAL_NAMES}
    degraded_weights,_=dynamic_weights(degraded,families)
    delta=float(weights[heaviest]-degraded_weights[heaviest])
    checks={
      'causal_cutoff_exact': int(contests[-1])==target-1,
      'dynamic_weights_nonuniform': max(weights.values())-min(weights.values()) > 1e-6,
      'multiple_policy_outputs_exist': len(distinct_sets) >= 2,
      'signal_weight_responds_to_quality_degradation': delta > 1e-6,
      'meta_governor_blocks_unpromoted_alternate': pred.meta_governor.get('allow_alternate_selection') is False,
      'current_result_not_used': target not in set(map(int,contests.tolist())),
    }
    doc={
      'schema':SCHEMA,'generated_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS' if all(checks.values()) else 'FAIL',
      'target_contest':target,'cutoff_contest':int(contests[-1]),'data_file':data_name,'data_sha256':sha256_file(data),
      'checks':checks,'anchor_top6':list(pred.top6),'policy_top6':policy_top6,'distinct_top6_sets':len(distinct_sets),
      'weights':weights,'weight_range':float(max(weights.values())-min(weights.values())),'heaviest_signal':heaviest,
      'heaviest_weight_before':weights[heaviest],'heaviest_weight_after_forced_quality_degradation':float(degraded_weights[heaviest]),
      'heaviest_weight_delta':delta,'meta_governor':pred.meta_governor,
      'walk_forward_mean_hits':float(back['mean_hits']),'walk_forward_excess_hits':float(back['excess_hits']),
      'claim':'The current SMART predictive pipeline is not output-inert: actual policies produce multiple Top-6 sets and signal weights causally respond to quality degradation. This does not prove lottery predictability or 6/6.',
      'component_hashes':{x:sha256_file(root/x) for x in ['smart_signal_agent.py','smart_signal_weights.py','smart_multi_challengers.py','smart_meta_governor.py']},
    }
    raw=json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode(); doc['sha256']=hashlib.sha256(raw).hexdigest()
    return doc

if __name__=='__main__':
    d=run(Path(__file__).resolve().parent); out=Path(__file__).resolve().parent/'SMART_ADVERSARIAL_CLAIM_AUDIT.json'; out.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'status':d['status'],'checks':d['checks'],'anchor_top6':d['anchor_top6'],'policy_top6':d['policy_top6'],'heaviest_signal':d['heaviest_signal'],'weight_delta':d['heaviest_weight_delta'],'sha256':d['sha256']},ensure_ascii=False,indent=2))
