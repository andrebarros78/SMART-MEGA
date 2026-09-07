from __future__ import annotations
from dataclasses import dataclass,asdict
from datetime import datetime

ACTIONABLE='ACTIONABLE_SAME_CONTEST'
SCIENTIFIC='SCIENTIFIC_MECHANISM_ONLY'
VALID={ACTIONABLE,SCIENTIFIC}

@dataclass(frozen=True)
class GateResult:
    status:str
    evidence_scope:str
    causal_before_draw:bool
    actionable_before_bet_close:bool
    same_contest_weight_allowed:bool
    reason:str
    def to_dict(self): return asdict(self)

def _dt(value:str)->datetime:
    x=datetime.fromisoformat(value.replace('Z','+00:00'))
    if x.tzinfo is None: raise ValueError('timezone required')
    return x

def evaluate(*,scheduled_datetime:str,bet_close_datetime:str,evidence_timestamp:str,evidence_scope:str)->GateResult:
    scope=str(evidence_scope).strip().upper()
    if scope not in VALID: raise ValueError('invalid evidence_scope')
    draw=_dt(scheduled_datetime); close=_dt(bet_close_datetime); evidence=_dt(evidence_timestamp)
    if close>=draw: raise ValueError('bet close must precede scheduled draw')
    causal=evidence<=draw
    actionable=evidence<=close
    if not causal:
        return GateResult('REJECT',scope,False,False,False,'evidence occurs after scheduled draw')
    if scope==ACTIONABLE and not actionable:
        return GateResult('REJECT',scope,True,False,False,'same-contest actionable evidence occurs after bet close')
    if scope==SCIENTIFIC:
        return GateResult('PASS_SCIENTIFIC_ONLY',scope,True,actionable,False,'mechanism evidence cannot influence same contest weight')
    return GateResult('PASS_ACTIONABLE',scope,True,True,True,'evidence available before bet close')

@dataclass(frozen=True)
class FreezeWindowResult:
    status:str
    scheduled_datetime:str
    observed_at:str
    before_draw:bool
    freeze_authority_allowed:bool
    reason:str
    def to_dict(self): return asdict(self)

def evaluate_freeze_window(*,scheduled_datetime:str,observed_at:str)->FreezeWindowResult:
    draw=_dt(scheduled_datetime)
    observed=_dt(observed_at)
    allowed=observed < draw
    if not allowed:
        return FreezeWindowResult(
            'REJECT', scheduled_datetime, observed_at, False, False,
            'freeze authority requires observed_at strictly before scheduled draw'
        )
    return FreezeWindowResult(
        'PASS', scheduled_datetime, observed_at, True, True,
        'freeze authority is inside the pre-draw window'
    )

__all__=['ACTIONABLE','SCIENTIFIC','GateResult','FreezeWindowResult','evaluate','evaluate_freeze_window']
