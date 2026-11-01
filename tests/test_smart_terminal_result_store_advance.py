"""Canonical result-store transition is prefix-safe and idempotent."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest

from smart_terminal_result_store import advance_canonical_result_store


def _case(tmp_path, *, canonical_rows=(3079,), through_rows=(3079, 3080)):
    def payload(rows):
        return "".join(
            f"{index}:1,2,3,4,5,6\n" for index in rows
        ).encode("ascii")
    canonical = tmp_path / "Mega-Sena.xlsx"
    through = tmp_path / "official.xlsx"
    canonical.write_bytes(payload(canonical_rows))
    through.write_bytes(payload(through_rows))

    def draws(path):
        out={}
        for row in Path(path).read_text(encoding="ascii").splitlines():
            contest, balls=row.split(":",1)
            out[int(contest)]=tuple(int(ball) for ball in balls.split(","))
        return out

    def file_hash(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def read_doc(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def write_doc(path, doc):
        Path(path).write_text(json.dumps(doc), encoding="utf-8")

    config = dict(
        target=3080, cutoff=3079, result_data="official.xlsx",
        result_store_proof="proof.json", draw_map=draws,
        sha256_file=file_hash, read_json=read_doc, atomic_write_json=write_doc,
    )

    def run():
        return advance_canonical_result_store(tmp_path, **config)
    return canonical, through, config, run


def test_advancement_preserves_prefix_and_persists_proof(tmp_path):
    canonical, through, config, run = _case(tmp_path)
    expected_before = canonical.read_bytes()
    proof = run()
    assert canonical.read_bytes() == through.read_bytes()
    assert expected_before != canonical.read_bytes()
    assert proof["target_contest"] == 3080
    assert proof["canonical_max_after"] == 3080
    assert proof["status"] == "PASS"
    assert proof["retroactive_rewrite"] is False
    assert proof["canonical_sha256_before"] == hashlib.sha256(expected_before).hexdigest()
    assert proof["canonical_sha256_after"] == hashlib.sha256(through.read_bytes()).hexdigest()
    assert json.loads((tmp_path / "proof.json").read_text()) == proof


def test_repeated_advancement_returns_existing_proof_without_rewriting(tmp_path):
    canonical, through, config, run = _case(tmp_path)
    first = run()
    before_proof = (tmp_path / "proof.json").read_bytes()
    before_store = canonical.read_bytes()
    assert run() == first
    assert (tmp_path / "proof.json").read_bytes() == before_proof
    assert canonical.read_bytes() == before_store


@pytest.mark.parametrize("canonical_rows, through_rows, expected", [
    ((3079,), (3079, 3081), "does not end"),
    ((3078,), (3078, 3079, 3080), "pre-advance cutoff"),
    ((3079,), (3080,), "prefix mismatch"),
    ((3079, 3080), (3079, 3080, 3081), "does not end"),
    ((3079, 3080), (3079, 3080), "without its proof"),
])
def test_invalid_canonical_transition_fails_without_changes(
    tmp_path, canonical_rows, through_rows, expected
):
    canonical, through, config, run = _case(
        tmp_path, canonical_rows=canonical_rows, through_rows=through_rows
    )
    before=canonical.read_bytes()
    with pytest.raises(ValueError, match=expected):
        run()
    assert canonical.read_bytes()==before
    assert not (tmp_path / "proof.json").exists()


def test_conflicting_existing_final_store_never_reused(tmp_path):
    canonical, through, config, run = _case(
        tmp_path, canonical_rows=(3079, 3080), through_rows=(3079, 3080)
    )
    # Existing store differs from verified through-file despite matching contests.
    canonical.write_bytes(b"3079:1,2,3,4,5,6\n3080:6,5,4,3,2,1\n")
    with pytest.raises(ValueError, match="canonical result prefix mismatch"):
        run()


def test_temporary_copy_mismatch_fails_before_store_replace(tmp_path, monkeypatch):
    import smart_terminal_result_store as store
    canonical, through, config, run = _case(tmp_path)
    before=canonical.read_bytes()
    original_copy=store.shutil.copyfile

    def corrupt_copy(source, target):
        result=original_copy(source, target)
        if Path(source)==through:
            Path(target).write_bytes(b"3079:1,2,3,4,5,6\n3080:9,8,7,6,5,4\n")
        return result

    monkeypatch.setattr(store.shutil, "copyfile", corrupt_copy)
    with pytest.raises(RuntimeError, match="temporary canonical result store verification failed"):
        run()
    assert canonical.read_bytes()==before
    assert not list(tmp_path.glob("Mega-Sena.3054.*.tmp.xlsx"))
    assert not (tmp_path / "proof.json").exists()


def test_proof_writer_failure_propagates_without_false_claim(tmp_path):
    canonical, through, config, run = _case(tmp_path)
    config["atomic_write_json"] = lambda *args: (_ for _ in ()).throw(OSError("disk full"))
    with pytest.raises(OSError, match="disk full"):
        run()
    assert not (tmp_path / "proof.json").exists()


def test_failed_proof_write_can_recover_after_restart(tmp_path):
    canonical, through, config, run = _case(tmp_path)
    before=canonical.read_bytes()
    real_writer=config["atomic_write_json"]
    config["atomic_write_json"]=lambda path, doc: (
        (_ for _ in ()).throw(OSError("storage unavailable"))
        if Path(path)==tmp_path/"proof.json" else real_writer(path, doc)
    )
    with pytest.raises(OSError, match="storage unavailable"):
        run()
    assert canonical.read_bytes()==through.read_bytes()
    assert not (tmp_path/"proof.json").exists()
    config["atomic_write_json"]=real_writer
    proof=run()
    assert proof["canonical_sha256_before"]==hashlib.sha256(before).hexdigest()
    assert proof["canonical_sha256_after"]==hashlib.sha256(through.read_bytes()).hexdigest()
    assert json.loads((tmp_path/"proof.json").read_text())==proof
    assert not list(tmp_path.glob(".Mega-Sena.3080.advance-*"))


def test_interruption_after_swap_recovers_without_rewriting_canonical(tmp_path, monkeypatch):
    import smart_terminal_result_store as store
    canonical, through, config, run = _case(tmp_path)
    first_sha=hashlib.sha256(canonical.read_bytes()).hexdigest()
    original_replace=store.os.replace
    def interrupted_replace(src, dest):
        result=original_replace(src, dest)
        if Path(dest)==canonical:
            raise KeyboardInterrupt("simulated process interruption after replace")
        return result
    monkeypatch.setattr(store.os, "replace", interrupted_replace)
    with pytest.raises(KeyboardInterrupt, match="simulated process interruption"):
        run()
    monkeypatch.setattr(store.os, "replace", original_replace)
    assert canonical.read_bytes()==through.read_bytes()
    assert not (tmp_path/"proof.json").exists()
    proof=run()
    assert proof["canonical_sha256_before"]==first_sha
    assert proof["status"]=="PASS"
    assert not list(tmp_path.glob(".Mega-Sena.3080.advance-*"))


@pytest.mark.parametrize("altered", ["backup", "intent", "through"])
def test_pending_transaction_tampering_is_rejected(tmp_path, altered):
    canonical, through, config, run = _case(tmp_path)
    real_writer=config["atomic_write_json"]
    config["atomic_write_json"]=lambda path, doc: (
        (_ for _ in ()).throw(OSError("writer failed"))
        if Path(path)==tmp_path/"proof.json" else real_writer(path, doc)
    )
    with pytest.raises(OSError, match="writer failed"):
        run()
    if altered=="backup":
        [backup]=list(tmp_path.glob(".Mega-Sena.3080.advance-before*"))
        backup.write_bytes(b"corrupt historic prefix")
    elif altered=="intent":
        [intent]=list(tmp_path.glob(".Mega-Sena.3080.advance-intent*"))
        intent.write_text(json.dumps({"status":"FORGED"}))
    else:
        through.write_bytes(b"3079:1,2,3,4,5,6\n3080:9,8,7,6,5,4\n")
    config["atomic_write_json"]=lambda path, doc: Path(path).write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="pending canonical transaction"):
        run()
    assert not (tmp_path/"proof.json").exists()


def test_existing_unjournaled_advanced_store_remains_fail_closed(tmp_path):
    canonical, through, config, run = _case(tmp_path, canonical_rows=(3079,3080))
    with pytest.raises(ValueError, match="without its proof"):
        run()
    assert not list(tmp_path.glob(".Mega-Sena.3080.advance-*"))


def test_crash_after_proof_commit_recovers_cleanup_without_rewriting(tmp_path, monkeypatch):
    import smart_terminal_result_store as store
    canonical, through, config, run = _case(tmp_path)
    intent = tmp_path / ".Mega-Sena.3080.advance-intent.json"
    original_unlink=Path.unlink
    def interrupted_unlink(path, *args, **kwargs):
        if Path(path)==intent:
            raise KeyboardInterrupt("post-proof cleanup interrupted")
        return original_unlink(path, *args, **kwargs)
    monkeypatch.setattr(store.Path, "unlink", interrupted_unlink)
    with pytest.raises(KeyboardInterrupt, match="cleanup interrupted"):
        run()
    monkeypatch.setattr(store.Path, "unlink", original_unlink)
    proof_before=(tmp_path/"proof.json").read_bytes()
    assert intent.exists()
    assert run()==json.loads(proof_before)
    assert (tmp_path/"proof.json").read_bytes()==proof_before
    assert not list(tmp_path.glob(".Mega-Sena.3080.advance-*"))


def test_intent_writer_failure_never_replaces_canonical(tmp_path):
    canonical, through, config, run = _case(tmp_path)
    before=canonical.read_bytes()
    config["atomic_write_json"]=lambda path, doc: (_ for _ in ()).throw(OSError("intent storage unavailable"))
    with pytest.raises(OSError, match="intent storage unavailable"):
        run()
    assert canonical.read_bytes()==before
    assert not (tmp_path/"proof.json").exists()


def test_incomplete_backup_before_intent_recovers_safely(tmp_path):
    canonical, through, config, run = _case(tmp_path)
    before=canonical.read_bytes()
    backup=tmp_path/".Mega-Sena.3080.advance-before.xlsx"
    writer=config["atomic_write_json"]
    config["atomic_write_json"]=lambda *args: (_ for _ in ()).throw(OSError("intent writer unavailable"))
    with pytest.raises(OSError, match="intent writer unavailable"):
        run()
    assert canonical.read_bytes()==before
    assert backup.exists()
    config["atomic_write_json"]=writer
    assert run()["status"]=="PASS"
    assert canonical.read_bytes()==through.read_bytes()


def test_incomplete_backup_with_different_canonical_is_rejected(tmp_path):
    canonical, through, config, run = _case(tmp_path)
    backup=tmp_path/".Mega-Sena.3080.advance-before.xlsx"
    backup.write_bytes(b"invalid backup")
    with pytest.raises(ValueError, match="pending canonical transaction"):
        run()
    assert canonical.read_bytes()!=through.read_bytes()



def test_interruption_between_cleanup_steps_is_idempotent(tmp_path, monkeypatch):
    import smart_terminal_result_store as store
    canonical, through, config, run = _case(tmp_path)
    backup = tmp_path / ".Mega-Sena.3080.advance-before.xlsx"
    old_unlink = Path.unlink
    def interrupt_backup(path, *args, **kwargs):
        if Path(path) == backup:
            raise KeyboardInterrupt("interrupted after journal cleanup")
        return old_unlink(path, *args, **kwargs)
    monkeypatch.setattr(store.Path, "unlink", interrupt_backup)
    with pytest.raises(KeyboardInterrupt, match="journal cleanup"):
        run()
    monkeypatch.setattr(store.Path, "unlink", old_unlink)
    assert backup.exists()
    assert not (tmp_path / ".Mega-Sena.3080.advance-intent.json").exists()
    saved = json.loads((tmp_path / "proof.json").read_text())
    assert run() == saved
    assert not backup.exists()


def test_real_excel_terminal_hashes_and_restart_recovery(tmp_path):
    import pandas as pd
    import smart_terminal_engine as terminal
    def workbook(indices):
        rows = []
        for i in indices:
            rows.append({"Concurso": i, "Data do Sorteio": pd.Timestamp("2026-10-01"),
                         **{f"Bola{k}": k for k in range(1,7)}})
        return pd.DataFrame(rows)
    original=tmp_path / "Mega-Sena.xlsx"
    official=tmp_path / "official.xlsx"
    workbook([3052,3053]).to_excel(original,index=False)
    workbook([3052,3053,3054]).to_excel(official,index=False)
    before=terminal.sha256_file(original)
    writer=terminal._atomic_write_json
    def fail_proof(path, document):
        if Path(path)==tmp_path/"proof.json":
            raise OSError("proof writer stopped")
        writer(path,document)
    params=dict(target=3054,cutoff=3053,result_data="official.xlsx",
                result_store_proof="proof.json", draw_map=terminal._draw_map,
                sha256_file=terminal.sha256_file,
                read_json=terminal._read_json,atomic_write_json=fail_proof)
    with pytest.raises(OSError, match="proof writer stopped"):
        advance_canonical_result_store(tmp_path,**params)
    assert terminal._contest_max(original)==3054
    params["atomic_write_json"]=writer
    proof=advance_canonical_result_store(tmp_path,**params)
    assert proof["canonical_sha256_before"]==before
    assert proof["canonical_sha256_after"]==terminal.sha256_file(official)
    assert terminal.sha256_file(original)==terminal.sha256_file(official)
    assert not list(tmp_path.glob(".Mega-Sena.3054.advance-*"))