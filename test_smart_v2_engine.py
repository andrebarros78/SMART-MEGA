import json, math, tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import smart_v2_engine as s


def test_rank_tie_break():
    score=np.zeros(60)
    top,_=s.rank_top6(score)
    assert top==[1,2,3,4,5,6]


def test_uniform_expectation():
    assert math.isclose(s.UNIFORM_EXPECTED_HITS,0.6)


def test_redundancy_penalty_bounds():
    scores={'a':np.arange(60,dtype=float),'b':np.arange(60,dtype=float),'c':np.arange(60,dtype=float)[::-1]}
    p,_=s.redundancy_penalty(scores)
    assert all(0.15 <= v <= 1.0 for v in p.values())


def test_walk_no_future_leakage_shape():
    rng=np.random.default_rng(1)
    draws=np.array([np.sort(rng.choice(s.NUMBERS,6,replace=False)) for _ in range(130)],dtype=int)
    contests=np.arange(1,131)
    r=s.walk_forward(draws,contests,start=100)
    assert len(r.rows)==30
    assert r.rows[0]['contest']==101
    assert set(r.final_weights)
    assert abs(sum(r.final_weights.values())-1)<1e-9


def test_load_draws_validation(tmp_path):
    rows=[]
    for c in range(1,4):
        rows.append({'Concurso':c,**{f'Bola{i}':i for i in range(1,7)}})
    p=tmp_path/'x.xlsx'; pd.DataFrame(rows).to_excel(p,index=False)
    d,c=s.load_draws(p)
    assert d.shape==(3,6) and c.tolist()==[1,2,3]
