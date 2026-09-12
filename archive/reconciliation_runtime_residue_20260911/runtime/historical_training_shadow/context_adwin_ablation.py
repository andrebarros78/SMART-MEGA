from pathlib import Path
import sys,json
import pandas as pd
import numpy as np
from river import drift
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import smart_signal_agent as ssa
import smart_context_regime as base

class AdwinContext(base.ContextRegimeEngine):
    @property
    def active(self):
        return bool(len(self.recent_rows)==base.TOTAL_WINDOW and (self.last_score>=base.REGIME_L1_THRESHOLD or bool(self.score_detector.drift_detected) or self.cooldown>0))
    def update(self, draw):
        if self.cooldown>0: self.cooldown-=1
        x=base._onehot_draw(draw)
        if len(self.recent_rows)<base.TOTAL_WINDOW:
            self.recent_rows.append(x)
            if len(self.recent_rows)==base.TOTAL_WINDOW:
                rows=list(self.recent_rows); self.reference_sum=np.sum(rows[:base.REFERENCE_WINDOW],axis=0); self.recent_sum=np.sum(rows[base.REFERENCE_WINDOW:],axis=0)
        else:
            oldest=self.recent_rows.popleft(); transition=self.recent_rows[base.REFERENCE_WINDOW-1]
            self.reference_sum += transition-oldest; self.recent_sum += x-transition; self.recent_rows.append(x)
        self.observations+=1; score=self._score(); self.last_score=score; self.score_detector.update(score)
        if len(self.recent_rows)==base.TOTAL_WINDOW and (score>=base.REGIME_L1_THRESHOLD or bool(self.score_detector.drift_detected)) and self.cooldown==0:
            self.detection_count+=1; self.last_detection_step=self.observations; self.cooldown=base.CONTEXT_COOLDOWN
    def metrics(self):
        m=super().metrics(); m['schema']='SMART_CONTEXT_REGIME_ADWIN_CHALLENGER_1'; return m

hist=pd.read_excel(ROOT/'runtime/historical_training_shadow/Mega-Sena_uploaded_2026-09-05.xlsx')
draws=np.array([[int(getattr(r,f'Bola{i}')) for i in range(1,7)] for r in hist.itertuples(index=False)],dtype=int)
contests=np.array([int(r.Concurso) for r in hist.itertuples(index=False)],dtype=int)

def run(cls):
    old=ssa.ContextRegimeEngine; ssa.ContextRegimeEngine=cls
    try:
        a=ssa.SmartSignalAgent(start=1000); rep=a.replay_history(draws,contests)
        rows=rep['rows']
        def hits(lo,hi): return sum(r['challenger_hits'] for r in rows if lo<=r['contest']<=hi)
        return {'detections':a.context_engine.detection_count,'active_final':a.context_engine.active,'calibration_hits_1001_2200':hits(1001,2200),'validation_hits_2201_2700':hits(2201,2700),'holdout_hits_2701_3053':hits(2701,3053),'global_hits':rep['total_hits']}
    finally: ssa.ContextRegimeEngine=old

out={'schema':'SMART_CONTEXT_ADWIN_ABLATION_V1','design':'candidate mechanism specified before comparison; calibration/validation/holdout chronological','baseline':run(base.ContextRegimeEngine),'adwin_or_fixed':run(AdwinContext),'predictive_weight_authorized':False,'production_mutated':False}
out['validation_delta']=out['adwin_or_fixed']['validation_hits_2201_2700']-out['baseline']['validation_hits_2201_2700']; out['holdout_delta']=out['adwin_or_fixed']['holdout_hits_2701_3053']-out['baseline']['holdout_hits_2701_3053']; out['global_delta']=out['adwin_or_fixed']['global_hits']-out['baseline']['global_hits']
(ROOT/'runtime/historical_training_shadow/CONTEXT_ADWIN_ABLATION.json').write_text(json.dumps(out,indent=2),encoding='utf-8'); print(json.dumps(out,indent=2))
