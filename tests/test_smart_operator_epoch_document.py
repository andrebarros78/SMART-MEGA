"""Contract tests for the prepared, immutable active-epoch document.

The layout and builder must not open/write a ledger, select a target, or
authorize preparation. The caller owns all those responsibilities.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from smart_operator_epoch_document import epoch_artifact_paths, build_active_epoch_document


TARGET = 3079
CERT = "c" * 64
HISTORY = "h" * 64
LEDGER_SHA = "l" * 64
CREATED = "2026-11-01T17:00:00+00:00"


@pytest.fixture
def inputs(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    epoch_dir = root / "runtime" / "learning_epochs" / "epoch-x"
    layout = epoch_artifact_paths(epoch_dir, TARGET)
    kwargs = {
        "root": root,
        "target": TARGET,
        "epoch_id": "epoch-x",
        "created_utc": CREATED,
        "schema": "SMART_LEARNING_EPOCH_TEST",
        "certification_file": Path("evidence") / "product.json",
        "certification_sha256": CERT,
        "layout": layout,
        "data_sha256": HISTORY,
        "canonical_history_sha256": HISTORY,
        "schedule": {"target_contest": TARGET, "pre_draw": True},
        "temporal": {"status": "PASS"},
        "previous_sha256": "p" * 64,
        "ledger_seed": {"sha256": LEDGER_SHA, "event_count": 27},
    }
    return kwargs


def test_layout_matches_all_six_existing_prepare_artifacts(inputs):
    paths = inputs["layout"]
    assert set(paths) == {"snapshot", "ledger", "state", "activation_authority", "expansion_registry", "freeze"}
    assert paths["snapshot"].name == "Mega-Sena_cutoff_3078.xlsx"
    assert paths["ledger"].name == "SMART_SIGNAL_LEDGER.json"
    assert paths["state"].name == "SMART_SIGNAL_STATE.json"
    assert paths["activation_authority"].name == "SMART_LEARNING_ACTIVATION_AUTHORITY.json"
    assert paths["expansion_registry"].name == "SMART_SIGNAL_EXPANSION_REGISTRY.json"
    assert paths["freeze"].name == "SMART_3079_CHAMPION_CHALLENGER_FREEZE.json"


def test_document_exact_schema_and_immutable_prospective_guards(inputs):
    result = build_active_epoch_document(**inputs)
    assert result["schema"] == "SMART_LEARNING_EPOCH_TEST"
    assert result["status"] == "RESET_READY"
    assert result["project"] == "SMART-MEGA"
    assert result["operator_selected_target"] is True
    assert result["immutable_history_snapshot"] is True
    assert result["result_used"] is False
    assert result["freeze_authority"] is None
    assert result["learning_state_authority"] is None
    assert result["target_contest"] == TARGET
    assert result["cutoff_contest"] == TARGET - 1
    assert result["authority_mode"] == "OPERATOR_SELECTED_TARGET"
    assert result["current_engineering_role"] == "PRODUCT_CERTIFIED_OPERATION"
    assert result["first_possible_authoritative_target_for_current_engineering"] == TARGET


def test_document_proves_hash_and_certification_bindings(inputs):
    result = build_active_epoch_document(**inputs)
    assert result["product_certification_file"] == "evidence/product.json"
    assert result["product_certification_sha256"] == CERT
    assert result["data_sha256"] == HISTORY
    assert result["canonical_source_file"] == "Mega-Sena.xlsx"
    assert result["canonical_source_sha256_at_prepare"] == HISTORY
    assert result["canonical_ledger_seed_sha256"] == LEDGER_SHA
    assert result["canonical_ledger_seed_event_count"] == 27
    assert result["supersedes_active_epoch_sha256"] == "p" * 64


def test_document_paths_are_relative_to_root_with_forward_slashes(inputs):
    result = build_active_epoch_document(**inputs)
    prefix = "runtime/learning_epochs/epoch-x/"
    assert result["data_file"] == prefix + "Mega-Sena_cutoff_3078.xlsx"
    assert result["state_paths"] == {
        "ledger": prefix + "SMART_SIGNAL_LEDGER.json",
        "state": prefix + "SMART_SIGNAL_STATE.json",
        "activation_authority": prefix + "SMART_LEARNING_ACTIVATION_AUTHORITY.json",
        "expansion_registry": prefix + "SMART_SIGNAL_EXPANSION_REGISTRY.json",
        "freeze": prefix + "SMART_3079_CHAMPION_CHALLENGER_FREEZE.json",
    }


def test_document_passes_temporal_scope_and_creation_epoch(inputs):
    result = build_active_epoch_document(**inputs)
    assert result["epoch_id"] == "epoch-x"
    assert result["created_utc"] == CREATED
    assert result["target_schedule"] == inputs["schedule"]
    assert result["temporal_guard"] == inputs["temporal"]


def test_document_inputs_are_not_modified(inputs):
    before = deepcopy(inputs)
    build_active_epoch_document(**inputs)
    assert inputs == before


def test_document_contains_exact_historical_contract_fields(inputs):
    result = build_active_epoch_document(**inputs)
    assert set(result) == {
        "schema", "status", "project", "epoch_id", "created_utc",
        "product_certification_file", "product_certification_sha256",
        "operator_selected_target", "state_paths", "data_file", "data_sha256",
        "canonical_source_file", "canonical_source_sha256_at_prepare",
        "immutable_history_snapshot", "cutoff_contest", "target_contest",
        "authority_mode", "current_engineering_role",
        "first_possible_authoritative_target_for_current_engineering",
        "target_schedule", "temporal_guard", "result_used",
        "freeze_authority", "learning_state_authority",
        "supersedes_active_epoch_sha256", "canonical_ledger_seed_sha256",
        "canonical_ledger_seed_event_count",
    }


def test_document_accepts_new_epoch_with_no_predecessor(inputs):
    inputs["previous_sha256"] = None
    assert build_active_epoch_document(**inputs)["supersedes_active_epoch_sha256"] is None


@pytest.mark.parametrize("field", ["snapshot", "ledger", "freeze"])
def test_document_refuses_artifacts_outside_project(inputs, field):
    inputs["layout"][field] = inputs["root"].parent / "external" / "secret"
    with pytest.raises(ValueError):
        build_active_epoch_document(**inputs)


def test_document_is_buildable_before_artifacts_exist_without_creating_them(inputs):
    result = build_active_epoch_document(**inputs)
    assert result["state_paths"]["ledger"].endswith("SMART_SIGNAL_LEDGER.json")
    assert not inputs["layout"]["ledger"].exists()
    assert not inputs["layout"]["snapshot"].exists()


def test_layout_uses_target_converted_to_integer(inputs):
    layout = epoch_artifact_paths(inputs["layout"]["snapshot"].parent, "3079")
    assert layout["snapshot"] == inputs["layout"]["snapshot"]
    assert layout["freeze"] == inputs["layout"]["freeze"]
