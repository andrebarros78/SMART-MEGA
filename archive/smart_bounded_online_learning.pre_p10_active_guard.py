from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

SCHEMA = 'SMART_BOUNDED_ONLINE_LEARNING_1'
DEFAULT_MAX_ABS_STEP = 4.0
DEFAULT_WARMUP_MAX_ABS_STEP = 1.0
DEFAULT_WARMUP_FULL_AFTER = 5
DEFAULT_MIN_WARMUP_SCALE = 0.50
DEFAULT_MAX_ABS_CENTERED_LOGIT = 1_000_000_000.0
BASELINE_HITS = 0.60


def _validate_hits(rewards: dict[str, int | float]) -> dict[str, float]:
    if not rewards:
        raise ValueError('rewards cannot be empty')
    out: dict[str, float] = {}
    for name, value in rewards.items():
        v = float(value)
        if not math.isfinite(v) or v < 0.0 or v > 6.0 or abs(v-round(v)) > 1e-12:
            raise ValueError(f'{name}: reward must be an integer in [0,6]')
        out[name] = v
    return out


@dataclass
class BoundedOnlineLearningGuard:
    eta: float
    baseline_hits: float = BASELINE_HITS
    max_abs_step: float = DEFAULT_MAX_ABS_STEP
    warmup_max_abs_step: float = DEFAULT_WARMUP_MAX_ABS_STEP
    prior_observations: int = 0
    warmup_full_after: int = DEFAULT_WARMUP_FULL_AFTER
    min_warmup_scale: float = DEFAULT_MIN_WARMUP_SCALE
    max_abs_centered_logit: float = DEFAULT_MAX_ABS_CENTERED_LOGIT
    updates: int = 0
    clipped_update_count: int = 0
    warmup_update_count: int = 0
    spread_clip_count: int = 0
    max_abs_proposed_delta: float = 0.0
    max_abs_applied_delta: float = 0.0
    last_update: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.eta=float(self.eta); self.baseline_hits=float(self.baseline_hits)
        self.max_abs_step=float(self.max_abs_step); self.warmup_max_abs_step=float(self.warmup_max_abs_step)
        self.prior_observations=int(self.prior_observations); self.warmup_full_after=int(self.warmup_full_after)
        self.min_warmup_scale=float(self.min_warmup_scale); self.max_abs_centered_logit=float(self.max_abs_centered_logit)
        if not math.isfinite(self.eta) or self.eta <= 0: raise ValueError('eta must be finite and positive')
        if not 0 <= self.baseline_hits <= 6: raise ValueError('baseline_hits must be in [0,6]')
        if not math.isfinite(self.max_abs_step) or self.max_abs_step <= 0: raise ValueError('max_abs_step must be finite and positive')
        if not math.isfinite(self.warmup_max_abs_step) or not 0 < self.warmup_max_abs_step <= self.max_abs_step: raise ValueError('warmup_max_abs_step must be in (0,max_abs_step]')
        if self.prior_observations < 0: raise ValueError('prior_observations must be >=0')
        if self.warmup_full_after < 1: raise ValueError('warmup_full_after must be >=1')
        if not 0 < self.min_warmup_scale <= 1: raise ValueError('min_warmup_scale must be in (0,1]')
        if not math.isfinite(self.max_abs_centered_logit) or self.max_abs_centered_logit <= 0: raise ValueError('max_abs_centered_logit must be finite and positive')

    def evidence_scale(self) -> float:
        maturity=self.prior_observations+self.updates
        if maturity >= self.warmup_full_after-1: return 1.0
        progress=(maturity+1)/self.warmup_full_after
        return float(self.min_warmup_scale+(1-self.min_warmup_scale)*progress)

    def update(self, log_weights: dict[str,float], rewards: dict[str,int|float]) -> tuple[dict[str,float],dict[str,Any]]:
        if not log_weights: raise ValueError('log_weights cannot be empty')
        if set(log_weights)!=set(rewards): raise ValueError('log_weights and rewards ids must match')
        clean=_validate_hits(rewards); old={k:float(v) for k,v in log_weights.items()}
        if any(not math.isfinite(v) for v in old.values()): raise ValueError('log_weights must be finite')
        scale=self.evidence_scale(); effective_cap=self.warmup_max_abs_step if scale < 1 else self.max_abs_step
        if scale < 1: self.warmup_update_count += 1
        proposed={k:self.eta*(clean[k]-self.baseline_hits)*scale for k in old}
        applied={}; clipped=[]
        for k,delta in proposed.items():
            d=max(-effective_cap,min(effective_cap,float(delta))); applied[k]=d
            if abs(d-delta)>1e-15: clipped.append(k)
        self.clipped_update_count += len(clipped)
        self.max_abs_proposed_delta=max(self.max_abs_proposed_delta,max(abs(v) for v in proposed.values()))
        self.max_abs_applied_delta=max(self.max_abs_applied_delta,max(abs(v) for v in applied.values()))
        updated={k:old[k]+applied[k] for k in old}; center=sum(updated.values())/len(updated)
        centered={k:updated[k]-center for k in updated}; bounded={}; spread=[]
        for k,value in centered.items():
            b=max(-self.max_abs_centered_logit,min(self.max_abs_centered_logit,value)); bounded[k]=b
            if abs(b-value)>1e-15: spread.append(k)
        if spread:
            self.spread_clip_count += 1; c=sum(bounded.values())/len(bounded); bounded={k:v-c for k,v in bounded.items()}
        self.updates += 1
        audit={'schema':SCHEMA,'update_index':self.updates,'evidence_scale':scale,'effective_step_cap':effective_cap,
               'proposed_delta':{k:float(v) for k,v in proposed.items()},'applied_delta':{k:float(v) for k,v in applied.items()},
               'clipped_ids':clipped,'spread_clipped_ids':spread,'max_abs_step':self.max_abs_step,
               'warmup_max_abs_step':self.warmup_max_abs_step,'prior_observations':self.prior_observations,
               'max_abs_centered_logit':self.max_abs_centered_logit,'update_after_result_only':True,
               'few_observation_protection':bool(scale<1),'centering_regularization':True,
               'recovery_supported_by_bounded_spread_and_downstream_prior':True}
        self.last_update=audit
        return bounded,audit

    def state(self) -> dict[str,Any]:
        return {'schema':SCHEMA,'eta':self.eta,'baseline_hits':self.baseline_hits,'max_abs_step':self.max_abs_step,
                'warmup_max_abs_step':self.warmup_max_abs_step,'prior_observations':self.prior_observations,
                'warmup_full_after':self.warmup_full_after,'min_warmup_scale':self.min_warmup_scale,
                'max_abs_centered_logit':self.max_abs_centered_logit,'updates':self.updates,
                'clipped_update_count':self.clipped_update_count,'warmup_update_count':self.warmup_update_count,
                'spread_clip_count':self.spread_clip_count,'max_abs_proposed_delta':self.max_abs_proposed_delta,
                'max_abs_applied_delta':self.max_abs_applied_delta,'last_update':self.last_update,
                'downstream_recovery_prior_mix':0.05,'downstream_expert_cap':0.42,'downstream_family_cap':0.70,
                'causal_update_after_result_only':True}
