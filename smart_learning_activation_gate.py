from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class ActivationDecision:
    status: str
    predictive_weight_authorized: bool
    prospective_challenger_authorized: bool
    reason: str
    def to_dict(self): return asdict(self)

def evaluate(*, calibration_gain: float, validation_gain: float, holdout_gain: float, global_gain: float,
             preregistered: bool, prospective_evidence: bool, leakage_free: bool) -> ActivationDecision:
    vals=[calibration_gain,validation_gain,holdout_gain,global_gain]
    if not all(float(x)==float(x) for x in vals):
        raise ValueError('gains must be finite')
    if not leakage_free:
        return ActivationDecision('REJECT',False,False,'future leakage or causal-integrity failure')
    if validation_gain < 0 or holdout_gain < 0 or global_gain < 0:
        return ActivationDecision('REJECT_NON_REGRESSION',False,False,'candidate regresses validation, holdout, or global result')
    if calibration_gain <= 0 and validation_gain <= 0 and holdout_gain <= 0 and global_gain <= 0:
        return ActivationDecision('NO_PROVEN_GAIN',False,False,'candidate does not improve any declared partition')
    if not preregistered:
        return ActivationDecision('SHADOW_ONLY',False,False,'candidate was not preregistered')
    if not prospective_evidence:
        return ActivationDecision('PROSPECTIVE_CHALLENGER_ONLY',False,True,'retrospective evidence is non-regressive but cannot authorize predictive weight')
    return ActivationDecision('ELIGIBLE_FOR_BOUNDED_PROMOTION',True,True,'preregistered prospective evidence is leakage-free and non-regressive')

__all__=['ActivationDecision','evaluate']
