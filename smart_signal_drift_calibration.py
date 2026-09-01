from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from smart_signal_agent import SmartSignalAgent
from smart_signal_50_round_simulation import build_scenario


def one(job):
    kind, seed = job
    draws = build_scenario(kind, seed, steps=450)
    contests = np.arange(1, len(draws) + 1)
    agent = SmartSignalAgent(start=150)
    agent.replay_history(draws, contests)
    profile = sum(s.profile_drift_count for s in agent.states.values())
    perf = sum(s.performance_drift_count for s in agent.states.values())
    return {'kind': kind, 'seed': seed, 'profile_drift_count': profile, 'performance_drift_count': perf,
            'profile_detected': profile > 0, 'performance_detected': perf > 0}


def main():
    jobs = []
    for i in range(100):
        jobs.append(('iid_null', 811000 + i))
        jobs.append(('regime_shift', 822000 + i))
    workers = min(8, os.cpu_count() or 1)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(one, jobs, chunksize=2))
    out = {}
    for kind in ('iid_null', 'regime_shift'):
        rs = [r for r in rows if r['kind'] == kind]
        out[kind] = {
            'rounds': len(rs),
            'profile_detection_rate': float(np.mean([r['profile_detected'] for r in rs])),
            'performance_detection_rate': float(np.mean([r['performance_detected'] for r in rs])),
            'mean_profile_drift_count': float(np.mean([r['profile_drift_count'] for r in rs])),
            'max_profile_drift_count': int(max(r['profile_drift_count'] for r in rs)),
        }
    checks = {
        'iid_profile_false_positive_rate_le_0_10': out['iid_null']['profile_detection_rate'] <= 0.10,
        'regime_profile_detection_rate_ge_0_80': out['regime_shift']['profile_detection_rate'] >= 0.80,
        'exactly_200_rounds': len(rows) == 200,
    }
    report = {'schema': 'SMART_SIGNAL_DRIFT_CALIBRATION_1', 'workers': workers, 'seed_sets': {'iid':'811000..811099','regime':'822000..822099'},
              'summary': out, 'checks': checks, 'passed': all(checks.values()), 'rows': rows,
              'note': 'calibration seeds are disjoint from final 2000 validation seeds'}
    Path('SMART_SIGNAL_DRIFT_CALIBRATION.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    Path('SMART_SIGNAL_DRIFT_CALIBRATION.done').write_text('PASS' if report['passed'] else 'FAIL', encoding='utf-8')


if __name__ == '__main__':
    main()
