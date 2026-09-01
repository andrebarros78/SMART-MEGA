from __future__ import annotations

import hashlib
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

import smart_v2_engine as e
from smart_context_regime import CALIBRATION_ID, REGIME_L1_THRESHOLD
from smart_signal_agent import SmartSignalAgent
from smart_signal_50_round_simulation import build_scenario

VAR_ONE = 6 * (6 / 60) * (1 - 6 / 60) * (54 / 59)
SCENARIOS = ['iid_null', 'persistent_bias', 'regime_shift', 'signal_vanishes', 'alternating_adversarial']
ROUNDS_PER_SCENARIO = 400
START = 150
STEPS = 450
WORKERS = min(8, os.cpu_count() or 1)
SOURCE_FILES = [
    'smart_v2_engine.py', 'smart_v2_production.py', 'smart_signal_agent.py',
    'smart_signal_quality.py', 'smart_signal_weights.py', 'smart_context_regime.py',
    'freeze_next_research.py', 'smart_champion_challenger.py', 'adjudicate_signal_challenger.py'
]
EXPECTED_CHAMPION_ENGINE_SHA256 = 'bff5d8beb464b94049d5933c9d6bee157f445aa9b6d15ebabcf42a848c4412d8'
ORIGINAL_CHAMPION_PRODUCTION_SHA256 = '068f2ec120791795d3c64d7a9414344d2825c799e5f49f8ced65aa85d6afa6e8'
EXPECTED_AUDITED_PRODUCTION_SHA256 = 'f43e0976f69e882dda19fb8a89e6e03e73aa898cd25a704d115405fa362e1156'


def sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def zscore(excess: float, n: int) -> float:
    return float(excess / math.sqrt(max(1e-12, n * VAR_ONE)))


def run_round(job):
    kind, seed = job
    draws = build_scenario(kind, seed, steps=STEPS)
    contests = np.arange(1, len(draws) + 1)
    agent = SmartSignalAgent(start=START)
    back = agent.replay_history(draws, contests)
    champion = e.walk_forward(draws, contests, start=START)
    rows = back['rows']
    n = len(rows)
    max_expert = max(max(r['weights_before_result'].values()) for r in rows)
    max_family = 0.0
    for r in rows:
        fw = {'freq': 0.0, 'ewma': 0.0}
        for name, w in r['weights_before_result'].items():
            fw[e.family_of(name)] += w
        max_family = max(max_family, max(fw.values()))
    context = agent.context_engine.metrics()
    values = [back['total_hits'], champion.total_hits, back['excess_hits'], max_expert, max_family,
              context['l1_score'], context['detection_count']]
    return {
        'scenario': kind,
        'seed': int(seed),
        'predictions': n,
        'challenger_hits': int(back['total_hits']),
        'champion_hits': int(champion.total_hits),
        'uniform_expected': float(back['uniform_expected_hits']),
        'challenger_excess': float(back['excess_hits']),
        'challenger_z': zscore(back['excess_hits'], n),
        'regret_vs_champion': int(champion.total_hits - back['total_hits']),
        'regret_per_prediction': float((champion.total_hits - back['total_hits']) / n),
        'context_detected': bool(context['detection_count'] > 0),
        'context_detection_count': int(context['detection_count']),
        'context_last_score': float(context['l1_score']),
        'max_expert_weight': float(max_expert),
        'max_family_weight': float(max_family),
        'finite': all(math.isfinite(float(v)) for v in values),
    }


def summarize(rows):
    out = {}
    for kind in SCENARIOS:
        rs = [r for r in rows if r['scenario'] == kind]
        total_predictions = sum(r['predictions'] for r in rs)
        total_regret = sum(r['regret_vs_champion'] for r in rs)
        out[kind] = {
            'rounds': len(rs),
            'predictions': total_predictions,
            'mean_challenger_hits': float(np.mean([r['challenger_hits'] for r in rs])),
            'mean_champion_hits': float(np.mean([r['champion_hits'] for r in rs])),
            'total_regret_vs_champion': int(total_regret),
            'mean_regret_per_prediction': float(total_regret / total_predictions),
            'mean_z': float(np.mean([r['challenger_z'] for r in rs])),
            'min_z': float(np.min([r['challenger_z'] for r in rs])),
            'max_z': float(np.max([r['challenger_z'] for r in rs])),
            'rate_z_ge_2': float(np.mean([r['challenger_z'] >= 2.0 for r in rs])),
            'context_detection_rate': float(np.mean([r['context_detected'] for r in rs])),
            'mean_context_detections': float(np.mean([r['context_detection_count'] for r in rs])),
            'max_expert_weight': float(np.max([r['max_expert_weight'] for r in rs])),
            'max_family_weight': float(np.max([r['max_family_weight'] for r in rs])),
            'all_finite': all(r['finite'] for r in rs),
        }
    return out


def main():
    source_hashes_before = {f: sha256(f) for f in SOURCE_FILES}
    jobs = []
    bases = {
        'iid_null': 1_000_000,
        'persistent_bias': 1_100_000,
        'regime_shift': 1_200_000,
        'signal_vanishes': 1_300_000,
        'alternating_adversarial': 1_400_000,
    }
    for kind in SCENARIOS:
        for i in range(ROUNDS_PER_SCENARIO):
            jobs.append((kind, bases[kind] + i))

    rows = []
    completed = 0
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        future_map = {ex.submit(run_round, job): job for job in jobs}
        for fut in as_completed(future_map):
            rows.append(fut.result())
            completed += 1
            if completed % 50 == 0 or completed == len(jobs):
                Path('SMART_SIGNAL_2000_PROGRESS.json').write_text(
                    json.dumps({'completed': completed, 'total': len(jobs), 'percent': completed / len(jobs)}, indent=2),
                    encoding='utf-8'
                )

    rows.sort(key=lambda r: (SCENARIOS.index(r['scenario']), r['seed']))
    summary = summarize(rows)
    total_predictions = sum(r['predictions'] for r in rows)
    total_regret = sum(r['regret_vs_champion'] for r in rows)

    # Re-run one frozen seed per scenario to prove deterministic replay.
    determinism = []
    for kind in SCENARIOS:
        seed = bases[kind]
        original = next(r for r in rows if r['scenario'] == kind and r['seed'] == seed)
        repeated = run_round((kind, seed))
        keys = ['challenger_hits', 'champion_hits', 'challenger_excess', 'challenger_z',
                'regret_vs_champion', 'context_detected', 'context_detection_count',
                'max_expert_weight', 'max_family_weight']
        determinism.append({'scenario': kind, 'seed': seed,
                            'identical': all(original[k] == repeated[k] for k in keys)})

    source_hashes_after = {f: sha256(f) for f in SOURCE_FILES}
    source_hashes_unchanged = source_hashes_before == source_hashes_after
    max_abs_scenario_regret = max(abs(summary[k]['mean_regret_per_prediction']) for k in SCENARIOS)

    checks = {
        'exactly_2000_rounds': len(rows) == 2000,
        'four_hundred_per_scenario': all(summary[k]['rounds'] == 400 for k in SCENARIOS),
        'all_metrics_finite': all(r['finite'] for r in rows),
        'expert_cap_respected': max(r['max_expert_weight'] for r in rows) <= 0.4200001,
        'family_cap_respected': max(r['max_family_weight'] for r in rows) <= 0.7000001,
        'iid_predictive_false_positive_rate_le_0_10': summary['iid_null']['rate_z_ge_2'] <= 0.10,
        'iid_context_false_positive_rate_le_0_10': summary['iid_null']['context_detection_rate'] <= 0.10,
        'regime_context_detection_rate_ge_0_80': summary['regime_shift']['context_detection_rate'] >= 0.80,
        'vanishing_context_detection_rate_ge_0_80': summary['signal_vanishes']['context_detection_rate'] >= 0.80,
        'persistent_bias_predictive_detection_ge_0_80': summary['persistent_bias']['rate_z_ge_2'] >= 0.80,
        'regime_predictive_detection_ge_0_80': summary['regime_shift']['rate_z_ge_2'] >= 0.80,
        'synthetic_alignment_max_abs_regret_per_prediction_le_0_03': max_abs_scenario_regret <= 0.03,
        'deterministic_replay': all(x['identical'] for x in determinism),
        'source_hashes_unchanged_during_validation': source_hashes_unchanged,
        'champion_engine_unchanged_since_preintegration': source_hashes_after['smart_v2_engine.py'] == EXPECTED_CHAMPION_ENGINE_SHA256,
        'production_governor_matches_audited_fix': source_hashes_after['smart_v2_production.py'] == EXPECTED_AUDITED_PRODUCTION_SHA256,
    }

    report = {
        'schema': 'SMART_SIGNAL_2000_SIMULATION_1',
        'rounds_total': len(rows),
        'workers': WORKERS,
        'steps_per_round': STEPS,
        'walk_forward_start': START,
        'predictions_per_round': STEPS - START,
        'total_predictions': total_predictions,
        'calibration_frozen_before_validation': True,
        'context_calibration_id': CALIBRATION_ID,
        'context_threshold': REGIME_L1_THRESHOLD,
        'validation_seed_sets': {k: f"{bases[k]}..{bases[k]+ROUNDS_PER_SCENARIO-1}" for k in SCENARIOS},
        'summary': summary,
        'global': {
            'total_challenger_hits': int(sum(r['challenger_hits'] for r in rows)),
            'total_champion_hits': int(sum(r['champion_hits'] for r in rows)),
            'total_regret_vs_champion': int(total_regret),
            'mean_regret_per_prediction': float(total_regret / total_predictions),
            'max_abs_scenario_regret_per_prediction': float(max_abs_scenario_regret),
        },
        'determinism': determinism,
        'checks': checks,
        'passed': all(checks.values()),
        'source_hashes_before': source_hashes_before,
        'source_hashes_after': source_hashes_after,
        'governance_audit': {
            'original_production_sha256': ORIGINAL_CHAMPION_PRODUCTION_SHA256,
            'audited_production_sha256': EXPECTED_AUDITED_PRODUCTION_SHA256,
            'change_reason': 'ledger contest-order validation corrected; predictive Champion engine unchanged',
            'predictive_champion_engine_sha256': EXPECTED_CHAMPION_ENGINE_SHA256,
        },
        'guardrails': {
            'synthetic_engineering_evidence_only': True,
            'prospective_predictive_claim': False,
            'no_parameter_change_after_validation_started': source_hashes_unchanged,
            'final_validation_seeds_disjoint_from_calibration': True,
        },
        'rounds': rows,
    }
    Path('SMART_SIGNAL_2000_SIMULATION.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    Path('SMART_SIGNAL_2000_SIMULATION.done').write_text('PASS' if report['passed'] else 'FAIL', encoding='utf-8')
    print(json.dumps({'rounds_total': len(rows), 'summary': summary, 'global': report['global'], 'checks': checks, 'passed': report['passed']}, indent=2))


if __name__ == '__main__':
    main()

