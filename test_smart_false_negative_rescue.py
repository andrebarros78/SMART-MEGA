
from smart_false_negative_rescue import apply_rescue, build_profile_from_reports

def test_apply_rescue_without_profile_is_inactive():
    scores={str(n):float(n) for n in range(1,61)}
    adjusted,audit=apply_rescue(scores,None)
    assert adjusted==scores and audit["status"]=="INACTIVE" and audit["result_used"] is False

def test_apply_rescue_band_level_boosts_low_band_when_profile_says_so():
    scores={str(n):0.5 for n in range(1,61)}
    profile={"sha256":"x","observations":1,"config":{},"false_negative_counts":{},"false_positive_counts":{},"band_false_negative_counts":{"low":4,"mid":1,"high":1}}
    adjusted,audit=apply_rescue(scores,profile)
    assert adjusted["5"]>adjusted["35"]
    assert audit["status"]=="PASS" and audit["result_used"] is False


def test_false_positive_penalty_reduces_repeated_false_positive():
    scores={str(n):0.5 for n in range(1,61)}
    profile={"sha256":"x","observations":3,"config":{},"false_negative_counts":{},"false_positive_counts":{"1":3},"band_false_negative_counts":{"low":0,"mid":0,"high":0}}
    adjusted,audit=apply_rescue(scores,profile)
    assert adjusted["1"] < adjusted["2"]
    assert audit["result_used"] is False

def test_profile_cutoff_excludes_future_and_deduplicates_contests(tmp_path):
    import json
    def report(name,contest,actual,generated):
        (tmp_path/name).write_text(json.dumps({"contest_number":contest,"official_result":actual,"generated_card":generated}),encoding="utf-8")
    report('SMART_POST_RESULT_REPORT_3061_A.json',3061,[1,2,3,4,5,6],[1,2,3,7,8,9])
    report('SMART_POST_RESULT_REPORT_3061_B.json',3061,[1,2,3,4,5,6],[1,2,3,7,8,9])
    report('SMART_POST_RESULT_REPORT_3062.json',3062,[10,11,12,13,14,15],[10,11,12,16,17,18])
    profile=build_profile_from_reports(tmp_path,through_contest=3061)
    assert profile["causal_cutoff_enforced"] is True
    assert profile["through_contest"] == 3061
    assert profile["source_contests"] == [3061]
    assert profile["observations"] == 1 and profile["duplicates_ignored"] == 1
    assert all(x["contest"] <= 3061 for x in profile["recent_observations"])

def test_profile_conflicting_duplicate_fails_closed(tmp_path):
    import json, pytest
    (tmp_path/'SMART_POST_RESULT_REPORT_X1.json').write_text(json.dumps({"contest_number":3061,"official_result":[1,2,3,4,5,6],"generated_card":[1,2,3,7,8,9]}),encoding='utf-8')
    (tmp_path/'SMART_POST_RESULT_REPORT_X2.json').write_text(json.dumps({"contest_number":3061,"official_result":[1,2,3,4,5,6],"generated_card":[1,2,3,10,11,12]}),encoding='utf-8')
    with pytest.raises(ValueError,match='conflicting post-result reports'):
        build_profile_from_reports(tmp_path,through_contest=3061)
