from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
import smart_v2_engine as e

VAR_ONE=6*(6/60)*(1-6/60)*(54/59)
def z(excess,n): return float(excess/math.sqrt(max(1e-12,n*VAR_ONE)))

def run_eta(draws,contests,start,etas):
    pre=e.precompute_scores(e.onehot(draws)); out={}
    for eta in etas:
        r=e.walk_forward(draws,contests,start,eta=eta,pre=pre); out[str(eta)]={'hits':r.total_hits,'excess':r.excess_hits,'z':z(r.excess_hits,len(draws)-start),'final_weights':r.final_weights}
    return out

def weak_power(weight,trials=20,steps=800,warmup=200):
    zs=[]; rng=np.random.default_rng(9000+int(weight*100))
    w=np.ones(60); w[:6]=weight; p=w/w.sum()
    for _ in range(trials):
        d=np.array([np.sort(rng.choice(e.NUMBERS,6,replace=False,p=p)) for _ in range(steps)],int)
        r=e.walk_forward(d,np.arange(steps),warmup); zs.append(z(r.excess_hits,steps-warmup))
    a=np.array(zs); return {'relative_weight':weight,'trials':trials,'mean_z':float(a.mean()),'power_z_ge_2':float(np.mean(a>=2)),'min_z':float(a.min()),'max_z':float(a.max())}

def main():
    draws,contests=e.load_draws(Path('Mega-Sena.xlsx')); etas=[0.10,0.25,math.log(2),1.0,1.5]
    report={'schema':'SMART_V2_STRESS_1','historical_eta_sensitivity':run_eta(draws,contests,2800,etas),
      'null_100_trials':e.simulate_null(trials=100,steps=500,warmup=150,seed=20260828),
      'power_curve':[weak_power(w) for w in (1.15,1.30,1.50,2.0)],
      'interpretation':'diagnostic only; hyperparameters are not selected from historical winner'}
    Path('SMART_V2_STRESS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
