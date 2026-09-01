import hashlib
import math
import pytest

import smart_v2_production as p


def base_audit():
    return {
        'walk_forward': {'excess_hits': 10, 'diagnostic_z_vs_uniform': 3.0, 'total_hits': 170},
        'placebo': {'total_hits': 150},
        'monte_carlo_null': {'false_positive_rate_z_ge_2': 0.05},
    }


def ledger(n=20, smart=2, base=1, evalue=12.0):
    rows=[]
    for i in range(n):
        rows.append({
            'contest': 4000+i, 'frozen_before_result': True, 'adjudicated': True,
            'prediction_sha256': hashlib.sha256(str(i).encode()).hexdigest(),
            'smart_hits': smart, 'baseline_hits': base,
            'e_value_after': evalue if i == n-1 else max(1.0, evalue*(i+1)/n),
            'comparison_eligible': True,
        })
    return {'schema': p.LEGACY_LEDGER_SCHEMA, 'records': rows}


def test_legacy_gate_is_diagnostic_only_even_when_all_conditions_pass():
    state=p.decide(base_audit(), ledger())
    assert state['prospective_validation']['valid'] is True
    assert state['legacy_diagnostic_signal_detected'] is True
    assert state['mode']=='NO_PREDICTIVE_SIGNAL_DETECTED'
    assert state['predictive_signal_weight']==0.0
    assert state['production_switch_may_proceed'] is False
    assert state['legacy_production_authority_disabled'] is True
    assert state['production_authority']==p.PRODUCTION_AUTHORITY


def test_boolean_cannot_fake_proof_and_missing_ledger_stays_neutral():
    a=base_audit(); a['guardrails']={'prospective_proof':True}
    state=p.decide(a,None)
    assert state['mode']=='NO_PREDICTIVE_SIGNAL_DETECTED'
    assert state['prospective_validation']['valid'] is False


def test_minimum_prospective_count_enforced():
    assert not p.validate_ledger(ledger(19))['valid']


def test_regret_must_be_negative():
    assert not p.validate_ledger(ledger(20,1,2,20))['valid']


def test_evalue_threshold_enforced():
    assert not p.validate_ledger(ledger(20,2,1,9.9))['valid']


def test_duplicate_contest_rejected():
    obj=ledger(); obj['records'][1]['contest']=obj['records'][0]['contest']
    assert p.validate_ledger(obj)['reason']=='duplicate prospective contest'


def test_strict_record_contract_rejects_coercions_and_bad_hashes():
    mutations = [
        ('frozen_before_result', 'false', 'explicit causal'),
        ('adjudicated', 1, 'explicit causal'),
        ('prediction_sha256', 'g'*64, 'hexadecimal SHA-256'),
        ('smart_hits', True, 'smart_hits'),
        ('smart_hits', 1.0, 'smart_hits'),
        ('baseline_hits', 7, 'baseline_hits'),
        ('e_value_after', float('nan'), 'finite'),
        ('comparison_eligible', None, 'explicit boolean'),
        ('contest', True, 'positive integer'),
        ('contest', 0, 'positive integer'),
    ]
    for field, value, reason in mutations:
        obj=ledger(); obj['records'][0][field]=value
        out=p.validate_ledger(obj)
        assert not out['valid'] and reason in out['reason']


def test_noncomparison_rows_are_explicitly_excluded_and_no_eligible_rows_fail():
    obj=ledger(); obj['records'][0]['comparison_eligible']=False
    assert p.validate_ledger(obj)['n']==19
    for row in obj['records']:
        row['comparison_eligible']=False
    out=p.validate_ledger(obj)
    assert not out['valid'] and 'no adjudicated comparison-eligible' in out['reason']


def test_ledger_shape_and_order_fail_closed():
    assert not p.validate_ledger({'schema':'BAD','records':[]})['valid']
    out=p.validate_ledger({'schema':p.LEGACY_LEDGER_SCHEMA,'records':{}})
    assert 'records must be a list' in out['reason']
    obj=ledger(); obj['records'][0]='bad'
    assert 'malformed' in p.validate_ledger(obj)['reason']
    obj=ledger(); obj['records']=list(reversed(obj['records']))
    assert p.validate_ledger(obj)['reason']=='contest order invalid'


def test_malformed_audit_is_rejected_not_coerced():
    with pytest.raises(ValueError, match='audit must be an object'):
        p.decide(None, ledger())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match='malformed legacy production audit'):
        p.decide({'walk_forward': {}}, ledger())


def test_bad_historical_gate_neutralizes_diagnostic_signal():
    a=base_audit(); a['walk_forward']['excess_hits']=-1
    state=p.decide(a,ledger())
    assert state['legacy_diagnostic_signal_detected'] is False
    assert state['mode']=='NO_PREDICTIVE_SIGNAL_DETECTED'
