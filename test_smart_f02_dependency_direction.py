from pathlib import Path

import smart_operator
import smart_operator_contract
from smart_component_reachability import build_registry

ROOT = Path(__file__).resolve().parent


def _component(registry, path):
    return next(c for c in registry["components"] if c["source_file"] == path)


def test_f02_operator_pipeline_dependency_is_one_way():
    registry = build_registry(ROOT)
    debt = registry["known_debt_observations"]
    assert debt["operator_pipeline_cycle_detected"] is False

    operator = _component(registry, "smart_operator.py")
    pipeline = _component(registry, "smart_full_process_pipeline.py")
    product_certification = _component(registry, "smart_product_certification.py")
    recovery = _component(registry, "smart_operation_recovery.py")

    assert "smart_full_process_pipeline" in operator["producers"]
    assert "smart_operator" not in pipeline["producers"]
    assert "smart_operator" not in product_certification["producers"]
    assert "smart_operator" not in recovery["producers"]
    assert "smart_full_process_pipeline" not in recovery["producers"]


def test_f02_operator_contract_preserves_public_compatibility():
    assert smart_operator.contract() == smart_operator_contract.contract()
    contests = [1, 2, 3, 4]
    assert smart_operator.validate_target_sequence(contests, 5) == smart_operator_contract.validate_target_sequence(contests, 5)


def test_f02_recovery_is_reexported_from_operator():
    from smart_operation_recovery import recover_interrupted_freeze_operation
    assert smart_operator.recover_interrupted_freeze_operation is recover_interrupted_freeze_operation
