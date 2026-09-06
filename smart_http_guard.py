from __future__ import annotations

import json
from urllib.parse import urlparse
from typing import Any

CHUNK_BYTES = 64 * 1024


def read_limited_bytes(response: Any, *, max_bytes: int) -> bytes:
    if not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    headers = getattr(response, "headers", {}) or {}
    raw_length = headers.get("Content-Length") if hasattr(headers, "get") else None
    if raw_length not in (None, ""):
        try:
            declared = int(raw_length)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid Content-Length") from exc
        if declared < 0 or declared > max_bytes:
            raise ValueError("remote response exceeds size limit")
    iterator = getattr(response, "iter_content", None)
    if callable(iterator):
        chunks: list[bytes] = []
        total = 0
        for chunk in iterator(chunk_size=CHUNK_BYTES):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("remote response exceeds size limit")
            chunks.append(bytes(chunk))
        return b"".join(chunks)
    content = getattr(response, "content", None)
    if content is not None:
        data = bytes(content)
        if len(data) > max_bytes:
            raise ValueError("remote response exceeds size limit")
        return data
    json_method = getattr(response, "json", None)
    if callable(json_method):
        data = json.dumps(json_method(), ensure_ascii=False).encode("utf-8")
        if len(data) > max_bytes:
            raise ValueError("remote response exceeds size limit")
        return data
    raise ValueError("response body is unavailable")


def validate_https_url(url: str, *, allowed_host_suffixes: tuple[str, ...]) -> str:
    parsed = urlparse(str(url))
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("remote URL must be credential-free HTTPS")
    host = parsed.hostname.lower().rstrip(".")
    normalized = tuple(s.lower().lstrip(".").rstrip(".") for s in allowed_host_suffixes if s)
    if not normalized or not any(host == suffix or host.endswith("." + suffix) for suffix in normalized):
        raise ValueError("remote URL host is not allowed")
    return str(url)
