from __future__ import annotations

import json, hashlib, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import smart_v2_engine as e
from smart_signal_agent import SmartSignalAgent
from smart_bounded_online_learning import BoundedOnlineLearningGuard

CAL_END=2200
START=1000
CANDIDATES=[
    {'name':'P10_CAP_2_SPREAD_6','max_abs_step':2.0,'warmup_max_abs_step':1.0,'max_abs_centered_logit':6.0},
    {'name':'P10_CAP_1_5_SPREAD_4_5','max_abs_step':1.5,'warmup_max_abs_step':0.75,'max_abs_centered_logit':4.5},
    {'name':'P10_CAP_1_SPREAD_3','max_abs_step':1.0,'warmup_max_abs_step':0.5,'max_abs_centered_logit':3.0},
]

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

class ConfigAgent(SmartSignalAgent):
    config=None
    def _reset_states(self):
        super()._reset_states()
        if self.config is not None:
            c=self.config
            kw=dict(eta=self.eta,max_abs_step=c['max_abs_step'],warmup_max_abs_step=c['warmup_max_abs_step'],
                    prior_observations=0,warmup_full_after=5,min_warmup_scale=.5,
                    max_abs_centered_logit=c['max_abs_centered_logit'])
            self.expert_learning_guard=BoundedOnlineLearningGuard(**kw)
            self.family_learning_guard=BoundedOnlineLearningGuard(**kw)

class ReferenceAgent(SmartSignalAgent):
    def _reset_states(self):
        super()._reset_states()
        kw=dict(eta=self.eta,max_abs_step=100.0,warmup_max_abs_step=100.0,prior_observations=0,
                warmup_full_after=1,min_warmup_scale=1.0,max_abs_centered_logit=1e9)
        self.expert_learning_guard=BoundedOnlineLearningGuard(**kw)
        self.family_learning_guard=BoundedOnlineLearningGuard(**kw)

data=ROOT/'Mega-Sena_through_3050.xlsx'
draws,contests=e.load_draws(data)
mask=contests<=CAL_END
draws=draws[mask]; contests=contests[mask]
ref=ReferenceAgent(start=START); _,rb=ref.predict_next(draws,contests,target_contest=CAL_END+1)
rows=[]
for c in CANDIDATES:
    ConfigAgent.config=c
    a=ConfigAgent(start=START); pred,back=a.predict_next(draws,contests,target_contest=CAL_END+1)
    expert=a.expert_learning_guard.state(); family=a.family_learning_guard.state()
    active=(expert['warmup_update_count']>0 and family['warmup_update_count']>0 and
            (expert['clipped_update_count']>0 or family['clipped_update_count']>0))
    rows.append({
        **c,'calibration_hits':back['total_hits'],'reference_hits':rb['total_hits'],
        'delta':back['total_hits']-rb['total_hits'],'active_protection':active,
        'expert_clipped_ids_total':expert['clipped_update_count'],'family_clipped_ids_total':family['clipped_update_count'],
        'expert_warmup_updates':expert['warmup_update_count'],'family_warmup_updates':family['warmup_update_count'],
        'expert_spread_clip_updates':expert['spread_clip_count'],'family_spread_clip_updates':family['spread_clip_count'],
        'next_top6':pred.top6,
    })
eligible=[r for r in rows if r['active_protection']]
if not eligible: raise SystemExit('no candidate has active protection')
# Selection uses calibration only. Maximize hits; ties prefer the least restrictive (largest cap/spread).
selected=max(eligible,key=lambda r:(r['calibration_hits'],r['max_abs_step'],r['max_abs_centered_logit']))
out={'schema':'SMART_P10_ACTIVE_GUARD_CALIBRATION_1','selection_scope':'1001-2200 only','start_index':START,
     'holdout_2801_3050_used_for_selection':False,'candidate_grid_predeclared_in_script':True,
     'reference_calibration_hits':rb['total_hits'],'candidates':rows,'selected':selected,
     'hashes':{'data':sha(data),'script':sha(Path(__file__))}}
path=ROOT/'SMART_P10_ACTIVE_GUARD_CALIBRATION.json'; path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2)); print('SHA256',sha(path))
