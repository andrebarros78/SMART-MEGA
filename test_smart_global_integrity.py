from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import smart_continuous_red_team as rt
import smart_global_integrity as gi
import smart_material_deficiency_registry as mdr


def _gate() -> dict:
    items = [
        {'priority': i, 'id': item_id, 'status': 'PROVEN',
         'evidence': [{'type': 'proof', 'file': f'p{i}.json', 'sha256': f'{i:064x}'}]}
        for i, item_id in enumerate(gi.EXPECTED_GATE_IDS, start=1)
    ]
    return {
        'schema': gi.GATE_SCHEMA,
        'target_contest': 3052,
        'mandatory_before_freeze': True,
        'freeze_allowed': True,
        'completion_rule': 'ALL_15_ITEMS_STATUS_PROVEN_WITH_EVIDENCE',
        'governance': {k: True for k in gi.REQUIRED_GATE_GOVERNANCE},
        'items': items,
        'notes': [],
        'progress': {'proven_items': 15, 'total_items': 15, 'remaining_items': 0, 'remaining_ids': []},
    }


def _write_coverage(root: Path, name: str = 'cov.json', source: str = 'a.py') -> Path:
    obj = {'meta': {'branch_coverage': True}, 'files': {source: {'summary': {
        'missing_lines': 0, 'missing_branches': 0, 'covered_lines': 1, 'num_statements': 1,
        'covered_branches': 0, 'num_branches': 0,
    }}}}
    p = root / name
    p.write_text(json.dumps(obj), encoding='utf-8')
    return p


def _write_junit(root: Path, failures: int = 0, errors: int = 0, tests: int = 3, skipped: int = 0) -> Path:
    p = root / 'junit.xml'
    p.write_text(
        f'<testsuites><testsuite tests="{tests}" failures="{failures}" errors="{errors}" skipped="{skipped}"></testsuite></testsuites>',
        encoding='utf-8',
    )
    return p


def _p14_obj() -> dict:
    bindings = [
        {'status': 'PASS', 'source_file': source, 'source_sha256': 'a' * 64,
         'coverage_report_file': f'{source}.coverage.json', 'coverage_report_sha256': 'b' * 64,
         'covered_lines': 1, 'statements': 1, 'covered_branches': 0, 'branches': 0}
        for source in gi.REQUIRED_P14_COVERAGE_SOURCES
    ]
    obj = {
        'schema': gi.P14_SCHEMA,
        'status': 'PASS',
        'promotion_authority': False,
        'independent_of_promotion_decision': True,
        'material_deficiencies': [],
        'checks': {name: True for name in gi.REQUIRED_P14_CHECKS},
        'independence': {'status': 'PASS', 'independent': True, 'static_import_scan': True,
                         'forbidden_dependencies_found': []},
        'coverage': {'status': 'PASS', 'count': len(bindings), 'bindings': bindings},
        'prospective_ledger': {
            'status': 'PASS', 'no_future_leakage': True, 'hash_integrity': True,
            'e_process_recomputed': True,
            'full_champion_comparison': {'all_pairs_recomputed': True},
            'promotion_lineage_comparison': {
                'lineage_recomputed_independently': True, 'lineage_pairs_recomputed': True,
            },
        },
        'deterministic_replay': {'status': 'PASS', 'deterministic': True, 'causal_cutoff_verified': True,
                                 'independent_decision_oracle': {'status':'PASS','verified':True,'production_engine_imported':False}},
    }
    obj['sha256'] = gi.sha256_json(obj)
    return obj


def _write_p14(root: Path, mutator=None) -> Path:
    registry_path = root / mdr.DEFAULT_PATH
    if not registry_path.exists():
        mdr.write_registry(registry_path, mdr.build_registry([]))
    obj = _p14_obj()
    obj['material_deficiency_registry'] = mdr.load_registry(root=root)
    obj['material_deficiencies'] = list(obj['material_deficiency_registry']['open_deficiencies'])
    if mutator is not None:
        mutator(obj)
    obj['sha256'] = gi.sha256_json({k: v for k, v in obj.items() if k != 'sha256'})
    p = root / gi.DEFAULT_P14_PATH
    p.write_text(json.dumps(obj), encoding='utf-8')
    return p


def _red_status() -> dict:
    return {'status': 'PASS', 'report_sha256': 'r' * 64, 'behavioral_hashes_current': True,
            'self_hash_valid': True, 'scenario_count': 10}


def test_policy_and_exact_gate_contract_are_self_consistent():
    policy = gi.policy_snapshot()
    assert policy['schema'] == gi.POLICY_SCHEMA
    assert policy['sha256'] == gi.sha256_json({k: v for k, v in policy.items() if k != 'sha256'})
    assert set(policy['exact_current_coverage_set_required']) == set(gi.REQUIRED_GLOBAL_COVERAGE_SOURCES)
    gate = _gate()
    out = gi.validate_gate_state(gate)
    assert out == {'status': 'PASS', 'item_count': 15, 'pending': [], 'freeze_allowed': True, 'contract_exact': True}
    assert gi.gate_state_sha256(gate) == gi.sha256_json(gi.gate_state_document(gate))


@pytest.mark.parametrize('mutator,match', [
    (lambda g: g.update(schema='BAD'), 'schema'),
    (lambda g: g.update(target_contest=3053), 'target'),
    (lambda g: g.update(mandatory_before_freeze=False), 'mandatory'),
    (lambda g: g.update(completion_rule='BAD'), 'completion'),
    (lambda g: g['governance'].update(no_partial_success=False), 'governance'),
    (lambda g: g.update(items=g['items'][:-1]), 'exactly 15'),
    (lambda g: g['items'][0].update(priority=99), 'priorities'),
    (lambda g: g['items'][0].update(id='WRONG'), 'IDs'),
    (lambda g: g['items'][0].update(evidence={'x': 1}), 'pending'),
    (lambda g: g['items'][0].update(status='PENDING', evidence=[]), 'pending'),
    (lambda g: g.update(freeze_allowed=False), 'freeze_allowed'),
    (lambda g: g.update(progress={'proven_items': 14, 'total_items': 15, 'remaining_items': 1}), 'progress'),
    (lambda g: g['progress'].update(remaining_ids=['P14']), 'remaining IDs'),
])
def test_gate_validation_fails_closed(mutator, match):
    gate = _gate(); mutator(gate)
    with pytest.raises(ValueError, match=match):
        gi.validate_gate_state(gate)


def test_source_hashes_require_every_critical_file(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(gi, 'CRITICAL_SOURCE_FILES', ('a.py', 'b.py'))
    (tmp_path / 'a.py').write_text('a=1\n')
    with pytest.raises(ValueError, match='critical SMART source missing'):
        gi.current_source_hashes(tmp_path)
    (tmp_path / 'b.py').write_text('b=1\n')
    out = gi.current_source_hashes(tmp_path)
    assert set(out) == {'a.py', 'b.py'} and all(len(v) == 64 for v in out.values())


def test_coverage_helper_and_exact_set_fail_closed(tmp_path: Path):
    (tmp_path / 'a.py').write_text('x=1\n')
    cov = _write_coverage(tmp_path)
    row = gi.coverage_summary(tmp_path, cov.name, 'a.py')
    assert row['statements'] == 1
    with pytest.raises(ValueError, match='coverage report missing'):
        gi.coverage_summary(tmp_path, 'none.json', 'a.py')
    obj = json.loads(cov.read_text()); obj['meta']['branch_coverage'] = False; cov.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match='branch coverage disabled'):
        gi.coverage_summary(tmp_path, cov.name, 'a.py')
    _write_coverage(tmp_path); obj = json.loads(cov.read_text()); obj['files'].pop('a.py'); cov.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match='coverage source missing'):
        gi.coverage_summary(tmp_path, cov.name, 'a.py')
    _write_coverage(tmp_path); obj = json.loads(cov.read_text()); obj['files']['a.py']['summary']['missing_lines'] = 1; cov.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match='line/branch'):
        gi.coverage_summary(tmp_path, cov.name, 'a.py')
    _write_coverage(tmp_path); obj = json.loads(cov.read_text()); obj['files']['a.py']['summary']['covered_lines'] = 0; cov.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match='line coverage'):
        gi.coverage_summary(tmp_path, cov.name, 'a.py')
    _write_coverage(tmp_path); obj = json.loads(cov.read_text()); obj['files']['a.py']['summary']['covered_branches'] = 0; obj['files']['a.py']['summary']['num_branches'] = 1; cov.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match='branch coverage'):
        gi.coverage_summary(tmp_path, cov.name, 'a.py')

    original = gi.REQUIRED_GLOBAL_COVERAGE_SOURCES
    try:
        gi.REQUIRED_GLOBAL_COVERAGE_SOURCES = ('a.py',)
        gi._validate_coverage_set([{'source_key': 'a.py'}])
        with pytest.raises(ValueError, match='duplicate'):
            gi._validate_coverage_set([{'source_key': 'a.py'}, {'source_key': 'a.py'}])
        with pytest.raises(ValueError, match='incomplete'):
            gi._validate_coverage_set([])
    finally:
        gi.REQUIRED_GLOBAL_COVERAGE_SOURCES = original


def test_junit_parser_rejects_missing_empty_failed_and_malformed(tmp_path: Path):
    junit = _write_junit(tmp_path)
    assert gi.junit_summary(junit) == {'tests': 3, 'failures': 0, 'errors': 0, 'skipped': 0}
    with pytest.raises(ValueError, match='missing'):
        gi.junit_summary(tmp_path / 'none.xml')
    (tmp_path / 'junit.xml').write_text('<root/>')
    with pytest.raises(ValueError, match='no test suites'):
        gi.junit_summary(junit)
    _write_junit(tmp_path, failures=1)
    with pytest.raises(ValueError, match='not clean'):
        gi.junit_summary(junit)


def test_p14_validation_accepts_only_complete_independent_report(tmp_path: Path):
    _write_p14(tmp_path)
    assert gi.validate_p14_report(tmp_path)['status'] == 'PASS'
    cases = [
        (lambda o: o.update(status='FAIL'), 'not PASS'),
        (lambda o: o.update(promotion_authority=True), 'authority'),
        (lambda o: o.update(material_deficiencies=['x']), 'material deficien'),
        (lambda o: o.update(checks={}), 'checks'),
        (lambda o: o['independence'].update(independent=False), 'independence'),
        (lambda o: o['coverage'].update(bindings=o['coverage']['bindings'][:-1]), 'coverage sources'),
        (lambda o: o['coverage']['bindings'][0].update(status='FAIL'), 'binding'),
        (lambda o: o['prospective_ledger'].update(hash_integrity=False), 'ledger'),
        (lambda o: o['prospective_ledger'].update(full_champion_comparison={}), 'Champion'),
        (lambda o: o['prospective_ledger'].update(promotion_lineage_comparison={}), 'promotion lineage'),
        (lambda o: o['deterministic_replay'].update(deterministic=False), 'deterministic'),
    ]
    for mutator, match in cases:
        _write_p14(tmp_path, mutator)
        with pytest.raises(ValueError, match=match):
            gi.validate_p14_report(tmp_path)
    p = _write_p14(tmp_path)
    obj = json.loads(p.read_text()); obj['sha256'] = '0' * 64; p.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match='self-hash'):
        gi.validate_p14_report(tmp_path)


def test_build_and_verify_global_integrity_detects_staleness(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(gi, 'CRITICAL_SOURCE_FILES', ('a.py',))
    monkeypatch.setattr(gi, 'REQUIRED_GLOBAL_COVERAGE_SOURCES', ('a.py',))
    (tmp_path / 'a.py').write_text('x=1\n')
    red_path = tmp_path / gi.DEFAULT_RED_TEAM_PATH; red_path.write_text('red', encoding='utf-8')
    monkeypatch.setattr(rt, 'verify_latest_report', lambda path=rt.REPORT_PATH, root=Path('.'): _red_status())
    _write_p14(tmp_path); cov = _write_coverage(tmp_path); junit = _write_junit(tmp_path)
    gate = _gate()
    proof = gi.build_global_integrity_proof(tmp_path, gate, junit, [(cov.name, 'a.py')])
    proof_path = tmp_path / gi.DEFAULT_PROOF_PATH; proof_path.write_text(json.dumps(proof), encoding='utf-8')
    gate['global_integrity'] = {'file': proof_path.name, 'sha256': gi.sha256_file(proof_path)}
    gate_path = tmp_path / 'gate.json'; gate_path.write_text(json.dumps(gate), encoding='utf-8')
    out = gi.verify_global_integrity(tmp_path, gate_path, proof_path)
    assert out['status'] == 'PASS' and out['coverage_current'] is True

    (tmp_path / 'a.py').write_text('x=2\n')
    with pytest.raises(ValueError, match='source hashes are stale'):
        gi.verify_global_integrity(tmp_path, gate_path, proof_path)


def test_build_requires_exact_coverage_set(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(gi, 'CRITICAL_SOURCE_FILES', ('a.py',))
    monkeypatch.setattr(gi, 'REQUIRED_GLOBAL_COVERAGE_SOURCES', ('a.py',))
    (tmp_path / 'a.py').write_text('x=1\n')
    (tmp_path / gi.DEFAULT_RED_TEAM_PATH).write_text('red')
    monkeypatch.setattr(rt, 'verify_latest_report', lambda path=rt.REPORT_PATH, root=Path('.'): _red_status())
    _write_p14(tmp_path); junit = _write_junit(tmp_path)
    with pytest.raises(ValueError, match='coverage set'):
        gi.build_global_integrity_proof(tmp_path, _gate(), junit, [])


def test_verify_rejects_tampered_proof_and_missing_gate_binding(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(gi, 'CRITICAL_SOURCE_FILES', ('a.py',))
    monkeypatch.setattr(gi, 'REQUIRED_GLOBAL_COVERAGE_SOURCES', ('a.py',))
    (tmp_path / 'a.py').write_text('x=1\n')
    (tmp_path / gi.DEFAULT_RED_TEAM_PATH).write_text('red')
    monkeypatch.setattr(rt, 'verify_latest_report', lambda path=rt.REPORT_PATH, root=Path('.'): _red_status())
    _write_p14(tmp_path); cov = _write_coverage(tmp_path); junit = _write_junit(tmp_path)
    gate = _gate(); proof = gi.build_global_integrity_proof(tmp_path, gate, junit, [(cov.name, 'a.py')])
    proof_path = tmp_path / gi.DEFAULT_PROOF_PATH; proof_path.write_text(json.dumps(proof))
    gate_path = tmp_path / 'gate.json'; gate_path.write_text(json.dumps(gate))
    with pytest.raises(ValueError, match='gate does not bind'):
        gi.verify_global_integrity(tmp_path, gate_path, proof_path)
    gate['global_integrity'] = {'file': proof_path.name, 'sha256': gi.sha256_file(proof_path)}
    gate_path.write_text(json.dumps(gate))
    obj = json.loads(proof_path.read_text()); obj['status'] = 'FAIL'; proof_path.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match='not PASS'):
        gi.verify_global_integrity(tmp_path, gate_path, proof_path)


def test_global_integrity_remaining_fail_closed_branches(monkeypatch, tmp_path: Path):
    list_json=tmp_path/'list.json'; list_json.write_text('[]',encoding='utf-8')
    with pytest.raises(ValueError, match='JSON object required'):
        gi._load_json(list_json)
    with pytest.raises(ValueError, match='independent audit report missing'):
        gi.validate_p14_report(tmp_path)
    _write_p14(tmp_path, lambda o:o.update(coverage=[]))
    with pytest.raises(ValueError, match='coverage evidence invalid'):
        gi.validate_p14_report(tmp_path)

    monkeypatch.setattr(gi,'CRITICAL_SOURCE_FILES',('a.py',))
    monkeypatch.setattr(gi,'REQUIRED_GLOBAL_COVERAGE_SOURCES',('a.py',))
    (tmp_path/'a.py').write_text('x=1\n')
    red_path=tmp_path/gi.DEFAULT_RED_TEAM_PATH; red_path.write_text('red',encoding='utf-8')
    monkeypatch.setattr(rt,'verify_latest_report',lambda path=rt.REPORT_PATH,root=Path('.'):_red_status())
    _write_p14(tmp_path); cov=_write_coverage(tmp_path); junit=_write_junit(tmp_path); gate=_gate()
    base=gi.build_global_integrity_proof(tmp_path,gate,junit,[(cov.name,'a.py')])
    proof_path=tmp_path/gi.DEFAULT_PROOF_PATH; gate_path=tmp_path/'gate.json'

    def write_variant(mutator, rehash=True):
        obj=copy.deepcopy(base); mutator(obj)
        if rehash: obj['sha256']=gi.sha256_json({k:v for k,v in obj.items() if k!='sha256'})
        proof_path.write_text(json.dumps(obj),encoding='utf-8')
        g=copy.deepcopy(gate); g['global_integrity']={'file':proof_path.name,'sha256':gi.sha256_file(proof_path)}
        gate_path.write_text(json.dumps(g),encoding='utf-8')
        return g

    cases=[
      (lambda o:o.update(sha256='0'*64),False,'self-hash invalid'),
      (lambda o:o.update(gate_state_sha256='0'*64),True,'gate state changed'),
      (lambda o:o.update(coverage={}),True,'coverage evidence missing'),
      (lambda o:o['coverage'][0].update(report_sha256='0'*64),True,'coverage evidence is stale'),
      (lambda o:o['red_team'].update(file_sha256='0'*64),True,'Red Team evidence is stale'),
      (lambda o:o.update(independent_audit={}),True,'independent audit evidence is stale'),
      (lambda o:o['full_regression'].update(junit_sha256='0'*64),True,'regression evidence is stale'),
      (lambda o:o['full_regression'].update(tests=o['full_regression']['tests']+1),True,'regression summary mismatch'),
    ]
    for mutator,rehash,match in cases:
        write_variant(mutator,rehash)
        with pytest.raises(ValueError,match=match):
            gi.verify_global_integrity(tmp_path,gate_path,proof_path)


def test_global_integrity_final_missing_proof_and_malformed_junit(tmp_path: Path):
    malformed=tmp_path/'malformed.xml'; malformed.write_text('<testsuites><testsuite>',encoding='utf-8')
    with pytest.raises(ValueError,match='malformed'):
        gi.junit_summary(malformed)
    gate=_gate(); gate_path=tmp_path/'gate.json'; gate_path.write_text(json.dumps(gate),encoding='utf-8')
    with pytest.raises(ValueError,match='global integrity proof missing'):
        gi.verify_global_integrity(tmp_path,gate_path,tmp_path/'missing-proof.json')
