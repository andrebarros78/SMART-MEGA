from dataclasses import dataclass
from hashlib import sha256
import json

@dataclass(frozen=True)
class HyperparameterRule:
    name: str
    minimum: float
    maximum: float
    max_step_fraction: float = 0.25

class CalibrationGovernor:
    def __init__(self, rules):
        self.rules=dict(rules)
        if not self.rules: raise ValueError("rules_required")
    def evaluate(self,current,proposed,actor,reason):
        if not str(actor).strip() or not str(reason).strip(): raise ValueError("actor_and_reason_required")
        errors=[]
        for name,value in proposed.items():
            rule=self.rules.get(name)
            if rule is None: errors.append("unknown_parameter:"+name); continue
            value=float(value)
            if not rule.minimum <= value <= rule.maximum: errors.append("out_of_bounds:"+name); continue
            if name in current:
                span=max(rule.maximum-rule.minimum,1e-12)
                if abs(value-float(current[name]))/span > rule.max_step_fraction: errors.append("step_too_large:"+name)
        raw=json.dumps({"current":dict(current),"proposed":dict(proposed),"actor":actor,"reason":reason},sort_keys=True).encode()
        return {"approved":not errors,"reasons":errors or ["approved"],"proposal_hash":sha256(raw).hexdigest()}
