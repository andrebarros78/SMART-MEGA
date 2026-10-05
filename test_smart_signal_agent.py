import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import smart_v2_engine as e
import smart_champion_challenger as cc
from smart_champion_challenger import freeze_champion_challenger, promotion_eligibility_status
from smart_signal_agent import SIGNAL_NAMES, SmartSignalAgent
from smart_signal_quality import SignalQualityState


def _draws(seed=123, n=220):
    rng = np.random.default_rng(seed)
    return np.array([np.sort(rng.choice(e.NUMBERS, 6, replace=False)) for _ in range(n)], dtype=int)


def test_signal_adapter_exposes_all_signals_with_causal_cutoff_and_hashes():
    draws = _draws()
    contests = np.arange(1, len(draws) + 1)
    agent = SmartSignalAgent(start=50)
    pred, _ = agent.predict_next(draws, contests, target_contest=221, cutoff_timestamp='2026-08-28T00:00:00')
    assert set(pred.raw_signals) == set(SIGNAL_NAMES)
    for name, sig in pred.raw_signals.items():
        assert sig['signal_id'] == name
        assert sig['family'] in {'freq', 'ewma'}
        assert sig['cutoff_contest'] == 220
        assert sig['target_contest'] == 221
        assert sig['causal'] is True
        assert len(sig['values']) == 60
        assert len(sig['values_sha256']) == 64


def test_dynamic_weights_are_complete_normalized_and_use_required_factors():
    draws = _draws(seed=456)
    contests = np.arange(1, len(draws) + 1)
    pred, _ = SmartSignalAgent(start=50).predict_next(draws, contests, target_contest=221)
    assert abs(sum(pred.weights.values()) - 1.0) < 1e-10
    required = {'utility', 'quality', 'confidence', 'context', 'redundancy_penalty', 'raw_product', 'final_weight'}
    for name in SIGNAL_NAMES:
        assert required <= set(pred.weight_components[name])
        assert pred.weights[name] > 0
    fam = {'freq': 0.0, 'ewma': 0.0}
    for name, w in pred.weights.items():
        fam[e.family_of(name)] += w
    assert max(fam.values()) <= 0.7000001


def test_future_result_does_not_change_pre_result_signal_vector():
    draws = _draws(seed=789)
    X = e.onehot(draws)
    pre = e.precompute_scores(X)
    future = np.sort(np.random.default_rng(790).choice(e.NUMBERS, 6, replace=False))
    extended = np.vstack([draws, future])
    pre_ext = e.precompute_scores(e.onehot(extended))
    t = len(draws)
    for name in SIGNAL_NAMES:
        assert np.allclose(pre[name][t], pre_ext[name][t])


def test_river_adwin_updates_and_detects_large_regime_change():
    state = SignalQualityState('synthetic', 'freq')
    for h in [0] * 300 + [6] * 300:
        state.update(h)
    metrics = state.metrics(1.0)
    assert metrics['n_oos'] == 600
    assert metrics['drift_count'] >= 1
    assert metrics['adwin_width'] > 0


def test_promotion_requires_all_prospective_gates():
    ledger = {'schema': 'SMART_SIGNAL_LEDGER_1', 'events': []}
    ev = 1.0
    for c in range(1, 21):
        freeze_hash = f'{c:064x}'[-64:]
        component_hashes = {name: ('a' * 64) for name in cc.PROMOTION_LINEAGE_COMPONENTS}
        lineage = {
            'schema': cc.PROMOTION_LINEAGE_SCHEMA,
            'component_hashes': component_hashes,
        }
        lineage['sha256'] = hashlib.sha256(
            json.dumps(lineage, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        ).hexdigest()
        ledger['events'].append({'event_type': 'FREEZE', 'target_contest': c, 'frozen_before_result': True,
                                 'causal_cutoff': True, 'freeze_sha256': freeze_hash,
                                 'hashes': component_hashes, 'promotion_lineage': lineage})
        ev *= 1.25
        ledger['events'].append({'event_type': 'ADJUDICATION', 'target_contest': c, 'freeze_sha256': freeze_hash,
                                 'challenger_hits': 6, 'champion_hits': 0, 'e_value_after': ev})
    p = promotion_eligibility_status(ledger)
    assert p['n'] == 20
    assert p['e_value'] >= 10.0
    assert p['eligible'] is True
    assert p['decision'] == 'PROMOTE_SIGNAL_INTELLIGENCE_CHALLENGER'


def test_freeze_creates_champion_challenger_and_append_only_event(tmp_path: Path, record_property):
    draws = _draws(seed=999, n=120)
    rows = []
    for i, d in enumerate(draws, start=1):
        row = {'Concurso': i, 'Data do Sorteio': pd.Timestamp('2020-01-01') + pd.Timedelta(days=i)}
        row.update({f'Bola{j}': int(d[j - 1]) for j in range(1, 7)})
        rows.append(row)
    data = tmp_path / 'mega.xlsx'
    pd.DataFrame(rows).to_excel(data, index=False)
    out = tmp_path / 'freeze.json'
    ledger = tmp_path / 'ledger.json'
    state = tmp_path / 'state.json'
    result = freeze_champion_challenger(data, 121, out, ledger, state, start=30, enforce_temporal_guard=False)
    assert result['status'] == 'FROZEN'
    obj = json.loads(out.read_text(encoding='utf-8'))
    assert obj['champion_remains_active'] is True
    assert obj['production_switch_performed'] is False
    assert obj['challenger']['cutoff_contest'] == 120
    assert len(obj['challenger']['raw_signals']) == len(SIGNAL_NAMES)
    assert len(obj['redundancy_consensus_sha256']) == 64
    assert obj['challenger']['redundancy_consensus']['threshold'] == 0.90
    led = json.loads(ledger.read_text(encoding='utf-8'))
    assert len(led['events']) == 1
    assert led['events'][0]['event_type'] == 'FREEZE'
    assert led['events'][0]['frozen_before_result'] is True
    assert led['events'][0]['snapshot']['signal_interactions']['pair_count'] == 66
    assert len(led['events'][0]['hashes']['signal_interactions']) == 64
    assert len(led['events'][0]['hashes']['redundancy_consensus']) == 64
    assert led['events'][0]['snapshot']['redundancy_consensus']['threshold'] == 0.90

    # Exercise real generation, persisted primary card, replay and outcome scoring.
    from adjudicate_signal_challenger import adjudicate
    import pytest

    portfolio = json.loads(Path(result['portfolio_file']).read_text(encoding='utf-8'))
    card = portfolio['primary_card']
    assert card['numbers'] == led['events'][0]['primary_card']['numbers']
    assert len(set(card['numbers'])) == 6
    assert all(1 <= n <= 60 for n in card['numbers'])
    assert card['selector']['status'] == 'PASS'
    assert card['freeze_sha256'] == result['freeze_sha256']
    from smart_full_process_pipeline import _primary_card_artifact
    from smart_github_operator import _verified_freeze_publication
    bound_card = _primary_card_artifact(
        card, run_id='fixture-121', frozen_utc=obj['frozen_utc'],
        freeze_file=str(out), portfolio_file=result['portfolio_file'],
        portfolio_sha256=result['portfolio_sha256'],
    )
    primary_path = tmp_path / 'SMART_121_PRIMARY_CARD.json'
    primary_path.write_text(json.dumps(bound_card), encoding='utf-8')
    publication_proof = {
        'status': 'PASS', 'result_used': False, 'target_contest': 121,
        'epoch_id': 'fixture-121', 'freeze_sha256': result['freeze_sha256'],
        'primary_card': bound_card, 'primary_card_file': primary_path.name,
        'primary_card_sha256': hashlib.sha256(primary_path.read_bytes()).hexdigest(),
        'target_schedule': {'schema': 'SMART_TARGET_SCHEDULE_AUTHORITY_3',
                            'target_contest': 121, 'scheduled_datetime': '2100-01-01T21:00:00-03:00'},
    }
    response = _verified_freeze_publication(
        tmp_path, {'proof': publication_proof}, [primary_path.name], '121')
    assert response['run_id'] == 'fixture-121'
    assert response['numbers'] == card['numbers']
    assert response['confidence']['status'] == 'UNPROVEN_PROSPECTIVE'
    assert response['confidence']['probability_six_hits'] is None
    assert response['confidence']['guaranteed'] is False
    assert json.loads(primary_path.read_text(encoding='utf-8')) == bound_card
    assert bound_card['generated_utc'] == obj['frozen_utc']
    probabilities = led['events'][0]['snapshot']['rank_score_calibration']['probabilities_by_number']
    assert len(probabilities) == 60
    assert all(np.isfinite(p) and 0 <= p <= 1 for p in probabilities.values())
    assert sum(probabilities.values()) == pytest.approx(6.0)

    frozen_bytes = out.read_bytes()
    ledger_bytes = ledger.read_bytes()
    replay = freeze_champion_challenger(data, 121, out, ledger, state, start=30, enforce_temporal_guard=False)
    assert replay['status'] == 'ALREADY_FROZEN_IDENTICAL_EVENT_PRESERVED'
    assert out.read_bytes() == frozen_bytes
    assert ledger.read_bytes() == ledger_bytes

    actual = [4, 13, 22, 31, 40, 59]
    result_row = {'Concurso': 121, 'Data do Sorteio': pd.Timestamp('2020-05-01')}
    result_row.update({f'Bola{j}': n for j, n in enumerate(actual, start=1)})
    result_data = tmp_path / 'official_result_fixture.xlsx'
    pd.DataFrame([*rows, result_row]).to_excel(result_data, index=False)
    scored = adjudicate(result_data, 121, ledger)
    adjudicated = json.loads(ledger.read_text(encoding='utf-8'))
    outcome = next(ev for ev in adjudicated['events'] if ev['event_type'] == 'ADJUDICATION')
    calibration = next(ev for ev in adjudicated['events'] if ev['event_type'] == 'RANK_SCORE_CALIBRATION')
    assert scored['actual_numbers'] == actual
    assert outcome['freeze_sha256'] == card['freeze_sha256']
    assert 0 <= scored['champion_hits'] <= 6
    assert 0 <= scored['challenger_hits'] <= 6
    assert 0 <= calibration['analysis']['brier'] <= 1
    assert calibration['analysis']['uniform_brier'] == pytest.approx(0.09)
    assert out.read_bytes() == frozen_bytes
    assert adjudicated['events'][0] == led['events'][0]
    after_bytes = ledger.read_bytes()
    with pytest.raises(ValueError, match='already adjudicated'):
        adjudicate(result_data, 121, ledger)
    assert ledger.read_bytes() == after_bytes
    record_property('fixture_e2e', json.dumps({'fixture_e2e': 'PASS', 'target': 121, 'card': card['numbers'],
                      'freeze_sha256': card['freeze_sha256'], 'actual': actual,
                      'run_id': response['run_id'], 'confidence': response['confidence'],
                      'primary_card_hits': len(set(card['numbers']) & set(actual)),
                      'brier': calibration['analysis']['brier'],
                      'uniform_brier': calibration['analysis']['uniform_brier'],
                      'freeze_replay_unchanged': True, 'duplicate_outcome_rejected': True}))

def test_profile_adwin_detects_signal_vector_regime_shift():
    state = SignalQualityState('profile', 'freq')
    a = np.zeros(60, dtype=float); a[:6] = 1.0
    b = np.zeros(60, dtype=float); b[30:36] = 1.0
    for _ in range(300):
        state.update_profile(a)
    for _ in range(300):
        state.update_profile(b)
    metrics = state.metrics(1.0)
    assert metrics['profile_observations'] == 600
    assert metrics['profile_drift_count'] >= 1
    assert metrics['last_profile_drift_step'] is not None
