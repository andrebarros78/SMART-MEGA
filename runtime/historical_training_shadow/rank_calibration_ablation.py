from pathlib import Path
import sys,json
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from smart_signal_agent import SmartSignalAgent

hist=pd.read_excel(ROOT/'runtime/historical_training_shadow/Mega-Sena_uploaded_2026-09-05.xlsx')
draws=np.array([[int(getattr(r,f'Bola{i}')) for i in range(1,7)] for r in hist.itertuples(index=False)],dtype=int)
contests=np.array([int(r.Concurso) for r in hist.itertuples(index=False)],dtype=int)

def run(s):
    a=SmartSignalAgent(start=1000,calibration_strength=s); rep=a.replay_history(draws,contests); rows=rep['rows']
    def part(lo,hi):
        rr=[r for r in rows if lo<=r['contest']<=hi]
        vals=[float(r['rank_calibration_brier_after_result']['delta_vs_uniform']) for r in rr]
        return {'n':len(rr),'mean_delta_vs_uniform':sum(vals)/len(vals),'sum_delta_vs_uniform':sum(vals)}
    return {'strength':s,'calibration':part(1001,2200),'validation':part(2201,2700),'holdout':part(2701,3053),'global':part(1001,3053),'global_hits':rep['total_hits']}

results=[]
for s in [0.0,0.25,0.5,0.75,1.0]:
    r=run(s); results.append(r); print(json.dumps(r))
selected=min(results[1:],key=lambda r:(r['calibration']['mean_delta_vs_uniform'],r['strength']))
base=results[0]
out={'schema':'SMART_RANK_CALIBRATION_ABLATION_V1','metric':'Brier delta vs uniform; lower is better','design':'strength selected only by calibration 1001-2200; validation 2201-2700; diagnostic holdout 2701-3053','results':results,'selected_by_calibration':selected,'baseline':base,'validation_improvement':base['validation']['mean_delta_vs_uniform']-selected['validation']['mean_delta_vs_uniform'],'holdout_improvement':base['holdout']['mean_delta_vs_uniform']-selected['holdout']['mean_delta_vs_uniform'],'global_improvement':base['global']['mean_delta_vs_uniform']-selected['global']['mean_delta_vs_uniform'],'top6_invariant_expected':True,'predictive_weight_authorized':False,'production_mutated':False}
(ROOT/'runtime/historical_training_shadow/RANK_CALIBRATION_ABLATION.json').write_text(json.dumps(out,indent=2),encoding='utf-8'); print(json.dumps(out,indent=2))
