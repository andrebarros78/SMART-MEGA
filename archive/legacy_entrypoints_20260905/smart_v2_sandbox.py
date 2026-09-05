from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
import smart_v2_engine as e

VAR_ONE=6*(6/60)*(1-6/60)*(54/59)
def zscore(excess,n): return float(excess/math.sqrt(max(1e-12,n*VAR_ONE)))

def gen_uniform(rng,steps): return np.array([np.sort(rng.choice(e.NUMBERS,6,replace=False)) for _ in range(steps)],int)
def gen_weighted(rng,steps,weights):
    p=np.asarray(weights,float); p/=p.sum(); return np.array([np.sort(rng.choice(e.NUMBERS,6,replace=False,p=p)) for _ in range(steps)],int)

def scenario(draws,warmup=150):
    r=e.walk_forward(draws,np.arange(1,len(draws)+1),warmup)
    n=len(draws)-warmup
    return {'hits':r.total_hits,'expected':r.uniform_expected,'excess':r.excess_hits,'z':zscore(r.excess_hits,n),'max_corr':r.max_abs_corr}

def main():
    rng=np.random.default_rng(20260828); report={'schema':'SMART_V2_SANDBOX_1','scenarios':{}}
    # 1) IID null across seeds: should not systematically create signal.
    zs=[]
    for seed in range(20):
        rr=np.random.default_rng(1000+seed); zs.append(scenario(gen_uniform(rr,700),200)['z'])
    report['scenarios']['iid_null_20_seeds']={'mean_z':float(np.mean(zs)),'max_z':float(np.max(zs)),'min_z':float(np.min(zs)),'rate_z_ge_2':float(np.mean(np.array(zs)>=2))}
    # 2) Strong persistent bias: six numbers have 3x sampling weight.
    w=np.ones(60); w[:6]=3.0; report['scenarios']['persistent_bias']=scenario(gen_weighted(rng,900,w),200)
    # 3) Regime shift: bias 1..6 then 31..36.
    w1=np.ones(60); w1[:6]=3.0; w2=np.ones(60); w2[30:36]=3.0
    d=np.vstack([gen_weighted(rng,450,w1),gen_weighted(rng,450,w2)]); report['scenarios']['regime_shift']=scenario(d,200)
    # 4) Vanishing signal: biased then uniform. Expected to lose confidence after change.
    d=np.vstack([gen_weighted(rng,450,w1),gen_uniform(rng,450)]); full=scenario(d,200); tail=scenario(d[450:],150); report['scenarios']['signal_vanishes']={'full':full,'uniform_tail':tail}
    # 5) Alternating adversarial regimes every draw.
    alt=[]
    for i in range(900): alt.append(gen_weighted(rng,1,w1 if i%2==0 else w2)[0])
    report['scenarios']['alternating_regimes']=scenario(np.asarray(alt),200)
    # 6) Label permutation invariance: relabeling a null stream should retain null behavior.
    base=gen_uniform(np.random.default_rng(77),800); perm=np.random.default_rng(78).permutation(e.NUMBERS)+0; mapping={i+1:int(perm[i]) for i in range(60)}; rel=np.array([np.sort([mapping[int(x)] for x in row]) for row in base]);
    a=scenario(base,200); b=scenario(rel,200); report['scenarios']['label_permutation_null']={'original_z':a['z'],'permuted_z':b['z'],'abs_delta_z':abs(a['z']-b['z'])}
    # 7) Determinism / reproducibility.
    d=gen_uniform(np.random.default_rng(123),600); r1=scenario(d,150); r2=scenario(d.copy(),150); report['scenarios']['determinism']={'identical':r1==r2,'run1':r1,'run2':r2}
    # Acceptance statements are deliberately structural, not tuned to historical outcomes.
    checks={
      'null_fpr_le_0_10': report['scenarios']['iid_null_20_seeds']['rate_z_ge_2']<=0.10,
      'detects_persistent_bias_z_ge_2': report['scenarios']['persistent_bias']['z']>=2,
      'detects_regime_shift_z_ge_2': report['scenarios']['regime_shift']['z']>=2,
      'deterministic': report['scenarios']['determinism']['identical'],
      'permutation_null_not_materially_changed': report['scenarios']['label_permutation_null']['abs_delta_z']<2.0,
    }
    report['checks']=checks; report['passed']=all(checks.values())
    Path('SMART_V2_SANDBOX.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
