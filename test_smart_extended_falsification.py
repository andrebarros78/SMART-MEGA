import numpy as np
import smart_randomness_cartography as rc
import smart_extended_falsification as f

def test_holm_monotone_and_bounded():
    o=f.holm({'a':.001,'b':.02,'c':.5}); assert all(0<=v<=1 for v in o.values()); assert o['a']<=o['b']<=o['c']

def test_metrics_valid_on_null_and_regime_control():
    n=rc.u0_uniform_iid(300,np.random.default_rng(1)); m=f.metrics(n); assert set(m)==set(f.METRICS); assert all(np.isfinite(list(m.values())))
    r=rc.u6_adversarial_controls(600,np.random.default_rng(2))['u6_regime_switch']; assert f.metrics(r)['regime_count']>=1

def test_underpowered_falsification_is_rejected():
    import pytest
    d=rc.u0_uniform_iid(120,np.random.default_rng(3))
    with pytest.raises(ValueError,match='underpowered Monte Carlo'):
        f.build(d,seed=4,reps_u0=5,reps_other=5)
