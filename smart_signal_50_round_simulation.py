from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

import smart_v2_engine as e
from smart_signal_agent import SmartSignalAgent

VAR_ONE = 6 * (6 / 60) * (1 - 6 / 60) * (54 / 59)


def zscore(excess: float, n: int) -> float:
    return float(excess / math.sqrt(max(1e-12, n * VAR_ONE)))


def gen_uniform(rng, steps):
    return np.array([np.sort(rng.choice(e.NUMBERS, 6, replace=False)) for _ in range(steps)], dtype=int)


def gen_weighted(rng, steps, weights):
    p = np.asarray(weights, dtype=float)
    p /= p.sum()
    return np.array([np.sort(rng.choice(e.NUMBERS, 6, replace=False, p=p)) for _ in range(steps)], dtype=int)


def build_scenario(kind: str, seed: int, steps: int = 450):
    rng = np.random.default_rng(seed)
    w1 = np.ones(60); w1[:6] = 4.0
    w2 = np.ones(60); w2[30:36] = 4.0
    if kind == 'iid_null':
        return gen_uniform(rng, steps)
    if kind == 'persistent_bias':
        return gen_weighted(rng, steps, w1)
    if kind == 'regime_shift':
        return np.vstack([gen_weighted(rng, steps // 2, w1), gen_weighted(rng, steps - steps // 2, w2)])
    if kind == 'signal_vanishes':
        return np.vstack([gen_weighted(rng, steps // 2, w1), gen_uniform(rng, steps - steps // 2)])
    if kind == 'alternating_adversarial':
        rows = []
        for i in range(steps):
            rows.append(gen_weighted(rng, 1, w1 if i % 2 == 0 else w2)[0])
        return np.asarray(rows, dtype=int)
    raise ValueError(kind)


def run_round(kind: str, seed: int, start: int = 150):
    draws = build_scenario(kind, seed)
    contests = np.arange(1, len(draws) + 1)
    agent = SmartSignalAgent(start=start)
    back = agent.replay_history(draws, contests)
    champion = e.walk_forward(draws, contests, start=start)
    n = len(draws) - start
    rows = back['rows']
    max_expert = max(max(r['weights_before_result'].values()) for r in rows)
    max_family = 0.0
    for r in rows:
        fw = {'freq': 0.0, 'ewma': 0.0}
        for name, w in r['weights_before_result'].items():
            fw[e.family_of(name)] += w
        max_family = max(max_family, max(fw.values()))
    drift_count = sum(s.performance_drift_count + s.profile_drift_count for s in agent.states.values())
    return {
        'scenario': kind,
        'seed': seed,
        'challenger_hits': back['total_hits'],
        'champion_hits': champion.total_hits,
        'uniform_expected': back['uniform_expected_hits'],
        'challenger_excess': back['excess_hits'],
        'challenger_z': zscore(back['excess_hits'], n),
        'regret_vs_champion': champion.total_hits - back['total_hits'],
        'drift_count_total': drift_count,
        'drift_detected': drift_count > 0,
        'max_expert_weight': max_expert,
        'max_family_weight': max_family,
        'finite': all(math.isfinite(float(x)) for x in [back['total_hits'], champion.total_hits, back['excess_hits'], max_expert, max_family]),
    }


def main():
    scenarios = ['iid_null', 'persistent_bias', 'regime_shift', 'signal_vanishes', 'alternating_adversarial']
    rounds = []
    for sidx, kind in enumerate(scenarios):
        for i in range(10):
            rounds.append(run_round(kind, seed=2026082800 + sidx * 100 + i))

    summary = {}
    for kind in scenarios:
        rs = [r for r in rounds if r['scenario'] == kind]
        summary[kind] = {
            'rounds': len(rs),
            'mean_challenger_hits': float(np.mean([r['challenger_hits'] for r in rs])),
            'mean_champion_hits': float(np.mean([r['champion_hits'] for r in rs])),
            'mean_regret_vs_champion': float(np.mean([r['regret_vs_champion'] for r in rs])),
            'mean_z': float(np.mean([r['challenger_z'] for r in rs])),
            'min_z': float(np.min([r['challenger_z'] for r in rs])),
            'max_z': float(np.max([r['challenger_z'] for r in rs])),
            'rate_z_ge_2': float(np.mean([r['challenger_z'] >= 2.0 for r in rs])),
            'drift_detection_rate': float(np.mean([r['drift_detected'] for r in rs])),
            'max_expert_weight': float(np.max([r['max_expert_weight'] for r in rs])),
            'max_family_weight': float(np.max([r['max_family_weight'] for r in rs])),
            'all_finite': all(r['finite'] for r in rs),
        }

    checks = {
        'exactly_50_rounds': len(rounds) == 50,
        'ten_per_scenario': all(summary[k]['rounds'] == 10 for k in scenarios),
        'all_metrics_finite': all(r['finite'] for r in rounds),
        'expert_cap_respected': max(r['max_expert_weight'] for r in rounds) <= 0.4200001,
        'family_cap_respected': max(r['max_family_weight'] for r in rounds) <= 0.7000001,
        'iid_false_positive_rate_le_0_10': summary['iid_null']['rate_z_ge_2'] <= 0.10,
        'persistent_bias_detection_rate_ge_0_80': summary['persistent_bias']['rate_z_ge_2'] >= 0.80,
        'regime_shift_detection_rate_ge_0_80': summary['regime_shift']['rate_z_ge_2'] >= 0.80,
    }
    report = {
        'schema': 'SMART_SIGNAL_50_ROUND_SIMULATION_1',
        'rounds_total': len(rounds),
        'scenarios': summary,
        'checks': checks,
        'passed': all(checks.values()),
        'guardrails': {
            'synthetic_engineering_evidence_only': True,
            'prospective_predictive_claim': False,
            'hyperparameter_selection_from_test_results_prohibited': True,
        },
        'rounds': rounds,
    }
    Path('SMART_SIGNAL_50_ROUND_SIMULATION.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'rounds_total': len(rounds), 'scenarios': summary, 'checks': checks, 'passed': report['passed']},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

