import json
import pytest
from smart_video_official_catalog import CHANNEL, ingest
import smart_video_caixa_harvest as h

def source(n):
    return {"channel_id": CHANNEL, "entries": [
        {"id": f"{i:011d}", "title": "Loterias CAIXA"} for i in range(1,n+1)]}

def test_fetch_uses_video_details_and_channel(monkeypatch):
    class Fake:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):return None
        def read(self,count):
            return ('var ytInitialPlayerResponse = '+json.dumps({
                "playabilityStatus":{"status":"OK"},
                "videoDetails":{"videoId":"00000000001","channelId":CHANNEL,
                    "shortDescription":"Mega-Sena concurso 2963"}
                })+';').encode()
    monkeypatch.setattr(h.urllib.request,"urlopen",lambda *a,**kw: Fake())
    assert "2963" in h.fetch_public("00000000001")["description"]

def test_harvest_cache_resume_and_consistency(tmp_path,monkeypatch):
    ingest(source(3),tmp_path,max_items=3)
    calls=[]
    def fn(id_,**kw):
        calls.append(id_)
        return {"id":id_,"channel_id":CHANNEL,
                "description":"Mega-sena concurso "+str(2900+int(id_))}
    monkeypatch.setattr(h,"fetch_public",fn)
    result=h.harvest(tmp_path,take=3,workers=2)
    assert result["new_verified"]==3 and result["confirmed_mega_count"]==3
    p=tmp_path/"SMART_CAIXA_CATALOG_CURRENT.json";before=p.read_bytes()
    again=h.harvest(tmp_path,take=3,workers=2)
    assert again["new_verified"]==0 and again["cache_reused"]==3
    assert len(calls)==3 and before==p.read_bytes()

def test_wrong_author_does_not_enter_cache(tmp_path,monkeypatch):
    ingest(source(1),tmp_path,max_items=1)
    monkeypatch.setattr(h,"fetch_public",
        lambda id_,**kw: {"id":id_,"channel_id":"UCWRONG",
            "description":"Mega-sena concurso 2963"})
    r=h.harvest(tmp_path,take=1)
    assert r["new_verified"]==0 and r["failed"]==1
    assert not list((tmp_path/"youtube_metadata").glob("*.json"))
    assert not h.harvest(tmp_path,take=1)["new_verified"]
    row=json.loads((tmp_path/"SMART_CAIXA_CATALOG_CURRENT.json").read_text())["rows"][0]
    assert row["status"]=="UNCONFIRMED_MEGA"

def test_login_error_cached_with_retry_cooldown(tmp_path,monkeypatch):
    ingest(source(1),tmp_path,max_items=1)
    def fails(id_,**kw):raise RuntimeError("LOGIN_REQUIRED")
    monkeypatch.setattr(h,"fetch_public",fails)
    a=h.harvest(tmp_path,take=1)
    b=h.harvest(tmp_path,take=1)
    assert a["failed"]==1 and b["cooldown_skipped"]==1
    assert b["failed"]==0

def test_corrupted_immutable_cache_fails_closed(tmp_path,monkeypatch):
    ingest(source(1),tmp_path,max_items=1)
    monkeypatch.setattr(h,"fetch_public",
        lambda id_,**kw: {"id":id_,"channel_id":CHANNEL,"description":"Mega Sena concurso 2963"})
    h.harvest(tmp_path,take=1)
    p=next((tmp_path/"youtube_metadata").glob("*.json"))
    p.write_text("tampered")
    with pytest.raises(Exception):h.harvest(tmp_path,take=1)

@pytest.mark.parametrize("kwargs",[{"offset":-1},{"take":101},{"take":0},{"workers":7}])
def test_bounds_without_network(tmp_path,kwargs):
    ingest(source(1),tmp_path,max_items=1)
    with pytest.raises(ValueError):h.harvest(tmp_path,**kwargs)
