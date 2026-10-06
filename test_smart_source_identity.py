from pathlib import Path

from smart_source_identity import normalize_source_bytes, sha256_source_bytes, sha256_source_file, source_hashes


def test_source_identity_is_lf_crlf_invariant(tmp_path: Path):
    lf = tmp_path / 'lf.py'
    crlf = tmp_path / 'crlf.py'
    lf.write_bytes(b"x = 1\ny = 2\n")
    crlf.write_bytes(b"x = 1\r\ny = 2\r\n")
    assert sha256_source_file(lf) == sha256_source_file(crlf)


def test_source_identity_normalizes_legacy_bare_cr():
    assert sha256_source_bytes(b'a\rb\r') == sha256_source_bytes(b'a\nb\n')
    assert normalize_source_bytes(b'a\r\nb\r') == b'a\nb\n'


def test_source_identity_preserves_meaningful_non_eol_bytes():
    assert sha256_source_bytes(b'x = 1\n') != sha256_source_bytes(b'x = 2\n')


def test_source_hashes_rejects_duplicate_paths(tmp_path: Path):
    (tmp_path / 'a.py').write_text('x=1\n', encoding='utf-8')
    try:
        source_hashes(tmp_path, ['a.py', 'a.py'])
    except ValueError as exc:
        assert 'duplicate source identity path' in str(exc)
    else:
        raise AssertionError('duplicate source identity paths must fail closed')


def test_product_fingerprint_orders_names_independently_of_host(tmp_path: Path):
    from smart_product_certification import code_fingerprint

    contents = {
        "smart_example.py": b"x = 1\n",
        "test_example.py": b"def test_example(): pass\n",
        "requirements.lock.txt": b"example==1.0\n",
        "SMART_DATA_CONTRACT.md": b"# Contract\n",
    }
    for name, raw in contents.items():
        (tmp_path / name).write_bytes(raw)

    expected_names = (
        "SMART_DATA_CONTRACT.md",
        "requirements.lock.txt",
        "smart_example.py",
        "test_example.py",
    )
    expected_rows = [
        {"path": name, "sha256": sha256_source_bytes(contents[name])}
        for name in expected_names
    ]
    assert code_fingerprint(tmp_path)["files"] == expected_rows
