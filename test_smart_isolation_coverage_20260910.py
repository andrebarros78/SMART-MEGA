from pathlib import Path
import hashlib
import pytest
import smart_independent_audit as ia


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_strict_resolver_rejects_relative_traversal(tmp_path):
    root=tmp_path/'root'; root.mkdir()
    outside=tmp_path/'outside.bin'; outside.write_bytes(b'outside')
    with pytest.raises(ValueError,match='escapes project root'):
        ia._resolve_hash_bound_evidence(root,'../outside.bin',_sha(outside),'traversal')


def test_historical_hash_lookup_skips_directory_and_fails_missing(tmp_path):
    root=tmp_path/'root'; root.mkdir(); (root/'artifact.bin').mkdir()
    with pytest.raises(ValueError,match='missing'):
        ia._resolve_historical_evidence_by_hash(root,'artifact.bin','0'*64,'artifact')


def test_historical_hash_lookup_rejects_resolved_escape(tmp_path,monkeypatch):
    root=tmp_path/'root'; root.mkdir(); candidate=root/'artifact.bin'; candidate.write_bytes(b'x')
    escaped=tmp_path/'escaped.bin'
    original=Path.resolve
    def guarded(self,*args,**kwargs):
        if str(self)==str(candidate): return escaped
        return original(self,*args,**kwargs)
    monkeypatch.setattr(Path,'resolve',guarded)
    with pytest.raises(ValueError,match='evidence candidate escapes project root'):
        ia._resolve_historical_evidence_by_hash(root,'artifact.bin',_sha(candidate),'artifact')


def test_historical_hash_lookup_oserror_fails_closed(tmp_path,monkeypatch):
    root=tmp_path/'root'; root.mkdir(); candidate=root/'artifact.bin'; candidate.write_bytes(b'x')
    real=ia.sha256_file
    def broken(path):
        if Path(path)==candidate: raise OSError('simulated read failure')
        return real(path)
    monkeypatch.setattr(ia,'sha256_file',broken)
    with pytest.raises(ValueError,match='missing'):
        ia._resolve_historical_evidence_by_hash(root,'artifact.bin','0'*64,'artifact')


def test_historical_hash_lookup_no_candidate_fails_closed(tmp_path):
    root=tmp_path/'root'; root.mkdir()
    with pytest.raises(ValueError,match='missing'):
        ia._resolve_historical_evidence_by_hash(root,'absent.bin','0'*64,'artifact')
