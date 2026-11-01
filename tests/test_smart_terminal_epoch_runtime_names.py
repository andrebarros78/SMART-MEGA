"""Active-epoch path derivation is pure; engine alone owns global scope."""
from __future__ import annotations

import copy
from pathlib import Path
import pytest

from smart_terminal_epoch_names import epoch_runtime_names


def _epoch(target=9001):
    return {
        "target_contest":target,
        "data_file":"runtime/learning_epochs/alpha/cutoff.xlsx",
        "state_paths":{
            "ledger":"runtime/learning_epochs/alpha/SMART_SIGNAL_LEDGER.json"
        }
    }


def test_complete_names_and_value_types():
    names=epoch_runtime_names(_epoch(),9001)
    assert set(names)=={
        "SCHEMA","TARGET","CUTOFF","PRE_RESULT_DATA","RESULT_DATA",
        "INGEST_PROOF","PRIMARY_PAYLOAD","CONSENSUS_FILE","LEARNED_STATE",
        "RESULT_STORE_PROOF","TERMINAL_PROOF","STATUS_FILE",
        "INDEPENDENT_AUDIT_FILE",
    }
    assert names["SCHEMA"]=="SMART_TERMINAL_EXECUTOR_ACTIVE_EPOCH_1"
    assert names["TARGET"]==9001 and names["CUTOFF"]==9000
    assert names["PRE_RESULT_DATA"]=="runtime/learning_epochs/alpha/cutoff.xlsx"
    assert names["RESULT_DATA"]=="runtime/learning_epochs/alpha/Mega-Sena_through_9001.xlsx"
    assert names["INGEST_PROOF"]=="runtime/learning_epochs/alpha/SMART_OFFICIAL_RESULT_INGEST_9001.json"
    assert names["PRIMARY_PAYLOAD"]=="runtime/learning_epochs/alpha/SMART_9001_OFFICIAL_PRIMARY_PAYLOAD.json"
    assert names["CONSENSUS_FILE"]=="runtime/learning_epochs/alpha/SMART_9001_OFFICIAL_EVIDENCE_CURRENT.json"
    assert names["LEARNED_STATE"]=="SMART_SIGNAL_STATE_9001_LEARNED.json"
    assert names["RESULT_STORE_PROOF"]=="SMART_CANONICAL_HISTORY_ADVANCE_9001.json"
    assert names["TERMINAL_PROOF"]=="runtime/learning_epochs/alpha/SMART_TERMINAL_6OF6_PROOF_9001.json"
    assert names["STATUS_FILE"]=="runtime/learning_epochs/alpha/SMART_TERMINAL_EXECUTOR_STATUS_9001.json"
    assert names["INDEPENDENT_AUDIT_FILE"]=="runtime/learning_epochs/alpha/SMART_P14_INDEPENDENT_AUDIT_9001.json"


@pytest.mark.parametrize("ledger",[None,"",False])
def test_missing_active_ledger_is_rejected(ledger):
    active=_epoch()
    active["state_paths"]={"ledger":ledger}
    with pytest.raises(ValueError,match="active epoch ledger path missing"):
        epoch_runtime_names(active,9001)


@pytest.mark.parametrize("state_paths",[None,[], "invalid"])
def test_invalid_path_mapping_is_rejected(state_paths):
    active=_epoch()
    active["state_paths"]=state_paths
    with pytest.raises(ValueError,match="active epoch ledger path missing"):
        epoch_runtime_names(active,9001)


def test_derivation_does_not_modify_epoch_document():
    active=_epoch()
    before=copy.deepcopy(active)
    result=epoch_runtime_names(active,9001)
    result["TARGET"]=1
    assert active==before


def test_canonical_legacy_learned_paths_remain_root_relative():
    active=_epoch(3054)
    names=epoch_runtime_names(active,3054)
    assert "/" not in names["LEARNED_STATE"]
    assert "/" not in names["RESULT_STORE_PROOF"]
    assert names["TARGET"]==3054


def test_epoch_directory_comes_from_ledger_parent():
    active=_epoch()
    active["state_paths"]["ledger"]="runtime/learning_epochs/another/ledger.json"
    assert epoch_runtime_names(active,9001)["RESULT_DATA"].startswith("runtime/learning_epochs/another/")


def test_nested_active_context_restores_outer_target(tmp_path, monkeypatch):
    import smart_terminal_engine as terminal
    active=_epoch(9001)
    monkeypatch.setattr(terminal,"verify_active_epoch",lambda path:active)
    old=(terminal.TARGET,terminal.RESULT_DATA)
    with terminal.active_epoch_context(tmp_path,9001):
        outer=(terminal.TARGET,terminal.RESULT_DATA)
        with terminal.active_epoch_context(tmp_path,9001):
            assert (terminal.TARGET,terminal.RESULT_DATA)==outer
        assert (terminal.TARGET,terminal.RESULT_DATA)==outer
    assert (terminal.TARGET,terminal.RESULT_DATA)==old


def test_context_restores_globals_even_if_body_fails(tmp_path,monkeypatch):
    import smart_terminal_engine as terminal
    monkeypatch.setattr(terminal,"verify_active_epoch",lambda path:_epoch())
    original=(terminal.TARGET,terminal.CUTOFF,terminal.CONSENSUS_FILE)
    with pytest.raises(RuntimeError,match="consumer failed"):
        with terminal.active_epoch_context(tmp_path,9001):
            assert terminal.TARGET==9001
            raise RuntimeError("consumer failed")
    assert (terminal.TARGET,terminal.CUTOFF,terminal.CONSENSUS_FILE)==original