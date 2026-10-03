from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

SCHEMA = 'SMART_SOURCE_IDENTITY_1'


def normalize_source_bytes(raw: bytes) -> bytes:
    if not isinstance(raw, bytes):
        raise TypeError('source identity requires bytes')
    return raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def sha256_source_bytes(raw: bytes) -> str:
    return hashlib.sha256(normalize_source_bytes(raw)).hexdigest()


def sha256_source_file(path: str | Path) -> str:
    return sha256_source_bytes(Path(path).read_bytes())


def source_hashes(root: str | Path, filenames: Iterable[str]) -> dict[str, str]:
    base = Path(root)
    out: dict[str, str] = {}
    for name in filenames:
        if name in out:
            raise ValueError(f'duplicate source identity path: {name}')
        path = base / name
        if not path.is_file():
            raise FileNotFoundError(path)
        out[name] = sha256_source_file(path)
    return out


__all__ = ['SCHEMA', 'normalize_source_bytes', 'sha256_source_bytes', 'sha256_source_file', 'source_hashes']
