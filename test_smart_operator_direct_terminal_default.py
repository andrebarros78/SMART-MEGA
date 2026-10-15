"""Every active consumer entrypoint defaults to the local operator authority."""
from __future__ import annotations

import inspect
import json

import pytest
import smart_terminal_engine as engine
import smart_operator_result as op_result


def test_all_terminal_entrypoint_defaults_are_operator_only():
    for function in (engine.probe, engine.execute,
                     engine.probe_active_epoch, engine.execute_active_epoch):
        assert inspect.signature(function).parameters["fetcher"].default is None


def test_generic_fetcher_reads_only_registered_operator_data(tmp_path, monkeypatch):
    monkeypatch.setattr(engine.official_consensus, "fetch_consensus",
                        lambda *a, **kw: pytest.fail("CAIXA fetch forbidden"))
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({"schema":"SMART_OPERATOR_RESULT_INPUT_1",
      "target_contest":3071,"draw_date":"17/10/2026",
      "numbers":[2,13,21,32,45,60]}),encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="operator result"):
        engine._default_operator_fetcher(tmp_path)(3071)
    op_result.register(tmp_path, 3071, input_path)
    payload,evidence = engine._default_operator_fetcher(tmp_path)(3071)
    assert evidence["primary"]["channel"] == "OPERATOR"
    assert evidence["terminal_source_corroboration_authorized"] is False
    assert payload["numero"] == 3071
