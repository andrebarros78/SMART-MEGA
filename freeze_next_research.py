from __future__ import annotations
import argparse, hashlib, json, math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import smart_v2_engine as e

def sha256(p:Path):
    p=Path(p)
    if not p.is_absolute():
        p=Path(__file__).resolve().parent / p
    h=hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest()

def current_policy(draws,start=1000,eta=math.log(2)):
    pre=e.precompute_scores(e.onehot(draws)); names=list(pre); fams=sorted(set(e.family_of(n) for n in names)); elog={n:0.0 for n in names}; flog={f:0.0 for f in fams}
    def policy(t):
        sc={n:pre[n][t] for n in names}; pen,_=e.redundancy_penalty(sc); fw=e.regularize(e.softmax(flog),prior_mix=e.PRIOR_MIX,cap=e.FAMILY_CAP); eff={}; fam_scores={}
        for f in fams:
            fn=[n for n in names if e.family_of(n)==f]; ew=e.regularize(e.softmax({n:elog[n] for n in fn}),prior_mix=e.PRIOR_MIX,cap=e.EXPERT_CAP_WITHIN_FAMILY)
            adj={n:ew[n]*pen[n] for n in fn}; z=sum(adj.values()); adj={n:v/z for n,v in adj.items()}
            for n in fn: eff[n]=fw[f]*adj[n]
            fam_scores[f]=sum(adj[n]*sc[n] for n in fn)
        agg=sum(eff[n]*sc[n] for n in names); return sc,fw,eff,fam_scores,agg
    for t in range(start,len(draws)):
        sc,fw,eff,fam_scores,agg=policy(t); actual=set(draws[t])
        for n in names:
            top,_=e.rank_top6(sc[n]); elog[n]+=eta*(len(set(top)&actual)-e.UNIFORM_EXPECTED_HITS)
        for f in fams:
            top,_=e.rank_top6(fam_scores[f]); flog[f]+=eta*(len(set(top)&actual)-e.UNIFORM_EXPECTED_HITS)
    sc,fw,eff,fam_scores,agg=policy(len(draws)); top,order=e.rank_top6(agg)
    ranking=(e.NUMBERS[order]).tolist(); return {'top6':top,'ranking60':ranking,'aggregate_scores':{str(i+1):float(agg[i]) for i in range(60)},'expert_weights':eff,'family_weights':fw}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--data',required=True); ap.add_argument('--target',type=int,required=True); ap.add_argument('--out',default=None); ap.add_argument('--start',type=int,default=1000); a=ap.parse_args()
    data=Path(a.data); draws,contests=e.load_draws(data)
    if int(contests[-1])>=a.target: raise SystemExit('target already present in data; refusing retrospective freeze')
    if int(contests[-1])!=a.target-1: raise SystemExit('data must end immediately before target contest')
    pol=current_policy(draws,a.start)
    obj={'schema':'SMART_RESEARCH_FREEZE_1','target_contest':a.target,'frozen_utc':datetime.now(timezone.utc).isoformat(),'frozen_before_result':True,'research_only':True,'operational_cards':False,'production_predictive_weight':0.0,
      'data_file':str(data),'data_sha256':sha256(data),'engine_file':'smart_v2_engine.py','engine_sha256':sha256(Path('smart_v2_engine.py')),'start_index':a.start,'eta':math.log(2),'tie_break':'score desc, number asc',**pol}
    out=Path(a.out or f'SMART_{a.target}_RESEARCH_FREEZE.json'); out.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps({'target':a.target,'top6':pol['top6'],'data_sha256':obj['data_sha256'],'engine_sha256':obj['engine_sha256'],'freeze_file_sha256':sha256(out)},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
