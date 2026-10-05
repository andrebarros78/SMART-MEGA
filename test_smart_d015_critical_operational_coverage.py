from __future__ import annotations

import hashlib
import json
import runpy
import shutil as std_shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

import smart_canonical_history_advance as cha
import smart_global_integrity as gi
import smart_operator as op
import smart_product_certification as pc
from test_smart_canonical_history_advance import _fixture, _frame, _sha


def test_d015_global_integrity_covers_operational_authority():
    assert 'smart_operator.py' in gi.REQUIRED_GLOBAL_COVERAGE_SOURCES
    assert 'smart_canonical_history_advance.py' in gi.REQUIRED_GLOBAL_COVERAGE_SOURCES
    assert 'smart_operator.py' in gi.CRITICAL_SOURCE_FILES
    assert 'smart_canonical_history_advance.py' in gi.CRITICAL_SOURCE_FILES
    assert len(gi.REQUIRED_GLOBAL_COVERAGE_SOURCES) == 23


def test_cha_helper_fail_closed_branches(tmp_path: Path):
    with pytest.raises(ValueError, match='escapes project root'):
        cha._under_root(tmp_path / 'root', tmp_path / 'outside')
    with pytest.raises(ValueError, match='lacks Concurso'):
        cha._contest_sequence(pd.DataFrame({'X': [1]}))
    with pytest.raises(ValueError, match='duplicate'):
        cha._contest_sequence(pd.DataFrame({'Concurso': [1, 1, 2]}))
    with pytest.raises(ValueError, match='contiguous'):
        cha._contest_sequence(pd.DataFrame({'Concurso': [1, 3]}))
    with pytest.raises(ValueError, match='contiguous'):
        cha._contest_sequence(pd.DataFrame({'Concurso': []}))
    a = pd.DataFrame({'A': [1]}); b = pd.DataFrame({'A': [1, 2]})
    assert cha._frames_value_equal(a, b) is False
    assert cha._frames_value_equal(a, pd.DataFrame({'B': [1]})) is False
    assert cha._frames_value_equal(a, pd.DataFrame({'A': [2]})) is False
    with pytest.raises(ValueError, match='missing draw columns'):
        cha._numbers(pd.DataFrame({'Concurso': [1]}), 1)
    dup_rows = pd.DataFrame([
        {'Concurso': 1, **{f'Bola{i}': i for i in range(1, 7)}},
        {'Concurso': 1, **{f'Bola{i}': i + 6 for i in range(1, 7)}},
    ])
    with pytest.raises(ValueError, match='exactly once'):
        cha._numbers(dup_rows, 1)
    bad_nums = pd.DataFrame([{'Concurso': 1, **{f'Bola{i}': 1 for i in range(1, 7)}}])
    with pytest.raises(ValueError, match='numbers invalid'):
        cha._numbers(bad_nums, 1)


@pytest.mark.parametrize('active,match', [
    (None, 'active epoch authority invalid'),
    ({'project': 'SMART-MEGA', 'target_contest': 1, 'state_paths': {'ledger': 'x'}}, 'target invalid'),
    ({'project': 'SMART-MEGA', 'target_contest': 4}, 'ledger path missing'),
])
def test_cha_active_authority_guards(tmp_path: Path, active, match):
    with pytest.raises(ValueError, match=match):
        cha.advance_completed_epoch(tmp_path, active)


def test_cha_requires_exactly_one_adjudication(tmp_path: Path, monkeypatch):
    canonical, through, result, ledger, active = _fixture(tmp_path, monkeypatch)
    ledger['events'] = []
    monkeypatch.setattr(cha, 'validate_target_sequence', lambda *a, **k: {'valid': True, 'adjudicated': True})
    with pytest.raises(ValueError, match='exactly one adjudication'):
        cha.advance_completed_epoch(tmp_path, active)


def test_cha_rejects_invalid_actual_numbers(tmp_path: Path, monkeypatch):
    canonical, through, result, ledger, active = _fixture(tmp_path, monkeypatch)
    ledger['events'][0]['actual_numbers'] = [1, 1, 2, 3, 4, 5]
    with pytest.raises(ValueError, match='actual numbers invalid'):
        cha.advance_completed_epoch(tmp_path, active)


def test_cha_missing_through_and_canonical_and_schema_guards(tmp_path: Path, monkeypatch):
    canonical, through, result, ledger, active = _fixture(tmp_path, monkeypatch)
    through.unlink()
    with pytest.raises(FileNotFoundError, match='through-dataset missing'):
        cha.advance_completed_epoch(tmp_path, active)

    canonical, through, result, ledger, active = _fixture(tmp_path / 'c2', monkeypatch)
    canonical.unlink()
    with pytest.raises(FileNotFoundError):
        cha.advance_completed_epoch(tmp_path / 'c2', active)

    base = tmp_path / 'c3'
    canonical, through, result, ledger, active = _fixture(base, monkeypatch)
    df = pd.read_excel(through); df['EXTRA'] = 1; df.to_excel(through, index=False)
    with pytest.raises(ValueError, match='column schemas differ'):
        cha.advance_completed_epoch(base, active)


def test_cha_through_sequence_and_prefix_guards(tmp_path: Path, monkeypatch):
    base = tmp_path / 'a'
    canonical, through, result, ledger, active = _fixture(base, monkeypatch)
    df = pd.read_excel(through).iloc[:-1].copy(); df.to_excel(through, index=False)
    with pytest.raises(ValueError, match='does not end'):
        cha.advance_completed_epoch(base, active)

    base = tmp_path / 'b'
    canonical, through, result, ledger, active = _fixture(base, monkeypatch)
    df = pd.read_excel(canonical).iloc[1:].copy(); df.to_excel(canonical, index=False)
    with pytest.raises(ValueError, match='exact through-dataset prefix'):
        cha.advance_completed_epoch(base, active)


def test_cha_already_advanced_hash_mismatch(tmp_path: Path, monkeypatch):
    canonical, through, result, ledger, active = _fixture(tmp_path, monkeypatch)
    # Make the canonical contest sequence current but bytes different from the through authority.
    df = pd.read_excel(through).copy(); df.to_excel(canonical, index=False)
    with canonical.open('ab') as handle: handle.write(b'nonsemantic-byte-difference')
    with pytest.raises(ValueError, match='already-advanced canonical history differs'):
        cha.advance_completed_epoch(tmp_path, active)


def test_cha_preexisting_valid_and_corrupt_backup_paths(tmp_path: Path, monkeypatch):
    base = tmp_path / 'ok'
    canonical, through, result, ledger, active = _fixture(base, monkeypatch)
    before = _sha(canonical); archive = base / 'SMART_STATE_ARCHIVE' / 'canonical-result-store'; archive.mkdir(parents=True)
    backup = archive / f'Mega-Sena.{before}.xlsx'; std_shutil.copy2(canonical, backup)
    out = cha.advance_completed_epoch(base, active)
    assert out['status'] == 'PASS'

    base = tmp_path / 'bad'
    canonical, through, result, ledger, active = _fixture(base, monkeypatch)
    before = _sha(canonical); archive = base / 'SMART_STATE_ARCHIVE' / 'canonical-result-store'; archive.mkdir(parents=True)
    (archive / f'Mega-Sena.{before}.xlsx').write_bytes(b'corrupt')
    with pytest.raises(RuntimeError, match='backup hash mismatch'):
        cha.advance_completed_epoch(base, active)


def test_cha_temporary_verification_and_hash_guards(tmp_path: Path, monkeypatch):
    base = tmp_path / 'verify'
    canonical, through, result, ledger, active = _fixture(base, monkeypatch)
    real_copyfile = cha.shutil.copyfile
    def corrupt_copy(src, dst):
        real_copyfile(src, dst)
        df = pd.read_excel(dst); df.loc[0, 'Bola1'] = 60; df.to_excel(dst, index=False)
        return dst
    monkeypatch.setattr(cha.shutil, 'copyfile', corrupt_copy)
    with pytest.raises(RuntimeError, match='temporary canonical history verification failed'):
        cha.advance_completed_epoch(base, active)
    monkeypatch.setattr(cha.shutil, 'copyfile', real_copyfile)

    base = tmp_path / 'hash'
    canonical, through, result, ledger, active = _fixture(base, monkeypatch)
    real_sha = cha.sha256_file
    def bad_tmp_sha(path):
        p = Path(path)
        if '.tmp.xlsx' in p.name:
            return '0' * 64
        return real_sha(p)
    monkeypatch.setattr(cha, 'sha256_file', bad_tmp_sha)
    with pytest.raises(RuntimeError, match='temporary canonical history hash mismatch'):
        cha.advance_completed_epoch(base, active)


def test_cha_post_replace_hash_and_postcondition_guards(tmp_path: Path, monkeypatch):
    base = tmp_path / 'hash'
    canonical, through, result, ledger, active = _fixture(base, monkeypatch)
    real_replace = cha.os.replace
    def tamper_after_replace(src, dst):
        real_replace(src, dst)
        if Path(dst).name == 'Mega-Sena.xlsx':
            with Path(dst).open('ab') as handle: handle.write(b'X')
    monkeypatch.setattr(cha.os, 'replace', tamper_after_replace)
    with pytest.raises(RuntimeError, match='advance hash mismatch'):
        cha.advance_completed_epoch(base, active)
    monkeypatch.setattr(cha.os, 'replace', real_replace)

    base = tmp_path / 'post'
    canonical, through, result, ledger, active = _fixture(base, monkeypatch)
    real_numbers = cha._numbers; calls = {'n': 0}
    def wrong_final(frame, target):
        calls['n'] += 1
        values = real_numbers(frame, target)
        return values if calls['n'] == 1 else [1, 2, 3, 4, 5, 6]
    monkeypatch.setattr(cha, '_numbers', wrong_final)
    with pytest.raises(RuntimeError, match='postcondition failed'):
        cha.advance_completed_epoch(base, active)


def test_operator_target_sequence_and_history_guards(tmp_path: Path):
    for target in (True, '4', 1):
        with pytest.raises(ValueError, match='positive contest integer'):
            op.validate_target_sequence([1, 2, 3], target)
    with pytest.raises(ValueError, match='empty'):
        op.validate_target_sequence([], 4)
    with pytest.raises(ValueError, match='duplicates'):
        op.validate_target_sequence([1, 1, 2], 3)
    with pytest.raises(ValueError, match='gaps'):
        op.validate_target_sequence([1, 3], 4)
    with pytest.raises(ValueError, match='requires canonical history'):
        op.validate_target_sequence([1, 2], 4)
    assert op.validate_target_sequence([1, 2, 3], 4)['cutoff_contest'] == 3

    with pytest.raises(FileNotFoundError):
        op.validate_target_against_history(tmp_path / 'missing.xlsx', 4)
    bad = tmp_path / 'bad.xlsx'; pd.DataFrame({'X': [1]}).to_excel(bad, index=False)
    with pytest.raises(ValueError, match='lacks Concurso'):
        op.validate_target_against_history(bad, 4)
    good = tmp_path / 'good.xlsx'; pd.DataFrame({'Concurso': [1, 2, 3]}).to_excel(good, index=False)
    out = op.validate_target_against_history(good, 4)
    assert out['row_count'] == 3 and len(out['data_sha256']) == 64


def test_operator_archive_active_all_paths(tmp_path: Path):
    active = tmp_path / 'SMART_ACTIVE_EPOCH.json'
    assert op._archive_active(tmp_path, active) is None
    active.write_text('{"x":1}', encoding='utf-8')
    digest = op._archive_active(tmp_path, active)
    assert digest == op.sha256_file(active)
    # Existing valid archive path.
    assert op._archive_active(tmp_path, active) == digest
    archive = tmp_path / 'SMART_STATE_ARCHIVE' / f'operator_active_epoch_{digest}.json'
    archive.write_text('corrupt', encoding='utf-8')
    with pytest.raises(RuntimeError, match='archive hash mismatch'):
        op._archive_active(tmp_path, active)


def _patch_prepare_common(monkeypatch, root: Path):
    monkeypatch.setattr(pc, 'verify_product_certification', lambda *a, **k: {'sha256': 'c' * 64})
    monkeypatch.setattr(op, 'resolve_target_schedule', lambda root, target: {'target_contest': int(target), 'scheduled_datetime': '2099-01-01T20:00:00-03:00'})
    monkeypatch.setattr(op, 'assert_pre_draw_window', lambda schedule: {'status': 'PASS', 'target_contest': schedule['target_contest']})
    monkeypatch.setattr(op, 'seed_ledger_from_canonical', lambda canonical, destination: {'status': 'SEEDED', 'sha256': 'd' * 64, 'event_count': 7})
    monkeypatch.setattr(op, 'write_active_epoch', lambda path, payload: payload)
    monkeypatch.setattr(op, '_require_next_cycle_authority', lambda root, target: {'status': 'AUTHORIZED', 'sha256': 'a' * 64})
    monkeypatch.setattr(op, '_consume_next_cycle_authority', lambda root, target, epoch_id: {'status': 'CONSUMED_FOR_PREPARE', 'sha256': 'b' * 64, 'prepared_epoch_id': epoch_id})
    pd.DataFrame({'Concurso': [1, 2, 3]}).to_excel(root / 'Mega-Sena.xlsx', index=False)


def test_operator_prepare_no_active_success(tmp_path: Path, monkeypatch):
    _patch_prepare_common(monkeypatch, tmp_path)
    out = op.prepare_operation(tmp_path, 4)
    assert out['status'] == 'READY_TO_FREEZE'
    assert out['prior_epoch_reconciliation'] is None
    assert out['canonical_result_store_reconciliation'] is None
    assert out['ledger_seed']['event_count'] == 7
    epochs = list((tmp_path / 'runtime' / 'learning_epochs').iterdir())
    assert len(epochs) == 1 and (epochs[0] / 'Mega-Sena_cutoff_3.xlsx').is_file()


def test_operator_prepare_existing_without_supersede_and_unresolved(tmp_path: Path, monkeypatch):
    _patch_prepare_common(monkeypatch, tmp_path)
    active_path = tmp_path / op.ACTIVE_PATH; active_path.write_text('{}', encoding='utf-8')
    with pytest.raises(FileExistsError, match='already exists'):
        op.prepare_operation(tmp_path, 4)

    previous = {'target_contest': 3, 'state_paths': {'ledger': 'runtime/prev/SMART_SIGNAL_LEDGER.json'}}
    monkeypatch.setattr(op, 'verify_active_epoch', lambda path: previous)
    monkeypatch.setattr(op, 'load_ledger', lambda path: {'events': []})
    with pytest.raises(ValueError, match='unresolved prospective attempt'):
        op.prepare_operation(tmp_path, 4, supersede_existing=True)


def test_operator_prepare_completed_supersede_success(tmp_path: Path, monkeypatch):
    _patch_prepare_common(monkeypatch, tmp_path)
    active_path = tmp_path / op.ACTIVE_PATH; active_path.write_text('{"old":1}', encoding='utf-8')
    previous = {'target_contest': 3, 'state_paths': {'ledger': 'runtime/prev/SMART_SIGNAL_LEDGER.json'}}
    monkeypatch.setattr(op, 'verify_active_epoch', lambda path: previous)
    monkeypatch.setattr(op, 'load_ledger', lambda path: {'events': [{'event_type': 'ADJUDICATION', 'target_contest': 3}]})
    monkeypatch.setattr(op, 'reconcile_completed_epoch_ledger', lambda *a, **k: {'status': 'PASS'})
    monkeypatch.setattr(op, 'advance_completed_epoch', lambda *a, **k: {'status': 'ALREADY_CURRENT'})
    out = op.prepare_operation(tmp_path, 4, supersede_existing=True)
    assert out['prior_epoch_reconciliation']['status'] == 'PASS'
    assert out['canonical_result_store_reconciliation']['status'] == 'ALREADY_CURRENT'
    assert out['active_epoch']['supersedes_active_epoch_sha256'] is not None


def test_operator_prepare_snapshot_hash_guard(tmp_path: Path, monkeypatch):
    _patch_prepare_common(monkeypatch, tmp_path)
    real_copy2 = op.shutil.copy2
    def corrupt_snapshot(src, dst):
        real_copy2(src, dst)
        with Path(dst).open('ab') as handle: handle.write(b'X')
        return dst
    monkeypatch.setattr(op.shutil, 'copy2', corrupt_snapshot)
    with pytest.raises(RuntimeError, match='immutable history snapshot hash mismatch'):
        op.prepare_operation(tmp_path, 4)


def test_operator_freeze_all_short_circuit_paths(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(op, 'verify_active_epoch', lambda p: {'operator_selected_target': False, 'target_contest': 4})
    with pytest.raises(ValueError, match='does not match'):
        op.freeze_operation(tmp_path, 4)
    monkeypatch.setattr(op, 'verify_active_epoch', lambda p: {'operator_selected_target': True, 'target_contest': 5})
    with pytest.raises(ValueError, match='does not match'):
        op.freeze_operation(tmp_path, 4)
    monkeypatch.setattr(op, 'verify_active_epoch', lambda p: {'operator_selected_target': True, 'target_contest': 4})
    monkeypatch.setattr(op, 'run_full_process', lambda root, manual_generation_authorized=False: {'status': 'PASS', 'manual': manual_generation_authorized})
    assert op.freeze_operation(tmp_path, 4) == {'status': 'PASS', 'manual': True}


def test_operator_adjudicate_status_and_main_paths(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(op, 'verify_active_epoch', lambda p: {'target_contest': 5, 'state_paths': {'ledger': 'ledger.json'}})
    with pytest.raises(ValueError, match='does not match'):
        op.adjudicate_operation(tmp_path, 4, 'result.xlsx')
    monkeypatch.setattr(op, 'verify_active_epoch', lambda p: {'target_contest': 4, 'state_paths': {'ledger': 'ledger.json'}})
    monkeypatch.setattr(op, 'resolve_current_epoch', lambda root: {'status': 'FROZEN', 'freeze_authority_present': True, 'target_contest': 4, 'generation_proof_valid': True, 'freeze_sha256': 'a' * 64})
    monkeypatch.setattr(op, 'load_ledger', lambda path: {'events': []})
    monkeypatch.setattr(op, 'active_freeze', lambda ledger, target: {'freeze_sha256': 'a' * 64})
    monkeypatch.setattr(op, 'adjudicate', lambda result, target, ledger: {'status': 'PASS', 'target': target})
    import smart_sequential_prospective_proof as sequential
    monkeypatch.setattr(sequential, 'complete_post_result_learning', lambda *a, **k: {'status': 'TEST_COMPLETE'})
    assert op.adjudicate_operation(tmp_path, 4, 'result.xlsx')['status'] == 'PASS'

    empty = tmp_path / 'empty'; empty.mkdir()
    assert op.status(empty)['product_certification'] is None and op.status(empty)['active_operation'] is None
    full = tmp_path / 'full'; full.mkdir(); (full / 'SMART_PRODUCT_CERTIFICATION.json').write_text('{"status":"X"}', encoding='utf-8'); (full / op.ACTIVE_PATH).write_text('{}', encoding='utf-8')
    monkeypatch.setattr(op, 'verify_active_epoch', lambda p: {'target_contest': 4})
    st = op.status(full); assert st['product_certification']['status'] == 'X' and st['active_operation']['target_contest'] == 4

    monkeypatch.setattr(op, 'status', lambda root: {'action': 'status'})
    monkeypatch.setattr(op, 'prepare_operation', lambda root, target, supersede_existing=False: {'action': 'prepare', 'supersede': supersede_existing})
    monkeypatch.setattr(op, 'freeze_operation', lambda root, target: {'action': 'freeze'})
    monkeypatch.setattr(op, 'adjudicate_operation', lambda root, target, result: {'action': 'adjudicate'})
    op.main(['status'])
    op.main(['prepare', '--target', '4', '--supersede'])
    op.main(['freeze', '--target', '4'])
    op.main(['adjudicate', '--target', '4', '--result-data', 'r.xlsx'])
    text = capsys.readouterr().out
    assert 'status' in text and 'prepare' in text and 'freeze' in text and 'adjudicate' in text


def test_operator_module_main_guard_executes_read_only(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['smart_operator.py', 'status'])
    runpy.run_path(str(Path(op.__file__).resolve()), run_name='__main__')
    assert 'operator_contract' in capsys.readouterr().out


def test_operator_post_result_hold_requires_explicit_next_cycle_authority(tmp_path: Path):
    pd.DataFrame({"Concurso": [1, 2, 3]}).to_excel(tmp_path / "Mega-Sena.xlsx", index=False)
    review = tmp_path / "SMART_POST_RESULT_REVIEW_3.json"
    review.write_text('{"status":"POST_RESULT_REVIEW_COMPLETE"}\\n', encoding="utf-8")
    op._write_operator_hashed_doc(tmp_path / op.POST_RESULT_HOLD_PATH, {
        "schema": op.NEXT_CYCLE_HOLD_SCHEMA,
        "status": "AWAITING_OPERATOR_APPLY_OR_GENERATE",
        "completed_contest": 3,
        "next_target": 4,
        "review_file": review.name,
        "review_file_sha256": op.sha256_file(review),
        "review_sha256": "c" * 64,
        "canonical_sha256_at_review": op.sha256_file(tmp_path / "Mega-Sena.xlsx"),
        "automatic_prepare_forbidden": True,
        "prepare_allowed": False,
        "generation_allowed": False,
        "operator_command_required": True,
    })
    with pytest.raises(FileNotFoundError):
        op._require_next_cycle_authority(tmp_path, 4)
    authority = op.authorize_next_cycle_operation(tmp_path, 4)
    assert authority["authorized_by"] == "USER_EXPLICIT_APPLY_OR_GENERATE"
    assert op._require_next_cycle_authority(tmp_path, 4)["sha256"] == authority["sha256"]
    consumed = op._consume_next_cycle_authority(tmp_path, 4, "operator-4-test")
    assert consumed["consumed"] is True
    with pytest.raises(PermissionError, match="not active"):
        op._require_next_cycle_authority(tmp_path, 4)


def test_operator_prepare_is_blocked_before_product_work_without_post_result_gate(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        op.prepare_operation(tmp_path, 4)
