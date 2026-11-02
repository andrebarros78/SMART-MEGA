"""Characterize the fail-closed official provider outage decision."""
from __future__ import annotations

import copy
import pytest

from smart_terminal_official_evidence import official_fetch_failure_waiting


@pytest.mark.parametrize("error", [OSError("offline"), TimeoutError("token: secret"), ConnectionError("private-url")])
def test_pre_adjudication_absence_yields_wait_without_leaking_provider_detail(error):
    result = official_fetch_failure_waiting(
        existing=None, adjudications=[], error=error,
        target=3080, schema="SMART_TERMINAL_ACTIVE_1",
    )
    assert result == {
        "schema": "SMART_TERMINAL_ACTIVE_1",
        "target_contest": 3080,
        "status": "WAITING_OFFICIAL_RESULT",
        "preflight_status": "PASS",
        "official_result_available": False,
        "canonical_writes_performed": False,
        "error_type": type(error).__name__,
        "terminal_6of6_proven": False,
    }
    assert str(error) not in str(result)


@pytest.mark.parametrize("adjudications", [
    [{"event_type": "ADJUDICATION"}],
    [{"event_type": "ADJUDICATION"}, {"event_type": "ADJUDICATION"}],
])
def test_adjudicated_missing_evidence_never_claims_waiting(adjudications):
    assert official_fetch_failure_waiting(
        existing=None, adjudications=adjudications,
        error=RuntimeError("upstream unavailable"), target=3080, schema="x",
    ) is None


@pytest.mark.parametrize("adjudications", [[], [{"event_type": "ADJUDICATION"}]])
def test_persisted_evidence_uses_recovery_not_waiting(adjudications):
    persisted = ({"numbers": [1, 2, 3, 4, 5, 6]}, {"status": "CORROBORATED"})
    before = copy.deepcopy((persisted, adjudications))
    assert official_fetch_failure_waiting(
        existing=persisted, adjudications=adjudications,
        error=OSError("unavailable"), target=3080, schema="x",
    ) is None
    assert (persisted, adjudications) == before


def test_classifier_does_not_consume_or_modify_error():
    err = ValueError("provider rejected request")
    result = official_fetch_failure_waiting(
        existing=None, adjudications=[], error=err, target=3080, schema="x",
    )
    assert err.args == ("provider rejected request",)
    assert result["error_type"] == "ValueError"


def test_classifier_has_no_storage_side_effects(tmp_path):
    assert official_fetch_failure_waiting(
        existing=None, adjudications=[], error=FileNotFoundError("missing"),
        target=3080, schema="x",
    )["canonical_writes_performed"] is False
    assert list(tmp_path.iterdir()) == []
