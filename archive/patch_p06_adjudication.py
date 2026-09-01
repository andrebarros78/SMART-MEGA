from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\adjudicate_signal_challenger.py')
s=p.read_text(encoding='utf-8-sig')
s=s.replace("from smart_signal_interactions import SCHEMA as INTERACTION_SCHEMA, analyze_snapshot as analyze_interaction_snapshot\n",
            "from smart_signal_interactions import SCHEMA as INTERACTION_SCHEMA, analyze_snapshot as analyze_interaction_snapshot\nfrom smart_rank_score_calibration import SCHEMA as RANK_CALIBRATION_SCHEMA, UNIFORM_PROB, brier_score, sha256_json as rank_calibration_sha256_json\n")
insert="""

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
"""
marker="\ndef _interaction_events(ledger: dict, target: int) -> list[dict]:\n"
assert marker in s
s=s.replace(marker,insert+marker)
s=s.replace("    if _interaction_events(ledger, target):\n        raise ValueError('interactions cannot predate adjudication')\n",
            "    if _interaction_events(ledger, target):\n        raise ValueError('interactions cannot predate adjudication')\n    if _rank_calibration_events(ledger, target):\n        raise ValueError('rank calibration cannot predate adjudication')\n")
old="""    interaction_event = _build_interaction_event(fr, actual, target)\n    ledger['events'].append(event)\n    ledger['events'].append(attribution_event)\n    ledger['events'].append(marginal_event)\n    ledger['events'].append(interaction_event)\n    ledger_hash = write_ledger(ledger_path, ledger)\n    return {'target_contest': int(target), 'actual_numbers': actual, 'champion_hits': champion_hits,\n            'challenger_hits': challenger_hits, 'e_value_after': e_after, 'ledger_sha256': ledger_hash,\n            'attribution_sha256': attribution_event['attribution_sha256'],\n            'marginal_utility_sha256': marginal_event['marginal_utility_sha256'],\n            'interaction_sha256': interaction_event['interaction_sha256'],\n            'promotion': promotion_status(ledger)}\n"""
new="""    interaction_event = _build_interaction_event(fr, actual, target)\n    rank_calibration_event = _build_rank_calibration_event(fr, actual, target)\n    ledger['events'].append(event)\n    ledger['events'].append(attribution_event)\n    ledger['events'].append(marginal_event)\n    ledger['events'].append(interaction_event)\n    if rank_calibration_event is not None:\n        ledger['events'].append(rank_calibration_event)\n    ledger_hash = write_ledger(ledger_path, ledger)\n    return {'target_contest': int(target), 'actual_numbers': actual, 'champion_hits': champion_hits,\n            'challenger_hits': challenger_hits, 'e_value_after': e_after, 'ledger_sha256': ledger_hash,\n            'attribution_sha256': attribution_event['attribution_sha256'],\n            'marginal_utility_sha256': marginal_event['marginal_utility_sha256'],\n            'interaction_sha256': interaction_event['interaction_sha256'],\n            'rank_score_calibration_evaluation_sha256': None if rank_calibration_event is None else rank_calibration_event['evaluation_sha256'],\n            'promotion': promotion_status(ledger)}\n"""
assert old in s
s=s.replace(old,new)
p.write_text(s,encoding='utf-8')
print('patched adjudication')
