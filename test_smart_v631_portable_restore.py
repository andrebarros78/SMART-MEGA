from pathlib import Path
import json
import pytest

import smart_agent_skill_orchestration as aso
import smart_champion_challenger as cc


def test_external_absolute_paths_fail_closed(tmp_path):
    with pytest.raises(ValueError, match='absolute external paths are forbidden'):
        aso._resolve_project_file(tmp_path, r'Z:\retired\SMART-MEGA\runtime\freeze.json', label='external freeze')


def test_external_absolute_paths_fail_closed_even_when_target_name_exists(tmp_path):
    target = tmp_path / 'runtime' / 'freeze.json'
    target.parent.mkdir(parents=True)
    target.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='absolute external paths are forbidden'):
        aso._resolve_project_file(tmp_path, r'C:\Other\Project\runtime\freeze.json', label='foreign freeze')


def test_relative_project_path_resolves_inside_root(tmp_path):
    target = tmp_path / 'runtime' / 'freeze.json'
    target.parent.mkdir(parents=True)
    target.write_text('{}', encoding='utf-8')
    assert aso._resolve_project_file(tmp_path, 'runtime/freeze.json', label='freeze') == target.resolve()


def test_relative_traversal_fails_closed(tmp_path):
    with pytest.raises(ValueError, match='escapes project root'):
        aso._resolve_project_file(tmp_path, '../outside/freeze.json', label='traversal freeze')


def test_new_project_local_paths_are_persisted_relative(tmp_path):
    p = tmp_path / 'runtime' / 'state.json'
    p.parent.mkdir(parents=True)
    p.write_text('{}', encoding='utf-8')
    assert cc._persist_project_path(p, tmp_path) == 'runtime/state.json'


def test_external_paths_are_not_relabelled_as_project_local(tmp_path):
    outside = tmp_path.parent / 'outside.json'
    assert Path(cc._persist_project_path(outside, tmp_path)).is_absolute()


def test_tracked_quarantine_manifest_is_runtime_self_contained():
    manifest_path = Path(__file__).resolve().parent / 'SMART_EXTERNAL_SKILLS_QUARANTINE_MANIFEST.json'
    doc = json.loads(manifest_path.read_text(encoding='utf-8'))
    assert doc['acquired_items'] == 21
    assert doc['source_payload_required_at_runtime'] is False
    assert doc['external_code_auto_execute'] is False
    assert len(doc['items']) == 21
    assert all('local_path' not in item for item in doc['items'])
    assert all(item['execution_policy'] == 'SOURCE_ONLY_QUARANTINE' for item in doc['items'])


def test_quarantine_probe_does_not_require_ignored_external_payload(tmp_path):
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


def test_relative_rebound_filesystem_escape_fails_closed(tmp_path, monkeypatch):
    restored = tmp_path / 'restored'
    restored.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    candidate = restored / 'runtime' / 'escape' / 'freeze.json'
    escaped_target = outside / 'freeze.json'
    original_resolve = Path.resolve

    def guarded_resolve(self, *args, **kwargs):
        if str(self) == str(candidate):
            return escaped_target
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'resolve', guarded_resolve)
    with pytest.raises(ValueError, match='escapes project root'):
        aso._resolve_project_file(restored, 'runtime/escape/freeze.json', label='junction escape')
