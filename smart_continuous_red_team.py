from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

import smart_v2_engine as e
from smart_context_regime import ContextRegimeEngine, REGIME_L1_THRESHOLD
from smart_meta_governor import MetaGovernor
from smart_multi_challengers import POLICY_IDS, build_multi_challengers
from smart_signal_agent import SmartSignalAgent
from smart_signal_quality import SignalQualityState
from smart_signal_redundancy_consensus import consensus_penalties
from smart_signal_weights import dynamic_weights
from smart_source_identity import sha256_source_file

SCHEMA = 'SMART_CONTINUOUS_RED_TEAM_1'
REPORT_PATH = Path('SMART_P09_RED_TEAM_LATEST.json')
BASE_SEED = 20260830
BEHAVIORAL_FILES = (
    'smart_v2_engine.py',
    'smart_v2_production.py',
    'smart_signal_quality.py',
    'smart_signal_weights.py',
    'smart_context_regime.py',
    'smart_signal_marginal_utility.py',
    'smart_signal_redundancy_consensus.py',
    'smart_signal_interactions.py',
    'smart_contextual_meta_weights.py',
    'smart_rank_score_calibration.py',
    'smart_multi_challengers.py',
    'smart_meta_governor.py',
    'smart_bounded_online_learning.py',
    'smart_signal_expansion_governance.py',
    'smart_sequential_prospective_proof.py',
    'smart_promotion_gate.py',
    'smart_independent_audit.py',
    'smart_independent_oracle.py',
    'smart_evidence_only_promotion.py',
    'smart_global_integrity.py',
    'smart_signal_agent.py',
    'smart_data_quality_gate.py',
    'smart_learning_activation_gate.py',
    'smart_learning_activation_authority.py',
    'smart_ai_fine_tuning.py',
    'smart_material_deficiency_registry.py',
    'smart_champion_challenger.py',
    'smart_agent_skill_orchestration.py',
    'smart_agent_runtime.py',
    'smart_agent_skill_functional_gate.py',
    'smart_skill_runtime.py',
    'smart_total_integration_gate.py',
    'adjudicate_signal_challenger.py',
)
EXPECTED_SCENARIOS = (
    'iid', 'gradual_drift', 'abrupt_shift', 'false_signal_recovery',
    'missing_corrupt_data', 'redundancy_false_consensus', 'online_anti_ranking',
    'recurring_regimes', 'regime_recovery', 'full_stack_smoke',
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def current_behavior_hashes(root: Path = Path('.')) -> dict[str, str]:
    out = {}
    for name in BEHAVIORAL_FILES:
        p = Path(root) / name
        if not p.is_file():
            raise ValueError(f'missing behavioral file: {name}')
        out[name] = sha256_source_file(p)
    return out


def _uniform_draw(rng: np.random.Generator) -> np.ndarray:
    return np.sort(rng.choice(e.NUMBERS, 6, replace=False)).astype(int)


def _weighted_draw(rng: np.random.Generator, target, weight: float) -> np.ndarray:
    w = np.ones(60, dtype=float)
    w[np.asarray(target, dtype=int) - 1] = float(weight)
    p = w / w.sum()
    return np.sort(rng.choice(e.NUMBERS, 6, replace=False, p=p)).astype(int)


def _disjoint_targets(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    a = np.sort(rng.choice(e.NUMBERS, 6, replace=False))
    rest = np.setdiff1d(e.NUMBERS, a)
    b = np.sort(rng.choice(rest, 6, replace=False))
    return a, b


def _run_engine(draws: list[np.ndarray], boundary: int | None = None) -> dict[str, Any]:
    eng = ContextRegimeEngine()
    before = 0
    first_after = None
    for i, row in enumerate(draws):
        if boundary is not None and i == boundary:
            before = eng.detection_count
        eng.update(row)
        if boundary is not None and i >= boundary and eng.detection_count > before and first_after is None:
            first_after = i
    return {
        'detection_count': int(eng.detection_count),
        'new_detection_after_boundary': None if boundary is None else bool(eng.detection_count > before),
        'first_after_boundary': first_after,
        'delay': None if first_after is None or boundary is None else int(first_after - boundary),
        'active_final': bool(eng.active),
        'final_score': float(eng.last_score),
        'threshold': float(REGIME_L1_THRESHOLD),
    }


def scenario_iid(rounds: int = 30, steps: int = 650) -> dict[str, Any]:
    flagged = 0
    detections = []
    for r in range(rounds):
        rng = np.random.default_rng(BASE_SEED + 1000 + r * 17)
        res = _run_engine([_uniform_draw(rng) for _ in range(steps)])
        flagged += int(res['detection_count'] > 0)
        detections.append(res['detection_count'])
    rate = flagged / rounds
    return {'rounds': rounds, 'false_positive_rate': rate, 'detections': detections,
            'pass': bool(rate <= 0.10), 'criterion': 'IID context false-positive rate <= 10%'}


def scenario_abrupt_shift(rounds: int = 30, block: int = 350) -> dict[str, Any]:
    flags = []; delays = []
    for r in range(rounds):
        rng = np.random.default_rng(BASE_SEED + 2000 + r * 19)
        a, b = _disjoint_targets(rng)
        draws = [_weighted_draw(rng, a, 3.0) for _ in range(block)] + [_weighted_draw(rng, b, 3.0) for _ in range(block)]
        res = _run_engine(draws, block)
        flags.append(bool(res['new_detection_after_boundary']))
        if res['delay'] is not None: delays.append(res['delay'])
    rate = float(np.mean(flags))
    return {'rounds':rounds,'detection_rate':rate,'mean_delay':None if not delays else float(np.mean(delays)),
            'pass':bool(rate >= 0.80),'criterion':'abrupt regime shift detected in >=80% of rounds'}


def scenario_gradual_drift(rounds: int = 30, baseline: int = 300, ramp: int = 400) -> dict[str, Any]:
    flags=[]; delays=[]
    for r in range(rounds):
        rng=np.random.default_rng(BASE_SEED+3000+r*23)
        target=np.sort(rng.choice(e.NUMBERS,6,replace=False))
        draws=[_uniform_draw(rng) for _ in range(baseline)]
        for i in range(ramp):
            weight=1.0+3.0*(i+1)/ramp
            draws.append(_weighted_draw(rng,target,weight))
        res=_run_engine(draws,baseline)
        flags.append(bool(res['new_detection_after_boundary']))
        if res['delay'] is not None: delays.append(res['delay'])
    rate=float(np.mean(flags))
    return {'rounds':rounds,'detection_rate':rate,'mean_delay':None if not delays else float(np.mean(delays)),
            'pass':bool(rate>=0.60),'criterion':'gradual drift detected in >=60% of rounds'}


def scenario_recurring_regimes(rounds: int = 20, block: int = 280) -> dict[str, Any]:
    good=0; counts=[]
    for r in range(rounds):
        rng=np.random.default_rng(BASE_SEED+4000+r*29)
        a,b=_disjoint_targets(rng)
        draws=[]
        for target in (a,b,a,b):
            draws.extend(_weighted_draw(rng,target,3.0) for _ in range(block))
        res=_run_engine(draws)
        counts.append(res['detection_count'])
        good += int(res['detection_count']>=2)
    rate=good/rounds
    return {'rounds':rounds,'rate_at_least_two_detections':rate,'detection_counts':counts,
            'pass':bool(rate>=0.70),'criterion':'recurring regimes produce >=2 detections in >=70% of rounds'}


def scenario_regime_recovery(rounds: int = 20) -> dict[str, Any]:
    recovered=0; final_scores=[]
    for r in range(rounds):
        rng=np.random.default_rng(BASE_SEED+5000+r*31)
        target=np.sort(rng.choice(e.NUMBERS,6,replace=False))
        draws=[_weighted_draw(rng,target,3.5) for _ in range(350)] + [_uniform_draw(rng) for _ in range(650)]
        res=_run_engine(draws)
        final_scores.append(res['final_score'])
        recovered += int((not res['active_final']) and res['final_score'] < REGIME_L1_THRESHOLD)
    rate=recovered/rounds
    return {'rounds':rounds,'recovery_rate':rate,'mean_final_score':float(np.mean(final_scores)),
            'pass':bool(rate>=0.80),'criterion':'context returns inactive after signal disappears in >=80%'}


def _signal_weight(states: dict[str, SignalQualityState]) -> dict[str,float]:
    metrics={n:s.metrics(1.0) for n,s in states.items()}
    fam={n:s.family for n,s in states.items()}
    w,_=dynamic_weights(metrics,fam)
    return w


def scenario_false_signal_and_recovery() -> dict[str, Any]:
    states={'good':SignalQualityState('good','freq'),'false':SignalQualityState('false','ewma'),
            'neutral':SignalQualityState('neutral','neutral')}
    for _ in range(120):
        states['good'].update(2); states['false'].update(0); states['neutral'].update(1)
    degraded=_signal_weight(states)
    for _ in range(180):
        states['good'].update(1); states['false'].update(2); states['neutral'].update(1)
    recovered=_signal_weight(states)
    ok=degraded['false'] < degraded['good'] and recovered['false'] > degraded['false'] and recovered['false'] >= 0.30
    return {'degraded_weights':degraded,'recovered_weights':recovered,'pass':bool(ok),
            'criterion':'false signal is penalized after failure and can recover after sustained real utility'}


def scenario_redundancy_false_consensus() -> dict[str, Any]:
    x=np.linspace(0.0,1.0,60)
    scores={f'clone{i}':x.copy() for i in range(4)}
    scores['independent']=np.roll(x[::-1],11)
    base={n:0.2 for n in scores}
    penalties,audit=consensus_penalties(scores,base,0.90)
    clone_penalty=float(np.mean([penalties[f'clone{i}'] for i in range(4)]))
    independent=float(penalties['independent'])
    ok=clone_penalty < independent and independent >= 0.5
    return {'clone_mean_penalty':clone_penalty,'independent_penalty':independent,'clusters':audit['clusters'],
            'pass':bool(ok),'criterion':'cloned consensus must be penalized more than independent information'}


def scenario_missing_and_corrupt_data() -> dict[str, Any]:
    checks={}
    try:
        consensus_penalties({'x':np.zeros(59)},None,0.90); checks['short_signal_rejected']=False
    except ValueError: checks['short_signal_rejected']=True
    try:
        consensus_penalties({'x':np.r_[np.zeros(59),np.nan]},None,0.90); checks['nonfinite_signal_rejected']=False
    except ValueError: checks['nonfinite_signal_rejected']=True
    try:
        ContextRegimeEngine().update([1,1,2,3,4,5]); checks['invalid_draw_rejected']=False
    except ValueError: checks['invalid_draw_rejected']=True
    try:
        SmartSignalAgent(start=10).replay_history(np.zeros((11,6),dtype=int),np.arange(1,10)); checks['length_mismatch_rejected']=False
    except ValueError: checks['length_mismatch_rejected']=True
    return {'checks':checks,'pass':bool(all(checks.values())),'criterion':'missing/corrupt inputs fail closed'}


def _red_team_multi() -> dict[str,Any]:
    names=['freq25','freq100','freq1000','freq_global','ewma10','ewma250']
    x=np.linspace(0,1,60)
    scores={'freq25':x,'freq100':np.roll(x,3),'freq1000':np.roll(x,8),'freq_global':np.roll(x,13),'ewma10':x[::-1],'ewma250':np.roll(x[::-1],5)}
    weights={'freq25':.08,'freq100':.12,'freq1000':.30,'freq_global':.20,'ewma10':.12,'ewma250':.18}
    fam={n:'freq' if n.startswith('freq') else 'ewma' for n in names}
    metrics={n:{'regime_context':1.0} for n in names}
    red={'penalties':{n:1.0 for n in names}}
    return build_multi_challengers(scores,weights,metrics,fam,red,{'active':False})


def scenario_online_anti_ranking(steps: int = 100) -> dict[str,Any]:
    multi=_red_team_multi(); gov=MetaGovernor(); selected_hits=[]; oracle=[]; switches=0; prev=None
    for _ in range(steps):
        sel=gov.select(multi); chosen=sel['selected_policy']
        if prev is not None and chosen!=prev: switches+=1
        prev=chosen
        forbidden=set(sel['selected_top6'])
        candidates=[]
        for pid in POLICY_IDS:
            if pid==chosen: continue
            for n in multi['policies'][pid]['top6']:
                if n not in forbidden and n not in candidates: candidates.append(int(n))
        for n in range(1,61):
            if n not in forbidden and n not in candidates: candidates.append(n)
        actual=set(candidates[:6])
        hits={pid:len(set(multi['policies'][pid]['top6'])&actual) for pid in POLICY_IDS}
        selected_hits.append(hits[chosen]); oracle.append(max(hits.values()))
        gov.update(hits,chosen)
    ok=max(selected_hits)==0 and all(x>=0 for x in oracle) and gov.observations==steps
    return {'steps':steps,'selected_hits_total':int(sum(selected_hits)),'selected_hits_max':int(max(selected_hits)),
            'posthoc_oracle_hits_total':int(sum(oracle)),'switches':switches,'final_state':gov.state(),
            'pass':bool(ok),'criterion':'adaptive anti-ranking adversary cannot trigger post-result reselection or invalid state'}


def scenario_full_stack_smoke(rounds: int = 3, n: int = 260, start: int = 120) -> dict[str,Any]:
    rows=[]; ok=True
    for r in range(rounds):
        rng=np.random.default_rng(BASE_SEED+7000+r*37)
        draws=np.array([_uniform_draw(rng) for _ in range(n)],dtype=int); contests=np.arange(1,n+1)
        pred,back=SmartSignalAgent(start=start).predict_next(draws,contests,target_contest=n+1)
        finite=all(math.isfinite(float(v)) for v in pred.weights.values())
        row={'round':r+1,'oos':len(back['rows']),'top6':pred.top6,'policy_count':pred.multi_challengers['policy_count'],
             'meta_policy':pred.meta_governor['selected_policy'],'weights_finite':finite,'weight_sum':float(sum(pred.weights.values()))}
        row['pass']=bool(len(pred.top6)==6 and pred.multi_challengers['policy_count']==5 and pred.meta_governor['selected_policy'] in POLICY_IDS and finite and abs(row['weight_sum']-1.0)<1e-9)
        ok &= row['pass']; rows.append(row)
    return {'rounds':rounds,'records':rows,'pass':bool(ok),'criterion':'full P01-P08 stack remains finite and structurally valid under IID smoke'}


def run_suite(root: Path = Path('.')) -> dict[str,Any]:
    scenarios={
        'iid':scenario_iid(),
        'gradual_drift':scenario_gradual_drift(),
        'abrupt_shift':scenario_abrupt_shift(),
        'false_signal_recovery':scenario_false_signal_and_recovery(),
        'missing_corrupt_data':scenario_missing_and_corrupt_data(),
        'redundancy_false_consensus':scenario_redundancy_false_consensus(),
        'online_anti_ranking':scenario_online_anti_ranking(),
        'recurring_regimes':scenario_recurring_regimes(),
        'regime_recovery':scenario_regime_recovery(),
        'full_stack_smoke':scenario_full_stack_smoke(),
    }
    checks={name:bool(row['pass']) for name,row in scenarios.items()}
    report={'schema':SCHEMA,'status':'PASS' if all(checks.values()) else 'FAIL','all_checks_pass':all(checks.values()),
            'checks':checks,'failed':[k for k,v in checks.items() if not v],'base_seed':BASE_SEED,
            'behavioral_hashes':current_behavior_hashes(root),'red_team_module_sha256':sha256_file(Path(root)/Path(__file__).name),
            'continuous_policy':'any behavioral hash change makes this report stale and blocks future freeze once the 15-point gate opens',
            'prospective_predictive_claim':False,'scenarios':scenarios}
    report['sha256']=sha256_json(report)
    return report


def _validate_report_document(report: dict[str, Any]) -> None:
    if not isinstance(report, dict):
        raise ValueError('continuous Red Team report must be an object')
    if report.get('schema') != SCHEMA or report.get('status') != 'PASS' or report.get('all_checks_pass') is not True:
        raise ValueError('continuous Red Team report is not passing')
    observed = report.get('sha256')
    if not isinstance(observed, str) or len(observed) != 64:
        raise ValueError('continuous Red Team report self-hash missing')
    canonical = dict(report); canonical.pop('sha256', None)
    if observed.lower() != sha256_json(canonical):
        raise ValueError('continuous Red Team report self-hash mismatch')
    scenarios = report.get('scenarios')
    checks = report.get('checks')
    failed = report.get('failed')
    if not isinstance(scenarios, dict) or set(scenarios) != set(EXPECTED_SCENARIOS):
        raise ValueError('continuous Red Team scenario set mismatch')
    if not isinstance(checks, dict) or set(checks) != set(EXPECTED_SCENARIOS):
        raise ValueError('continuous Red Team checks set mismatch')
    recomputed = {}
    for name in EXPECTED_SCENARIOS:
        row = scenarios.get(name)
        if not isinstance(row, dict) or not isinstance(row.get('pass'), bool):
            raise ValueError(f'continuous Red Team scenario invalid: {name}')
        recomputed[name] = bool(row['pass'])
    if checks != recomputed:
        raise ValueError('continuous Red Team checks do not match scenarios')
    expected_failed = [name for name in EXPECTED_SCENARIOS if not recomputed[name]]
    if failed != expected_failed:
        raise ValueError('continuous Red Team failed list mismatch')
    if not all(recomputed.values()):
        raise ValueError('continuous Red Team report contains a failed scenario')


def write_report(report: dict[str,Any], path: Path = REPORT_PATH) -> str:
    _validate_report_document(report)
    Path(path).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return sha256_file(Path(path))


def verify_latest_report(path: Path = REPORT_PATH, root: Path = Path('.')) -> dict[str,Any]:
    p=Path(path)
    if not p.is_file(): raise ValueError('continuous Red Team report missing')
    report=json.loads(p.read_text(encoding='utf-8'))
    _validate_report_document(report)
    current=current_behavior_hashes(root)
    if report.get('behavioral_hashes')!=current:
        raise ValueError('continuous Red Team report is stale for current behavioral hashes')
    if report.get('red_team_module_sha256')!=sha256_file(Path(root)/Path(__file__).name):
        raise ValueError('continuous Red Team module hash mismatch')
    return {'status':'PASS','report_sha256':sha256_file(p),'behavioral_hashes_current':True,
            'self_hash_valid':True,'scenario_count':len(report.get('scenarios',{}))}


def main() -> None:
    report=run_suite(Path('.'))
    h=write_report(report,REPORT_PATH)
    print(json.dumps({'status':report['status'],'failed':report['failed'],'checks':report['checks'],'report_sha256':h,
                      'scenario_count':len(report['scenarios'])},ensure_ascii=False,indent=2))
    if not report['all_checks_pass']:
        raise SystemExit(1)


if __name__=='__main__':
    main()


