
from smart_primary_card_selector import PrimaryCardSelectorConfig, select_primary_card

def test_selector_rejects_concentrated_top6_and_keeps_six_unique_numbers():
    ranking=[11,53,38,37,35,27,14,10,43,30,16,46,25,6,58,17,5,9]+[n for n in range(1,61) if n not in {11,53,38,37,35,27,14,10,43,30,16,46,25,6,58,17,5,9}]
    scores={n:60-i for i,n in enumerate(ranking)}
    result=select_primary_card(scores,ranking60=ranking,config=PrimaryCardSelectorConfig(candidate_pool_size=18))
    nums=result["selected_numbers"]
    assert result["status"]=="PASS" and len(nums)==6 and len(set(nums))==6
    assert result["selected_band_counts"]["low"]>=2 and result["selected_band_counts"]["mid"]<=3
    assert nums!=sorted(ranking[:6]) and result["result_used"] is False

def test_selector_is_deterministic_and_bounded():
    ranking=list(range(1,61)); scores={n:100-n for n in ranking}
    a=select_primary_card(scores,ranking60=ranking); b=select_primary_card(scores,ranking60=ranking)
    assert a["selected_numbers"]==b["selected_numbers"] and a["sha256"]==b["sha256"]
    assert max(x["pool_size"] for x in a["adaptive_attempts"])<=30

import math
import pytest

@pytest.mark.parametrize("config", [
    PrimaryCardSelectorConfig(score_weight=math.nan),
    PrimaryCardSelectorConfig(rank_weight=math.inf),
    PrimaryCardSelectorConfig(concentration_penalty=-1),
    PrimaryCardSelectorConfig(candidate_pool_size=6.5),
    PrimaryCardSelectorConfig(numbers_per_card=True),
    PrimaryCardSelectorConfig(min_low_band=-1),
    PrimaryCardSelectorConfig(min_mid_band=4, max_mid_band=3),
])
def test_selector_rejects_invalid_config_before_generation(config):
    with pytest.raises(ValueError):
        select_primary_card({n:61-n for n in range(1,61)}, config=config)

def test_selector_refuses_infeasible_card_instead_of_passing_invalid_fallback():
    with pytest.raises(ValueError, match="no valid primary card"):
        select_primary_card(
            {n:61-n for n in range(1,61)},
            config=PrimaryCardSelectorConfig(candidate_pool_size=6,max_candidate_pool_size=6),
        )

@pytest.mark.parametrize("key", [1.5, True])
def test_selector_rejects_lossy_number_coercion(key):
    scores={n:61-n for n in range(2,61)}
    scores[key]=60
    with pytest.raises(ValueError, match="number must"):
        select_primary_card(scores)

def test_selector_rejects_duplicate_normalized_number():
    scores={n:61-n for n in range(1,61)}
    scores["01"]=60
    with pytest.raises(ValueError, match="duplicate number"):
        select_primary_card(scores)

def test_selector_expands_through_exact_odd_pool_limit():
    ranking=list(range(1,7))+[21]+list(range(7,21))+list(range(22,61))
    result=select_primary_card(
        {n:61-i for i,n in enumerate(ranking)}, ranking60=ranking,
        config=PrimaryCardSelectorConfig(
            candidate_pool_size=6,max_candidate_pool_size=7,
            max_low_band=5,min_mid_band=1,max_mid_band=1,max_high_band=0,
        ),
    )
    assert result["candidate_pool_size"]==7
    assert result["selected_band_counts"]=={"low":5,"mid":1,"high":0}
    assert result["fallback_used"] is False and math.isfinite(result["objective_value"])

def test_selector_rejects_objective_overflow():
    ranking=[1,2,3,21,22,41]+[n for n in range(1,61) if n not in {1,2,3,21,22,41}]
    with pytest.raises(ValueError,match="objective must be finite"):
        select_primary_card(
            {n:61-i for i,n in enumerate(ranking)},ranking60=ranking,
            config=PrimaryCardSelectorConfig(candidate_pool_size=6,max_candidate_pool_size=6,score_weight=1e308),
        )
