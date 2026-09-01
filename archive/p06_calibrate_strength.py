from pathlib import Path
import sys, json, hashlib
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import smart_v2_engine as e
from smart_signal_agent import SmartSignalAgent
from smart_rank_score_calibration import UNIFORM_PROB

DATA = ROOT / 'Mega-Sena_through_3050.xlsx'
draws, contests = e.load_draws(DATA)
mask = contests <= 2200
d = draws[mask]
c = contests[mask]
agent = SmartSignalAgent(start=1000, calibration_strength=1.0)
pred, back = agent.predict_next(d, c, target_contest=2201)
lookup = {int(cc): set(map(int, dd)) for cc, dd in zip(c, d)}
candidates = [0.0, 0.25, 0.5, 0.75, 1.0]
res = {}
for strength in candidates:
    total = 0.0
    raw_total = 0.0
    for row in back['rows']:
        ranking = [int(x) for x in row['ranking60_before_result']]
        audit = row['rank_calibration_before_result']
        iso = np.asarray(audit['calibrated_probability_by_rank'], float)
        raw = np.asarray(audit['raw_posterior_by_rank'], float)
        p = UNIFORM_PROB + strength * (iso - UNIFORM_PROB)
        actual = lookup[int(row['contest'])]
        y = np.array([1.0 if n in actual else 0.0 for n in ranking])
        total += float(np.mean((p - y) ** 2))
        raw_total += float(np.mean((raw - y) ** 2))
    res[str(strength)] = {
        'strength': strength,
        'n': len(back['rows']),
        'mean_brier': total / len(back['rows']),
        'raw_unconstrained_posterior_mean_brier': raw_total / len(back['rows']),
    }
selected = min(candidates, key=lambda x: (res[str(x)]['mean_brier'], x))
state = agent.rank_calibrator.state()
proof = {
    'schema': 'SMART_P06_STRENGTH_CALIBRATION_1',
    'point_id': 'P06_RANK_SCORE_CALIBRATION',
    'data_scope': 'CONTESTS_1_TO_2200_ONLY',
    'oos_scope': '1001_TO_2200',
    'candidate_strengths': candidates,
    'selection_rule': 'minimum prequential Brier score; tie chooses lower strength',
    'selected_strength': selected,
    'holdout_2201_plus_accessed_for_selection': False,
    'uniform_brier': 0.09,
    'candidates': res,
    'final_rank_state_calibration_scope': {
        'observations': state['observations'],
        'raw_monotonic_violations': state['monotonic_violations_before_isotonic'],
        'monotonic_after_isotonic': state['monotonic_after_isotonic'],
        'probability_sum': state['probability_sum'],
        'rank1_probability_full_strength': state['calibrated_probability_by_rank'][0],
        'rank60_probability_full_strength': state['calibrated_probability_by_rank'][-1],
    },
    'anti_overfit': {
        'future_leakage': False,
        'final_holdout_not_used': True,
        'ranking_or_weights_changed_by_calibration': False,
    },
    'hashes': {
        'data': hashlib.sha256(DATA.read_bytes()).hexdigest(),
        'module': hashlib.sha256((ROOT / 'smart_rank_score_calibration.py').read_bytes()).hexdigest(),
        'agent': hashlib.sha256((ROOT / 'smart_signal_agent.py').read_bytes()).hexdigest(),
    },
}
raw_bytes = json.dumps(proof, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
proof['sha256'] = hashlib.sha256(raw_bytes).hexdigest()
out = ROOT / 'SMART_P06_STRENGTH_CALIBRATION.json'
out.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(proof, ensure_ascii=False, indent=2))
