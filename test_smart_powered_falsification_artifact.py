import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_powered_falsification_has_sufficient_holm_resolution_and_no_predictive_authority():
    report=json.loads((ROOT/'SMART_FALSIFICATION_REPORT_POWERED.json').read_text(encoding='utf-8'))
    assert report['replications'] >= report['multiplicity']['minimum_replications_for_resolution']
    assert report['multiplicity']['resolution_sufficient'] is True
    assert report['multiplicity']['family_size'] == 10
    assert len(report['comparisons']) == 10
    assert report['predictive_weight_authorized'] is False
    assert report['terminal_6of6_proven'] is False
    assert report['mission_state'] == 'MISSION_ACTIVE'
    assert report['adversarial_sensitivity']['all_expected_directions_detected'] is True


def test_powered_falsification_binds_canonical_cutoff_dataset_and_preregistration():
    report=json.loads((ROOT/'SMART_FALSIFICATION_REPORT_POWERED.json').read_text(encoding='utf-8'))
    prereg=json.loads((ROOT/'SMART_P4_P5_PREREGISTRATION_POWERED.json').read_text(encoding='utf-8'))
    data=ROOT/'Mega-Sena_through_3053_v2.xlsx'
    assert report['cutoff_contest'] == 3053
    assert report['data_sha256'] == sha(data)
    assert report['preregistration_design_sha256'] == prereg['design_sha256']
    assert report['holdout_integrity'] == 'RETROSPECTIVE_TIME_SPLIT_NOT_PRISTINE'
