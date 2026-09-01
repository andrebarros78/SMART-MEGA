from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import smart_continuous_red_team as rt


def _valid_report(root: Path) -> dict:
    scenarios = {name: {'pass': True} for name in rt.EXPECTED_SCENARIOS}
    report = {
        'schema': rt.SCHEMA,
        'status': 'PASS',
        'all_checks_pass': True,
        'checks': {name: True for name in rt.EXPECTED_SCENARIOS},
        'failed': [],
        'base_seed': rt.BASE_SEED,
        'behavioral_hashes': rt.current_behavior_hashes(root),
        'red_team_module_sha256': rt.sha256_file(root / 'smart_continuous_red_team.py'),
        'continuous_policy': 'test',
        'prospective_predictive_claim': False,
        'scenarios': scenarios,
    }
    report['sha256'] = rt.sha256_json(report)
    return report


def _resign(report: dict) -> None:
    report.pop('sha256', None)
    report['sha256'] = rt.sha256_json(report)


def test_behavioral_hash_set_includes_all_late_governance_layers():
    required = {
        'smart_sequential_prospective_proof.py',
        'smart_promotion_gate.py',
        'smart_independent_audit.py',
        'smart_evidence_only_promotion.py',
    }
    assert required.issubset(set(rt.BEHAVIORAL_FILES))


def test_report_self_hash_and_internal_consistency_are_fail_closed(tmp_path: Path):
    root = Path(__file__).resolve().parent
    report = _valid_report(root)
    rt._validate_report_document(report)

    bad = copy.deepcopy(report); bad['continuous_policy'] = 'tampered'
    with pytest.raises(ValueError, match='self-hash mismatch'):
        rt._validate_report_document(bad)

    bad = copy.deepcopy(report); bad['sha256'] = 'short'
    with pytest.raises(ValueError, match='self-hash missing'):
        rt._validate_report_document(bad)

    bad = copy.deepcopy(report); bad['scenarios'].pop(rt.EXPECTED_SCENARIOS[0]); _resign(bad)
    with pytest.raises(ValueError, match='scenario set mismatch'):
        rt._validate_report_document(bad)

    bad = copy.deepcopy(report); bad['checks'].pop(rt.EXPECTED_SCENARIOS[0]); _resign(bad)
    with pytest.raises(ValueError, match='checks set mismatch'):
        rt._validate_report_document(bad)

    bad = copy.deepcopy(report); bad['scenarios'][rt.EXPECTED_SCENARIOS[0]] = []; _resign(bad)
    with pytest.raises(ValueError, match='scenario invalid'):
        rt._validate_report_document(bad)

    bad = copy.deepcopy(report); bad['checks'][rt.EXPECTED_SCENARIOS[0]] = False; _resign(bad)
    with pytest.raises(ValueError, match='checks do not match'):
        rt._validate_report_document(bad)

    bad = copy.deepcopy(report); bad['failed'] = ['iid']; _resign(bad)
    with pytest.raises(ValueError, match='failed list mismatch'):
        rt._validate_report_document(bad)

    bad = copy.deepcopy(report); name = rt.EXPECTED_SCENARIOS[0]; bad['scenarios'][name]['pass'] = False; bad['checks'][name] = False; bad['failed'] = [name]; _resign(bad)
    with pytest.raises(ValueError, match='contains a failed scenario'):
        rt._validate_report_document(bad)


def test_write_and_verify_report_reject_missing_stale_or_wrong_module_hash(tmp_path: Path):
    root = Path(__file__).resolve().parent
    report = _valid_report(root)
    path = tmp_path / 'red.json'
    file_hash = rt.write_report(report, path)
    assert len(file_hash) == 64
    verified = rt.verify_latest_report(path, root)
    assert verified['status'] == 'PASS'
    assert verified['self_hash_valid'] is True
    assert verified['scenario_count'] == len(rt.EXPECTED_SCENARIOS)

    with pytest.raises(ValueError, match='missing'):
        rt.verify_latest_report(tmp_path / 'none.json', root)

    stale = copy.deepcopy(report); stale['behavioral_hashes']['smart_v2_engine.py'] = '0' * 64; _resign(stale); path.write_text(json.dumps(stale), encoding='utf-8')
    with pytest.raises(ValueError, match='stale'):
        rt.verify_latest_report(path, root)

    wrong = copy.deepcopy(report); wrong['red_team_module_sha256'] = '0' * 64; _resign(wrong); path.write_text(json.dumps(wrong), encoding='utf-8')
    with pytest.raises(ValueError, match='module hash mismatch'):
        rt.verify_latest_report(path, root)


def test_current_behavior_hashes_fails_if_required_component_is_missing(tmp_path: Path):
    with pytest.raises(ValueError, match='missing behavioral file'):
        rt.current_behavior_hashes(tmp_path)


def test_red_team_report_document_and_cli_fail_closed(monkeypatch, tmp_path):
    import smart_continuous_red_team as rt
    import pytest
    with pytest.raises(ValueError, match='must be an object'):
        rt._validate_report_document(None)
    bad={'schema':rt.SCHEMA,'status':'FAIL','all_checks_pass':False}
    with pytest.raises(ValueError, match='not passing'):
        rt._validate_report_document(bad)
    failed={'schema':rt.SCHEMA,'status':'FAIL','all_checks_pass':False,'failed':['iid'],'checks':{'iid':False},'scenarios':{}}
    monkeypatch.setattr(rt,'run_suite',lambda root: failed)
    monkeypatch.setattr(rt,'write_report',lambda report,path: '0'*64)
    with pytest.raises(SystemExit) as exc:
        rt.main()
    assert exc.value.code==1
