from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
import smart_v2_engine as e


def z_from_excess(excess,n):
    p=6/60; var_one=6*p*(1-p)*(54/59)
    return excess/math.sqrt(max(1e-12,n*var_one))


def temporal_folds(draws,contests):
    folds=[(1000,1500),(1500,2000),(2000,2500),(2500,2800),(2800,len(draws))]
    out=[]
    for start,end in folds:
        r=e.walk_forward(draws[:end],contests[:end],start=start)
        n=end-start
        out.append({'start_index':start,'end_index_exclusive':end,'contests':n,'hits':r.total_hits,'uniform_expected':r.uniform_expected,'excess':r.excess_hits,'z':z_from_excess(r.excess_hits,n)})
    return out


def synthetic_power(trials=30,steps=800,warmup=300,seed=20260828):
    rng=np.random.default_rng(seed); zs=[]
    weights=np.ones(60,float); weights[:6]=3.0; weights/=weights.sum()
    for _ in range(trials):
        d=np.array([np.sort(rng.choice(e.NUMBERS,6,replace=False,p=weights)) for _ in range(steps)],int)
        r=e.walk_forward(d,np.arange(1,steps+1),start=warmup)
        zs.append(z_from_excess(r.excess_hits,steps-warmup))
    a=np.asarray(zs,float)
    return {'trials':trials,'biased_numbers':[1,2,3,4,5,6],'relative_sampling_weight':3.0,'mean_z':float(a.mean()),'median_z':float(np.median(a)),'power_z_ge_2':float(np.mean(a>=2.0)),'min_z':float(a.min()),'max_z':float(a.max())}


def main():
    draws,contests=e.load_draws(Path('Mega-Sena.xlsx'))
    report={'schema':'SMART_V2_ROBUSTNESS_1','temporal_folds':temporal_folds(draws,contests),'synthetic_power':synthetic_power()}
    Path('SMART_V2_ROBUSTNESS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
