"""Historical freeze checks may degrade history but never active authority."""
from __future__ import annotations

from pathlib import Path
import pytest

from smart_terminal_historical_freeze import (
    precheck_historical_freeze_evidence,
    write_unverified_history_audit,
)


def _case(tmp_path):
    observed=[]
    records=[
        {"event_type":"FREEZE", "target_contest":9000,
         "freeze_file":"old.json", "freeze_sha256":"a"*64},
        {"event_type":"ADJUDICATION", "target_contest":9000},
        {"event_type":"FREEZE", "target_contest":9001,
         "freeze_file":"now.json", "freeze_sha256":"b"*64},
        {"event_type":"FREEZE", "target_contest":8999,
         "freeze_file":"unrelated.json", "freeze_sha256":"c"*64},
    ]
    ledger={"events":records}
    inspected={"status":"DEGRADED_HISTORICAL_EVIDENCE_MISSING",
               "promotion_authority":False,"unverified_contests":[9000]}
    def resolve(*args):
        observed.append(("resolve",args))
        return {"verified":True}
    def inspect(*args,**kwargs):
        observed.append(("inspect",args,kwargs))
        return inspected
    opts={"target":9001,"resolve_audit_evidence":resolve,
          "inspect_freeze_evidence":inspect}
    def run(*,allow=False,sha=None):
        return precheck_historical_freeze_evidence(
            tmp_path,ledger,allow_unverified_history=allow,current_sha256=sha,**opts)
    return records,ledger,opts,observed,inspected,run


def test_strict_path_verifies_only_adjudicated_and_active_freezes(tmp_path):
    rows,ledger,opts,observed,inspected,run=_case(tmp_path)
    assert run() is None
    assert observed==[
        ("resolve",(tmp_path,"old.json","a"*64,"frozen artifact")),
        ("resolve",(tmp_path,"now.json","b"*64,"frozen artifact"))]
    assert rows[-1]["freeze_file"]=="unrelated.json"


def test_scope_checks_use_original_inspection_and_never_promote(tmp_path):
    rows,ledger,opts,observed,inspected,run=_case(tmp_path)
    assert run(allow=True,sha="b"*64) is inspected
    assert observed==[
        ("inspect",(tmp_path,ledger,9001,opts["resolve_audit_evidence"]),
         {"current_sha256":"b"*64})]
    assert inspected["promotion_authority"] is False


@pytest.mark.parametrize("error", [ValueError("hash mismatch"),OSError("missing freeze")])
def test_strict_selected_historical_freeze_error_fails_closed(tmp_path,error):
    rows,ledger,opts,observed,inspected,run=_case(tmp_path)
    def reject(root,name,digest,label):
        if name=="old.json": raise error
    opts["resolve_audit_evidence"]=reject
    with pytest.raises(ValueError,match="historical freeze evidence unavailable for contest 9000"):
        run()


def test_active_current_freeze_error_is_never_downgraded(tmp_path):
    rows,ledger,opts,observed,inspected,run=_case(tmp_path)
    def reject(root,name,digest,label):
        if name=="now.json": raise ValueError("invalid active authority")
    opts["resolve_audit_evidence"]=reject
    with pytest.raises(ValueError,match="historical freeze evidence unavailable for contest 9001"):
        run()


def test_scoped_active_freeze_error_propagates(tmp_path):
    rows,ledger,opts,observed,inspected,run=_case(tmp_path)
    opts["inspect_freeze_evidence"]=lambda *args,**kwargs: (_ for _ in ()).throw(ValueError("active freeze invalid"))
    with pytest.raises(ValueError,match="active freeze invalid"):
        run(allow=True,sha="b"*64)


def test_irrelevant_freeze_is_not_required_in_strict_path(tmp_path):
    rows,ledger,opts,observed,inspected,run=_case(tmp_path)
    def reject_unrelated(root,name,digest,label):
        if name=="unrelated.json":raise ValueError("should not be used")
        observed.append(name)
    opts["resolve_audit_evidence"]=reject_unrelated
    assert run() is None
    assert observed==["old.json","now.json"]


def test_legacy_without_events_is_read_only_and_returns_none(tmp_path):
    rows,ledger,opts,observed,inspected,run=_case(tmp_path)
    ledger["events"]=[]
    assert run() is None
    assert observed==[]
    assert not list(tmp_path.iterdir())


def test_invalid_adjudication_contest_does_not_become_ignored(tmp_path):
    rows,ledger,opts,observed,inspected,run=_case(tmp_path)
    rows[1]["target_contest"]="invalid"
    with pytest.raises(ValueError):
        run()
    assert observed==[]


def _unverified_report(tmp_path, scope):
    writes=[]
    def write_json(path, doc):
        writes.append((Path(path), doc))
    def run():
        return write_unverified_history_audit(
            tmp_path, scope, target=9001,
            independent_audit_file="independent.json", atomic_write_json=write_json)
    return writes,run


def test_unverified_history_report_records_only_nonpromotion_evidence(tmp_path):
    scope={
        "status":"DEGRADED_HISTORICAL_EVIDENCE_MISSING",
        "active_freeze_verified":True,
        "promotion_authority":False,
        "unverified_contests":[9000,8999],
    }
    writes,run=_unverified_report(tmp_path,scope)
    doc=run()
    assert writes==[(tmp_path/"independent.json",doc)]
    assert doc["schema"]=="SMART_HISTORICAL_EVIDENCE_NONPROMOTION_AUDIT_1"
    assert doc["target_contest"]==9001
    assert doc["unverified_contests"]==[9000,8999]
    for key in ("historical_verified","scientific_coverage_certified",
                "independent_full_audit_completed","promotion_authority",
                "terminal_promotion_permitted"):
        assert doc[key] is False
    assert doc["active_freeze_verified"] is True
    assert doc["prospective_ledger"]=={
        "status":"NOT_PROVEN_HISTORICAL_EVIDENCE_MISSING",
        "pair_count":None,"no_future_leakage":False,
    }
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("changes",[
    {"status":"PASS_SCOPED_FREEZE_EVIDENCE"},
    {"active_freeze_verified":False},
    {"promotion_authority":True},
    {"unverified_contests":[]},
    {"unverified_contests":None},
])
def test_unverified_history_report_fails_closed_without_complete_scope(tmp_path,changes):
    scope={"status":"DEGRADED_HISTORICAL_EVIDENCE_MISSING",
           "active_freeze_verified":True,"promotion_authority":False,
           "unverified_contests":[9000]}
    scope.update(changes)
    writes,run=_unverified_report(tmp_path,scope)
    with pytest.raises(ValueError,match="verified current freeze and real history gaps"):
        run()
    assert writes==[]


def test_unverified_report_does_not_suppress_writer_errors(tmp_path):
    scope={"status":"DEGRADED_HISTORICAL_EVIDENCE_MISSING",
           "active_freeze_verified":True,"promotion_authority":False,
           "unverified_contests":[9000]}
    with pytest.raises(OSError,match="audit disk unavailable"):
        write_unverified_history_audit(
            tmp_path,scope,target=9001,independent_audit_file="independent.json",
            atomic_write_json=lambda *args: (_ for _ in ()).throw(OSError("audit disk unavailable")))
    assert not list(tmp_path.iterdir())