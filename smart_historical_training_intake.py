from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

BALL_COLUMNS = [f"Bola{i}" for i in range(1, 7)]
REQUIRED_COLUMNS = ["Concurso", *BALL_COLUMNS]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_frame(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return pd.read_excel(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError("Formato nao suportado. Use XLSX ou CSV.")


def validate(path: Path) -> dict:
    df = load_frame(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Colunas obrigatorias ausentes: {missing}")

    work = df[REQUIRED_COLUMNS].copy()
    for col in REQUIRED_COLUMNS:
        work[col] = pd.to_numeric(work[col], errors="raise").astype(int)

    contests = work["Concurso"].tolist()
    if len(contests) != len(set(contests)):
        raise ValueError("Existem concursos duplicados")
    if any(b <= a for a, b in zip(contests, contests[1:])):
        raise ValueError("Concursos devem estar em ordem estritamente crescente")

    for idx, row in work.iterrows():
        balls = [int(row[c]) for c in BALL_COLUMNS]
        if len(set(balls)) != 6:
            raise ValueError(f"Concurso {int(row['Concurso'])}: dezenas repetidas")
        if any(v < 1 or v > 60 for v in balls):
            raise ValueError(f"Concurso {int(row['Concurso'])}: dezena fora de 1..60")

    return {
        "schema": "SMART_HISTORICAL_TRAINING_INPUT_VALIDATION_V1",
        "status": "PASS",
        "file": path.name,
        "sha256": sha256_file(path),
        "rows": int(len(work)),
        "contest_min": int(work.iloc[0]["Concurso"]),
        "contest_max": int(work.iloc[-1]["Concurso"]),
        "has_draw_date": "Data do Sorteio" in df.columns,
        "ready_for_shadow_replay": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("--out", type=Path, default=Path("runtime/historical_training_shadow/INPUT_VALIDATION.json"))
    args = parser.parse_args()
    result = validate(args.data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
