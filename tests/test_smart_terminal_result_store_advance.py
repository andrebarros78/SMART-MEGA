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