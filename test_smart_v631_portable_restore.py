from pathlib import Path
import pytest

import smart_agent_skill_orchestration as aso
import smart_champion_challenger as cc


def test_v631_legacy_project_path_rebinds_only_inside_trusted_old_root(tmp_path):
    target = tmp_path / 'runtime' / 'learning_epochs' / 'epoch-1' / 'freeze.json'
    target.parent.mkdir(parents=True)
    target.write_text('{}', encoding='utf-8')
    legacy = r'C:\New Projet\SMART-MEGA\runtime\learning_epochs\epoch-1\freeze.json'
    assert aso._resolve_project_file(tmp_path, legacy, label='legacy freeze') == target.resolve()


def test_v631_legacy_rebind_rejects_arbitrary_absolute_path(tmp_path):
    with pytest.raises(ValueError, match='escapes project root'):
        aso._resolve_project_file(tmp_path, r'C:\Other\Project\runtime\freeze.json', label='foreign freeze')


def test_v631_legacy_rebind_rejects_traversal_outside_trusted_root(tmp_path):
    with pytest.raises(ValueError, match='escapes project root'):
        aso._resolve_project_file(tmp_path, r'C:\New Projet\SMART-MEGA\..\outside\freeze.json', label='traversal freeze')


def test_new_project_local_paths_are_persisted_relative(tmp_path):
    p = tmp_path / 'runtime' / 'state.json'
    p.parent.mkdir(parents=True)
    p.write_text('{}', encoding='utf-8')
    assert cc._persist_project_path(p, tmp_path) == 'runtime/state.json'


def test_external_paths_are_not_relabelled_as_project_local(tmp_path):
    outside = tmp_path.parent / 'outside.json'
    assert Path(cc._persist_project_path(outside, tmp_path)).is_absolute()



def test_tracked_quarantine_manifest_is_runtime_self_contained():
    import json
    manifest_path = Path(__file__).resolve().parent / 'SMART_EXTERNAL_SKILLS_QUARANTINE_MANIFEST.json'
    doc = json.loads(manifest_path.read_text(encoding='utf-8'))
    assert doc['acquired_items'] == 21
    assert doc['source_payload_required_at_runtime'] is False
    assert doc['external_code_auto_execute'] is False
    assert len(doc['items']) == 21
    assert all('local_path' not in item for item in doc['items'])
    assert all(item['execution_policy'] == 'SOURCE_ONLY_QUARANTINE' for item in doc['items'])


def test_quarantine_probe_does_not_require_ignored_external_payload(tmp_path):
    import json
    from smart_agent_runtime import SmartAgentRuntime
    source = Path(__file__).resolve().parent / 'SMART_EXTERNAL_SKILLS_QUARANTINE_MANIFEST.json'
    (tmp_path / source.name).write_bytes(source.read_bytes())
    runtime = object.__new__(SmartAgentRuntime)
    runtime.root = tmp_path
    result = runtime._probe_quarantine_curator()
    assert result['pass'] is True
    assert result['optional_source_payload_present'] is False
    assert result['source_payload_required_at_runtime'] is False
    assert result['external_code_executed'] is False


def test_v631_legacy_rebind_rejects_rebound_filesystem_escape(tmp_path, monkeypatch):
    restored = tmp_path / 'restored'
    restored.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    rebound_candidate = restored / 'runtime' / 'escape' / 'freeze.json'
    escaped_target = outside / 'freeze.json'
    original_resolve = Path.resolve

    def guarded_resolve(self, *args, **kwargs):
        if str(self) == str(rebound_candidate):
            return escaped_target
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'resolve', guarded_resolve)
    legacy = r'C:\New Projet\SMART-MEGA\runtime\escape\freeze.json'
    with pytest.raises(ValueError, match='escapes project root'):
        aso._resolve_project_file(restored, legacy, label='junction escape')


def test_active_context_rebinds_legacy_absolute_paths_to_project_relative(tmp_path, monkeypatch):
    import json
    import smart_agent_skill_orchestration as aso
    import smart_champion_challenger as cc

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    data = runtime / "data.xlsx"
    data.write_bytes(b"portable-data")
    state = runtime / "state.json"
    state.write_text("{}", encoding="utf-8")
    ledger = tmp_path / "SMART_SIGNAL_LEDGER.json"
    ledger.write_text("{}", encoding="utf-8")

    freeze = runtime / "freeze.json"
    frozen = {
        "cutoff_contest": 3054,
        "data_file": r"C:\New Projet\SMART-MEGA\runtime\data.xlsx",
        "data_sha256": aso._sha256(data),
        "signal_state_file": r"C:\New Projet\SMART-MEGA\runtime\state.json",
        "signal_state_sha256": aso._sha256(state),
    }
    freeze.write_text(json.dumps(frozen), encoding="utf-8")
    freeze_event = {
        "event_type": "FREEZE",
        "target_contest": 3055,
        "cutoff_contest": 3054,
        "freeze_file": r"C:\New Projet\SMART-MEGA\runtime\freeze.json",
        "freeze_sha256": aso._sha256(freeze),
        "data_sha256": aso._sha256(data),
    }
    monkeypatch.setattr(cc, "load_ledger", lambda path: {"events": [freeze_event]})
    monkeypatch.setattr(cc, "active_freeze", lambda loaded, target: freeze_event)

    ctx = aso._resolve_active_context(tmp_path)
    assert ctx["freeze_file"] == "runtime/freeze.json"
    assert ctx["data_file"] == "runtime/data.xlsx"
    assert ctx["signal_state_file"] == "runtime/state.json"
    assert ctx["ledger_file"] == "SMART_SIGNAL_LEDGER.json"


def test_portable_caixa_archive_manifest_is_complete_and_self_hashed():
    import hashlib
    import json
    root = Path(__file__).resolve().parent
    manifest_path = root / 'SMART_PORTABLE_CAIXA_CRONOGRAM_ARCHIVE_MANIFEST.json'
    doc = json.loads(manifest_path.read_text(encoding='utf-8'))
    declared = doc.pop('sha256')
    canonical = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    assert declared == hashlib.sha256(canonical).hexdigest()
    assert doc['schema'] == 'SMART_PORTABLE_CAIXA_CRONOGRAM_ARCHIVE_1'
    assert doc['file_count'] == 60
    assert len(doc['items']) == 60
    archive = root / 'portable_evidence' / 'cronogramas_caixa'
    assert archive.is_dir()
    for item in doc['items']:
        path = archive / item['file']
        assert path.is_file()
        assert path.stat().st_size == item['bytes']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256']


def _write_portable_archive_fixture(tmp_path, *, tamper_pdf=False, tamper_manifest=False):
    import hashlib
    import json
    import shutil
    root = Path(__file__).resolve().parent
    shutil.copy2(root / 'Mega-Sena.xlsx', tmp_path / 'Mega-Sena.xlsx')
    shutil.copy2(root / 'SMART_MEGA_SENA_DRAW_TIME_POLICY.json', tmp_path / 'SMART_MEGA_SENA_DRAW_TIME_POLICY.json')
    portable = tmp_path / 'portable_evidence' / 'cronogramas_caixa'
    portable.mkdir(parents=True)
    pdf = portable / '2026-09.pdf'
    shutil.copy2(root / 'portable_evidence' / 'cronogramas_caixa' / '2026-09.pdf', pdf)
    raw = pdf.read_bytes()
    item = {'file': pdf.name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    doc = {
        'schema': 'SMART_PORTABLE_CAIXA_CRONOGRAM_ARCHIVE_1',
        'authority': 'TEST_FIXTURE',
        'source_consensus': 'TEST_FIXTURE',
        'file_count': 1,
        'items': [item],
    }
    canonical = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    doc['sha256'] = hashlib.sha256(canonical).hexdigest()
    manifest = tmp_path / 'SMART_PORTABLE_CAIXA_CRONOGRAM_ARCHIVE_MANIFEST.json'
    manifest.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if tamper_pdf:
        pdf.write_bytes(raw + b'corruption')
    if tamper_manifest:
        bad = json.loads(manifest.read_text(encoding='utf-8'))
        bad['items'][0]['bytes'] += 1
        manifest.write_text(json.dumps(bad, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return portable, manifest


def test_target_schedule_uses_packaged_caixa_archive_when_runtime_overlay_is_absent(tmp_path):
    import smart_target_schedule as sts
    _write_portable_archive_fixture(tmp_path)
    assert not (tmp_path / 'runtime' / 'procedural_sources' / 'cronogramas_caixa').exists()
    doc = sts.resolve_target_schedule(tmp_path, 3054)
    assert doc['target_date'] == '06/09/2026'
    assert doc['authority'] == 'CAIXA_ARCHIVED_CRONOGRAM_PDF'
    assert doc['source_file'] == 'portable_evidence/cronogramas_caixa/2026-09.pdf'
    assert doc['result_used'] is False


def test_target_schedule_rejects_tampered_portable_caixa_pdf(tmp_path):
    import smart_target_schedule as sts
    _write_portable_archive_fixture(tmp_path, tamper_pdf=True)
    with pytest.raises(ValueError, match='evidence integrity failure'):
        sts.resolve_target_schedule(tmp_path, 3054)


def test_target_schedule_rejects_tampered_portable_caixa_manifest(tmp_path):
    import smart_target_schedule as sts
    _write_portable_archive_fixture(tmp_path, tamper_manifest=True)
    with pytest.raises(ValueError, match='manifest self-hash invalid'):
        sts.resolve_target_schedule(tmp_path, 3054)


def test_smart_python_launcher_scrubs_external_python_environment():
    import os
    import subprocess
    root = Path(__file__).resolve().parent
    env = os.environ.copy()
    env['PYTHONPATH'] = r'C:\New Projet\WMCP 3.1\src'
    env['PYTHONHOME'] = r'C:\ForeignPythonHome'
    code = "import os,sys; assert not os.environ.get('PYTHONPATH'); assert not os.environ.get('PYTHONHOME'); assert all('WMCP 3.1' not in p for p in sys.path); print('SMART_PYTHON_ISOLATION_PASS')"
    launcher = root / 'smart_python.cmd'
    proc = subprocess.run(
        f'call "{launcher}" -c "{code}"',
        cwd=root,
        shell=True,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert 'SMART_PYTHON_ISOLATION_PASS' in proc.stdout


def test_smart_python_launcher_fails_closed_when_venv_is_missing(tmp_path):
    import shutil
    import subprocess
    root = Path(__file__).resolve().parent
    launcher = tmp_path / 'smart_python.cmd'
    shutil.copy2(root / 'smart_python.cmd', launcher)
    proc = subprocess.run(
        f'call "{launcher}" -V',
        cwd=tmp_path,
        shell=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 2
    assert 'portable runtime missing' in proc.stderr
