from __future__ import annotations

import copy
import pytest

import smart_sequential_prospective_proof as sp
import smart_independent_audit as ia


def f(h: str, target: int = 10) -> dict:
    return {'event_type':'FREEZE','target_contest':target,'cutoff_contest':target-1,'freeze_sha256':h,
            'freeze_file':'f.json','frozen_before_result':True,'causal_cutoff':True}


def sup(old: str, new: str, target: int = 10) -> dict:
    return {'event_type':'SUPERSEDE','target_contest':target,'old_freeze_sha256':old,'new_freeze_sha256':new}


def adj(h: str, target: int = 10) -> dict:
    return {'event_type':'ADJUDICATION','target_contest':target,'freeze_sha256':h,
            'champion_hits':1,'challenger_hits':1,'retroactive_rewrite':False}


def test_p12_linear_supersede_chain_accepts_only_exact_active_replacement():
    a,b,c='a'*64,'b'*64,'c'*64
    events=[f(a),f(b),sup(a,b),f(c),sup(b,c),adj(c)]
    out=sp.validate_target_sequence({'events':events},10)
    assert out['active_freeze_sha256']==c
    assert out['supersede_count']==2
    assert sp.freeze_snapshot()['linear_supersede_chain_required'] is True


@pytest.mark.parametrize('events', [
    [f('a'*64), sup('a'*64,'b'*64)],
    [f('a'*64), f('b'*64), sup('c'*64,'b'*64)],
    [f('a'*64), f('b'*64), sup('a'*64,'c'*64)],
    [f('a'*64), f('a'*64)],
    [f('a'*64), f('b'*64)],
    [f('a'*64), f('b'*64), {'event_type':'ATTRIBUTION','target_contest':10}, sup('a'*64,'b'*64)],
    [f('not-a-hash')],
    [f('a'*64), f('b'*64), sup('a'*64,'a'*64)],
])
def test_p12_rejects_malformed_supersede_topologies(events):
    with pytest.raises(ValueError):
        sp.validate_target_sequence({'events':copy.deepcopy(events)},10)


def test_p14_independent_supersede_resolver_matches_linear_chain():
    a,b,c='a'*64,'b'*64,'c'*64
    events=[f(a),f(b),sup(a,b),f(c),sup(b,c)]
    out=ia._audit_supersede_chains(events)
    assert out[10]==c


@pytest.mark.parametrize('events', [
    [sup('a'*64,'b'*64)],
    [f('a'*64),f('b'*64),sup('c'*64,'b'*64)],
    [f('a'*64),f('b'*64),sup('a'*64,'c'*64)],
    [f('a'*64),f('a'*64)],
    [f('a'*64),f('b'*64),f('c'*64)],
    [f('a'*64),f('b'*64),sup('a'*64,'a'*64)],
])
def test_p14_rejects_malformed_supersede_topologies(events):
    with pytest.raises(ValueError):
        ia._audit_supersede_chains(copy.deepcopy(events))
