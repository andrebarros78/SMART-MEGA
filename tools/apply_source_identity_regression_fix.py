from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    return raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n"), newline


def write_text(path: Path, text: str, newline: str) -> None:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    raw = normalized if newline == "\n" else normalized.replace("\n", "\r\n")
    path.write_bytes(raw.encode("utf-8"))


def replace(path: str, old: str, new: str, *, expected: int = 1) -> None:
    p = ROOT / path
    text, newline = read_text(p)
    observed = text.count(old)
    if observed != expected:
        raise RuntimeError(f"{path}: expected {expected} occurrences, observed {observed}: {old!r}")
    write_text(p, text.replace(old, new, expected), newline)


def insert_after(path: str, anchor: str, addition: str) -> None:
    p = ROOT / path
    text, newline = read_text(p)
    if addition.strip() in text:
        return
    if text.count(anchor) != 1:
        raise RuntimeError(f"{path}: import anchor count != 1: {anchor!r}")
    write_text(p, text.replace(anchor, anchor + addition, 1), newline)


def main() -> None:
    insert_after(
        "smart_portfolio_pipeline.py",
        "from smart_false_negative_rescue import apply_rescue, build_profile_from_reports\n",
        "from smart_source_identity import sha256_source_file\n",
    )
    replace(
        "smart_portfolio_pipeline.py",
        '"optimizer_sha256": sha256(Path(__file__).with_name("smart_portfolio_optimizer.py")),',
        '"optimizer_sha256": sha256_source_file(Path(__file__).with_name("smart_portfolio_optimizer.py")),',
    )
    replace(
        "smart_portfolio_pipeline.py",
        '"pipeline_sha256": sha256(Path(__file__)),',
        '"pipeline_sha256": sha256_source_file(Path(__file__)),',
    )

    p = ROOT / "test_smart_architecture_alignment.py"
    text, newline = read_text(p)
    old = "sha256(Path('smart_"
    count = text.count(old)
    if count < 14:
        raise RuntimeError(f"architecture marker migration expected >=14 markers, observed {count}")
    text = text.replace(old, "sha256_source_file(Path('smart_")
    write_text(p, text, newline)

    replace(
        "test_smart_evidence_only_promotion.py",
        "cc.sha256(Path('smart_evidence_only_promotion.py'))",
        "cc.sha256_source_file(Path('smart_evidence_only_promotion.py'))",
    )
    replace(
        "test_smart_independent_audit.py",
        "'source_sha256': _sha(source),",
        "'source_sha256': ia.sha256_source_file(source),",
    )
    replace(
        "test_smart_independent_audit.py",
        "ia.sha256_file(Path('smart_independent_audit.py'))",
        "ia.sha256_source_file(Path('smart_independent_audit.py'))",
    )
    replace(
        "test_smart_mission_coverage_closure_20260906.py",
        "original_sha = ia.sha256_file",
        "original_sha = ia.sha256_source_file",
    )
    replace(
        "test_smart_mission_coverage_closure_20260906.py",
        "monkeypatch.setattr(ia, 'sha256_file', same_oracle_hash)",
        "monkeypatch.setattr(ia, 'sha256_source_file', same_oracle_hash)",
    )
    replace(
        "test_smart_promotion_gate.py",
        "cc.sha256(Path('smart_promotion_gate.py'))",
        "cc.sha256_source_file(Path('smart_promotion_gate.py'))",
    )

    print("SOURCE_IDENTITY_REGRESSION_FIX=PASS")


if __name__ == "__main__":
    main()
