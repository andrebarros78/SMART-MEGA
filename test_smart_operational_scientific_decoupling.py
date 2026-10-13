"""Operation stays safe when P14 evidence is stale; scientific claims stay blocked."""
from pathlib import Path

import pytest

import smart_authority_freshness as freshness
import smart_startup_reconciler as startup


def _mock_freshness(monkeypatch, *, cert=True, governance=True, global_proof=False, open_count=0):
    monkeypatch.setattr(freshness, "build_critical_code_manifest", lambda root: {"file_count": 0})
    monkeypatch.setattr(freshness, "load_registry", lambda *a, **k: {"open_count": open_count})

    def verify_cert(*args, **kwargs):
        if not cert:
            raise ValueError("stale construction certificate")
        return {"status": "CONSTRUCTION_PROVEN"}

    def verify_governance(root):
        if not governance:
            raise ValueError("stale live governance")
        return {"status": "PASS"}

    def verify_global(*args):
        if not global_proof:
            raise ValueError("independent historical P14 evidence not current")
        return {"status": "PASS"}

    monkeypatch.setattr(freshness, "verify_product_certification", verify_cert)
    monkeypatch.setattr(freshness, "verify_governance", verify_governance)
    monkeypatch.setattr("smart_global_integrity.verify_global_integrity", verify_global)
    return freshness.audit(Path("."))


def test_live_operation_does_not_inherit_missing_historical_p14(monkeypatch):
    observation = _mock_freshness(monkeypatch, global_proof=False)
    assert observation["operational_compatible"] is True
    assert observation["operational_status"] == "PASS"
    assert all(observation["operational_checks"].values())
    assert observation["status"] == "STALE_OR_BLOCKED"
    assert observation["terminal_compatible"] is False
    assert observation["authorities"]["global_integrity"]["current"] is False


@pytest.mark.parametrize("bad", ["cert", "governance", "material"])
def test_live_operation_fails_closed_for_real_deficiency(monkeypatch, bad):
    observation = _mock_freshness(
        monkeypatch,
        cert=bad != "cert",
        governance=bad != "governance",
        open_count=int(bad == "material"),
        global_proof=False,
    )
    assert observation["operational_compatible"] is False
    assert observation["operational_status"] == "BLOCKED"
    assert observation["terminal_compatible"] is False


def _mock_startup(monkeypatch):
    monkeypatch.setattr(startup, "require_canonical_identity", lambda root: {"status": "PASS"})
    monkeypatch.setattr(startup, "read_entries", lambda root: [])
    monkeypatch.setattr(startup, "open_transactions", lambda root: {})
    monkeypatch.setattr(startup, "load_lifecycle", lambda root: {
        "state": "HOLD", "target_contest": 3070, "completed_contest": 3069,
    })
    monkeypatch.setattr(startup, "_read_hashed", lambda path, schema=None: (
        {"next_target": 3070, "completed_contest": 3069}
        if path.name == "SMART_NEXT_CYCLE_HOLD.json" else None
    ))
    monkeypatch.setattr(startup, "read_lock_metadata", lambda root: None)
    monkeypatch.setattr(startup, "_dataset_max", lambda root: (3069, 3069))


@pytest.mark.parametrize("compatible,expected", [
    (True, "OK"),
    (False, "RECOVERY_REQUIRED"),
    (None, "RECOVERY_REQUIRED"),
])
def test_startup_uses_only_explicit_operational_compatibility(monkeypatch, tmp_path, compatible, expected):
    _mock_startup(monkeypatch)
    monkeypatch.setattr(freshness, "audit", lambda root: {
        "status": "STALE_OR_BLOCKED",
        "terminal_compatible": False,
        "operational_compatible": compatible,
        "authorities": {"global_integrity": {"current": False}},
    })
    result = startup.reconcile(tmp_path, 3070, include_authority_freshness=True)
    assert result["status"] == expected
    assert result["checks"]["authority_freshness"] is (compatible is True)
    assert result["details"]["authority_freshness"]["terminal_compatible"] is False


def test_startup_still_rejects_broken_target_history(monkeypatch, tmp_path):
    _mock_startup(monkeypatch)
    monkeypatch.setattr(startup, "_dataset_max", lambda root: (3068, 3068))
    monkeypatch.setattr(freshness, "audit", lambda root: {"operational_compatible": True})
    result = startup.reconcile(tmp_path, 3070, include_authority_freshness=True)
    assert result["status"] == "RECOVERY_REQUIRED"
    assert result["checks"]["target_dataset_monotonic"] is False
    assert result["checks"]["authority_freshness"] is True
