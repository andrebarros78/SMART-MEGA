import numpy as np
import pytest
import smart_cartography_extended as ex
import smart_randomness_cartography as rc

def sample(n=240,seed=7): return rc.u0_uniform_iid(n,np.random.default_rng(seed))

def test_extended_schema_and_guards():
    d=sample(); a=ex.build(d,np.arange(1,len(d)+1))
    assert a['schema']==ex.SCHEMA
    assert a['falsification']['future_information_used'] is False
    assert a['falsification']['predictive_weight_authorized'] is False
    assert 0 <= a['network']['density'] <= 1
    assert a['temporal_memory']['lag1_binary_mutual_information_mean_bits'] >= 0

def test_regime_control_detects_breakpoints():
    d=rc.u6_adversarial_controls(600,np.random.default_rng(123))['u6_regime_switch']
    r=ex.regime_structure(d)
    assert r['count'] >= 1
    assert all(0 < b < 600 for b in r['breakpoints_index'])

def test_write_rejects_future(monkeypatch,tmp_path):
    d=sample(60); c=np.arange(100,160)
    monkeypatch.setattr(ex,'load_draws',lambda _:(d,c))
    f=tmp_path/'x.xlsx'; f.write_bytes(b'x')
    with pytest.raises(ValueError,match='future contest'): ex.write(f,tmp_path/'o.json',158)
