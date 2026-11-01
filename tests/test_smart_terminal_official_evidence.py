"""Characterize immutable primary result and monotonic source corroboration."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

from smart_terminal_official_evidence import (
    ensure_primary_payload,
    ensure_monotonic_consensus,
    load_existing_official_evidence,
)


def _context(tmp_path):
    writes=[]
    def read_json(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))
    def write_json(path, document):
        writes.append(Path(path).name)
        Path(path).write_text(json.dumps(document),encoding="utf-8")
    def normalize(payload):
        return {"numbers": payload["numbers"], "draw_date": payload["draw_date"]}
    def primary(payload):
        return ensure_primary_payload(
            tmp_path, payload, primary_payload_file="primary.json",
            normalize_primary=normalize, read_json=read_json,
            atomic_write_json=write_json,
        )
    def consensus(document):
        return ensure_monotonic_consensus(
            tmp_path, document, target=3080, consensus_file="consensus.json",
            consensus_rank=lambda d:d["rank"], read_json=read_json,
            atomic_write_json=write_json,
        )
    def load():
        return load_existing_official_evidence(
            tmp_path, primary_payload_file="primary.json",
            consensus_file="consensus.json", normalize_primary=normalize,
            read_json=read_json,
        )
    first={"numbers":[1,2,3,4,5,6],"draw_date":"2026-11-01","channel":"operator"}
    stale={"target_contest":3080,"primary":{"numbers":first["numbers"],"draw_date":first["draw_date"],"validated":True}, "rank":1,"status":"PRIMARY"}
    corroborated={**stale,"rank":2,"status":"CORROBORATED"}
    return primary,consensus,load,first,stale,corroborated,writes


def test_first_primary_is_persisted_and_identical_retry_has_no_write(tmp_path):
    primary, consensus, load, first, stale, corroborated, writes=_context(tmp_path)
    assert primary(first) == first
    assert primary(dict(first)) == first
    assert writes==["primary.json"]


def test_conflicting_primary_observation_fails_without_rewrite(tmp_path):
    primary, consensus, load, first, stale, corroborated, writes=_context(tmp_path)
    primary(first)
    with pytest.raises(ValueError,match="immutable first observation"):
        primary({**first,"numbers":[1,2,3,4,5,7]})
    assert writes==["primary.json"]


def test_monotonic_upgrade_never_downgrades_corroboration(tmp_path):
    primary, consensus, load, first, stale, corroborated, writes=_context(tmp_path)
    assert consensus(stale)==stale
    assert consensus(corroborated)==corroborated
    assert consensus(stale)==corroborated
    assert consensus(corroborated)==corroborated
    assert writes==["consensus.json","consensus.json"]


def test_equal_rank_with_new_status_replaces_existing_document(tmp_path):
    primary, consensus, load, first, stale, corroborated, writes=_context(tmp_path)
    consensus(stale)
    next_doc={**stale,"status":"SECONDARY"}
    assert consensus(next_doc)==next_doc
    assert writes==["consensus.json","consensus.json"]


@pytest.mark.parametrize("mutation, message", [
    ({"target_contest":3081},"target mismatch"),
    ({"primary":{"validated":False}},"not validated"),
])
def test_invalid_consensus_is_rejected_before_writes(tmp_path,mutation,message):
    primary, consensus, load, first, stale, corroborated, writes=_context(tmp_path)
    invalid={**stale,**mutation}
    with pytest.raises(ValueError,match=message):
        consensus(invalid)
    assert writes==[]


@pytest.mark.parametrize("attribute,value", [
    ("numbers",[1,2,3,4,5,7]),
    ("draw_date","2026-11-02"),
])
def test_immutable_primary_consensus_cannot_be_changed(tmp_path,attribute,value):
    primary, consensus, load, first, stale, corroborated, writes=_context(tmp_path)
    consensus(stale)
    altered={**corroborated,"primary":{**stale["primary"],attribute:value}}
    with pytest.raises(ValueError,match="primary observation changed"):
        consensus(altered)
    assert writes==["consensus.json"]


def test_existing_evidence_is_loaded_without_file_writes(tmp_path):
    primary, consensus, load, first, stale, corroborated, writes=_context(tmp_path)
    assert load() is None
    primary(first)
    consensus(corroborated)
    assert load()==(first,corroborated)
    assert writes==["primary.json","consensus.json"]


@pytest.mark.parametrize("present", ["primary","consensus"])
def test_partial_official_evidence_fails_closed(tmp_path,present):
    primary, consensus, load, first, stale, corroborated, writes=_context(tmp_path)
    (tmp_path/f"{present}.json").write_text("{}",encoding="utf-8")
    with pytest.raises(ValueError,match="partially present"):
        load()


@pytest.mark.parametrize("attribute,value,message", [
    ("numbers",[6,5,4,3,2,1],"payload and consensus disagree"),
    ("draw_date","2026-11-02","consensus date disagree"),
])
def test_saved_consensus_must_match_stored_primary(tmp_path,attribute,value,message):
    primary, consensus, load, first, stale, corroborated, writes=_context(tmp_path)
    primary(first)
    consensus({**stale,"primary":{**stale["primary"],attribute:value}})
    with pytest.raises(ValueError,match=message):
        load()