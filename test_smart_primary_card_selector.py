
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
