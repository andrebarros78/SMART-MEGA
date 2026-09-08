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
