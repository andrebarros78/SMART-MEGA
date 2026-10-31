"""Executable RED/GREEN contracts for a research-only exact 60-ball selector."""
import itertools
import math
import random
import time
from dataclasses import replace

import pytest

from smart_primary_card_selector import PrimaryCardSelectorConfig, _band
from smart_primary_card_selector_research import select_primary_card_research


def _brute(ranking, scores, cfg):
    pool = ranking[:cfg.candidate_pool_size]
    lo, hi = min(scores[n] for n in pool), max(scores[n] for n in pool)
    normalized = {n: (scores[n]-lo)/(hi-lo) if hi != lo else 1 for n in pool}
    top3 = set(ranking[:3])
    best = None
    for chosen in itertools.combinations(pool, 6):
        count = {band:sum(_band(n) == band for n in chosen) for band in ('low','mid','high')}
        if any(not (getattr(cfg,f'min_{band}_band') <= count[band] <= getattr(cfg,f'max_{band}_band')) for band in count):
            continue
        if cfg.require_top3_presence and not set(chosen) & top3:
            continue
        normsum = sum(normalized[n] for n in chosen)
        rank = sum((len(pool)-pool.index(n))/len(pool) for n in chosen)
        bal = 1 - (abs(count['low']-2.5)+abs(count['mid']-2.5)+abs(count['high']-1.0))/6
        conc = max(count.values())-min(count.values())
        score = cfg.score_weight*normsum+cfg.rank_weight*rank+cfg.band_balance_weight*bal-cfg.concentration_penalty*max(0,conc-3)
        key = (score, tuple(sorted(chosen)))
        if best is None or score > best[0] or (math.isclose(score,best[0]) and key[1] < best[1]): best=key
    return best


@pytest.mark.parametrize("require_top3", [False,True])
@pytest.mark.parametrize("seed", [1,7,19])
def test_exact_optimizer_matches_full_enumeration_small_pools(seed,require_top3):
    rng=random.Random(seed)
    ranking=rng.sample(range(1,61),60)
    scores={n:float(1000-rank)+rng.random()*0.03 for rank,n in enumerate(ranking)}
    cfg=PrimaryCardSelectorConfig(
        candidate_pool_size=12,max_candidate_pool_size=12,
        require_top3_presence=require_top3,
        min_low_band=0,max_low_band=6,min_mid_band=0,max_mid_band=6,
        min_high_band=0,max_high_band=6,
    )
    expected=_brute(ranking,scores,cfg)
    actual=select_primary_card_research(scores,ranking,cfg)
    assert actual["selected_numbers"]==list(expected[1])
    assert actual["result_used"] is False
    assert actual["model_promotion_authorized"] is False
    assert actual["solver_status"]=="EXACT_OPTIMAL"
    assert actual["evaluated_combinations"] < math.comb(12,6)


def test_sixty_ball_pool_is_bounded_and_excludes_mandatory_top3_when_configured():
    ranking=list(range(1,61))
    scores={n:61.0-n for n in ranking}
    cfg=PrimaryCardSelectorConfig(
       candidate_pool_size=60,max_candidate_pool_size=60,require_top3_presence=False,
       min_low_band=0,max_low_band=6,min_mid_band=0,max_mid_band=6,
       min_high_band=0,max_high_band=6,
    )
    start=time.perf_counter()
    a=select_primary_card_research(scores,ranking,cfg)
    elapsed=time.perf_counter()-start
    assert len(a["selected_numbers"])==6
    assert a["candidate_pool_size"]==60
    assert a["theoretical_combinations"]==50_063_860
    assert a["evaluated_combinations"] < 2000
    assert elapsed<10
    assert a["model_promotion_authorized"] is False


def test_research_opt_in_never_changes_production_selector_defaults():
    from smart_primary_card_selector import select_primary_card
    rank=[1,2,3,21,22,41]+[n for n in range(1,61) if n not in {1,2,3,21,22,41}]
    scores={n:61.0-i for i,n in enumerate(rank)}
    cfg=PrimaryCardSelectorConfig(candidate_pool_size=6,max_candidate_pool_size=6,
        min_low_band=0,max_low_band=6,min_mid_band=0,max_mid_band=6,
        min_high_band=0,max_high_band=6)
    prod=select_primary_card(scores,rank,cfg)
    research=select_primary_card_research(scores,rank,cfg)
    assert prod["selected_numbers"]==research["selected_numbers"]
    assert prod["sha256"] != research["sha256"]
    assert research["model_promotion_authorized"] is False


def test_research_rejects_bad_config_and_future_result_argument():
    cfg=PrimaryCardSelectorConfig(candidate_pool_size=60,max_candidate_pool_size=60,require_top3_presence=False)
    scores={n:float(n) for n in range(1,61)}
    with pytest.raises(TypeError):
        select_primary_card_research(scores,actual_result=[5,9,16,40,41,59])
    with pytest.raises(ValueError):
        select_primary_card_research(scores,config=replace(cfg,candidate_pool_size=61))