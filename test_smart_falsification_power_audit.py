import json
from pathlib import Path

def test_falsification_power_audit_prevents_false_null_claim():
    p=json.loads(Path('SMART_FALSIFICATION_POWER_AUDIT.json').read_text(encoding='utf-8'))
    assert p['resolution_sufficient_for_alpha'] is False
    assert p['classification']=='INCONCLUSIVE_POWER_LIMITED_RETROSPECTIVE'
    assert p['best_case_smallest_holm_adjusted_p'] > p['alpha']
    h=json.loads(Path('SMART_HYPOTHESIS_REGISTRY.json').read_text(encoding='utf-8'))
    ids={'H_MARGINAL_001','H_MEMORY_001','H_GRAPH_001','H_REGIME_001'}
    rows={x['id']:x for x in h['hypotheses'] if x['id'] in ids}
    assert set(rows)==ids
    assert all(x['status']=='INCONCLUSIVE_POWER_LIMITED_RETROSPECTIVE' for x in rows.values())
    assert all(x['promotion_authority'] is False for x in rows.values())
