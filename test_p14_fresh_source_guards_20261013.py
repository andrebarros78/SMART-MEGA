"""Current-source P14 causal evidence and fail-closed branch regressions."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import smart_independent_audit as ia
from test_smart_independent_audit import _pair_fixture, _dataset


def test_relative_sha_and_evidence_rejects_external_paths(tmp_path):
    source = Path(ia.__file__).with_name('AGENTS.md')
    assert ia.sha256_file(Path('AGENTS.md')) == hashlib.sha256(source.read_bytes()).hexdigest()
    root = tmp_path / 'root'; root.mkdir()
    foreign = tmp_path / 'outside.txt'; foreign.write_text('evidence', encoding='utf-8')
    with pytest.raises(ValueError, match='external absolute path denied'):
        ia._resolve_hash_bound_evidence(root, foreign, ia.sha256_file(foreign), 'test')
    (root / 'escape.txt').symlink_to(foreign)
    with pytest.raises(ValueError, match='escapes project root'):
        ia._resolve_hash_bound_evidence(root, 'escape.txt', ia.sha256_file(foreign), 'test')


def test_historical_hash_resolution_ambiguity_and_recovery(tmp_path, monkeypatch):
    root = tmp_path / 'canonical'; root.mkdir()
    name = 'source.txt'
    (root / name).mkdir()  # directory is not an evidence file
    with pytest.raises(ValueError, match='missing'):
        ia._resolve_historical_evidence_by_hash(root, name, 'a'*64, 'proof')
    (root / name).rmdir()
    outside = tmp_path / name; outside.write_text('safe', encoding='utf-8')
    (root / name).symlink_to(outside)
    with pytest.raises(ValueError, match='escapes project root'):
        ia._resolve_historical_evidence_by_hash(root, name, ia.sha256_file(outside), 'proof')
    (root / name).unlink()
    live = root / 'live'; live.mkdir()
    f = live / name; f.write_text('equal', encoding='utf-8')
    old_sha = ia.sha256_file(f)
    original = ia.sha256_file
    def raises_oserror(path):
        if Path(path).name == name: raise OSError('transient read failure')
        return original(path)
    monkeypatch.setattr(ia, 'sha256_file', raises_oserror)
    with pytest.raises(ValueError, match='missing'):
        ia._resolve_historical_evidence_by_hash(root, name, old_sha, 'proof')
    monkeypatch.setattr(ia, 'sha256_file', original)
    archive = root / 'SMART_STATE_ARCHIVE'; archive.mkdir()
    (archive / name).write_text('equal', encoding='utf-8')
    assert ia._resolve_historical_evidence_by_hash(root, name, old_sha, 'proof') == f
    second = root / 'live2'; second.mkdir()
    (second / name).write_text('equal', encoding='utf-8')
    with pytest.raises(ValueError, match='ambiguous'):
        ia._resolve_historical_evidence_by_hash(root, name, old_sha, 'proof')
    (second / name).unlink();(archive / name).unlink()
    assert ia._resolve_historical_evidence_by_hash(root, name, '0'*64, 'legacy', allow_legacy_mismatch=True) == f


def test_project_oracle_source_and_import_isolation(tmp_path, monkeypatch):
    project = tmp_path / 'smart_independent_oracle.py'
    project.write_text('value=1\n', encoding='utf-8')
    with pytest.raises(ValueError, match='oracle project/runtime source mismatch'):
        ia.audit_independence(tmp_path)
    # A matching project oracle takes the verified local branch.
    project.write_bytes(Path(ia.__file__).with_name('smart_independent_oracle.py').read_bytes())
    assert ia.audit_independence(tmp_path)['status'] == 'PASS'
    project.write_text('import smart_untrusted\n', encoding='utf-8')
    original_hash = ia.sha256_source_file
    def controlled_hash(path):
        if Path(path).name == 'smart_independent_oracle.py': return 'f'*64
        return original_hash(path)
    monkeypatch.setattr(ia, 'sha256_source_file', controlled_hash)
    with pytest.raises(ValueError, match='imports project implementation'):
        ia.audit_independence(tmp_path)
    project.unlink()
    real_is_file = Path.is_file
    def selectively_missing(path):
        if Path(path).name == 'smart_independent_oracle.py': return False
        return real_is_file(path)
    monkeypatch.setattr(Path, 'is_file', selectively_missing)
    with pytest.raises(ValueError, match='oracle source missing'):
        ia.audit_independence(tmp_path)


@pytest.mark.parametrize('label,expected', [
    ('frozen artifact','frozen artifact hash mismatch'),
    ('frozen input data','frozen input data hash mismatch'),
    ('result data','result data missing'),
])
def test_atomic_evidence_validation_against_toctou(tmp_path, monkeypatch,label,expected):
    ledger, pre, result, freeze, state, fr, ad, actual = _pair_fixture(tmp_path)
    original = ia._resolve_audit_evidence
    wrong = tmp_path / 'wrong-evidence.json'; wrong.write_text('{}', encoding='utf-8')
    missing = tmp_path / 'gone.txt'
    def resolve(root, value, digest, requested, **kw):
        if requested == label: return missing if label == 'result data' else wrong
        return original(root,value,digest,requested,**kw)
    monkeypatch.setattr(ia, '_resolve_audit_evidence', resolve)
    with pytest.raises(ValueError, match=expected):
        ia.audit_prospective_ledger(tmp_path,ledger)


def test_replay_requires_independent_oracle(tmp_path,monkeypatch):
    data=tmp_path/'causal.xlsx'; _dataset(12).to_excel(data,index=False)
    monkeypatch.setattr(ia, 'validate_prediction_snapshot', lambda prediction: {'verified':False})
    with pytest.raises(ValueError, match='independent decision oracle could not verify replay'):
        ia.audit_deterministic_replay(tmp_path,data,13,start=5)


def test_oracle_pair_mismatch_is_rejected_at_aggregate_gate(tmp_path, monkeypatch):
    ledger, *_ = _pair_fixture(tmp_path)
    monkeypatch.setattr(ia, 'validate_frozen_decision', lambda frozen: {'status': 'FAIL', 'verified': False})
    with pytest.raises(ValueError, match='independent decision oracle did not verify every applicable frozen prediction'):
        ia.audit_prospective_ledger(tmp_path, ledger)


@pytest.mark.parametrize('field,value,expected', [
    ('advantage_hits', 0, 'advantage_hits is internally inconsistent'),
    ('cumulative_regret', 1, 'cumulative_regret is internally inconsistent'),
    ('lineage_pair_count', 0, 'eligible lineage pair count must equal n'),
])
def test_p15_p13_arithmetic_fails_closed(field, value, expected):
    import smart_evidence_only_promotion as p15
    from test_smart_evidence_only_promotion import _p13_eligible
    case = _p13_eligible()
    # Ensure a conflicting value regardless of the fixture's original value.
    case[field] = int(case[field]) + (1 if value == 0 else 2)
    with pytest.raises(ValueError, match=expected):
        p15._validated_p13(case)


def test_p15_gate_rejects_invalid_target_type_and_integrity_bad_digest():
    import smart_evidence_only_promotion as p15
    from test_smart_evidence_only_promotion import _gate, _integrity
    gate = _gate(); gate['target_contest'] = True
    assert 'implementation_gate_target_invalid' in p15._gate_evidence(gate)[0]
    integrity = _integrity(); integrity['proof_file_sha256'] = 'z' * 64
    assert 'global_integrity_proof_hash_invalid' in p15._global_integrity_evidence(integrity)[0]


def test_p15_independent_oracle_must_be_verified():
    import smart_evidence_only_promotion as p15
    from test_smart_evidence_only_promotion import _audit, _p13_eligible
    audit = _audit()
    audit['deterministic_replay']['independent_decision_oracle'] = {'verified': False, 'production_engine_imported': False}
    assert 'independent_audit_decision_oracle_not_verified' in p15._audit_evidence(audit, _p13_eligible())[0]


def test_champion_cutoff_invalid_date_fails_closed(tmp_path, monkeypatch):
    import pandas as pd
    import smart_champion_challenger as cc
    monkeypatch.setattr(cc.pd, 'read_excel', lambda *a, **k: pd.DataFrame({'Data do Sorteio':['invalid-date']}))
    with pytest.raises(ValueError, match='invalid cutoff draw date'):
        cc.source_cutoff_timestamp(tmp_path / 'invalid.xlsx')


def test_champion_freeze_requires_supersede_and_accepts_bound_tuning(tmp_path, monkeypatch):
    import smart_champion_challenger as cc
    from test_smart_coverage_governance import draws, make_excel
    data=make_excel(tmp_path/'data.xlsx', draws(47,8),start_contest=38)
    freeze=tmp_path/'freeze.json'; ledger=tmp_path/'ledger.json'; state=tmp_path/'state.json'
    monkeypatch.setattr(cc, 'load_ai_hyperparameter_authority',lambda *a,**k: {'sha256':'c'*64,'effective_candidate':{'eta':0.05,'redundancy_threshold':0.6,'meta_strength':0.1}})
    absolute_registry=Path(cc.__file__).resolve().with_name('SMART_SIGNAL_EXPANSION_REGISTRY.json')
    first=cc.freeze_champion_challenger(data,46,freeze,ledger,state,start=4,enforce_temporal_guard=False,expansion_registry_path=absolute_registry)
    assert first['status']=='FROZEN'
    with pytest.raises(ValueError, match='explicit pre-result supersede authorization required'):
        cc.freeze_champion_challenger(data,46,freeze,ledger,state,start=5,enforce_temporal_guard=False,expansion_registry_path=absolute_registry)


def test_champion_unexpected_fine_tuning_error_is_not_silenced(tmp_path, monkeypatch):
    import smart_champion_challenger as cc
    from test_smart_coverage_governance import draws, make_excel
    data=make_excel(tmp_path/'data.xlsx', draws(48,8),start_contest=38)
    monkeypatch.setattr(cc, 'load_ai_hyperparameter_authority',lambda *a,**k: (_ for _ in ()).throw(ValueError('malformed fine tuning authority')))
    with pytest.raises(ValueError, match='malformed fine tuning authority'):
        cc.freeze_champion_challenger(data,46,tmp_path/'freeze.json',tmp_path/'ledger.json',tmp_path/'state.json',start=10,enforce_temporal_guard=False)
