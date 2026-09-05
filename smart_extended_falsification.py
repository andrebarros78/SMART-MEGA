from __future__ import annotations
import json, math, hashlib
from pathlib import Path
import numpy as np
import smart_randomness_cartography as rc
import smart_cartography_extended as ex

SCHEMA='SMART_EXTENDED_FALSIFICATION_V1'
METRICS=('mi_lag1_mean','network_density','network_clustering','regime_count')

def metrics(draws):
    tm=ex.temporal_memory(draws); nw=ex.network_structure(draws); rg=ex.regime_structure(draws)
    return {
      'mi_lag1_mean':float(tm['lag1_binary_mutual_information_mean_bits']),
      'network_density':float(nw['density']),
      'network_clustering':float(nw['average_clustering']),
      'regime_count':float(rg['count'])}

def holm(ps):
    items=sorted(ps.items(),key=lambda kv:kv[1]); m=len(items); out={}
    running=0.0
    for rank,(k,p) in enumerate(items,1):
        adj=min(1.0,(m-rank+1)*p); running=max(running,adj); out[k]=running
    return out

def compare(obs,vals):
    a=np.asarray(vals,float); mean=float(a.mean()); sd=float(a.std(ddof=1)) if len(a)>1 else 0.0
    dev=abs(float(obs)-mean); p=float((1+np.sum(np.abs(a-mean)>=dev))/(len(a)+1))
    return {'observed':float(obs),'null_mean':mean,'null_std':sd,'replications':int(len(a)),'empirical_two_sided_p':p}

def build(draws,seed=20260904,reps_u0=500,reps_other=500):
    a=rc._v(draws); rng=np.random.default_rng(seed); obs=metrics(a)
    family_size=24; min_reps=int(np.ceil(family_size/0.05 - 1))
    if reps_u0 < min_reps or reps_other < min_reps:
        raise ValueError(f'underpowered Monte Carlo for Holm family: require >= {min_reps} replications per null')
    families={
      'U0':lambda:rc.u0_uniform_iid(len(a),rng),
      'U1':lambda:rc.u1_temporal_permutation(a,rng),
      'U2':lambda:rc.u2_label_permutation(a,rng),
      'U3':lambda:rc.u3_block_shuffle(a,rng,25),
      'U4':lambda:rc.u4_marginals_preserved(a,rng),
      'U5':lambda:rc.u5_fitted_dynamic(a,rng)}
    comps={}; rawp={}
    for fam,fn in families.items():
        reps=reps_u0 if fam=='U0' else reps_other
        vals={k:[] for k in METRICS}
        for _ in range(reps):
            mm=metrics(fn())
            for k in METRICS: vals[k].append(mm[k])
        comps[fam]={}
        for k in METRICS:
            c=compare(obs[k],vals[k]); comps[fam][k]=c; rawp[f'{fam}:{k}']=c['empirical_two_sided_p']
    adj=holm(rawp)
    for key,p in adj.items():
        fam,k=key.split(':',1); comps[fam][k]['holm_adjusted_p']=float(p); comps[fam][k]['reject_0_05']=bool(p<0.05)
    return {'schema':SCHEMA,'seed':seed,'observed':obs,'comparisons':comps,'multiplicity':{'method':'Holm','family_size':len(rawp),'alpha':0.05,'min_replications_for_resolution':min_reps,'resolution_guard_passed':True},'predictive_weight_authorized':False,'interpretation':'diagnostic falsification only; rejection of a null is not prospective predictive proof'}

def write(data='Mega-Sena_through_3053_v2.xlsx',out='SMART_EXTENDED_FALSIFICATION.json',cutoff=3053,reps_u0=500,reps_other=500):
    draws,contests=rc.load_draws(data)
    if int(np.max(contests))!=int(cutoff): raise ValueError('cutoff mismatch')
    obj=build(draws,reps_u0=reps_u0,reps_other=reps_other); obj['cutoff_contest']=int(cutoff); obj['data_file']=Path(data).name; obj['data_sha256']=rc.sha256_file(data)
    Path(out).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); return obj

if __name__=='__main__':
    o=write(); print(json.dumps({'schema':o['schema'],'comparisons':sum(len(x) for x in o['comparisons'].values()),'rejections':[f'{u}:{m}' for u,v in o['comparisons'].items() for m,c in v.items() if c['reject_0_05']]}))
