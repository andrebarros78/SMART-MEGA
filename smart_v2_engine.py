from __future__ import annotations

import argparse, hashlib, json, math
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd

NUMBERS=np.arange(1,61); K=6; UNIFORM_EXPECTED_HITS=K*K/60.0
FREQ_WINDOWS=(25,50,100,250,500,1000); EWMA_SPANS=(10,25,50,100,250)
PRIOR_MIX=0.20; EXPERT_CAP_WITHIN_FAMILY=0.60; FAMILY_CAP=0.70


def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def _strict_integral(value, label: str) -> int:
    if isinstance(value, (bool, np.bool_)) or pd.isna(value):
        raise ValueError(f'{label} ausente ou nao inteiro')
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        x=float(value)
        if not math.isfinite(x) or not x.is_integer():
            raise ValueError(f'{label} nao inteiro')
        return int(x)
    raise ValueError(f'{label} deve ser numerico inteiro')


def load_draws(path:Path):
    df=pd.read_excel(path); cols=[f'Bola{i}' for i in range(1,7)]
    required=['Concurso',*cols]
    if not all(c in df.columns for c in required):
        raise ValueError('colunas Concurso e Bola1..Bola6 ausentes')
    draws=[]; contests=[]
    for row_index,r in df.iterrows():
        try:
            vals=sorted(_strict_integral(r[c], f'linha {row_index} {c}') for c in cols)
            contest=_strict_integral(r['Concurso'], f'linha {row_index} Concurso')
        except ValueError as exc:
            raise ValueError('linha com dado ausente ou nao inteiro') from exc
        if len(set(vals))!=6 or vals[0]<1 or vals[-1]>60: raise ValueError('sorteio invalido')
        draws.append(vals); contests.append(contest)
    if not contests: raise ValueError('dataset vazio')
    if len(set(contests))!=len(contests): raise ValueError('concurso duplicado')
    if any(b<=a for a,b in zip(contests,contests[1:])): raise ValueError('concursos fora de ordem')
    if any(b!=a+1 for a,b in zip(contests,contests[1:])): raise ValueError('lacuna na sequencia de concursos')
    return np.asarray(draws,int),np.asarray(contests,int)


def onehot(draws):
    X=np.zeros((len(draws),60),float)
    for i,d in enumerate(draws): X[i,np.asarray(d)-1]=1.0
    return X


def row_minmax(M):
    lo=M.min(1,keepdims=True); hi=M.max(1,keepdims=True); den=hi-lo
    return np.divide(M-lo,den,out=np.zeros_like(M,float),where=den>1e-15)


def precompute_scores(X):
    T=len(X); cs=np.vstack([np.zeros((1,60)),np.cumsum(X,0)]); out={}; idx=np.arange(T+1)
    for w in FREQ_WINDOWS:
        starts=np.maximum(0,idx-w); lens=np.maximum(1,idx-starts)
        out[f'freq{w}']=row_minmax((cs[idx]-cs[starts])/lens[:,None])
    out['freq_global']=row_minmax(np.divide(cs,np.maximum(1,idx)[:,None]))
    for span in EWMA_SPANS:
        a=2/(span+1); raw=np.zeros((T+1,60))
        for t in range(1,T+1): raw[t]=a*X[t-1]+(1-a)*raw[t-1]
        out[f'ewma{span}']=row_minmax(raw)
    return out


def redundancy_penalty(scores,floor=0.15):
    names=list(scores); M=np.vstack([scores[n] for n in names]); C=np.corrcoef(M); C=np.nan_to_num(C)
    p={}
    for i,n in enumerate(names):
        o=np.delete(np.abs(C[i]),i); p[n]=max(floor,1-float(o.mean() if len(o) else 0))
    return p,C


def rank_top6(score):
    order=np.lexsort((NUMBERS,-np.asarray(score))); return NUMBERS[order[:6]].tolist(),order


def softmax(logw):
    a=np.array(list(logw.values()),float); a-=a.max(); e=np.exp(a); e/=e.sum(); return {k:float(v) for k,v in zip(logw,e)}


def regularize(w,prior_mix=PRIOR_MIX,cap=EXPERT_CAP_WITHIN_FAMILY):
    keys=list(w); n=len(keys); a=np.array([w[k] for k in keys],float)
    a=(1-prior_mix)*a+prior_mix/n
    # capped simplex projection by iterative clipping and redistribution
    active=np.ones(n,bool); out=np.zeros(n); rem=1.0
    while True:
        if not active.any(): break
        vals=a[active]; vals=vals/vals.sum()*rem
        over=vals>cap+1e-15
        if not over.any(): out[active]=vals; break
        inds=np.where(active)[0]; capped=inds[over]; out[capped]=cap; rem-=cap*len(capped); active[capped]=False
        if rem<=1e-15: break
    if out.sum()>0: out/=out.sum()
    return {k:float(v) for k,v in zip(keys,out)}


def family_of(name): return 'freq' if name.startswith('freq') else 'ewma'

@dataclass
class WalkResult:
    rows:list; final_weights:dict; family_weights:dict; total_hits:int; uniform_expected:float; excess_hits:float; max_abs_corr:float


def walk_forward(draws,contests,start=1000,eta=math.log(2),pre=None,allowed=None):
    pre=pre or precompute_scores(onehot(draws)); names=list(pre) if allowed is None else list(allowed)
    fams=sorted(set(family_of(n) for n in names)); elog={n:0.0 for n in names}; flog={f:0.0 for f in fams}; rows=[]; maxcorr=0.0
    for t in range(start,len(draws)):
        sc={n:pre[n][t] for n in names}; pen,C=redundancy_penalty(sc); maxcorr=max(maxcorr,float(np.max(np.abs(C-np.eye(len(C))))))
        fw=regularize(softmax(flog),prior_mix=PRIOR_MIX,cap=FAMILY_CAP)
        eff={}; fam_scores={}
        for f in fams:
            fn=[n for n in names if family_of(n)==f]
            ew=regularize(softmax({n:elog[n] for n in fn}),prior_mix=PRIOR_MIX,cap=EXPERT_CAP_WITHIN_FAMILY)
            adjusted={n:ew[n]*pen[n] for n in fn}; z=sum(adjusted.values()); adjusted={n:v/z for n,v in adjusted.items()}
            for n in fn: eff[n]=fw[f]*adjusted[n]
            fam_scores[f]=sum(adjusted[n]*sc[n] for n in fn)
        agg=sum(eff[n]*sc[n] for n in names); top,order=rank_top6(agg); actual=set(draws[t]); hits=len(set(top)&actual)
        indiv={}
        for n in names:
            etop,_=rank_top6(sc[n]); h=len(set(etop)&actual); indiv[n]=h; elog[n]+=eta*(h-UNIFORM_EXPECTED_HITS)
        fam_hits={}
        for f in fams:
            ftop,_=rank_top6(fam_scores[f]); h=len(set(ftop)&actual); fam_hits[f]=h; flog[f]+=eta*(h-UNIFORM_EXPECTED_HITS)
        rows.append({'contest':int(contests[t]),'top6':top,'ranking60':NUMBERS[order].tolist(),'aggregate_scores':{str(int(NUMBERS[i])):float(agg[i]) for i in range(len(NUMBERS))},'hits':hits,'expert_hits':indiv,'family_hits':fam_hits,'weights':eff,'family_weights':fw})
    total=sum(r['hits'] for r in rows); exp=len(rows)*UNIFORM_EXPECTED_HITS
    # return final effective policy summary from last row
    lastw=rows[-1]['weights'] if rows else {}; lastfw=rows[-1]['family_weights'] if rows else {}
    return WalkResult(rows,lastw,lastfw,total,exp,total-exp,maxcorr)


def placebo_walk(draws,start=1000,seed=20260828):
    rng=np.random.default_rng(seed); total=0
    for t in range(start,len(draws)):
        top,_=rank_top6(rng.random(60)); total+=len(set(top)&set(draws[t]))
    exp=(len(draws)-start)*UNIFORM_EXPECTED_HITS; return {'total_hits':int(total),'expected':exp,'excess':float(total-exp)}


def ablation(draws,contests,start=1000,eta=math.log(2)):
    pre=precompute_scores(onehot(draws)); names=list(pre); base=walk_forward(draws,contests,start,eta,pre,names); out={}
    for drop in names:
        r=walk_forward(draws,contests,start,eta,pre,[n for n in names if n!=drop]); out[drop]={'hits_without':r.total_hits,'delta_full_minus_without':base.total_hits-r.total_hits}
    return out


def simulate_null(trials=50,steps=400,warmup=100,eta=math.log(2),seed=3050):
    rng=np.random.default_rng(seed); excess=[]
    for _ in range(trials):
        d=np.array([np.sort(rng.choice(NUMBERS,6,replace=False)) for _ in range(steps)],int); r=walk_forward(d,np.arange(1,steps+1),warmup,eta); excess.append(r.excess_hits)
    a=np.asarray(excess,float); n=steps-warmup; p=6/60; var_one=6*p*(1-p)*(54/59); z=a/math.sqrt(max(1e-12,n*var_one))
    return {'trials':trials,'steps':steps,'warmup':warmup,'mean_excess':float(a.mean()),'std_excess':float(a.std(ddof=1)),'p95_excess':float(np.quantile(a,.95)),'p99_excess':float(np.quantile(a,.99)),'positive_excess_rate':float(np.mean(a>0)),'false_positive_rate_z_ge_2':float(np.mean(z>=2.0))}


def audit(data:Path,out:Path,start=1000,mc_trials=50):
    draws,contests=load_draws(data); pre=precompute_scores(onehot(draws)); wf=walk_forward(draws,contests,start,pre=pre); placebo=placebo_walk(draws,start); abl=ablation(draws,contests,start); mc=simulate_null(mc_trials)
    n=len(wf.rows); p=6/60; var_one=6*p*(1-p)*(54/59); z=(wf.total_hits-wf.uniform_expected)/math.sqrt(max(1e-12,n*var_one))
    report={'schema':'SMART_V2_AUDIT_2','data_file':str(data),'data_sha256':sha256(data),'engine_sha256':sha256(Path(__file__)),'contests_total':len(draws),'walk_start_index':start,'walk_contests':n,
      'dynamic_weighting':'two_level_hedge_reward_hits_minus_uniform_expectation','eta':math.log(2),'prior_mix':PRIOR_MIX,'expert_cap_within_family':EXPERT_CAP_WITHIN_FAMILY,'family_cap':FAMILY_CAP,
      'redundancy_penalty':'1-mean_abs_expert_correlation, floor=0.15','tie_break':'score desc, number asc',
      'walk_forward':{'total_hits':wf.total_hits,'uniform_expected_hits':wf.uniform_expected,'excess_hits':wf.excess_hits,'mean_hits':wf.total_hits/n,'diagnostic_z_vs_uniform':z,'final_weights':wf.final_weights,'final_family_weights':wf.family_weights,'max_abs_expert_corr':wf.max_abs_corr},
      'placebo':placebo,'ablation':abl,'monte_carlo_null':mc,'guardrails':{'predictive_claim':False,'legacy_v0_6_reproduced':False,'prospective_proof':False,'reason':'historical engineering evidence is not prospective proof'}}
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); return report


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--data', required=True, help='Explicit causal dataset path; no implicit dataset default'); ap.add_argument('--out',default='SMART_V2_AUDIT.json'); ap.add_argument('--start',type=int,default=1000); ap.add_argument('--mc-trials',type=int,default=50)
    a=ap.parse_args(); r=audit(Path(a.data),Path(a.out),a.start,a.mc_trials); print(json.dumps({'walk_forward':r['walk_forward'],'placebo':r['placebo'],'monte_carlo_null':r['monte_carlo_null']},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
