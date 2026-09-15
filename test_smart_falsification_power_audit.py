import json
from pathlib import Path

import smart_hypothesis_state_reconciler as reconciler


def test_historical_power_audit_is_preserved_without_downgrading_newer_registry_state():
    audit = json.loads((Path(__file__).resolve().parent / 'SMART_FALSIFICATION_POWER_AUDIT.json').read_text(encoding='utf-8'))
    assert audit['resolution_sufficient_for_alpha'] is False
    assert audit['classification'] == 'INCONCLUSIVE_POWER_LIMITED_RETROSPECTIVE'
    assert audit['best_case_smallest_holm_adjusted_p'] > audit['alpha']
    assert audit['registry_mutation'] == 'SKIPPED_SUPERSEDED_BY_POWERED_REPORT'
    assert audit['predictive_weight_authorized'] is False

    registry = json.loads((Path(__file__).resolve().parent / 'SMART_HYPOTHESIS_REGISTRY.json').read_text(encoding='utf-8'))
    rows = {
        item['id']: item
        for item in registry['hypotheses']
        if item['id'] in reconciler.TARGET_HYPOTHESES
    }
    assert set(rows) == reconciler.TARGET_HYPOTHESES
    assert all(item['status'] == reconciler.POWER_RESOLVED_STATUS for item in rows.values())
    assert all(item['promotion_authority'] is False for item in rows.values())
    assert all(item['power_resolution']['failure_to_reject_proves_null'] is False for item in rows.values())
