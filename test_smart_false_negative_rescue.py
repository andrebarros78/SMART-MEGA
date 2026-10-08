
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


def test_canonical_rescue_rejects_unsigned_report(tmp_path):
    import json, pytest
    (tmp_path/"SMART_CANONICAL_ROOT.json").write_text("{}",encoding="utf-8")
    report=tmp_path/"SMART_POST_RESULT_REPORT_9.json"
    report.write_text(json.dumps({"contest_number":9,"official_result":[1,2,3,4,5,6],"generated_card":[1,2,3,7,8,9]}),encoding="utf-8")
    with pytest.raises(ValueError,match="untrusted post-result report schema/status"):
        build_profile_from_reports(tmp_path,through_contest=9)


def test_canonical_rescue_rejects_tampered_lineage_without_score_promotion(tmp_path):
    import json, hashlib, pytest
    from smart_false_negative_rescue import sha256_json
    (tmp_path/"SMART_CANONICAL_ROOT.json").write_text("{}",encoding="utf-8")
    ledger=tmp_path/"ledger.json"
    ledger.write_text('{"schema":"SMART_SIGNAL_LEDGER_1","events":[]}',encoding="utf-8")
    freeze=tmp_path/"freeze.json"
    freeze.write_text(json.dumps({"target_contest":9,"champion":{"top6":[1,2,3,7,8,9]}}),encoding="utf-8")
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    audit={"freeze_artifact":"freeze.json","freeze_sha256":digest(freeze),"ledger":"ledger.json",
           "ledger_sha256":digest(ledger),"freeze_authority_present":True,"findings":[]}
    report={"schema":"SMART_POST_RESULT_REPORT_1","status":"PASS","contest_number":9,
            "official_result":[1,2,3,4,5,6],"generated_card":[1,2,3,7,8,9],
            "hit_count":3,"process_audit":audit}
    report["source_fingerprint"]=sha256_json({
        "target":9,"official_result":report["official_result"],"generated_card":report["generated_card"],
        "freeze_sha256":audit["freeze_sha256"],"ledger_sha256":audit["ledger_sha256"],
        "portfolio_sha256":None,"portfolio_hits_per_game":None})
    report["sha256"]=sha256_json(report)
    path=tmp_path/"SMART_POST_RESULT_REPORT_9.json"
    path.write_text(json.dumps(report),encoding="utf-8")
    approved=build_profile_from_reports(tmp_path,through_contest=9)
    assert approved["observations"]==1 and approved["source_contests"]==[9]
    freeze.write_text('{"target_contest":9,"champion":{"top6":[1,2,3,8,9,10]}}',encoding="utf-8")
    with pytest.raises(ValueError,match="freeze hash mismatch"):
        build_profile_from_reports(tmp_path,through_contest=9)
