from pathlib import Path

from smart_signal_agent import SIGNAL_NAMES
from smart_signal_expansion_governance import load_registry, write_registry
from smart_champion_challenger import archive_registry_snapshot, sha256


def test_empty_registry_materializes_with_embedded_and_file_hash(tmp_path: Path):
    path = tmp_path / "SMART_SIGNAL_EXPANSION_REGISTRY.json"
    assert not path.exists()
    governance = load_registry(path, tuple(SIGNAL_NAMES))
    file_hash = write_registry(path, governance)
    assert path.exists()
    assert len(file_hash) == 64
    loaded = load_registry(path, tuple(SIGNAL_NAMES))
    snap = loaded.snapshot()
    assert len(snap["sha256"]) == 64
    assert snap["candidate_count"] == 0
    assert snap["rules"]["registry_embedded_hash_required"] is True

def test_registry_archive_preserves_freeze_snapshot_when_live_registry_advances(tmp_path: Path):
    path = tmp_path / "SMART_SIGNAL_EXPANSION_REGISTRY.json"
    governance = load_registry(path, tuple(SIGNAL_NAMES))
    frozen_hash = write_registry(path, governance)
    archive = archive_registry_snapshot(path, frozen_hash)
    assert archive.exists()
    assert sha256(archive) == frozen_hash

    governance.register("frontier_probe", "shadow_probe", 3054)
    live_hash = write_registry(path, governance)
    assert live_hash != frozen_hash
    assert sha256(archive) == frozen_hash


def test_registry_archive_remains_immutable_after_live_registry_changes(tmp_path: Path):
    path = tmp_path / "SMART_SIGNAL_EXPANSION_REGISTRY.json"
    governance = load_registry(path, tuple(SIGNAL_NAMES))
    original_hash = write_registry(path, governance)
    archive = archive_registry_snapshot(path, original_hash)
    assert archive.exists()
    assert archive.read_bytes() == path.read_bytes()

    governance.register("shadow_candidate", "frequency", 3054)
    updated_hash = write_registry(path, governance)
    assert updated_hash != original_hash
    assert archive.read_bytes() != path.read_bytes()
    import hashlib
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == original_hash
