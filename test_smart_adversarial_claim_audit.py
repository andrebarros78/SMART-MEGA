from pathlib import Path
from smart_adversarial_claim_audit import run
ROOT=Path(__file__).resolve().parent

def test_adversarial_claim_audit_proves_non_inert_pipeline():
    d=run(ROOT)
    assert d['status']=='PASS'
    assert all(d['checks'].values())
    assert d['distinct_top6_sets'] >= 2
    assert d['heaviest_weight_delta'] > 0
