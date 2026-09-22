from __future__ import annotations
from smart_canonical_identity import canonical_root

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from smart_historical_training_intake import BALL_COLUMNS, sha256_file, validate
from tools.wmcp_scientific import EvidenceDocument, ScientificEvidenceRAG

SCHEMA = "SMART_RAG_EXCEL_V1"
PROOF_SCHEMA = "SMART_RAG_EXCEL_PREPARATION_PROOF_V1"
READ_ONLY_CRITICAL_FILES = (
    "Mega-Sena.xlsx",
    "SMART_MISSION_STATUS.json",
    "SMART_SIGNAL_LEDGER.json",
    "SMART_SIGNAL_STATE.json",
    "SMART_ACTIVE_EPOCH.json",
    "SMART_MANUAL_GENERATION_AUTHORITY.json",
)

def _critical_hashes(root: Path) -> dict[str, str | None]:
    return {name: sha256_file(root / name) if (root / name).is_file() else None for name in READ_ONLY_CRITICAL_FILES}

def _clean(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        try:
            return str(int(float(text)))
        except ValueError:
            return text
    return text

def _row_text(row: pd.Series) -> str:
    contest = int(row["Concurso"])
    balls = [int(row[c]) for c in BALL_COLUMNS]
    parts = [f"Concurso {contest}", "dezenas " + " ".join(f"{v:02d}" for v in balls)]
    date = _clean(row.get("Data do Sorteio", ""))
    if date:
        parts.append(f"data {date}")
    for col in ("Ganhadores 6 acertos", "Ganhadores 5 acertos", "Ganhadores 4 acertos", "Cidade / UF", "Observação"):
        if col in row.index:
            value = _clean(row.get(col, ""))
            if value:
                parts.append(f"{col}: {value}")
    return " | ".join(parts)

class SmartExcelRAG:
    def __init__(self, path: str | Path, as_of_contest: int):
        self.path = Path(path).resolve()
        self.as_of_contest = int(as_of_contest)
        validation = validate(self.path)
        if self.as_of_contest < int(validation["contest_min"]):
            raise ValueError("as_of_contest_before_dataset")
        if self.as_of_contest > int(validation["contest_max"]):
            raise ValueError("as_of_contest_beyond_dataset")
        self.validation = validation
        df = pd.read_excel(self.path) if self.path.suffix.lower() == ".xlsx" else pd.read_csv(self.path)
        work = df[df["Concurso"].astype(int) <= self.as_of_contest].copy()
        if work.empty:
            raise ValueError("no_rows_available_for_cutoff")
        self.frame = work
        source_sha = validation["sha256"]
        docs = []
        for _, row in work.iterrows():
            contest = int(row["Concurso"])
            docs.append(EvidenceDocument(
                evidence_id=f"mega:{source_sha[:16]}:{contest}",
                title=f"Mega-Sena concurso {contest}",
                text=_row_text(row),
                source=f"excel://{self.path.name}#sha256={source_sha}&contest={contest}",
            ))
        self.rag = ScientificEvidenceRAG(docs)

    @property
    def document_count(self) -> int:
        return len(self.rag.docs)

    def retrieve(self, query: str, k: int = 5, min_score: float = 0.05) -> tuple:
        return self.rag.retrieve(query, k=k, min_score=min_score)

    def context_block(self, query: str, k: int = 5, min_score: float = 0.05) -> str:
        return self.rag.context_block(self.retrieve(query, k=k, min_score=min_score))

    def manifest(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "status": "READY",
            "source_file": self.path.name,
            "source_sha256": self.validation["sha256"],
            "source_rows": self.validation["rows"],
            "source_contest_min": self.validation["contest_min"],
            "source_contest_max": self.validation["contest_max"],
            "as_of_contest": self.as_of_contest,
            "indexed_documents": self.document_count,
            "temporal_cutoff_enforced": True,
            "predictive_weight_authority": False,
            "freeze_mutation_authority": False,
            "signal_state_mutation_authority": False,
            "ledger_mutation_authority": False,
            "role": "READ_ONLY_RETRIEVAL_AND_LEARNING_SUPPORT",
        }

def build_preparation_proof(root: str | Path, excel: str | Path = "Mega-Sena.xlsx", as_of_contest: int | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    excel_path = Path(excel)
    if not excel_path.is_absolute():
        excel_path = root / excel_path
    validation = validate(excel_path)
    cutoff = int(as_of_contest if as_of_contest is not None else validation["contest_max"])
    before = _critical_hashes(root)
    engine = SmartExcelRAG(excel_path, cutoff)
    last_row = engine.frame.iloc[-1]
    contest = int(last_row["Concurso"])
    balls = [int(last_row[c]) for c in BALL_COLUMNS]
    query = f"concurso {contest} dezenas " + " ".join(f"{v:02d}" for v in balls)
    hits = engine.retrieve(query, k=3)
    context = engine.rag.context_block(hits)
    after = _critical_hashes(root)
    expected_id = f"mega:{validation['sha256'][:16]}:{contest}"
    checks = {
        "historical_input_valid": validation["status"] == "PASS",
        "all_rows_through_cutoff_indexed": engine.document_count == len(engine.frame),
        "cutoff_not_beyond_source": cutoff <= int(validation["contest_max"]),
        "latest_allowed_contest_retrievable": bool(hits) and hits[0].evidence_id == expected_id,
        "retrieval_context_has_provenance": bool(hits) and hits[0].source.startswith("excel://"),
        "retrieval_context_contains_evidence_id": expected_id in context,
        "critical_canonical_state_unchanged": before == after,
        "no_predictive_or_freeze_authority": all(
            engine.manifest()[key] is False for key in (
                "predictive_weight_authority",
                "freeze_mutation_authority",
                "signal_state_mutation_authority",
                "ledger_mutation_authority",
            )
        ),
    }
    doc = {
        "schema": PROOF_SCHEMA,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "manifest": engine.manifest(),
        "checks": checks,
        "retrieval_probe": {
            "query": query,
            "expected_evidence_id": expected_id,
            "hits": [asdict(h) for h in hits],
            "context": context,
        },
        "critical_hashes_before": before,
        "critical_hashes_after": after,
    }
    canonical = json.dumps(doc, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    doc["sha256"] = hashlib.sha256(canonical).hexdigest()
    return doc

def write_preparation_proof(root: str | Path, output: str | Path = "SMART_RAG_EXCEL_PREPARATION_PROOF.json", excel: str | Path = "Mega-Sena.xlsx", as_of_contest: int | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    out = Path(output)
    if not out.is_absolute():
        out = root / out
    doc = build_preparation_proof(root, excel=excel, as_of_contest=as_of_contest)
    if doc["status"] != "PASS":
        raise RuntimeError(f"RAG+Excel preparation failed: {doc['checks']}")
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(canonical_root()))
    parser.add_argument("--excel", default="Mega-Sena.xlsx")
    parser.add_argument("--as-of-contest", type=int)
    parser.add_argument("--output", default="SMART_RAG_EXCEL_PREPARATION_PROOF.json")
    parser.add_argument("--query")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args(argv)
    args.root = str(canonical_root(args.root))
    root = Path(args.root).resolve()
    if args.query:
        p = Path(args.excel)
        if not p.is_absolute():
            p = root / p
        validation = validate(p)
        cutoff = args.as_of_contest if args.as_of_contest is not None else int(validation["contest_max"])
        engine = SmartExcelRAG(p, cutoff)
        hits = engine.retrieve(args.query, k=args.k)
        print(json.dumps({"manifest": engine.manifest(), "hits": [asdict(h) for h in hits], "context": engine.rag.context_block(hits)}, ensure_ascii=False, indent=2))
        return 0
    doc = write_preparation_proof(root, args.output, args.excel, args.as_of_contest)
    print(json.dumps({"status": doc["status"], "manifest": doc["manifest"], "checks": doc["checks"], "sha256": doc["sha256"]}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
