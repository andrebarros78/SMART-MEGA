from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
import smart_v2_engine as e
VAR_ONE=6*(6/60)*(1-6/60)*(54/59)
def z(excess,n): return float(excess/math.sqrt(max(1e-12,n*VAR_ONE)))
def main():
    draws,contests=e.load_draws(Path('Mega-Sena.xlsx')); pre=e.precompute_scores(e.onehot(draws)); start=2800
    eta_out={}
    for eta in (0.10,math.log(2),1.5):
        r=e.walk_forward(draws,contests,start,eta=eta,pre=pre); eta_out[str(round(eta,6))]={'hits':r.total_hits,'excess':r.excess_hits,'z':z(r.excess_hits,len(draws)-start)}
    null=e.simulate_null(trials=40,steps=400,warmup=100,seed=20260828)
    power=[]; rng=np.random.default_rng(8128)
    for weight in (1.2,1.5,2.0):
        zs=[]; w=np.ones(60); w[:6]=weight; p=w/w.sum()
        for _ in range(8):
            d=np.array([np.sort(rng.choice(e.NUMBERS,6,replace=False,p=p)) for _ in range(550)],int)
            r=e.walk_forward(d,np.arange(550),150); zs.append(z(r.excess_hits,400))
        a=np.array(zs); power.append({'relative_weight':weight,'trials':8,'mean_z':float(a.mean()),'power_z_ge_2':float(np.mean(a>=2)),'min_z':float(a.min()),'max_z':float(a.max())})
    report={'schema':'SMART_V2_STRESS_FAST_1','historical_eta_sensitivity':eta_out,'null':null,'power_curve':power,'hyperparameter_selection_prohibited':True}
    Path('SMART_V2_STRESS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
