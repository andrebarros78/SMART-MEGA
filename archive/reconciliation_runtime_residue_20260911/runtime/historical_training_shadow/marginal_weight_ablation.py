from pathlib import Path
import sys,json,math
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import smart_signal_agent as ssa
import smart_signal_weights as sw

hist=pd.read_excel(ROOT/'runtime/historical_training_shadow/Mega-Sena_uploaded_2026-09-05.xlsx')
draws=np.array([[int(getattr(r,f'Bola{i}')) for i in range(1,7)] for r in hist.itertuples(index=False)],dtype=int)
contests=np.array([int(r.Concurso) for r in hist.itertuples(index=False)],dtype=int)
ORIG=ssa.dynamic_weights

def run(lam):
    def wrapped(metrics,families):
        mm={}
        for n,m in metrics.items():
            x=dict(m)
            if lam>0:
                d=float(x.get('marginal_utility_shrunk',0.0)); c=float(x.get('marginal_utility_confidence',0.0))
                # bounded, causal next-contest influence only
                factor=math.exp(max(-0.35,min(0.35,lam*d*c)))
                x['utility']=float(x['utility'])*factor
                x['marginal_utility_weight_factor']=factor
            mm[n]=x
        return sw.dynamic_weights(mm,families)
    ssa.dynamic_weights=wrapped
    try:
        a=ssa.SmartSignalAgent(start=1000); rep=a.replay_history(draws,contests); rows=rep['rows']
        def hits(lo,hi): return sum(r['challenger_hits'] for r in rows if lo<=r['contest']<=hi)
        return {'lambda':lam,'calibration_hits_1001_2200':hits(1001,2200),'validation_hits_2201_2700':hits(2201,2700),'holdout_hits_2701_3053':hits(2701,3053),'global_hits':rep['total_hits']}
    finally: ssa.dynamic_weights=ORIG

cands=[0.0,1.0,2.0,4.0,8.0]
results=[]
for x in cands:
    r=run(x); results.append(r); print(json.dumps(r))
base=results[0]
selected=max(results[1:],key=lambda r:(r['calibration_hits_1001_2200'],-r['lambda']))
out={'schema':'SMART_MARGINAL_WEIGHT_ABLATION_V1','design':'bounded marginal utility factor; lambda selected only on 1001-2200; validation 2201-2700; diagnostic holdout 2701-3053','results':results,'selected_by_calibration':selected,'baseline':base,'validation_delta':selected['validation_hits_2201_2700']-base['validation_hits_2201_2700'],'holdout_delta':selected['holdout_hits_2701_3053']-base['holdout_hits_2701_3053'],'global_delta':selected['global_hits']-base['global_hits'],'predictive_weight_authorized':False,'production_mutated':False}
(ROOT/'runtime/historical_training_shadow/MARGINAL_WEIGHT_ABLATION.json').write_text(json.dumps(out,indent=2),encoding='utf-8'); print(json.dumps(out,indent=2))
