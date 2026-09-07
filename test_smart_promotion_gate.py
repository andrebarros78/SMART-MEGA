from __future__ import annotations



import hashlib

import json

from pathlib import Path



import numpy as np

import pandas as pd

import pytest



from smart_promotion_gate import adaptive_min_contests, assess_promotion_records, policy_snapshot

from smart_champion_challenger import promotion_eligibility_status

import smart_champion_challenger as cc





def _rows(n: int, challenger: int, champion: int):

    return [{'challenger_hits': challenger, 'champion_hits': champion} for _ in range(n)]





def _ledger(n: int, challenger: int, champion: int, e_value: float):

    events = []

    component_hashes = {name: f'{idx + 1:064x}' for idx, name in enumerate(cc.PROMOTION_LINEAGE_COMPONENTS)}

    lineage = {'schema': cc.PROMOTION_LINEAGE_SCHEMA, 'component_hashes': component_hashes}

    lineage['sha256'] = hashlib.sha256(json.dumps(lineage, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    for i in range(n):

        contest = 4000 + i

        freeze_hash = f'{contest:064x}'[-64:]

        events.append({

            'event_type': 'FREEZE',

            'target_contest': contest,

            'freeze_sha256': freeze_hash,

            'frozen_before_result': True,

            'causal_cutoff': True,

            'hashes': component_hashes,

            'promotion_lineage': lineage,

        })

        events.append({

            'event_type': 'ADJUDICATION',

            'target_contest': contest,

            'freeze_sha256': freeze_hash,

            'challenger_hits': challenger,

            'champion_hits': champion,

            'e_value_after': e_value,

        })

    return {'schema': 'SMART_SIGNAL_LEDGER_1', 'events': events}





def test_adaptive_sample_floor_rises_when_advantage_shrinks():

    assert adaptive_min_contests(0.50) == 20

    assert adaptive_min_contests(0.25) == 30

    assert adaptive_min_contests(0.10) == 50

    assert adaptive_min_contests(0.01) == 80





def test_strong_advantage_can_pass_at_base_floor_with_sequential_evidence():

    status = assess_promotion_records(_rows(20, 4, 3), e_value=10.0)

    assert status['eligible'] is True

    assert status['required_prospective_contests'] == 20

    assert status['favorable_regret'] is True

    assert status['sequential_evidence'] is True





def test_small_advantage_escalates_sample_and_blocks_early_promotion():

    rows = ([{'challenger_hits': 4, 'champion_hits': 3}] +

            [{'challenger_hits': 3, 'champion_hits': 3} for _ in range(19)])

    status = assess_promotion_records(rows, e_value=100.0)

    assert status['eligible'] is False

    assert status['adaptive_sample_escalated'] is True

    assert status['required_prospective_contests'] == 80

    assert 'insufficient_adaptive_sample' in status['blockers']





def test_sequential_evidence_is_mandatory_even_with_superiority_and_sample():

    status = assess_promotion_records(_rows(20, 4, 3), e_value=9.99)

    assert status['eligible'] is False

    assert 'insufficient_sequential_evidence' in status['blockers']





def test_favorable_regret_and_cumulative_superiority_are_both_mandatory():

    status = assess_promotion_records(_rows(80, 3, 3), e_value=100.0)

    assert status['eligible'] is False

    assert status['cumulative_regret'] == 0

    assert status['favorable_regret'] is False

    assert 'no_cumulative_superiority' in status['blockers']

    assert 'regret_not_favorable' in status['blockers']





def test_no_prospective_records_never_promotes():

    status = assess_promotion_records([], e_value=1.0)

    assert status['eligible'] is False

    assert status['n'] == 0

    assert 'no_adjudicated_prospective_contests' in status['blockers']





def test_policy_snapshot_predeclares_adaptive_rule():

    policy = policy_snapshot()

    assert policy['base_min_prospective_contests'] == 20

    assert policy['min_e_value'] == 10.0

    assert policy['must_have_favorable_regret'] is True

    assert policy['adaptive_sample_rule']['mean_hit_advantage_gt_0'] == 80





def test_champion_challenger_integration_uses_adaptive_gate():

    status = promotion_eligibility_status(_ledger(20, challenger=6, champion=3, e_value=10.0))

    assert status['eligible'] is True

    assert status['decision'] == 'PROMOTE_SIGNAL_INTELLIGENCE_CHALLENGER'

    assert status['required_prospective_contests'] == 20





def test_champion_challenger_integration_blocks_small_margin_at_20():

    ledger = _ledger(20, challenger=3, champion=3, e_value=100.0)

    # Make only one prospective contest a +1 advantage: mean advantage 0.05.

    ledger['events'][-1]['challenger_hits'] = 4

    status = promotion_eligibility_status(ledger)

    assert status['eligible'] is False

    assert status['required_prospective_contests'] == 80

    assert status['adaptive_sample_escalated'] is True





def test_gate_rejects_invalid_hit_domain_instead_of_truncating_or_promoting():

    for bad in (-1, 7, 1.5, True, float('nan')):

        rows = [{'challenger_hits': bad, 'champion_hits': 0}]

        with pytest.raises(ValueError):

            assess_promotion_records(rows, e_value=100.0)

    with pytest.raises(ValueError):

        promotion_eligibility_status(_ledger(20, challenger=4, champion=3, e_value=10.0) | {

            'events': _ledger(20, challenger=4, champion=3, e_value=10.0)['events'][:-1] + [

                {**_ledger(20, challenger=4, champion=3, e_value=10.0)['events'][-1], 'challenger_hits': 6.5}

            ]

        })





def test_gate_rejects_nonfinite_or_negative_sequential_evidence():

    rows = _rows(20, 6, 0)

    for bad in (float('nan'), float('inf'), float('-inf'), -0.01):

        with pytest.raises(ValueError):

            assess_promotion_records(rows, e_value=bad)





def test_adaptive_sample_rejects_nonfinite_advantage():

    with pytest.raises(ValueError):

        adaptive_min_contests(float('nan'))

    with pytest.raises(ValueError):

        adaptive_min_contests(float('inf'))





def _dataset(n: int, seed: int) -> pd.DataFrame:

    rng = np.random.default_rng(seed)

    rows = []

    for i in range(1, n + 1):

        draw = np.sort(rng.choice(np.arange(1, 61), 6, replace=False))

        row = {'Concurso': i, 'Data do Sorteio': pd.Timestamp('2024-01-01') + pd.Timedelta(days=i)}

        row.update({f'Bola{j}': int(draw[j - 1]) for j in range(1, 7)})

        rows.append(row)

    return pd.DataFrame(rows)





def test_freeze_preserves_promotion_gate_hash_and_policy_in_file_and_ledger(tmp_path: Path):

    data = tmp_path / 'pre.xlsx'

    freeze = tmp_path / 'freeze.json'

    ledger = tmp_path / 'ledger.json'

    state = tmp_path / 'state.json'

    _dataset(65, 1313).to_excel(data, index=False)

    out = cc.freeze_champion_challenger(data, 66, freeze, ledger, state, start=30, enforce_temporal_guard=False)

    assert out['status'] == 'FROZEN'

    frozen = json.loads(freeze.read_text(encoding='utf-8'))

    led = json.loads(ledger.read_text(encoding='utf-8'))

    event = next(ev for ev in led['events'] if ev.get('event_type') == 'FREEZE')

    policy = policy_snapshot()

    assert frozen['promotion_policy'] == policy

    assert event['snapshot']['promotion_policy'] == policy

    assert frozen['promotion_gate_sha256'] == cc.sha256(Path('smart_promotion_gate.py'))

    assert event['hashes']['promotion_gate'] == frozen['promotion_gate_sha256']

    assert policy['schema'] == 'SMART_PROMOTION_GATE_POLICY_1'

    assert policy['invalid_or_nonfinite_inputs_rejected'] is True



