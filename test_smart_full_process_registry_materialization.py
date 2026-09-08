from pathlib import Path

from smart_signal_agent import SIGNAL_NAMES
from smart_signal_expansion_governance import load_registry, write_registry


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
