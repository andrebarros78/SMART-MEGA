import pytest

import smart_probability_audit as audit
from test_smart_probability_audit import source_document


@pytest.mark.parametrize("field,bad", [
    ("contest", 2000.9),
    ("cutoff_contest", 1999.9),
    ("hits", 6.9),
    ("hits", True),
])
def test_coerced_audit_row_cannot_create_performance_evidence(field, bad):
    source = source_document()
    source["rows"]["alpha"][0][field] = bad
    source["sha256"] = audit.sha256_json({k: v for k, v in source.items() if k != "sha256"})
    with pytest.raises(ValueError):
        audit.audit_historical(source, mc_replications=1000, bootstrap_replications=200, seed=9)
