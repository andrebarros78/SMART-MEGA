import json
import pytest
from smart_video_official_catalog import CHANNEL, URL, ingest, enrich, normalize, discover


def data(n=500):
    return {"channel_id": CHANNEL, "source_url": URL,
            "entries":[{"id":f"{i:011d}","title":f"CAIXA Loterias {i}"} for i in range(1,n+1)]}


def test_500_sources_are_cataloged_and_reusable(tmp_path):
    r=ingest(data(),tmp_path)
    assert r["indexed"]==500 and r["new_broadcasts"]==500 and r["real_videos_analyzed"]==0
    assert r["status_counts"]["UNCONFIRMED_MEGA"]==500 and r["predictive_weight"]==0
    p=tmp_path/"SMART_CAIXA_CATALOG_CURRENT.json";before=p.read_bytes()
    r2=ingest(data(),tmp_path)
    assert r2["new_broadcasts"]==0 and not r2["changed"] and r2["catalog_sha256"]==r["catalog_sha256"]
    assert p.read_bytes()==before and len(list((tmp_path/"catalog_history").glob("*.json")))==1


def test_refresh_keeps_all_prior_evidence(tmp_path):
    ingest(data(3),tmp_path,max_items=4)
    latest=data(4);latest["entries"]=latest["entries"][2:]
    r=ingest(latest,tmp_path,max_items=4)
    assert r["indexed"]==4 and r["new_broadcasts"]==1
    assert len(list((tmp_path/"catalog_history").glob("*.json")))==2
    saved=json.loads((tmp_path/"SMART_CAIXA_CATALOG_CURRENT.json").read_text())
    assert saved["rows"][0]["id"]=="00000000001"


@pytest.mark.parametrize("wrong",[
    {"channel_id":"fake","entries":[]},
    {"channel_id":CHANNEL,"source_url":"https://youtube.com/@other/streams","entries":[]},
    {"channel_id":CHANNEL,"entries":[{"id":"abc"}]},
    {"channel_id":CHANNEL,"entries":[{"id":"ABCDEFGHIJK"},{"id":"ABCDEFGHIJK"}]},
    {"channel_id":CHANNEL,"entries":[{"id":"AAAAAAAAAAA","channel_id":"UCOTHER"}]}
])
def test_fail_closed_source(wrong):
    with pytest.raises(ValueError):normalize(wrong)


def test_confirmed_mega_contest_is_still_not_video_analysis(tmp_path):
    ingest(data(2),tmp_path,max_items=2)
    metadata=[{"id":"00000000001","channel_id":CHANNEL,
               "description":"Transmissão CAIXA. Mega-sena - concurso nº 2963; Quina concurso nº 6934."}]
    r=enrich(metadata,tmp_path)
    assert r["status_counts"]["CONFIRMED_MEGA_METADATA"]==1 and r["predictive_weight"]==0
    doc=json.loads((tmp_path/"SMART_CAIXA_CATALOG_CURRENT.json").read_text())
    assert doc["rows"][0]["mega_contest"]=="2963" and not doc["rows"][0]["video_analyzed"]
    assert not enrich(metadata,tmp_path)["changed"]


def test_ambiguous_contest_no_fake_assignment(tmp_path):
    ingest(data(1),tmp_path,max_items=1)
    enrich([{"id":"00000000001","channel_id":CHANNEL,
             "description":"Mega Sena concurso 2963, Mega Sena concurso 2964"}],tmp_path)
    doc=json.loads((tmp_path/"SMART_CAIXA_CATALOG_CURRENT.json").read_text())
    assert doc["rows"][0]["status"]=="AMBIGUOUS_MEGA_METADATA"
    assert doc["rows"][0]["mega_contest"] is None


def test_reject_other_author_and_missing_description_atomically(tmp_path):
    ingest(data(2),tmp_path,max_items=2);p=tmp_path/"SMART_CAIXA_CATALOG_CURRENT.json"
    before=p.read_bytes()
    for detail in [
      [{"id":"00000000001","channel_id":"UCOTHER","description":"Mega Sena concurso 2963"}],
      [{"id":"00000000001","channel_id":CHANNEL}]
    ]:
        with pytest.raises(ValueError):enrich(detail,tmp_path)
        assert p.read_bytes()==before


def test_bad_history_never_overwritten(tmp_path):
    ingest(data(1),tmp_path,max_items=1)
    history=next((tmp_path/"catalog_history").glob("*.json"));history.write_text("TAMPERED")
    p=tmp_path/"SMART_CAIXA_CATALOG_CURRENT.json";before=p.read_bytes()
    with pytest.raises(ValueError,match="CORRUPT"):ingest(data(2),tmp_path,max_items=2)
    assert p.read_bytes()==before


def test_invalid_data_creates_no_files(tmp_path):
    with pytest.raises(ValueError):ingest({"channel_id":"fake","entries":[]},tmp_path)
    assert list(tmp_path.iterdir())==[]


def test_oversized_input_creates_no_files(tmp_path):
    with pytest.raises(ValueError):ingest(data(500),tmp_path,max_items=499)
    assert list(tmp_path.iterdir())==[]


def test_locked_writer_will_not_race(tmp_path):
    ingest(data(1),tmp_path,max_items=1)
    (tmp_path/".catalog.lock").write_text("active")
    with pytest.raises(RuntimeError,match="BUSY"):ingest(data(2),tmp_path,max_items=2)


def test_direct_official_discovery_bounded(monkeypatch):
    import smart_video_official_catalog as c
    class Result:
        returncode=0
        stdout=json.dumps(data(5))
    def mock(command,**kw):
        assert URL in command and "--skip-download" in command
        assert "--playlist-end" in command
        return Result()
    monkeypatch.setattr(c.subprocess,"run",mock)
    assert len(discover(limit=5)["entries"])==5
