
from __future__ import annotations
import hashlib,itertools,json,math
from dataclasses import asdict,dataclass
from typing import Any,Mapping
from numbers import Integral
SCHEMA="SMART_PRIMARY_CARD_SELECTOR_2"
@dataclass(frozen=True)
class PrimaryCardSelectorConfig:
    candidate_pool_size:int=18; max_candidate_pool_size:int=30; numbers_per_card:int=6
    min_low_band:int=2; max_low_band:int=4; min_mid_band:int=1; max_mid_band:int=3; min_high_band:int=0; max_high_band:int=2
    require_top3_presence:bool=True; score_weight:float=1.0; rank_weight:float=0.035; band_balance_weight:float=0.08; concentration_penalty:float=0.18
    def validate(self)->None:
        integer_fields = (
            "candidate_pool_size", "max_candidate_pool_size", "numbers_per_card",
            "min_low_band", "max_low_band", "min_mid_band", "max_mid_band",
            "min_high_band", "max_high_band",
        )
        for name in integer_fields:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Integral):
                raise ValueError(f"{name} must be an integer")
        if not 6 <= self.candidate_pool_size <= 60:
            raise ValueError("candidate_pool_size must be between 6 and 60")
        if not self.candidate_pool_size <= self.max_candidate_pool_size <= 60:
            raise ValueError("max_candidate_pool_size invalid")
        if self.numbers_per_card != 6:
            raise ValueError("Mega-Sena primary card must contain exactly 6 numbers")
        for band in ("low", "mid", "high"):
            if not 0 <= getattr(self, f"min_{band}_band") <= getattr(self, f"max_{band}_band") <= 6:
                raise ValueError(f"{band} band limits must satisfy 0 <= min <= max <= 6")
        if self.min_low_band+self.min_mid_band+self.min_high_band>6:
            raise ValueError("band minimums exceed card size")
        if self.max_low_band+self.max_mid_band+self.max_high_band<6:
            raise ValueError("band maximums cannot fill a card")
        if not isinstance(self.require_top3_presence, bool):
            raise ValueError("require_top3_presence must be a boolean")
        for name in ("score_weight", "rank_weight", "band_balance_weight", "concentration_penalty"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")

def sha256_json(obj:Any)->str:
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def _number(value:Any)->int:
    if isinstance(value, bool):
        raise ValueError("number must be an integer, not boolean")
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    raise ValueError("number must be an integer or decimal integer string")
def _coerce_scores(scores:Mapping[int|str,float])->dict[int,float]:
    out={}
    for k,v in scores.items():
        n=_number(k)
        if n in out: raise ValueError(f"duplicate number after key normalization: {n}")
        if isinstance(v, bool): raise ValueError(f"score must be numeric, not boolean: {n}")
        x=float(v)
        if not 1<=n<=60: raise ValueError(f"number out of range: {n}")
        if not math.isfinite(x): raise ValueError(f"non-finite score for number {n}")
        out[n]=x
    if len(out)!=60: raise ValueError("primary selector requires scores for all 60 numbers")
    return out
def _band(n:int)->str:
    if 1<=n<=20: return "low"
    if 21<=n<=40: return "mid"
    if 41<=n<=60: return "high"
    raise ValueError(f"number out of range: {n}")
def _counts(card)->dict[str,int]:
    return {"low":sum(1 for n in card if _band(int(n))=="low"),"mid":sum(1 for n in card if _band(int(n))=="mid"),"high":sum(1 for n in card if _band(int(n))=="high")}
def _normalized(scores,cands):
    vals=[scores[n] for n in cands]; lo=min(vals); hi=max(vals)
    span=hi-lo
    if not math.isfinite(span): raise ValueError("score range is too large to normalize safely")
    return {n:(1.0 if math.isclose(lo,hi) else (scores[n]-lo)/span) for n in cands}
def _try_select(scores,ranking,cfg,pool_size):
    cands=ranking[:pool_size]; norm=_normalized(scores,cands); pos={n:i for i,n in enumerate(cands)}; top3=set(ranking[:3])
    best=None; rejected={"band_guard":0,"top3_guard":0}; evaluated=feasible=0
    for combo in itertools.combinations(cands,int(cfg.numbers_per_card)):
        evaluated+=1; c=_counts(combo)
        if not(cfg.min_low_band<=c["low"]<=cfg.max_low_band and cfg.min_mid_band<=c["mid"]<=cfg.max_mid_band and cfg.min_high_band<=c["high"]<=cfg.max_high_band):
            rejected["band_guard"]+=1; continue
        if cfg.require_top3_presence and not(set(combo)&top3): rejected["top3_guard"]+=1; continue
        feasible+=1
        score=sum(norm[n] for n in combo); rank=sum((len(cands)-pos[n])/len(cands) for n in combo)
        bal=1.0-(abs(c["low"]-2.5)+abs(c["mid"]-2.5)+abs(c["high"]-1.0))/6.0
        conc=max(c.values())-min(c.values())
        obj=cfg.score_weight*score+cfg.rank_weight*rank+cfg.band_balance_weight*bal-cfg.concentration_penalty*max(0,conc-3)
        if not math.isfinite(obj): raise ValueError("selector objective must be finite; reduce score weights")
        key=(float(obj),tuple(sorted(combo)))
        if best is None or key[0]>best[0] or (math.isclose(key[0],best[0]) and key[1]<best[1]): best=key
    return best,{"candidate_pool":cands,"candidate_pool_size":len(cands),"evaluated_combinations":evaluated,"feasible_combinations":feasible,"rejected_combinations":rejected}
def select_primary_card(aggregate_scores:Mapping[int|str,float],ranking60:list[int]|tuple[int,...]|None=None,config:PrimaryCardSelectorConfig|None=None)->dict[str,Any]:
    cfg=config or PrimaryCardSelectorConfig(); cfg.validate(); scores=_coerce_scores(aggregate_scores)
    ranking=[_number(x) for x in ranking60] if ranking60 is not None else sorted(scores,key=lambda n:(-scores[n],n))
    if len(ranking)!=60 or set(ranking)!=set(range(1,61)): raise ValueError("ranking60 must be a permutation of 1..60")
    pure=sorted(ranking[:6]); attempts=[]; best=meta=None
    pools=list(range(int(cfg.candidate_pool_size),int(cfg.max_candidate_pool_size)+1,2))
    if pools[-1] != int(cfg.max_candidate_pool_size): pools.append(int(cfg.max_candidate_pool_size))
    for pool in pools:
        best,meta=_try_select(scores,ranking,cfg,pool); attempts.append({"pool_size":pool,"feasible":meta["feasible_combinations"],"evaluated":meta["evaluated_combinations"]})
        if best is not None: break
    if best is None:
        raise ValueError("no valid primary card within candidate pool; review band constraints or expand max_candidate_pool_size")
    else:
        selected=list(best[1]); obj=best[0]; fallback=False
    audit={"schema":SCHEMA,"status":"PASS","selection_rule":"hybrid frozen-score single-card selector with bounded adaptive expansion and band concentration guard","result_used":False,"pure_champion_top6_sorted":pure,"selected_numbers":selected,"selected_band_counts":_counts(selected),"pure_top6_band_counts":_counts(pure),"objective_value":obj,"fallback_used":fallback,"adaptive_attempts":attempts,"config":asdict(cfg)}
    audit.update(meta); audit["sha256"]=sha256_json(audit); return audit
