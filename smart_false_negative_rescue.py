
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
class MissingCanonicalLineage(ValueError):
    """Historical evidence is unavailable; it must not influence current scores."""


def _trusted_canonical_report(root:Path,path:Path,obj:dict[str,Any],contest:int,actual:list[int],generated:list[int])->None:
    """Reject tampered, foreign, or unbound evidence before it affects predictive scores."""
    if path.name != f"SMART_POST_RESULT_REPORT_{contest}.json":
        raise ValueError(f"untrusted post-result report filename: {path.name}")
    if obj.get("schema") != "SMART_POST_RESULT_REPORT_1" or obj.get("status") != "PASS":
        raise ValueError(f"untrusted post-result report schema/status: {path.name}")
    observed=obj.get("sha256")
    signed=dict(obj); signed.pop("sha256",None)
    if not isinstance(observed,str) or observed != sha256_json(signed):
        raise ValueError(f"post-result report self-hash mismatch: {path.name}")
    audit=obj.get("process_audit")
    if not isinstance(audit,dict) or audit.get("findings") or audit.get("freeze_authority_present") is not True:
        raise ValueError(f"post-result report missing verified process audit: {path.name}")
    trusted={}
    for name,source_key,digest_key in (
        ("freeze","freeze_artifact","freeze_sha256"),
        ("ledger","ledger","ledger_sha256"),
    ):
        rel=audit.get(source_key)
        sha=audit.get(digest_key)
        if not isinstance(rel,str) or not isinstance(sha,str) or len(sha)!=64:
            raise ValueError(f"post-result report missing {name} lineage: {path.name}")
        candidate=(root/rel).resolve()
        if not candidate.is_relative_to(root):
            raise ValueError(f"post-result report {name} escapes canonical root: {path.name}")
        if not candidate.is_file():
            raise MissingCanonicalLineage(f"post-result report {name} evidence absent: {path.name}")
        actual_sha=hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual_sha != sha:
            raise ValueError(f"post-result report {name} hash mismatch: {path.name}")
        trusted[name]=candidate
    freeze=json.loads(trusted["freeze"].read_text(encoding="utf-8-sig"))
    if int(freeze.get("target_contest",-1))!=contest:
        raise ValueError(f"post-result report target differs from frozen contest: {path.name}")
    ledger=json.loads(trusted["ledger"].read_text(encoding="utf-8-sig"))
    if not isinstance(ledger,dict) or not isinstance(ledger.get("events"),list):
        raise ValueError(f"post-result report ledger event structure invalid: {path.name}")
    events=[x for x in ledger["events"] if isinstance(x,dict) and x.get("target_contest")==contest]
    freeze_events=[x for x in events if x.get("event_type")=="FREEZE"]
    adjudications=[x for x in events if x.get("event_type")=="ADJUDICATION"]
    if (len(freeze_events)!=1 or len(adjudications)!=1
        or freeze_events[0].get("freeze_sha256")!=audit["freeze_sha256"]
        or adjudications[0].get("freeze_sha256")!=audit["freeze_sha256"]
        or sorted(adjudications[0].get("actual_numbers") or [])!=sorted(actual)):
        raise ValueError(f"post-result report is not bound to adjudicated ledger evidence: {path.name}")
    champion=sorted(int(x) for x in (freeze.get("champion") or {}).get("top6",[]))
    frozen_primary=(freeze_events[0].get("primary_card") or {}).get("numbers") or []
    trusted_cards=[champion]
    if isinstance(frozen_primary,list) and len(frozen_primary)==6:
        trusted_cards.append(sorted(int(x) for x in frozen_primary))
    if sorted(generated) not in trusted_cards:
        raise ValueError(f"post-result report card differs from its immutable freeze: {path.name}")
    if int(obj.get("hit_count",-1))!=len(set(actual)&set(generated)):
        raise ValueError(f"post-result report hit count mismatch: {path.name}")
    portfolio=obj.get("portfolio_adjudication") or {}
    fingerprint=sha256_json({
        "target":contest,"official_result":actual,"generated_card":generated,
        "freeze_sha256":audit["freeze_sha256"],"ledger_sha256":audit["ledger_sha256"],
        "portfolio_sha256":portfolio.get("portfolio_sha256"),
        "portfolio_hits_per_game":portfolio.get("hits_per_game"),
    })
    if obj.get("source_fingerprint")!=fingerprint:
        raise ValueError(f"post-result report evidence fingerprint mismatch: {path.name}")


def build_profile_from_reports(root:str|Path,config:FalseNegativeRescueConfig|None=None,through_contest:int|None=None)->dict[str,Any]:
    root=Path(root).resolve(); cfg=config or FalseNegativeRescueConfig()
    strict=(root/'SMART_CANONICAL_ROOT.json').is_file()
    cutoff=None if through_contest is None else int(through_contest)
    fn={str(n):0 for n in range(1,61)}; fp={str(n):0 for n in range(1,61)}; band_fn={"low":0,"mid":0,"high":0}; obs=[]
    quarantined=[]
    seen:dict[int,tuple[tuple[int,...],tuple[int,...]]]={}; duplicates_ignored=0
    for path in sorted(root.glob('SMART_POST_RESULT_REPORT_*.json')):
        try:
            obj=json.loads(path.read_text(encoding='utf-8-sig'))
            actual=[int(x) for x in obj.get('official_result') or obj.get('actual_numbers') or []]
            generated=[int(x) for x in obj.get('generated_card') or obj.get('primary_card') or []]
            contest=int(obj.get('contest_number') or obj.get('target_contest') or 0)
        except Exception as exc:
            if strict: raise ValueError(f'invalid canonical post-result report: {path.name}') from exc
            continue
        if contest<=0 or (cutoff is not None and contest>cutoff): continue
        if len(actual)!=6 or len(set(actual))!=6 or len(generated)!=6 or len(set(generated))!=6 or any(n<1 or n>60 for n in actual+generated):
            if strict: raise ValueError(f'invalid canonical post-result numbers: {path.name}')
            continue
        if strict:
            try:
                _trusted_canonical_report(root,path,obj,contest,actual,generated)
            except MissingCanonicalLineage:
                quarantined.append(path.name)
                continue
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
    profile={"schema":SCHEMA,"status":"PASS","result_used_for_future_only":True,"through_contest":cutoff,"causal_cutoff_enforced":cutoff is not None,"observations":total,"source_contests":[int(x["contest"]) for x in obs],"duplicates_ignored":duplicates_ignored,"quarantined_reports":quarantined,"quarantined_count":len(quarantined),"config":asdict(cfg),"false_negative_counts":fn,"false_positive_counts":fp,"band_false_negative_counts":band_fn,"recent_observations":obs[-20:],"activation":{"number_specific_active":total>=cfg.min_observations,"band_level_active":total>=1}}
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
