from __future__ import annotations

import math
from typing import Any, Iterable

POLICY_SCHEMA = 'SMART_PROMOTION_GATE_POLICY_1'
BASE_MIN_PROSPECTIVE_CONTESTS = 20
MIN_E_VALUE = 10.0
MIN_HITS = 0
MAX_HITS = 6


def _validated_hits(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f'{field} must be an integer in [{MIN_HITS}, {MAX_HITS}]')
    try:
        numeric = float(value)
        hits = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{field} must be an integer in [{MIN_HITS}, {MAX_HITS}]') from exc
    if not math.isfinite(numeric) or numeric != hits or not (MIN_HITS <= hits <= MAX_HITS):
        raise ValueError(f'{field} must be an integer in [{MIN_HITS}, {MAX_HITS}]')
    return hits


def adaptive_min_contests(mean_hit_advantage: float) -> int:
    """Return a predeclared sample floor that rises as observed advantage shrinks."""
    advantage = float(mean_hit_advantage)
    if not math.isfinite(advantage):
        raise ValueError('mean_hit_advantage must be finite')
    if advantage >= 0.50:
        return BASE_MIN_PROSPECTIVE_CONTESTS
    if advantage >= 0.25:
        return 30
    if advantage >= 0.10:
        return 50
    if advantage > 0.0:
        return 80
    return BASE_MIN_PROSPECTIVE_CONTESTS


def assess_promotion_records(records: Iterable[dict[str, Any]], e_value: float) -> dict[str, Any]:
    rows = list(records)
    validated = [
        {
            'challenger_hits': _validated_hits(row.get('challenger_hits'), 'challenger_hits'),
            'champion_hits': _validated_hits(row.get('champion_hits'), 'champion_hits'),
        }
        for row in rows
    ]
    observed_e_value = float(e_value)
    if not math.isfinite(observed_e_value) or observed_e_value < 0.0:
        raise ValueError('e_value must be finite and non-negative')
    n = len(validated)
    challenger_hits = sum(row['challenger_hits'] for row in validated)
    champion_hits = sum(row['champion_hits'] for row in validated)
    advantage_hits = challenger_hits - champion_hits
    mean_hit_advantage = advantage_hits / n if n else 0.0
    cumulative_regret = champion_hits - challenger_hits
    required_contests = adaptive_min_contests(mean_hit_advantage)

    superior = advantage_hits > 0
    favorable_regret = cumulative_regret < 0
    enough = n >= required_contests
    sequential_evidence = observed_e_value >= MIN_E_VALUE
    eligible = bool(n > 0 and superior and favorable_regret and enough and sequential_evidence)

    blockers: list[str] = []
    if n == 0:
        blockers.append('no_adjudicated_prospective_contests')
    if n > 0 and not superior:
        blockers.append('no_cumulative_superiority')
    if n > 0 and not favorable_regret:
        blockers.append('regret_not_favorable')
    if not enough:
        blockers.append('insufficient_adaptive_sample')
    if not sequential_evidence:
        blockers.append('insufficient_sequential_evidence')

    return {
        'decision': 'PROMOTE_SIGNAL_INTELLIGENCE_CHALLENGER' if eligible else 'KEEP_CHAMPION',
        'eligible': eligible,
        'n': n,
        'challenger_hits': challenger_hits,
        'champion_hits': champion_hits,
        'advantage_hits': advantage_hits,
        'mean_hit_advantage': mean_hit_advantage,
        'cumulative_regret': cumulative_regret,
        'e_value': observed_e_value,
        'inputs_validated': True,
        'base_min_prospective_contests': BASE_MIN_PROSPECTIVE_CONTESTS,
        'required_prospective_contests': required_contests,
        'adaptive_sample_escalated': required_contests > BASE_MIN_PROSPECTIVE_CONTESTS,
        'enough_contests': enough,
        'superior_to_champion': superior,
        'favorable_regret': favorable_regret,
        'sequential_evidence': sequential_evidence,
        'blockers': blockers,
        'reason': ('all promotion gates met' if eligible else
                   'no adjudicated prospective contests' if n == 0 else
                   'prospective promotion conditions not met'),
    }


def policy_snapshot() -> dict[str, Any]:
    return {
        'schema': POLICY_SCHEMA,
        'base_min_prospective_contests': BASE_MIN_PROSPECTIVE_CONTESTS,
        'min_e_value': MIN_E_VALUE,
        'must_beat_champion_cumulatively': True,
        'must_have_favorable_regret': True,
        'adaptive_sample_rule': {
            'mean_hit_advantage_gte_0_50': 20,
            'mean_hit_advantage_gte_0_25': 30,
            'mean_hit_advantage_gte_0_10': 50,
            'mean_hit_advantage_gt_0': 80,
        },
        'promotion_before_evidence_prohibited': True,
        'accepted_hit_domain': [MIN_HITS, MAX_HITS],
        'invalid_or_nonfinite_inputs_rejected': True,
    }
