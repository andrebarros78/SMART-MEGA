from pathlib import Path
import json
import numpy as np
import pytest
import smart_randomness_cartography as rc

def sample(n=120,seed=7): return rc.u0_uniform_iid(n,np.random.default_rng(seed))
def valid(a,n):
 assert a.shape==(n,6); assert np.all((a>=1)&(a<=60)); assert all(len(set(map(int,r)))==6 for r in a); assert np.all(np.diff(a,axis=1)>0)
def test_u0_reproducible_valid():
 a=rc.u0_uniform_iid(200,np.random.default_rng(42)); b=rc.u0_uniform_iid(200,np.random.default_rng(42)); assert np.array_equal(a,b); valid(a,200)
def test_u1_preserves_rows():
 d=sample(); p=rc.u1_temporal_permutation(d,np.random.default_rng(1)); assert sorted(map(tuple,p.tolist()))==sorted(map(tuple,d.tolist()))
def test_u2_preserves_overlap_geometry():
 d=sample(); p=rc.u2_label_permutation(d,np.random.default_rng(2)); valid(p,len(d)); assert [len(set(d[i])&set(d[i-1])) for i in range(1,len(d))]==[len(set(p[i])&set(p[i-1])) for i in range(1,len(p))]
def test_u3_preserves_rows():
 d=sample(123); p=rc.u3_block_shuffle(d,np.random.default_rng(3),20); assert sorted(map(tuple,p.tolist()))==sorted(map(tuple,d.tolist()))
def test_u4_u5_valid_deterministic():
 d=sample(80)
 for fn in (rc.u4_marginals_preserved,rc.u5_fitted_dynamic):
  a=fn(d,np.random.default_rng(9)); b=fn(d,np.random.default_rng(9)); assert np.array_equal(a,b); valid(a,len(d))
def test_u6_known_controls():
 c=rc.u6_adversarial_controls(140,np.random.default_rng(10)); assert set(c)=={'u6_null_control','u6_persistent_bias','u6_regime_switch','u6_repeated_motif'}
 for a in c.values(): valid(a,140)
 assert np.sum(np.all(c['u6_repeated_motif']==np.array([1,2,3,4,5,6]),axis=1))>=20
def test_manifest_u0_to_u6():
 m=rc.build_null_manifest(sample(),20,12); assert list(m['families'])==['U0','U1','U2','U3','U4','U5','U6']; assert m['causal_claim'] is False
def test_manifest_rejects_low_replications():
 with pytest.raises(ValueError): rc.build_null_manifest(sample(),5)
def test_atlas_required_windows_and_universes():
 d=sample(1200); a=rc.build_atlas(d,np.arange(1,1201),20,11); assert a['schema']==rc.SCHEMA_ATLAS; assert all(str(w) in a['windows'] for w in (1,2,3,5,10,25,50,100,250,500,1000)); assert set(a['null_comparisons'])=={'U0','U1','U2','U3','U4','U5'}; assert len(a['observed']['marginal_probability'])==60
def test_write_rejects_future(monkeypatch,tmp_path:Path):
 d=sample(30); c=np.arange(100,130); monkeypatch.setattr(rc,'load_draws',lambda _:(d,c)); f=tmp_path/'x.xlsx'; f.write_bytes(b'x')
 with pytest.raises(ValueError,match='future contest'): rc.write_program_artifacts(f,tmp_path/'m.json',tmp_path/'a.json',20,4,128)
def test_write_artifacts_bind_hash(monkeypatch,tmp_path:Path):
 d=sample(30); c=np.arange(100,130); monkeypatch.setattr(rc,'load_draws',lambda _:(d,c)); f=tmp_path/'x.xlsx'; f.write_bytes(b'xyz'); m=tmp_path/'m.json'; a=tmp_path/'a.json'; mm,aa=rc.write_program_artifacts(f,m,a,20,4,129); assert json.loads(m.read_text())['data_sha256']==rc.sha256_file(f); assert json.loads(a.read_text())['data_sha256']==mm['data_sha256']==aa['data_sha256']


def test_u4_preserves_exact_marginals():
    d=sample(80)
    s=rc.u4_marginals_preserved(d,np.random.default_rng(77),swap_steps=4000)
    assert np.array_equal(rc.onehot(d).sum(axis=0),rc.onehot(s).sum(axis=0))
    assert np.all(rc.onehot(s).sum(axis=1)==6)



def test_default_monte_carlo_resolution_is_research_grade():
    assert rc.DEFAULT_REPLICATIONS >= 1000
    assert 1.0 / (rc.DEFAULT_REPLICATIONS + 1) <= 0.001
