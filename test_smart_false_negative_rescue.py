
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
    ledger.write_text(json.dumps({"schema":"SMART_SIGNAL_LEDGER_1","events":[
        {"event_type":"FREEZE","target_contest":9,"freeze_sha256":"PLACEHOLDER"},
        {"event_type":"ADJUDICATION","target_contest":9,"freeze_sha256":"PLACEHOLDER","actual_numbers":[1,2,3,4,5,6]}
    ]}),encoding="utf-8")
    freeze=tmp_path/"freeze.json"
    freeze.write_text(json.dumps({"target_contest":9,"champion":{"top6":[1,2,3,7,8,9]}}),encoding="utf-8")
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    ledger_doc=json.loads(ledger.read_text(encoding="utf-8"))
    for event in ledger_doc["events"]: event["freeze_sha256"]=digest(freeze)
    ledger.write_text(json.dumps(ledger_doc),encoding="utf-8")
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
    quarantined=build_profile_from_reports(tmp_path,through_contest=9)
    assert quarantined["observations"]==0
    assert quarantined["quarantined_reports"]==["SMART_POST_RESULT_REPORT_9.json"]


def test_canonical_rescue_quarantines_orphaned_historical_report(tmp_path):
    import json
    from smart_false_negative_rescue import sha256_json
    (tmp_path/"SMART_CANONICAL_ROOT.json").write_text("{}",encoding="utf-8")
    actual=[1,2,3,4,5,6]
    generated=[1,2,3,7,8,9]
    audit={"freeze_artifact":"lost/freeze.json","freeze_sha256":"0"*64,
           "ledger":"lost/ledger.json","ledger_sha256":"1"*64,
           "freeze_authority_present":True,"findings":[]}
    obj={"schema":"SMART_POST_RESULT_REPORT_1","status":"PASS","contest_number":9,
         "official_result":actual,"generated_card":generated,"hit_count":3,"process_audit":audit}
    obj["source_fingerprint"]="f"*64
    obj["sha256"]=sha256_json(obj)
    (tmp_path/"SMART_POST_RESULT_REPORT_9.json").write_text(json.dumps(obj),encoding="utf-8")
    profile=build_profile_from_reports(tmp_path,through_contest=9)
    assert profile["observations"]==0
    assert profile["source_contests"]==[]
    assert profile["quarantined_reports"]==["SMART_POST_RESULT_REPORT_9.json"]
    assert profile["quarantined_count"]==1


def test_canonical_rescue_rejects_report_without_matching_adjudication(tmp_path):
    import json,hashlib,pytest
    from smart_false_negative_rescue import sha256_json
    (tmp_path/"SMART_CANONICAL_ROOT.json").write_text("{}",encoding="utf-8")
    freeze=tmp_path/"freeze.json"
    freeze.write_text(json.dumps({"target_contest":9,"champion":{"top6":[1,2,3,7,8,9]}}),encoding="utf-8")
    ledger=tmp_path/"ledger.json"
    ledger.write_text(json.dumps({"schema":"SMART_SIGNAL_LEDGER_1","events":[]}),encoding="utf-8")
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    audit={"freeze_artifact":"freeze.json","freeze_sha256":digest(freeze),
           "ledger":"ledger.json","ledger_sha256":digest(ledger),
           "freeze_authority_present":True,"findings":[]}
    actual=[1,2,3,4,5,6]; generated=[1,2,3,7,8,9]
    obj={"schema":"SMART_POST_RESULT_REPORT_1","status":"PASS","contest_number":9,
         "official_result":actual,"generated_card":generated,"hit_count":3,"process_audit":audit}
    obj["source_fingerprint"]=sha256_json({"target":9,"official_result":actual,
        "generated_card":generated,"freeze_sha256":audit["freeze_sha256"],
        "ledger_sha256":audit["ledger_sha256"],"portfolio_sha256":None,
        "portfolio_hits_per_game":None})
    obj["sha256"]=sha256_json(obj)
    (tmp_path/"SMART_POST_RESULT_REPORT_9.json").write_text(json.dumps(obj),encoding="utf-8")
    quarantined=build_profile_from_reports(tmp_path,through_contest=9)
    assert quarantined["observations"]==0
    assert quarantined["quarantined_count"]==1


def test_canonical_production_reports_only_count_traceable_lineage():
    from pathlib import Path
    root=Path(__file__).resolve().parent
    if not (root/"SMART_CANONICAL_ROOT.json").is_file():
        return  # Only meaningful in the real canonical GitHub repository.
    profile=build_profile_from_reports(root,through_contest=3066)
    current=[p for p in root.glob("SMART_POST_RESULT_REPORT_*.json")
             if int(__import__("json").loads(p.read_text(encoding="utf-8-sig"))["contest_number"])<=3066]
    assert profile["observations"]+profile["quarantined_count"]==len(current)
    assert len(profile["source_contests"])==len(set(profile["source_contests"]))
    assert not set(profile["source_contests"]) & {
        int(p.stem.split("_")[-1]) for p in current if p.name in profile["quarantined_reports"]
    }
