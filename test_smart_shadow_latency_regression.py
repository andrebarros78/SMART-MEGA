"""Regression: verified immutable shadow replay does not recompute 3070 historical draws."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
import smart_cap60_parallel as parallel
from test_smart_cap60_parallel import sandbox

def test_same_signed_shadow_is_reused_without_excel_or_model_replay(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parent
    isolated, relative = sandbox(root, tmp_path)
    first = parallel.produce(isolated, relative)
    assert first["status"] == "FROZEN_SHADOW_ONLY"
    # If the record is already signed, any second computation is wasted and
    # enlarges ingest/card latency. Re-validation must still hash real files.
    monkeypatch.setattr(parallel.e, "load_draws", lambda _: pytest.fail("repeat Excel scan"))
    monkeypatch.setattr(parallel.champion_engine, "current_policy",
                        lambda *args, **kwargs: pytest.fail("repeat champion replay"))
    monkeypatch.setattr(parallel.experimental_engine, "current_policy",
                        lambda *args, **kwargs: pytest.fail("repeat candidate replay"))
    again = parallel.produce(isolated, relative)
    assert again["status"] == "ALREADY_FROZEN_SHADOW"
    assert again["sha256"] == first["sha256"]
    assert again["production_authority"] is False


def test_existing_shadow_rejects_changed_code_before_any_cached_return(tmp_path):
    root = Path(__file__).resolve().parent
    isolated, relative = sandbox(root, tmp_path)
    parallel.produce(isolated, relative)
    original = (isolated / "smart_cap60_experiment_engine.py")
    original.write_bytes(original.read_bytes() + b"\n# modified-engine\n")
    with pytest.raises(ValueError, match="source"):
        parallel.produce(isolated, relative)
