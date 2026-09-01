from pathlib import Path
import json, hashlib, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import smart_v2_engine as e
from smart_signal_agent import SmartSignalAgent
from smart_bounded_online_learning import BoundedOnlineLearningGuard

class ReferenceAgent(SmartSignalAgent):
    def _reset_states(self):
        super()._reset_states()
        self.expert_learning_guard=BoundedOnlineLearningGuard(eta=self.eta,max_abs_step=100.0,warmup_full_after=1,min_warmup_scale=1.0,max_abs_centered_logit=1e9)
        self.family_learning_guard=BoundedOnlineLearningGuard(eta=self.eta,max_abs_step=100.0,warmup_full_after=1,min_warmup_scale=1.0,max_abs_centered_logit=1e9)

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def segment(back,lo,hi):
    return sum(int(r['challenger_hits']) for r in back['rows'] if lo <= int(r['contest']) <= hi)

data=ROOT/'Mega-Sena_through_3050.xlsx'
draws,contests=e.load_draws(data)
p10=SmartSignalAgent(start=1000)
pred10,b10=p10.predict_next(draws,contests,target_contest=3051)
ref=ReferenceAgent(start=1000)
pred0,b0=ref.predict_next(draws,contests,target_contest=3051)
blocks=[]
for lo in range(2801,3051,50):
    hi=min(3050,lo+49)
    blocks.append({'lo':lo,'hi':hi,'p10':segment(b10,lo,hi),'reference':segment(b0,lo,hi)})

out={
 'schema':'SMART_P10_HISTORICAL_NONREGRESSION_1','data_cutoff':3050,'oos_predictions':len(b10['rows']),
 'p10_total_hits':b10['total_hits'],'reference_total_hits':b0['total_hits'],'total_delta':b10['total_hits']-b0['total_hits'],
 'holdout_2801_3050':{'p10_hits':segment(b10,2801,3050),'reference_hits':segment(b0,2801,3050),'delta':segment(b10,2801,3050)-segment(b0,2801,3050),'blocks':blocks},
 'next_top6':{'p10':pred10.top6,'reference':pred0.top6},'next_weights_equal':pred10.weights==pred0.weights,
 'p10_guard_state':{'expert':p10.expert_learning_guard.state(),'family':p10.family_learning_guard.state()},
 'reference_guard_state':{'expert':ref.expert_learning_guard.state(),'family':ref.family_learning_guard.state()},
 'configuration_predeclared':True,'holdout_used_for_tuning':False,'prospective_predictive_claim':False,
 'hashes':{'data':sha(data),'p10_module':sha(ROOT/'smart_bounded_online_learning.py'),'agent':sha(ROOT/'smart_signal_agent.py')}
}
path=ROOT/'SMART_P10_HISTORICAL_NONREGRESSION.json'
path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:out[k] for k in ['oos_predictions','p10_total_hits','reference_total_hits','total_delta','holdout_2801_3050','next_top6','next_weights_equal']},ensure_ascii=False,indent=2))
print('SHA256',sha(path))
