import io
import json
import urllib.error

import pytest
from smart_video_official_catalog import CHANNEL, ingest
from smart_video_caixa_data_api import _query, hydrate_api, normalize_items


def discovery(n=500):
    return {"channel_id": CHANNEL, "entries": [
        {"id": f"{i:011d}", "title": "Loterias CAIXA"} for i in range(1,n+1)]}


def test_bulk_500_needs_only_10_api_requests_and_is_idempotent(tmp_path):
    ingest(discovery(500), tmp_path, max_items=500)
    called=[]
    def api(ids, key):
        assert key == "TEST_NONSECRET_PLACEHOLDER"
        assert 1 <= len(ids) <= 50
        called.append(tuple(ids))
        return {"items":[{"id":id_, "snippet":{
            "channelId":CHANNEL,"description":"Mega-Sena concurso "+str(int(id_)+2000)}} for id_ in ids]}
    first=hydrate_api(tmp_path,api_key="TEST_NONSECRET_PLACEHOLDER",query=api)
    assert first["api_requests"] == 10
    assert first["new_verified_metadata"] == 500
    assert len(called)==10
    assert first["predictive_weight"]==0
    after=hydrate_api(tmp_path,api_key="TEST_NONSECRET_PLACEHOLDER",query=api)
    assert after["api_requests"]==0 and after["cached_reused"]==500
    assert len(called)==10
    assert first["catalog_sha256"]==after["catalog_sha256"]
    assert after["api_key_exposed"] is False


def test_other_channel_rejected_before_any_file_cached(tmp_path):
    ingest(discovery(2), tmp_path, max_items=2)
    def api(ids,key):
        return {"items":[{"id":ids[0],"snippet":{"channelId":CHANNEL,"description":"safe"}},
                         {"id":ids[1],"snippet":{"channelId":"UCFAKE","description":"malicious"}}]}
    original=(tmp_path/"SMART_CAIXA_CATALOG_CURRENT.json").read_bytes()
    with pytest.raises(ValueError,match="CREATOR"):
        hydrate_api(tmp_path,api_key="TEST_NONSECRET_PLACEHOLDER",query=api)
    assert not list((tmp_path/"youtube_metadata").glob("*.json"))
    assert (tmp_path/"SMART_CAIXA_CATALOG_CURRENT.json").read_bytes()==original


def test_missing_api_video_resource_has_no_fake_mega(tmp_path):
    ingest(discovery(2), tmp_path, max_items=2)
    def api(ids,key):
        return {"items":[{"id":ids[0],"snippet":{"channelId":CHANNEL,"description":"Mega-Sena concurso 3001"}}]}
    result=hydrate_api(tmp_path,api_key="TEST_NONSECRET_PLACEHOLDER",query=api)
    assert result["missing_video_resources"]==1
    assert result["new_verified_metadata"]==1
    doc=json.loads((tmp_path/"SMART_CAIXA_CATALOG_CURRENT.json").read_text())
    assert doc["rows"][1]["status"]=="UNCONFIRMED_MEGA"
    assert doc["rows"][1]["video_analyzed"] is False


def test_no_key_fails_before_request_or_mutation(tmp_path, monkeypatch):
    ingest(discovery(1), tmp_path, max_items=1)
    monkeypatch.delenv("SMART_MEGA_YOUTUBE_API_KEY",raising=False)
    before=(tmp_path/"SMART_CAIXA_CATALOG_CURRENT.json").read_bytes()
    called=[]
    with pytest.raises(ValueError,match="KEY_NOT_CONFIGURED"):
        hydrate_api(tmp_path,query=lambda ids,key:called.append(1))
    assert called==[]
    assert (tmp_path/"SMART_CAIXA_CATALOG_CURRENT.json").read_bytes()==before


def test_http_key_only_header_not_url(monkeypatch):
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return b'{"items":[]}'
    def fake(req,timeout):
        assert req.get_header("X-goog-api-key")=="PLACEHOLDER_KEY"
        assert "PLACEHOLDER_KEY" not in req.full_url
        assert "id=00000000001" in req.full_url
        return Response()
    import smart_video_caixa_data_api as mod
    monkeypatch.setattr(mod.urllib.request,"urlopen",fake)
    assert _query(["00000000001"],"PLACEHOLDER_KEY")=={"items":[]}


def test_reject_unrequested_duplicate_and_invalid_metadata():
    with pytest.raises(ValueError,match="UNREQUESTED"):
        normalize_items(["00000000001"],{"items":[{"id":"00000000002","snippet":{"channelId":CHANNEL,"description":"no"}}]})
    with pytest.raises(ValueError,match="CREATOR"):
        normalize_items(["00000000001"],{"items":[{"id":"00000000001","snippet":{"channelId":"UCFAKE","description":"no"}}]})


@pytest.mark.parametrize("limit,batch",[(-1,50),(501,51),(0,50)])
def test_bounds_no_network(limit,batch,tmp_path):
    ingest(discovery(1), tmp_path,max_items=1)
    with pytest.raises(ValueError,match="LIMIT"):
        hydrate_api(tmp_path,limit=limit,batch_size=batch,api_key="TEST")


def test_api_http_error_sanitized(monkeypatch):
    import smart_video_caixa_data_api as mod
    def failed(req,timeout):
        raise urllib.error.HTTPError(req.full_url,403,"permission denied",{},io.BytesIO(b'sensitive body'))
    monkeypatch.setattr(mod.urllib.request,"urlopen",failed)
    with pytest.raises(RuntimeError,match="YOUTUBE_API_HTTP_403") as err:
        _query(["00000000001"],"KEY_SHOULD_NEVER_PRINT")
    assert "KEY_SHOULD_NEVER_PRINT" not in str(err.value)
    assert "sensitive body" not in str(err.value)
