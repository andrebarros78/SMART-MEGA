

def test_code_fingerprint_is_line_ending_invariant(tmp_path):
    from smart_ci_authority_gate import code_fingerprint
    target = tmp_path / "smart_probe.py"
    target.write_bytes(b"x = 1\nprint(x)\n")
    lf = code_fingerprint(tmp_path)
    target.write_bytes(b"x = 1\r\nprint(x)\r\n")
    crlf = code_fingerprint(tmp_path)
    assert lf == crlf


def test_code_fingerprint_is_line_ending_invariant(tmp_path):
    from smart_ci_authority_gate import code_fingerprint
    target = tmp_path / "smart_probe.py"
    target.write_bytes(b"x = 1\nprint(x)\n")
    lf = code_fingerprint(tmp_path)
    target.write_bytes(b"x = 1\r\nprint(x)\r\n")
    crlf = code_fingerprint(tmp_path)
    assert lf == crlf
