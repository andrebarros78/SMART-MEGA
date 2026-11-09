"""PC Casa local development may only run under the owner's approved root.

The legitimate GitHub/VPS execution portability remains intact.
"""
from pathlib import Path

import pytest

import smart_canonical_identity as identity


APPROVED = Path(r"C:\New Projet\SMART-MEGA-V6-CANONICAL")


def _simulate_checkout(monkeypatch, checkout: Path, local_host: bool):
    monkeypatch.setattr(identity, "OPERATIONAL_ROOT", checkout)
    monkeypatch.setattr(identity, "_looks_like_root", lambda _: True)
    monkeypatch.setattr(identity, "_local_development_host", lambda: local_host, raising=False)


def test_approved_local_development_root_is_pinned():
    assert identity.LOCAL_DEVELOPMENT_ROOT == APPROVED


@pytest.mark.parametrize("relative", ["main", "_worktrees\\feature-v6", "SMV6-NATIVE"])
def test_local_windows_checkouts_inside_approved_root_allowed(monkeypatch, relative):
    candidate = APPROVED / relative
    _simulate_checkout(monkeypatch, candidate, True)
    assert identity._resolve_operational_root(None) == candidate.resolve()


@pytest.mark.parametrize("outside", [
    Path(r"C:\Windows\Temp\smart-mega-v6-debug-20261109"),
    Path(r"C:\New Projet\SMART-MEGA-V6-CANONICAL-EVIL\main"),
    Path(r"C:\SMV6-NATIVE"),
    Path(r"C:\SMART-MEGA"),
])
def test_pc_casa_rejects_external_development_checkout(monkeypatch, outside):
    _simulate_checkout(monkeypatch, outside, True)
    with pytest.raises(identity.CanonicalIdentityError, match="outside authorized local development root"):
        identity._resolve_operational_root(None)


def test_cross_host_execution_checkout_stays_portable(monkeypatch):
    checkout = Path(r"C:\Remote-Executor\smart-mega")
    _simulate_checkout(monkeypatch, checkout, False)
    assert identity._resolve_operational_root(None) == checkout.resolve()


def test_pc_casa_real_host_detection_is_not_taken_from_environment_variables(monkeypatch):
    monkeypatch.setenv("SMART_DEV_ROOT_OVERRIDE", r"C:\Windows\Temp")
    assert identity.LOCAL_DEVELOPMENT_ROOT == APPROVED
