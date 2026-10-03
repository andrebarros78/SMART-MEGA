import hashlib

import pytest

import smart_repository_integrity as sri


def test_repository_integrity_contract() -> None:
    evidence = sri.validate_repository()
    assert evidence["status"] == "PASS"
    assert evidence["portable_identity"] is True
    assert evidence["epoch"]["status"] == "FROZEN"
    assert evidence["epoch"]["target_contest"] > evidence["epoch"]["cutoff_contest"]


def test_text_authority_hash_accepts_lf_crlf_equivalence(tmp_path, monkeypatch) -> None:
    payload_lf = b'{\n  "status": "PASS"\n}\n'
    path = tmp_path / "authority.json"
    path.write_bytes(payload_lf)
    expected_crlf = hashlib.sha256(payload_lf.replace(b"\n", b"\r\n")).hexdigest()

    monkeypatch.setattr(sri, "ROOT", tmp_path)
    sri._require_raw_hash("authority", "authority.json", expected_crlf)


def test_text_authority_hash_rejects_semantic_change(tmp_path, monkeypatch) -> None:
    actual = b'{\n  "status": "FAIL"\n}\n'
    expected = b'{\r\n  "status": "PASS"\r\n}\r\n'
    path = tmp_path / "authority.json"
    path.write_bytes(actual)

    monkeypatch.setattr(sri, "ROOT", tmp_path)
    with pytest.raises(sri.RepositoryIntegrityError, match="SHA-256 mismatch"):
        sri._require_raw_hash("authority", "authority.json", hashlib.sha256(expected).hexdigest())


def test_binary_authority_hash_remains_byte_exact(tmp_path, monkeypatch) -> None:
    payload_lf = b"header\nbody\n"
    path = tmp_path / "authority.xlsx"
    path.write_bytes(payload_lf)
    newline_variant = hashlib.sha256(payload_lf.replace(b"\n", b"\r\n")).hexdigest()

    monkeypatch.setattr(sri, "ROOT", tmp_path)
    with pytest.raises(sri.RepositoryIntegrityError, match="SHA-256 mismatch"):
        sri._require_raw_hash("authority", "authority.xlsx", newline_variant)
