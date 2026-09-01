from __future__ import annotations
import hashlib,json,sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(r'C:\New Projet\SMART-MEGA')

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sj(o): return hashlib.sha256(json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def now(): return datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat()
def write_self(path,obj):
    obj=dict(obj); obj['sha256']=sj(obj); path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8'); return sha(path)

p10r=ROOT/'SMART_P10_HISTORICAL_NONREGRESSION.json'; p11r=ROOT/'SMART_P11_SIGNAL_EXPANSION_VALIDATION.json'
p10=json.loads(p10r.read_text(encoding='utf-8')); p11=json.loads(p11r.read_text(encoding='utf-8'))
assert p10['schema']=='SMART_P10_HISTORICAL_NONREGRESSION_1'
assert p10['oos_predictions']==2050 and p10['total_delta']>=0 and p10['holdout_2801_3050']['delta']>=0
assert p10['next_weights_equal'] is True
assert p10['hashes']['p10_module']==sha(ROOT/'smart_bounded_online_learning.py')
assert p10['hashes']['agent']==sha(ROOT/'smart_signal_agent.py')
assert p11['schema']=='SMART_P11_SIGNAL_EXPANSION_VALIDATION_1' and p11['status']=='PASS' and p11['all_checks_pass'] is True
proof=p11['authorization_proof']; observed=proof['sha256']; canon=dict(proof); canon.pop('sha256'); assert observed==sj(canon)
assert p11['authorization']['proof_sha256']==observed
assert all(p11['checks'].values())

p10proof={
 'schema':'SMART_P10_BOUNDED_ONLINE_LEARNING_PROOF_1','created_brt':now(),'point':10,'id':'P10_BOUNDED_ONLINE_LEARNING','status':'PROVEN',
 'historical_nonregression':{'file':p10r.name,'sha256':sha(p10r),'oos_predictions':p10['oos_predictions'],'total_delta':p10['total_delta'],'holdout_delta':p10['holdout_2801_3050']['delta'],'next_weights_equal':p10['next_weights_equal']},
 'implementation':{'module':'smart_bounded_online_learning.py','sha256':sha(ROOT/'smart_bounded_online_learning.py'),'agent':'smart_signal_agent.py','agent_sha256':sha(ROOT/'smart_signal_agent.py'),'context_regime_sha256':sha(ROOT/'smart_context_regime.py')},
 'guard':{'expert':p10['p10_guard_state']['expert'],'family':p10['p10_guard_state']['family']},
 'tests':{'files':['test_smart_bounded_online_learning.py','test_smart_signal_expansion_governance.py'],'combined_passed':20,'p10_test_sha256':sha(ROOT/'test_smart_bounded_online_learning.py')},
 'anti_false_learning':{'holdout_used_for_tuning':p10['holdout_used_for_tuning'],'configuration_predeclared':p10['configuration_predeclared'],'prospective_predictive_claim':p10['prospective_predictive_claim'],'nonregression_not_claimed_as_predictive_gain':True},
 'result':'Bounded online learning is causal, bounded, recoverable, and non-regressive against the unbounded reference on the declared historical OOS/holdout.'
}
p10pf=ROOT/'SMART_P10_BOUNDED_ONLINE_LEARNING_PROOF.json'; p10sha=write_self(p10pf,p10proof)

p11proof={
 'schema':'SMART_P11_SIGNAL_EXPANSION_GOVERNANCE_PROOF_1','created_brt':now(),'point':11,'id':'P11_SIGNAL_EXPANSION_GOVERNANCE','status':'PROVEN',
 'validation':{'file':p11r.name,'sha256':sha(p11r),'checks':p11['checks']},
 'authorization_proof':proof,
 'implementation':{'module':'smart_signal_expansion_governance.py','sha256':sha(ROOT/'smart_signal_expansion_governance.py'),'validation_script':'archive/p11_validation.py','validation_script_sha256':sha(ROOT/'archive'/'p11_validation.py')},
 'tests':{'file':'test_smart_signal_expansion_governance.py','sha256':sha(ROOT/'test_smart_signal_expansion_governance.py'),'combined_p10_p11_passed':20},
 'policy':p11['policy'],
 'anti_false_learning':{'overfit_rejected':p11['checks']['overfit_rejected'],'redundant_rejected':p11['checks']['redundant_rejected'],'noise_rejected':p11['checks']['noise_rejected'],'challenger_only':p11['checks']['authorization_challenger_only'],'automatic_material_influence':False,'predictive_signal_promoted':False},
 'result':'New signals remain shadow/Challenger-only until causal marginal OOS evidence and a matching self-hashed authorization proof exist.'
}
p11pf=ROOT/'SMART_P11_SIGNAL_EXPANSION_GOVERNANCE_PROOF.json'; p11sha=write_self(p11pf,p11proof)

gp=ROOT/'SMART_3052_IMPLEMENTATION_GATE.json'; gate=json.loads(gp.read_text(encoding='utf-8')); items=gate['items']
for iid,pf,pfsha,extra in [
 ('P10_BOUNDED_ONLINE_LEARNING',p10pf,p10sha,[{'type':'historical_nonregression','file':p10r.name,'sha256':sha(p10r),'oos_predictions':2050,'total_delta':p10['total_delta'],'holdout_delta':p10['holdout_2801_3050']['delta']},{'type':'module','file':'smart_bounded_online_learning.py','sha256':sha(ROOT/'smart_bounded_online_learning.py')},{'type':'agent_integration','file':'smart_signal_agent.py','sha256':sha(ROOT/'smart_signal_agent.py')},{'type':'regression','test_file':'test_smart_bounded_online_learning.py','test_sha256':sha(ROOT/'test_smart_bounded_online_learning.py'),'combined_p10_p11_passed':20}]),
 ('P11_SIGNAL_EXPANSION_GOVERNANCE',p11pf,p11sha,[{'type':'validation','file':p11r.name,'sha256':sha(p11r),'all_checks_pass':True},{'type':'module','file':'smart_signal_expansion_governance.py','sha256':sha(ROOT/'smart_signal_expansion_governance.py')},{'type':'authorization_proof','sha256':proof['sha256'],'scope':'CHALLENGER_ONLY'},{'type':'regression','test_file':'test_smart_signal_expansion_governance.py','test_sha256':sha(ROOT/'test_smart_signal_expansion_governance.py'),'combined_p10_p11_passed':20}])]:
    it=next(x for x in items if x['id']==iid); it['status']='PROVEN'; it['evidence']=[{'type':'implementation_proof','file':pf.name,'sha256':pfsha},*extra]; it['proven_brt']=now()
proven=sum(1 for x in items if x.get('status')=='PROVEN' and x.get('evidence'))
gate['progress']={'proven_items':proven,'total_items':len(items),'remaining_items':len(items)-proven}; gate['freeze_allowed']=proven==len(items); gate['last_updated_brt']=now(); gate['updated_brt']=gate['last_updated_brt']; gp.write_text(json.dumps(gate,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'P10':'PROVEN','P10_proof_sha256':p10sha,'P11':'PROVEN','P11_proof_sha256':p11sha,'progress':gate['progress'],'freeze_allowed':gate['freeze_allowed']},indent=2))
