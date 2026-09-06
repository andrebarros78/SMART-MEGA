import pytest
from smart_http_guard import read_limited_bytes, validate_https_url

class FakeResponse:
    def __init__(self,chunks,headers=None): self._chunks=chunks; self.headers=headers or {}
    def iter_content(self,chunk_size=65536): yield from self._chunks

def test_read_limited_bytes_accepts_bounded_and_rejects_stream_overflow():
    assert read_limited_bytes(FakeResponse([b"abc",b"def"]),max_bytes=6)==b"abcdef"
    with pytest.raises(ValueError,match="size limit"):
        read_limited_bytes(FakeResponse([b"1234",b"5678"]),max_bytes=7)
    with pytest.raises(ValueError,match="size limit"):
        read_limited_bytes(FakeResponse([],headers={"Content-Length":"999"}),max_bytes=10)

def test_read_limited_bytes_rejects_invalid_content_length():
    with pytest.raises(ValueError,match="Content-Length"):
        read_limited_bytes(FakeResponse([],headers={"Content-Length":"broken"}),max_bytes=10)

def test_validate_https_url_rejects_ssrf_and_credentials():
    assert validate_https_url("https://www.youtube.com/api/timedtext",allowed_host_suffixes=("youtube.com","googlevideo.com"))
    assert validate_https_url("https://rr1---sn.example.googlevideo.com/x",allowed_host_suffixes=("youtube.com","googlevideo.com"))
    for url in ("http://www.youtube.com/x","https://youtube.com.evil.test/x","https://user:pass@youtube.com/x","https://127.0.0.1/x"):
        with pytest.raises(ValueError): validate_https_url(url,allowed_host_suffixes=("youtube.com","googlevideo.com"))
