from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any

from smart_multi_challengers import POLICY_IDS

SCHEMA = 'SMART_META_GOVERNOR_1'
META_ETA = math.log(2.0) / 6.0
PRIOR_MIX = 0.20
UNIFORM_EXPECTED_HITS = 0.60


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _softmax(log_weights: dict[str, float]) -> dict[str, float]:
    if set(log_weights) != set(POLICY_IDS):
        raise ValueError('meta log-weight ids must match P07 policies')
    vals = {p: float(log_weights[p]) for p in POLICY_IDS}
    if any(not math.isfinite(v) for v in vals.values()):
        raise ValueError('meta log-weights must be finite')
    m = max(vals.values())
    ex = {p: math.exp(vals[p] - m) for p in POLICY_IDS}
    z = sum(ex.values())
    return {p: ex[p] / z for p in POLICY_IDS}


def _regularized(log_weights: dict[str, float], prior_mix: float = PRIOR_MIX) -> dict[str, float]:
    if not 0.0 <= float(prior_mix) < 1.0:
        raise ValueError('prior_mix must be in [0,1)')
    raw = _softmax(log_weights)
    u = 1.0 / len(POLICY_IDS)
    return {p: (1.0 - float(prior_mix)) * raw[p] + float(prior_mix) * u for p in POLICY_IDS}


def _validate_multi(multi: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(multi, dict) or multi.get('policy_ids') != list(POLICY_IDS):
        raise ValueError('invalid P07 multi-challenger payload')
    policies = multi.get('policies')
    if not isinstance(policies, dict) or set(policies) != set(POLICY_IDS):
        raise ValueError('P07 policies mismatch')
    for pid in POLICY_IDS:
        top6 = [int(x) for x in policies[pid].get('top6', [])]
        if len(top6) != 6 or len(set(top6)) != 6 or min(top6) < 1 or max(top6) > 60:
            raise ValueError(f'{pid}: invalid top6')
    return policies


@dataclass
class MetaGovernor:
    eta: float = META_ETA
    prior_mix: float = PRIOR_MIX
    observations: int = 0
    log_weights: dict[str, float] = field(default_factory=lambda: {p: 0.0 for p in POLICY_IDS})
    cumulative_hits: dict[str, int] = field(default_factory=lambda: {p: 0 for p in POLICY_IDS})
    selection_counts: dict[str, int] = field(default_factory=lambda: {p: 0 for p in POLICY_IDS})
    selected_cumulative_hits: int = 0
    last_selected_policy: str | None = None

    def __post_init__(self):
        self.eta = float(self.eta); self.prior_mix = float(self.prior_mix)
        if not math.isfinite(self.eta) or self.eta <= 0.0:
            raise ValueError('eta must be finite and positive')
        if not 0.0 <= self.prior_mix < 1.0:
            raise ValueError('prior_mix must be in [0,1)')
        if set(self.log_weights) != set(POLICY_IDS) or set(self.cumulative_hits) != set(POLICY_IDS) or set(self.selection_counts) != set(POLICY_IDS):
            raise ValueError('governor state ids must match P07 policies')

    def weights(self) -> dict[str, float]:
        return _regularized(self.log_weights, self.prior_mix)

    def select(self, multi: dict[str, Any]) -> dict[str, Any]:
        policies = _validate_multi(multi)
        weights = self.weights()
        # POLICY_IDS defines deterministic tie-break; quality_dynamic is first.
        selected = max(POLICY_IDS, key=lambda p: (weights[p], -POLICY_IDS.index(p)))
        payload = {
            'schema': SCHEMA,
            'observations_before_result': int(self.observations),
            'eta': float(self.eta),
            'prior_mix': float(self.prior_mix),
            'policy_weights_before_result': weights,
            'selected_policy': selected,
            'selected_top6': [int(x) for x in policies[selected]['top6']],
            'selected_policy_sha256': str(policies[selected].get('sha256', '')),
            'selection_causal': True,
            'selection_uses_current_result': False,
            'selection_scope': 'P07_CHALLENGERS_ONLY',
            'production_authority': False,
            'champion_remains_active': True,
            'retroactive_selection_prohibited': True,
        }
        payload['sha256'] = sha256_json(payload)
        return payload

    def update(self, policy_hits: dict[str, int], selected_policy: str) -> dict[str, Any]:
        if set(policy_hits) != set(POLICY_IDS):
            raise ValueError('policy_hits ids must match P07 policies')
        if selected_policy not in POLICY_IDS:
            raise ValueError('unknown selected policy')
        clean = {}
        for p in POLICY_IDS:
            h = int(policy_hits[p])
            if h < 0 or h > 6:
                raise ValueError('policy hits must be integers in [0,6]')
            clean[p] = h
        before = self.weights()
        for p in POLICY_IDS:
            self.log_weights[p] += self.eta * (clean[p] - UNIFORM_EXPECTED_HITS)
            self.cumulative_hits[p] += clean[p]
        self.selection_counts[selected_policy] += 1
        self.selected_cumulative_hits += clean[selected_policy]
        self.observations += 1
        self.last_selected_policy = selected_policy
        after = self.weights()
        out = {
            'schema': SCHEMA,
            'observations_after_result': int(self.observations),
            'selected_policy_before_result': selected_policy,
            'selected_hits': int(clean[selected_policy]),
            'policy_hits': clean,
            'weights_before_result': before,
            'weights_after_result': after,
            'update_after_result_only': True,
        }
        out['sha256'] = sha256_json(out)
        return out

    def state(self) -> dict[str, Any]:
        payload = {
            'schema': SCHEMA,
            'eta': float(self.eta),
            'prior_mix': float(self.prior_mix),
            'observations': int(self.observations),
            'log_weights': {p: float(self.log_weights[p]) for p in POLICY_IDS},
            'policy_weights': self.weights(),
            'cumulative_hits': {p: int(self.cumulative_hits[p]) for p in POLICY_IDS},
            'selection_counts': {p: int(self.selection_counts[p]) for p in POLICY_IDS},
            'selected_cumulative_hits': int(self.selected_cumulative_hits),
            'last_selected_policy': self.last_selected_policy,
            'selection_scope': 'P07_CHALLENGERS_ONLY',
            'production_authority': False,
            'champion_remains_active': True,
        }
        payload['sha256'] = sha256_json(payload)
        return payload
