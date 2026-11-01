"""Characterize safe read-only probing of official result availability."""
from __future__ import annotations

from pathlib import Path
import pytest

from smart_terminal_probe import probe_terminal_result


def _case(tmp_path):
    freeze = tmp_path / "freeze.json"
    freeze.write_text("frozen", encoding="utf-8")
    calls=[]
    state={"events":[], "existing":None, "readiness":"PASS"}
    payload={"numbers":[1,2,3,4,5,6], "draw_date":"2026-11-01"}
    consensus={
        "terminal_source_corroboration_authorized":True,
        "primary":{"channel":"operator"},
    }
    def fetch(target):
        calls.append(("fetch", target))
        return payload,consensus
    options=dict(
        target=3080,schema="SMART_TERMINAL_ENGINE_LEGACY_COMPAT_V1",
        canonical_root=lambda root:Path(root),
        default_operator_fetcher=lambda root:fetch,
        runtime_binding=lambda root:{"freeze":freeze,"freeze_sha256":"frozen-sha",
                                      "ledger":root/"ledger.json"},
        sha256_file=lambda path:"frozen-sha",
        load_ledger=lambda path:{"events":state["events"]},
        target_events=lambda ledger,event:[e for e in ledger["events"]
                                           if e.get("event_type")==event],
        load_existing_official_evidence=lambda root:state["existing"],
        preflight_readiness=lambda root,binding:{"readiness_status":state["readiness"]},
        normalize_primary=lambda p:p,
    )
    def run(fetcher=fetch):
        return probe_terminal_result(tmp_path, fetcher, **options)
    return state,options,calls,fetch,payload,consensus,run


def test_available_probe_reports_operator_and_never_mutates(tmp_path):
    state,options,calls,fetch,payload,consensus,run=_case(tmp_path)
    result=run()
    assert result["status"]=="OFFICIAL_RESULT_AVAILABLE"
    assert result["target_contest"]==3080
    assert result["actual_numbers"]==payload["numbers"]
    assert result["draw_date"]==payload["draw_date"]
    assert result["result_input_authority"]=="operator"
    assert result["terminal_source_corroboration_authorized"] is True
    assert result["canonical_writes_performed"] is False
    assert result["terminal_6of6_proven"] is False
    assert calls==[("fetch",3080)]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["freeze.json"]


def test_unavailable_result_before_adjudication_waits_without_writes(tmp_path):
    state,options,calls,fetch,payload,consensus,run=_case(tmp_path)
    def unavailable(target):
        raise RuntimeError("no official result yet")
    result=run(unavailable)
    assert result["status"]=="WAITING_OFFICIAL_RESULT"
    assert result["error_type"]=="RuntimeError"
    assert result["preflight_status"]=="PASS"
    assert result["official_result_available"] is False
    assert result["canonical_writes_performed"] is False
    assert sorted(p.name for p in tmp_path.iterdir()) == ["freeze.json"]


def test_old_evidence_when_refresh_fails_is_still_read_only(tmp_path):
    state,options,calls,fetch,payload,consensus,run=_case(tmp_path)
    state["existing"]=(payload,consensus)
    def unavailable(target):
        raise OSError("offline provider")
    result=run(unavailable)
    assert result["status"]=="OFFICIAL_RESULT_ALREADY_CAPTURED_REFRESH_UNAVAILABLE"
    assert result["error_type"]=="OSError"
    assert result["terminal_source_corroboration_authorized"] is True
    assert result["canonical_writes_performed"] is False
    assert result["terminal_6of6_proven"] is False
    assert sorted(p.name for p in tmp_path.iterdir()) == ["freeze.json"]


def test_existing_adjudication_skips_preflight(tmp_path):
    state,options,calls,fetch,payload,consensus,run=_case(tmp_path)
    state["events"].append({"event_type":"ADJUDICATION"})
    state["readiness"]="NOT_READY"
    result=run()
    assert result["preflight_status"]=="POST_RESULT_SEQUENCE_IN_PROGRESS_OR_COMPLETE"
    assert result["status"]=="OFFICIAL_RESULT_AVAILABLE"


def test_adjudication_without_saved_evidence_propagates_provider_error(tmp_path):
    state,options,calls,fetch,payload,consensus,run=_case(tmp_path)
    state["events"].append({"event_type":"ADJUDICATION"})
    with pytest.raises(OSError,match="provider down"):
        run(lambda target: (_ for _ in ()).throw(OSError("provider down")))


@pytest.mark.parametrize("reason", ["absent", "hash"])
def test_invalid_freeze_is_rejected_before_provider_access(tmp_path,reason):
    state,options,calls,fetch,payload,consensus,run=_case(tmp_path)
    if reason=="absent":
        (tmp_path/"freeze.json").unlink()
    else:
        options["sha256_file"]=lambda path:"different-sha"
    with pytest.raises(ValueError,match="freeze hash differs"):
        run()
    assert calls==[]


def test_preflight_failure_blocks_before_provider_access(tmp_path):
    state,options,calls,fetch,payload,consensus,run=_case(tmp_path)
    state["readiness"]="WAITING"
    with pytest.raises(RuntimeError,match="preflight is not PASS"):
        run()
    assert calls==[]


def test_default_provider_is_resolved_only_when_fetcher_absent(tmp_path):
    state,options,calls,fetch,payload,consensus,run=_case(tmp_path)
    result=run(None)
    assert result["status"]=="OFFICIAL_RESULT_AVAILABLE"
    assert calls==[("fetch",3080)]


def test_invalid_normalization_error_is_not_silently_downgraded(tmp_path):
    state,options,calls,fetch,payload,consensus,run=_case(tmp_path)
    options["normalize_primary"]=lambda data: (_ for _ in ()).throw(ValueError("invalid official numbers"))
    with pytest.raises(ValueError,match="invalid official numbers"):
        run()


def test_no_automatic_evidence_upgrade_from_probe(tmp_path):
    state,options,calls,fetch,payload,consensus,run=_case(tmp_path)
    consensus["terminal_source_corroboration_authorized"]=False
    assert run()["terminal_source_corroboration_authorized"] is False
    assert sorted(p.name for p in tmp_path.iterdir()) == ["freeze.json"]