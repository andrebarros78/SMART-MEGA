"""Rigorously preserve value and hash audits without reparsing byte-identical copies."""
import pandas as pd

import smart_canonical_history_advance as cha
from test_smart_canonical_history_advance import _fixture


def test_history_advance_parses_each_source_only_once(tmp_path, monkeypatch):
    canonical, through, _, _, active = _fixture(tmp_path, monkeypatch)
    real_read = pd.read_excel
    seen = []

    def measured_read(path, *args, **kwargs):
        seen.append(path)
        return real_read(path, *args, **kwargs)

    monkeypatch.setattr(cha.pd, "read_excel", measured_read)
    report = cha.advance_completed_epoch(tmp_path, active)
    assert report["status"] == "PASS"
    assert seen == [canonical, through]
    assert cha.sha256_file(canonical) == cha.sha256_file(through)


def test_history_advance_again_is_idempotent_without_copy(tmp_path, monkeypatch):
    canonical, through, _, _, active = _fixture(tmp_path, monkeypatch)
    assert cha.advance_completed_epoch(tmp_path, active)["status"] == "PASS"

    def refuse_copy(*args, **kwargs):
        raise AssertionError("must not copy already-advanced history")

    monkeypatch.setattr(cha.shutil, "copyfile", refuse_copy)
    result = cha.advance_completed_epoch(tmp_path, active)
    assert result["status"] == "ALREADY_CURRENT"
    assert cha.sha256_file(canonical) == cha.sha256_file(through)
