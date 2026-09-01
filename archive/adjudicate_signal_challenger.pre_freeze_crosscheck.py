from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import smart_v2_engine as e
from smart_champion_challenger import E_BET_LAMBDA, active_freeze, load_ledger, paired_events, promotion_status, sha256, write_ledger
from smart_signal_attribution import ATTRIBUTION_SCHEMA, analyze_attribution
from smart_signal_marginal_utility import MARGINAL_UTILITY_SCHEMA, analyze_marginal_utility_snapshot
from smart_signal_interactions import SCHEMA as INTERACTION_SCHEMA, analyze_snapshot as analyze_interaction_snapshot
from smart_multi_challengers import POLICY_IDS as MULTI_POLICY_IDS, SCHEMA as MULTI_SCHEMA, sha256_json as multi_sha256_json
from smart_meta_governor import SCHEMA as META_GOVERNOR_SCHEMA, sha256_json as meta_governor_sha256_json
from smart_rank_score_calibration import SCHEMA as RANK_CALIBRATION_SCHEMA, UNIFORM_PROB, brier_score, sha256_json as rank_calibration_sha256_json


def _next_e_value(ledger: dict, challenger_hits: int, champion_hits: int) -> float:
    pairs = paired_events(ledger)
    previous = float(pairs[-1][2].get('e_value_after', 1.0)) if pairs else 1.0
    x = (float(challenger_hits) - float(champion_hits)) / 6.0
    factor = 1.0 + E_BET_LAMBDA * x
    if factor <= 0:
        raise ValueError('invalid e-process factor')
    return previous * factor





def _meta_governor_events(ledger: dict, target: int) -> list[dict]:
    return [ev for ev in ledger.get('events', []) if ev.get('event_type') == 'META_GOVERNOR' and int(ev.get('target_contest', -1)) == int(target)]

def _build_meta_governor_event(fr: dict, actual: list[int], target: int) -> dict | None:
    frozen = fr.get('snapshot', {}).get('meta_governor')
    multi = fr.get('snapshot', {}).get('multi_challengers')
    if frozen is None:
        return None
    if multi is None:
        raise ValueError('meta-governor freeze requires P07 multi-challengers')
    if frozen.get('schema') != META_GOVERNOR_SCHEMA:
        raise ValueError('invalid frozen meta-governor snapshot')
    selected = str(frozen.get('selected_policy', ''))
    if selected not in MULTI_POLICY_IDS:
        raise ValueError('invalid frozen meta-governor selected policy')
    policies = multi.get('policies', {})
    if set(policies) != set(MULTI_POLICY_IDS):
        raise ValueError('meta-governor requires complete frozen P07 policies')
    frozen_top6 = [int(x) for x in frozen.get('selected_top6', [])]
    policy_top6 = [int(x) for x in policies[selected].get('top6', [])]
    if frozen_top6 != policy_top6:
        raise ValueError('frozen meta-governor top6 must match selected P07 policy')
    actual_set = set(int(x) for x in actual)
    policy_hits = {pid: len(set(int(x) for x in policies[pid]['top6']) & actual_set) for pid in MULTI_POLICY_IDS}
    analysis = {
        'schema': 'SMART_META_GOVERNOR_ADJUDICATION_1',
        'selected_policy_before_result': selected,
        'selected_top6_before_result': frozen_top6,
        'selected_hits': int(policy_hits[selected]),
        'policy_hits': policy_hits,
        'best_post_result_hits': int(max(policy_hits.values())),
        'best_post_result_policies': [p for p in MULTI_POLICY_IDS if policy_hits[p] == max(policy_hits.values())],
        'post_result_reselection_performed': False,
        'selection_preserved_from_freeze': True,
        'production_authority': False,
        'champion_remains_active': True,
        'retroactive_selection_prohibited': True,
    }
    analysis['sha256'] = meta_governor_sha256_json(analysis)
    return {
        'event_type': 'META_GOVERNOR', 'target_contest': int(target),
        'created_utc': datetime.now(timezone.utc).isoformat(), 'freeze_sha256': fr['freeze_sha256'],
        'meta_governor_schema': META_GOVERNOR_SCHEMA, 'meta_governor_engine_file': 'smart_meta_governor.py',
        'meta_governor_engine_sha256': sha256(Path('smart_meta_governor.py')),
        'meta_governor_sha256': analysis['sha256'], 'analysis': analysis,
        'retroactive_rewrite': False, 'policy_effect': 'P08_SHADOW_SELECTION_ONLY_CHAMPION_UNCHANGED',
    }

def _rank_calibration_events(ledger: dict, target: int) -> list[dict]:
    return [ev for ev in ledger.get('events', [])
            if ev.get('event_type') == 'RANK_SCORE_CALIBRATION' and int(ev.get('target_contest', -1)) == int(target)]


def _build_rank_calibration_event(fr: dict, actual: list[int], target: int) -> dict | None:
    calibration = fr.get('snapshot', {}).get('rank_score_calibration')
    if calibration is None:
        return None
    probabilities = calibration.get('probabilities_by_number')
    if not isinstance(probabilities, dict) or len(probabilities) != 60:
        raise ValueError('frozen rank calibration requires 60 probabilities')
    score = brier_score(probabilities, actual)
    uniform = {str(n): UNIFORM_PROB for n in range(1, 61)}
    uniform_score = brier_score(uniform, actual)
    analysis = {
        'schema': RANK_CALIBRATION_SCHEMA,
        'strength_before_result': float(calibration.get('strength', 0.0)),
        'calibration_mode_before_result': calibration.get('calibration_mode'),
        'probabilities_by_number': probabilities,
        'brier': score,
        'uniform_brier': uniform_score,
        'delta_vs_uniform': score - uniform_score,
        'monotonic_violations_before_isotonic': int(calibration.get('monotonic_violations_before_isotonic', 0)),
        'monotonic_after_isotonic': bool(calibration.get('monotonic_after_isotonic', False)),
        'causal': True,
    }
    analysis['evaluation_sha256'] = rank_calibration_sha256_json(analysis)
    return {
        'event_type': 'RANK_SCORE_CALIBRATION',
        'target_contest': int(target),
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'freeze_sha256': fr['freeze_sha256'],
        'rank_calibration_schema': RANK_CALIBRATION_SCHEMA,
        'rank_calibration_engine_file': 'smart_rank_score_calibration.py',
        'rank_calibration_engine_sha256': sha256(Path('smart_rank_score_calibration.py')),
        'evaluation_sha256': analysis['evaluation_sha256'],
        'analysis': analysis,
        'retroactive_rewrite': False,
        'policy_effect': 'POST_RESULT_EVALUATION_ONLY',
    }


def _multi_challenger_events(ledger: dict, target: int) -> list[dict]:
    return [ev for ev in ledger.get('events', []) if ev.get('event_type') == 'MULTI_CHALLENGERS' and int(ev.get('target_contest', -1)) == int(target)]


def _build_multi_challenger_event(fr: dict, actual: list[int], target: int) -> dict | None:
    frozen = fr.get('snapshot', {}).get('multi_challengers')
    if frozen is None:
        return None
    if frozen.get('schema') != MULTI_SCHEMA or list(frozen.get('policy_ids', [])) != list(MULTI_POLICY_IDS):
        raise ValueError('invalid frozen multi-challenger snapshot')
    policies = frozen.get('policies', {})
    if set(policies) != set(MULTI_POLICY_IDS):
        raise ValueError('frozen multi-challenger policies mismatch')
    actual_set = set(int(x) for x in actual)
    hits = {}
    top6 = {}
    policy_hashes = {}
    for pid in MULTI_POLICY_IDS:
        nums = [int(x) for x in policies[pid].get('top6', [])]
        if len(nums) != 6 or len(set(nums)) != 6 or min(nums) < 1 or max(nums) > 60:
            raise ValueError('invalid frozen multi-challenger top6')
        top6[pid] = nums
        hits[pid] = len(set(nums) & actual_set)
        policy_hashes[pid] = str(policies[pid].get('sha256', ''))
    analysis = {
        'schema': 'SMART_MULTI_CHALLENGERS_ADJUDICATION_1',
        'policy_ids': list(MULTI_POLICY_IDS),
        'policy_top6': top6,
        'policy_hits': hits,
        'policy_hashes': policy_hashes,
        'selection_performed': False,
        'selection_deferred_to_p08': True,
        'retroactive_selection_prohibited': True,
    }
    analysis['sha256'] = multi_sha256_json(analysis)
    return {
        'event_type': 'MULTI_CHALLENGERS',
        'target_contest': int(target),
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'freeze_sha256': fr['freeze_sha256'],
        'multi_challenger_schema': MULTI_SCHEMA,
        'multi_challenger_engine_file': 'smart_multi_challengers.py',
        'multi_challenger_engine_sha256': sha256(Path('smart_multi_challengers.py')),
        'multi_challenger_sha256': analysis['sha256'],
        'analysis': analysis,
        'retroactive_rewrite': False,
        'policy_effect': 'NONE_P07_SHADOW_ONLY_SELECTION_DEFERRED_TO_P08',
    }

def _interaction_events(ledger: dict, target: int) -> list[dict]:
    return [ev for ev in ledger.get('events', []) if ev.get('event_type') == 'INTERACTIONS' and int(ev.get('target_contest', -1)) == int(target)]


def _build_interaction_event(fr: dict, actual: list[int], target: int) -> dict:
    analysis = analyze_interaction_snapshot(fr['snapshot'], actual, max_group_order=3)
    return {'event_type':'INTERACTIONS','target_contest':int(target),'created_utc':datetime.now(timezone.utc).isoformat(),
            'freeze_sha256':fr['freeze_sha256'],'interaction_schema':INTERACTION_SCHEMA,
            'interaction_engine_file':'smart_signal_interactions.py','interaction_engine_sha256':sha256(Path('smart_signal_interactions.py')),
            'interaction_sha256':analysis['interaction_sha256'],'analysis':analysis,'retroactive_rewrite':False,
            'policy_effect':'NONE_P04_MEASUREMENT_ONLY'}


def append_interactions_for_existing(ledger_path: Path, target: int) -> dict:
    ledger=load_ledger(ledger_path); existing=_interaction_events(ledger,target)
    if existing:
        if len(existing)!=1: raise ValueError('ledger must contain at most one interaction event per contest')
        return {'status':'ALREADY_INTERACTIONS_EVENT_PRESERVED','target_contest':int(target),'interaction_sha256':existing[0]['interaction_sha256'],'ledger_sha256':sha256(ledger_path)}
    ads=[ev for ev in ledger.get('events',[]) if ev.get('event_type')=='ADJUDICATION' and int(ev.get('target_contest',-1))==int(target)]
    if len(ads)!=1: raise ValueError('exactly one adjudication is required before interactions')
    fr=active_freeze(ledger,target)
    if fr is None or str(ads[0].get('freeze_sha256'))!=str(fr.get('freeze_sha256')): raise ValueError('adjudication must reference active freeze')
    ev=_build_interaction_event(fr,[int(x) for x in ads[0]['actual_numbers']],target); ledger['events'].append(ev)
    h=write_ledger(ledger_path,ledger)
    return {'status':'INTERACTIONS_APPENDED','target_contest':int(target),'interaction_sha256':ev['interaction_sha256'],'ledger_sha256':h}

def _attribution_events(ledger: dict, target: int) -> list[dict]:
    return [ev for ev in ledger.get('events', [])
            if ev.get('event_type') == 'ATTRIBUTION' and int(ev.get('target_contest', -1)) == int(target)]


def _marginal_utility_events(ledger: dict, target: int) -> list[dict]:
    return [ev for ev in ledger.get('events', [])
            if ev.get('event_type') == 'MARGINAL_UTILITY' and int(ev.get('target_contest', -1)) == int(target)]


def _build_marginal_utility_event(fr: dict, actual: list[int], target: int, attribution_sha256: str | None = None) -> dict:
    analysis = analyze_marginal_utility_snapshot(fr['snapshot'], actual)
    return {
        'event_type': 'MARGINAL_UTILITY',
        'target_contest': int(target),
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'freeze_sha256': fr['freeze_sha256'],
        'attribution_sha256': attribution_sha256,
        'marginal_utility_schema': MARGINAL_UTILITY_SCHEMA,
        'marginal_utility_engine_file': 'smart_signal_marginal_utility.py',
        'marginal_utility_engine_sha256': sha256(Path('smart_signal_marginal_utility.py')),
        'marginal_utility_sha256': analysis['marginal_utility_sha256'],
        'analysis': analysis,
        'retroactive_rewrite': False,
        'policy_effect': 'NONE_P02_MEASUREMENT_ONLY',
    }


def append_marginal_utility_for_existing(ledger_path: Path, target: int) -> dict:
    ledger = load_ledger(ledger_path)
    existing = _marginal_utility_events(ledger, target)
    if existing:
        if len(existing) != 1:
            raise ValueError('ledger must contain at most one marginal utility event per contest')
        return {'status': 'ALREADY_MARGINAL_UTILITY_EVENT_PRESERVED', 'target_contest': int(target),
                'marginal_utility_sha256': existing[0]['marginal_utility_sha256'], 'ledger_sha256': sha256(ledger_path)}
    adjudications = [ev for ev in ledger.get('events', [])
                     if ev.get('event_type') == 'ADJUDICATION' and int(ev.get('target_contest', -1)) == int(target)]
    if len(adjudications) != 1:
        raise ValueError('exactly one adjudication is required before marginal utility')
    ad = adjudications[0]
    fr = active_freeze(ledger, target)
    if fr is None or str(ad.get('freeze_sha256')) != str(fr.get('freeze_sha256')):
        raise ValueError('adjudication must reference the active frozen prediction')
    attrs = _attribution_events(ledger, target)
    if len(attrs) > 1:
        raise ValueError('ledger must contain at most one attribution event per contest')
    attr_sha = attrs[0].get('attribution_sha256') if attrs else None
    event = _build_marginal_utility_event(fr, [int(x) for x in ad['actual_numbers']], target, attr_sha)
    ledger['events'].append(event)
    ledger_hash = write_ledger(ledger_path, ledger)
    return {'status': 'MARGINAL_UTILITY_APPENDED', 'target_contest': int(target),
            'marginal_utility_sha256': event['marginal_utility_sha256'], 'ledger_sha256': ledger_hash}


def _build_attribution_event(fr: dict, actual: list[int], target: int) -> dict:
    attribution = analyze_attribution(fr['snapshot'], actual)
    return {
        'event_type': 'ATTRIBUTION',
        'target_contest': int(target),
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'freeze_sha256': fr['freeze_sha256'],
        'attribution_schema': ATTRIBUTION_SCHEMA,
        'attribution_engine_file': 'smart_signal_attribution.py',
        'attribution_engine_sha256': sha256(Path('smart_signal_attribution.py')),
        'attribution_sha256': attribution['attribution_sha256'],
        'analysis': attribution,
        'retroactive_rewrite': False,
        'policy_effect': 'NONE_POST_RESULT_DIAGNOSTIC_ONLY',
    }


def append_attribution_for_existing(ledger_path: Path, target: int) -> dict:
    ledger = load_ledger(ledger_path)
    existing = _attribution_events(ledger, target)
    if existing:
        if len(existing) != 1:
            raise ValueError('ledger must contain at most one attribution event per contest')
        return {'status': 'ALREADY_ATTRIBUTED_EVENT_PRESERVED', 'target_contest': int(target),
                'attribution_sha256': existing[0]['attribution_sha256'], 'ledger_sha256': sha256(ledger_path)}
    adjudications = [ev for ev in ledger.get('events', [])
                     if ev.get('event_type') == 'ADJUDICATION' and int(ev.get('target_contest', -1)) == int(target)]
    if len(adjudications) != 1:
        raise ValueError('exactly one adjudication is required before attribution')
    ad = adjudications[0]
    fr = active_freeze(ledger, target)
    if fr is None or str(ad.get('freeze_sha256')) != str(fr.get('freeze_sha256')):
        raise ValueError('adjudication must reference the active frozen prediction')
    event = _build_attribution_event(fr, [int(x) for x in ad['actual_numbers']], target)
    ledger['events'].append(event)
    ledger_hash = write_ledger(ledger_path, ledger)
    return {'status': 'ATTRIBUTION_APPENDED', 'target_contest': int(target),
            'attribution_sha256': event['attribution_sha256'], 'ledger_sha256': ledger_hash}


def adjudicate(result_data: Path, target: int, ledger_path: Path) -> dict:
    ledger = load_ledger(ledger_path)
    fr = active_freeze(ledger, target)
    if fr is None:
        raise ValueError('active frozen prediction is required')
    if any(ev.get('event_type') == 'ADJUDICATION' and int(ev.get('target_contest', -1)) == int(target)
           for ev in ledger['events']):
        raise ValueError('contest already adjudicated; append-only ledger refuses duplicate adjudication')
    if _attribution_events(ledger, target):
        raise ValueError('attribution cannot predate adjudication')
    if _marginal_utility_events(ledger, target):
        raise ValueError('marginal utility cannot predate adjudication')
    if _interaction_events(ledger, target):
        raise ValueError('interactions cannot predate adjudication')
    if _multi_challenger_events(ledger, target):
        raise ValueError('multi-challenger evaluation cannot predate adjudication')
    if _meta_governor_events(ledger, target):
        raise ValueError('meta-governor evaluation cannot predate adjudication')
    if _rank_calibration_events(ledger, target):
        raise ValueError('rank calibration cannot predate adjudication')
    freeze_file = Path(fr['freeze_file'])
    if not freeze_file.exists() or sha256(freeze_file) != fr['freeze_sha256']:
        raise ValueError('frozen artifact hash mismatch')

    df = pd.read_excel(result_data)
    row = df[df['Concurso'].astype(int) == int(target)]
    if len(row) != 1:
        raise ValueError('target result must occur exactly once in result data')
    r = row.iloc[0]
    actual = sorted(int(r[f'Bola{i}']) for i in range(1, 7))
    if len(set(actual)) != 6 or actual[0] < 1 or actual[-1] > 60:
        raise ValueError('invalid result')
    actual_set = set(actual)
    champion_top6 = [int(x) for x in fr['champion_top6']]
    challenger_top6 = [int(x) for x in fr['challenger_top6']]
    champion_hits = len(set(champion_top6) & actual_set)
    challenger_hits = len(set(challenger_top6) & actual_set)

    contributions = {}
    snapshot = fr['snapshot']
    for name, sig in snapshot['raw_signals'].items():
        values = sig['values']
        arr = [float(values[str(i)]) for i in range(1, 61)]
        top, _ = e.rank_top6(arr)
        expert_hits = len(set(top) & actual_set)
        w = float(snapshot['weights'][name])
        actual_score_sum = sum(float(values[str(n)]) for n in actual)
        contributions[name] = {
            'weight_before_result': w,
            'expert_top6_hits': expert_hits,
            'weighted_actual_score_sum': w * actual_score_sum,
            'quality_before_result': snapshot['quality_metrics'][name],
        }

    e_after = _next_e_value(ledger, challenger_hits, champion_hits)
    event = {
        'event_type': 'ADJUDICATION', 'target_contest': int(target), 'created_utc': datetime.now(timezone.utc).isoformat(),
        'freeze_sha256': fr['freeze_sha256'], 'result_data_file': str(result_data), 'result_data_sha256': sha256(result_data),
        'actual_numbers': actual, 'champion_hits': champion_hits, 'challenger_hits': challenger_hits,
        'difference_hits': challenger_hits - champion_hits, 'e_value_after': e_after,
        'signal_contributions': contributions, 'retroactive_rewrite': False,
    }
    attribution_event = _build_attribution_event(fr, actual, target)
    marginal_event = _build_marginal_utility_event(fr, actual, target, attribution_event['attribution_sha256'])
    interaction_event = _build_interaction_event(fr, actual, target)
    multi_event = _build_multi_challenger_event(fr, actual, target)
    meta_governor_event = _build_meta_governor_event(fr, actual, target)
    rank_calibration_event = _build_rank_calibration_event(fr, actual, target)
    ledger['events'].append(event)
    ledger['events'].append(attribution_event)
    ledger['events'].append(marginal_event)
    ledger['events'].append(interaction_event)
    if multi_event is not None:
        ledger['events'].append(multi_event)
    if meta_governor_event is not None:
        ledger['events'].append(meta_governor_event)
    if rank_calibration_event is not None:
        ledger['events'].append(rank_calibration_event)
    ledger_hash = write_ledger(ledger_path, ledger)
    return {'target_contest': int(target), 'actual_numbers': actual, 'champion_hits': champion_hits,
            'challenger_hits': challenger_hits, 'e_value_after': e_after, 'ledger_sha256': ledger_hash,
            'attribution_sha256': attribution_event['attribution_sha256'],
            'marginal_utility_sha256': marginal_event['marginal_utility_sha256'],
            'interaction_sha256': interaction_event['interaction_sha256'],
            'multi_challenger_sha256': None if multi_event is None else multi_event['multi_challenger_sha256'],
            'meta_governor_sha256': None if meta_governor_event is None else meta_governor_event['meta_governor_sha256'],
            'rank_score_calibration_evaluation_sha256': None if rank_calibration_event is None else rank_calibration_event['evaluation_sha256'],
            'promotion': promotion_status(ledger)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--result-data', required=True)
    ap.add_argument('--target', type=int, required=True)
    ap.add_argument('--ledger', default='SMART_SIGNAL_LEDGER.json')
    a = ap.parse_args()
    print(json.dumps(adjudicate(Path(a.result_data), a.target, Path(a.ledger)), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
