from pathlib import Path
import json
import pytest
import smart_monte_carlo_convergence as mc

ROOT=Path(__file__).resolve().parent

def test_degenerate_null_is_excluded_from_p_stability_aggregate():
    final={'U0':{
      'regular':{'null_mean':1.0,'null_std':0.2,'empirical_two_sided_p':0.4},
      'degenerate':{'null_mean':2.0,'null_std':1e-15,'empirical_two_sided_p':0.9},
    }}
    current={'U0':{
      'regular':{'null_mean':1.02,'null_std':0.21,'empirical_two_sided_p':0.5},
      'degenerate':{'null_mean':2.0+1e-14,'null_std':1e-15,'empirical_two_sided_p':0.1},
    }}
    out=mc._compare_checkpoint(current,final)
    assert out['degenerate_metric_count']==1
    assert out['max_p_abs_delta']==pytest.approx(0.1)
    assert out['max_degenerate_mean_abs_delta'] < 1e-12

def test_convergence_artifact_is_bound_to_final_1000_and_non_predictive():
    doc=json.loads((ROOT/'SMART_MONTE_CARLO_CONVERGENCE_1000.json').read_text(encoding='utf-8'))
    assert doc['schema']==mc.SCHEMA
    assert doc['final_replications']==1000
    assert doc['final_atlas_sha256']==mc.sha(ROOT/'SMART_RANDOMNESS_ATLAS_1000.json')
    assert doc['predictive_weight_authorized'] is False
    assert doc['terminal_6of6_proven'] is False
    assert doc['stability_summary']['degenerate_metric_count'] >= 1
