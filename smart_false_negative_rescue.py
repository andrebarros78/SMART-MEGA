
from __future__ import annotations
import hashlib,json
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Any,Mapping
SCHEMA="SMART_FALSE_NEGATIVE_RESCUE_1"
@dataclass(frozen=True)
class FalseNegativeRescueConfig:
    min_observations:int=3; max_number_boost:float=0.035; band_boost:float=0.018; false_positive_penalty:float=0.012; low_band_extra_cap:float=0.012
def sha256_json(obj:Any)->str:
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def band(n:int)->str:
    if 1<=n<=20: return "low"
    if 21<=n<=40: return "mid"
    if 41<=n<=60: return "high"
    raise ValueError(f"number out of range: {n}")
def build_profile_from_reports(root:str|Path,config:FalseNegativeRescueConfig|None=None,through_contest:int|None=None)->dict[str,Any]:
    root=Path(root); cfg=config or FalseNegativeRescueConfig()
    cutoff=None if through_contest is None else int(through_contest)
    fn={str(n):0 for n in range(1,61)}; fp={str(n):0 for n in range(1,61)}; band_fn={"low":0,"mid":0,"high":0}; obs=[]
    seen:dict[int,tuple[tuple[int,...],tuple[int,...]]]={}; duplicates_ignored=0
    for path in sorted(root.rglob('SMART_POST_RESULT_REPORT_*.json')):
        try:
            obj=json.loads(path.read_text(encoding='utf-8-sig'))
            actual=[int(x) for x in obj.get('official_result') or obj.get('actual_numbers') or []]
            generated=[int(x) for x in obj.get('generated_card') or obj.get('primary_card') or []]
            contest=int(obj.get('contest_number') or obj.get('target_contest') or 0)
        except Exception:
            continue
        if contest<=0 or (cutoff is not None and contest>cutoff): continue
        if len(actual)!=6 or len(set(actual))!=6 or len(generated)!=6 or len(set(generated))!=6: continue
        signature=(tuple(sorted(actual)),tuple(sorted(generated)))
        previous=seen.get(contest)
        if previous is not None:
            if previous!=signature: raise ValueError(f"conflicting post-result reports for contest {contest}")
            duplicates_ignored+=1; continue
        seen[contest]=signature
        aset=set(actual); gset=set(generated); fns=sorted(aset-gset); fps=sorted(gset-aset)
        for n in fns: fn[str(n)]+=1; band_fn[band(n)]+=1
        for n in fps: fp[str(n)]+=1
        obs.append({"contest":contest,"false_negatives":fns,"false_positives":fps,"hit_count":len(aset&gset)})
    obs.sort(key=lambda x:int(x["contest"])); total=len(obs)
    profile={"schema":SCHEMA,"status":"PASS","result_used_for_future_only":True,"through_contest":cutoff,"causal_cutoff_enforced":cutoff is not None,"observations":total,"source_contests":[int(x["contest"]) for x in obs],"duplicates_ignored":duplicates_ignored,"config":asdict(cfg),"false_negative_counts":fn,"false_positive_counts":fp,"band_false_negative_counts":band_fn,"recent_observations":obs[-20:],"activation":{"number_specific_active":total>=cfg.min_observations,"band_level_active":total>=1}}
    profile["sha256"]=sha256_json(profile); return profile
def write_profile(root:str|Path,out:str|Path|None=None,through_contest:int|None=None)->dict[str,Any]:
    root=Path(root); out=Path(out) if out else root/'SMART_FALSE_NEGATIVE_RESCUE_PROFILE.json'
    profile=build_profile_from_reports(root,through_contest=through_contest); tmp=out.with_suffix(out.suffix+'.tmp')
    tmp.write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(out); return profile
def apply_rescue(aggregate_scores:Mapping[int|str,float],profile:Mapping[str,Any]|None)->tuple[dict[str,float],dict[str,Any]]:
    scores={str(int(k)):float(v) for k,v in aggregate_scores.items()}
    if len(scores)!=60: raise ValueError('aggregate_scores must contain 60 values')
    if not profile: return scores,{"status":"INACTIVE","reason":"profile_missing","result_used":False}
    cfgd=profile.get('config') or {}; cfg=FalseNegativeRescueConfig(**{k:cfgd[k] for k in cfgd if k in FalseNegativeRescueConfig.__dataclass_fields__})
    obs=int(profile.get('observations') or 0); fn=profile.get('false_negative_counts') or {}; fp=profile.get('false_positive_counts') or {}; bandfn=profile.get('band_false_negative_counts') or {}
    total_band=max(1,sum(int(v) for v in bandfn.values())); adjusted=dict(scores); deltas={}
    for n in range(1,61):
        k=str(n); b=band(n); share=float(bandfn.get(b,0))/total_band; delta=0.0
        if obs>=1:
            delta+=cfg.band_boost*share
            if b=='low': delta+=min(cfg.low_band_extra_cap,cfg.band_boost*share)
        if obs>=cfg.min_observations:
            delta+=min(cfg.max_number_boost,cfg.max_number_boost*(float(fn.get(k,0))/max(1,obs)))
            delta-=min(cfg.false_positive_penalty,cfg.false_positive_penalty*(float(fp.get(k,0))/max(1,obs)))
        adjusted[k]=float(scores[k]+delta)
        if abs(delta)>1e-15: deltas[k]=delta
    audit={"schema":SCHEMA,"status":"PASS","observations":obs,"result_used":False,"profile_sha256":profile.get('sha256'),"nonzero_deltas":deltas}
    audit['sha256']=sha256_json(audit); return adjusted,audit
def load_profile(root:str|Path)->dict[str,Any]|None:
    p=Path(root)/'SMART_FALSE_NEGATIVE_RESCUE_PROFILE.json'
    return None if not p.exists() else json.loads(p.read_text(encoding='utf-8-sig'))
