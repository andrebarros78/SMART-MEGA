from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\SMART-MEGA").resolve()
OP = ROOT / "smart_operator.py"
POST = ROOT / "smart_post_result_report.py"
TPOST = ROOT / "test_smart_post_result_report.py"
BACKUP = ROOT / "SMART_STATE_ARCHIVE" / "post_result_report_backup_20260920"


def die(msg: str) -> None:
    raise RuntimeError(msg)


def read(path: Path) -> str:
    if not path.is_file():
        die(f"missing required file: {path}")
    return path.read_text(encoding="utf-8")


def atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    tmp = Path(raw)
    try:
        tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def backup(path: Path) -> None:
    if not path.is_file():
        return
    BACKUP.mkdir(parents=True, exist_ok=True)
    dst = BACKUP / path.name
    if not dst.exists():
        shutil.copy2(path, dst)


def run(*args: str) -> None:
    print("+", " ".join(args))
    cp = subprocess.run(args, cwd=ROOT)
    if cp.returncode:
        die(f"command failed ({cp.returncode}): {' '.join(args)}")


backup(OP)
backup(POST)
backup(TPOST)

POST_MODULE = r'''from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "SMART_POST_RESULT_REPORT_1"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_json(obj: dict[str, Any]) -> str:
    canonical = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    tmp = Path(raw)
    try:
        tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _numbers(value: Any) -> list[int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 6:
        return None
    try:
        nums = [int(x) for x in value]
    except (TypeError, ValueError):
        return None
    if len(set(nums)) != 6 or any(n < 1 or n > 60 for n in nums):
        return None
    return nums


def _extract_numbers(obj: Any, keys: tuple[str, ...]) -> list[int] | None:
    if not isinstance(obj, dict):
        return None
    for key in keys:
        nums = _numbers(obj.get(key))
        if nums is not None:
            return nums
    for key in ("champion", "freeze", "result", "official", "adjudication", "prediction"):
        nested = obj.get(key)
        if isinstance(nested, dict):
            nums = _extract_numbers(nested, keys)
            if nums is not None:
                return nums
    return None


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"expected JSON object: {path}")
    return obj


def _render_markdown(report: dict[str, Any]) -> str:
    def fmt(values: list[int]) -> str:
        return " - ".join(f"{int(x):02d}" for x in values) if values else "N/A"

    analysis = report["self_analysis"]
    lines = [
        f"# Relatório pós-resultado — Concurso {report['contest_number']}",
        "",
        f"- **Concurso:** {report['contest_number']}",
        f"- **Resultado oficial:** {fmt(report['official_result'])}",
        f"- **Cartão gerado/congelado:** {fmt(report['generated_card'])}",
        f"- **Número de acertos:** {report['hit_count']}/6",
        f"- **Dezenas acertadas:** {fmt(report['matched_numbers'])}",
        f"- **Dezenas do resultado não cobertas:** {fmt(report['missed_result_numbers'])}",
        "",
        "## Autoanálise construtiva",
        "",
        analysis["summary"],
        "",
        "### O que funcionou",
    ]
    lines += [f"- {x}" for x in analysis["what_worked"]]
    lines += ["", "### Erros e falhas observados"]
    lines += [f"- {x}" for x in analysis["errors_and_failures"]] or ["- Nenhuma falha material de processo foi detectada."]
    lines += ["", "### Correções, ajustes e implementações sugeridos"]
    lines += [f"- {x}" for x in analysis["recommended_actions"]]
    lines += [
        "",
        "### Proteção contra falso aprendizado",
        "",
        "Um único concurso não autoriza aumentar/diminuir pesos nem promover sinais. Qualquer mudança material deve ser validada em dados não usados na calibração, com teste prospectivo/OOS e regra de não regressão.",
        "",
    ]
    return "\n".join(lines)


def emit_post_result_report(root: str | Path, active: dict[str, Any], adjudication_result: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    target = int(active.get("target_contest", -1))
    if target <= 0:
        raise ValueError("post-result report requires a valid target contest")

    paths = active.get("state_paths") if isinstance(active.get("state_paths"), dict) else {}
    ledger_path = root / str(paths.get("ledger") or "")
    freeze_path = root / str(paths.get("freeze") or "")
    if not ledger_path.is_file():
        raise ValueError("post-result report requires signal ledger")
    if not freeze_path.is_file():
        raise ValueError("post-result report requires frozen card artifact")

    ledger = _load_json(ledger_path)
    events = ledger.get("events")
    if not isinstance(events, list):
        raise ValueError("post-result report ledger events invalid")
    target_events = [e for e in events if isinstance(e, dict) and int(e.get("target_contest", -1)) == target]
    adjudications = [e for e in target_events if e.get("event_type") == "ADJUDICATION"]
    freezes = [e for e in target_events if e.get("event_type") == "FREEZE"]
    if len(adjudications) != 1:
        raise ValueError("post-result report requires exactly one adjudication event")
    if len(freezes) != 1:
        raise ValueError("post-result report requires exactly one freeze event")

    freeze = _load_json(freeze_path)
    source = adjudication_result if isinstance(adjudication_result, dict) else {}
    official = (
        _extract_numbers(source, ("actual_numbers", "official_result", "result_numbers", "result"))
        or _extract_numbers(adjudications[0], ("actual_numbers", "official_result", "result_numbers", "result"))
    )
    card = (
        _extract_numbers(source, ("frozen_top6", "generated_card", "top6", "champion_top6"))
        or _extract_numbers(freeze, ("frozen_top6", "generated_card", "top6", "champion_top6"))
        or _extract_numbers(freezes[0], ("frozen_top6", "generated_card", "top6", "champion_top6"))
    )
    if official is None:
        raise ValueError("post-result report could not resolve official result")
    if card is None:
        raise ValueError("post-result report could not resolve frozen generated card")

    official_set, card_set = set(official), set(card)
    matched = sorted(official_set & card_set)
    missed = sorted(official_set - card_set)
    extra = sorted(card_set - official_set)
    hits = len(matched)

    reported_hits = source.get("hits") if isinstance(source, dict) else None
    if not isinstance(reported_hits, int):
        reported_hits = adjudications[0].get("hits")

    process_findings: list[str] = []
    if isinstance(reported_hits, int) and reported_hits != hits:
        process_findings.append(f"Divergência de contabilização: adjudicação informou {reported_hits} acertos, recomputação independente encontrou {hits}.")

    authority = active.get("freeze_authority")
    freeze_sha = _sha256_file(freeze_path)
    if not isinstance(authority, dict):
        process_findings.append("Freeze authority ausente no active epoch.")
    elif authority.get("sha256") != freeze_sha:
        process_findings.append("Hash do freeze diverge da freeze authority do active epoch.")
    event_freeze_sha = freezes[0].get("freeze_sha256")
    if isinstance(event_freeze_sha, str) and event_freeze_sha != freeze_sha:
        process_findings.append("Hash do evento FREEZE diverge do artefato congelado.")

    missed_text = ", ".join(f"{n:02d}" for n in missed)
    what_worked = [
        f"O cartão cobriu {hits} das 6 dezenas sorteadas.",
        "A comparação usa o cartão congelado, preservando previsão × resultado real e evitando reescrita retroativa.",
    ]
    errors = []
    if missed:
        errors.append(f"O cartão não cobriu {len(missed)} dezenas do resultado: {missed_text}.")
    errors.extend(process_findings)

    actions = [
        "Executar atribuição causal por família e sinal para identificar contribuição correta, excesso de peso, atraso, ruído e redundância.",
        "Comparar o comportamento com a janela histórica e com evidência prospectiva acumulada; não recalibrar pesos por um único concurso.",
        "Registrar falsos positivos e falsos negativos por sinal e procurar recorrência antes de promover, penalizar ou neutralizar influência.",
        "Validar qualquer ajuste em dados não usados na calibração e aplicar a regra medir antes -> alterar -> medir depois -> comparar.",
        "Se uma mudança melhorar métrica local mas piorar resultado global, reverter/corrigir e retestar.",
    ]
    if process_findings:
        actions.insert(0, "Corrigir primeiro as falhas de integridade/processo detectadas antes de interpretar desempenho preditivo.")

    ledger_sha = _sha256_file(ledger_path)
    source_fingerprint = _sha256_json({
        "target": target,
        "official_result": official,
        "generated_card": card,
        "freeze_sha256": freeze_sha,
        "ledger_sha256": ledger_sha,
    })

    report = {
        "schema": SCHEMA,
        "status": "PASS" if not process_findings else "PASS_WITH_PROCESS_FINDINGS",
        "contest_number": target,
        "official_result": official,
        "generated_card": card,
        "hit_count": hits,
        "matched_numbers": matched,
        "missed_result_numbers": missed,
        "card_numbers_not_drawn": extra,
        "process_audit": {
            "freeze_artifact": str(freeze_path.relative_to(root)).replace("\\", "/"),
            "freeze_sha256": freeze_sha,
            "ledger": str(ledger_path.relative_to(root)).replace("\\", "/"),
            "ledger_sha256": ledger_sha,
            "freeze_authority_present": isinstance(authority, dict),
            "reported_hits": reported_hits,
            "recomputed_hits": hits,
            "findings": process_findings,
        },
        "self_analysis": {
            "summary": f"Concurso {target}: {hits}/6 acertos. A análise separa desempenho observado, integridade do processo e recomendações de melhoria.",
            "what_worked": what_worked,
            "errors_and_failures": errors,
            "recommended_actions": actions,
            "single_contest_weight_change_prohibited": True,
            "oos_validation_required_for_material_changes": True,
        },
        "source_fingerprint": source_fingerprint,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    report["sha256"] = _sha256_json(report)

    json_path = root / f"SMART_POST_RESULT_REPORT_{target}.json"
    md_path = root / f"SMART_POST_RESULT_REPORT_{target}.md"
    if json_path.is_file():
        existing = _load_json(json_path)
        observed = existing.get("sha256")
        canonical = dict(existing)
        canonical.pop("sha256", None)
        if observed != _sha256_json(canonical):
            raise ValueError("existing post-result report self-hash invalid")
        if existing.get("source_fingerprint") != source_fingerprint:
            raise ValueError("existing post-result report is bound to different evidence")
        return {
            "status": "EXISTING_VALID",
            "report_file": json_path.name,
            "report_sha256": _sha256_file(json_path),
            "markdown_file": md_path.name if md_path.is_file() else None,
            "report": existing,
        }

    _atomic_write(json_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(md_path, _render_markdown(report))
    return {
        "status": "EMITTED",
        "report_file": json_path.name,
        "report_sha256": _sha256_file(json_path),
        "markdown_file": md_path.name,
        "markdown_sha256": _sha256_file(md_path),
        "report": report,
    }
'''

if POST.is_file() and 'SCHEMA = "SMART_POST_RESULT_REPORT_1"' not in read(POST):
    die("existing smart_post_result_report.py has unknown content; refusing overwrite")
atomic_write(POST, POST_MODULE)

op = read(OP)
if "post_result_report_operation" not in op:
    old = "    return adjudicate(Path(result_data), int(target), ledger_path)\n"
    new = '''    adjudication_result = adjudicate(Path(result_data), int(target), ledger_path)\n    if not isinstance(adjudication_result, dict):\n        raise RuntimeError("adjudication must return a structured result")\n    state_paths = active.get("state_paths") if isinstance(active.get("state_paths"), dict) else {}\n    if not state_paths.get("freeze"):\n        return adjudication_result\n    state_paths = active.get("state_paths") if isinstance(active.get("state_paths"), dict) else {}\n    if not state_paths.get("freeze"):\n        return adjudication_result\n    from smart_post_result_report import emit_post_result_report\n    report = emit_post_result_report(root, active, adjudication_result)\n    return {**adjudication_result, "post_result_report": report}\n'''
    if old not in op:
        die("adjudicate_operation anchor not found; refusing unsafe patch")
    op = op.replace(old, new, 1)

    terminal_anchor = "\ndef terminal_operation(\n"
    if terminal_anchor not in op:
        die("terminal_operation anchor not found")
    recovery = r'''def post_result_report_operation(root: str | Path, target: int) -> dict[str, Any]:
    root = Path(root).resolve()
    active = verify_active_epoch(root / ACTIVE_PATH)
    if int(active.get("target_contest", -1)) != int(target):
        raise ValueError("active operational epoch does not match report target")
    from smart_post_result_report import emit_post_result_report
    return emit_post_result_report(root, active, None)


'''
    op = op.replace(terminal_anchor, "\n" + recovery + terminal_anchor, 1)

    # Contract and CLI are fail-closed: every anchor must exist.
    if '"post-result-report"' not in op:
        old_actions = '"adjudicate", "terminal"'
        if old_actions not in op:
            die("supported_actions anchor not found")
        op = op.replace(old_actions, '"adjudicate", "post-result-report", "terminal"', 1)

        terminal_parser = '    t = sub.add_parser("terminal");'
        if terminal_parser not in op:
            die("terminal parser anchor not found")
        op = op.replace(terminal_parser, '    r = sub.add_parser("post-result-report"); r.add_argument("--target", type=int, required=True)\n' + terminal_parser, 1)

        dispatch = '    elif args.action == "adjudicate": out = adjudicate_operation(root, args.target, args.result_data)\n    else:'
        if dispatch not in op:
            die("adjudicate dispatch anchor not found")
        op = op.replace(dispatch, '    elif args.action == "adjudicate": out = adjudicate_operation(root, args.target, args.result_data)\n    elif args.action == "post-result-report": out = post_result_report_operation(root, args.target)\n    else:', 1)

    atomic_write(OP, op)

TEST_MODULE = r'''from pathlib import Path
import json

import smart_post_result_report as pr


def _fixture(tmp_path: Path, *, reported_hits=None):
    epoch = tmp_path / "runtime" / "learning_epochs" / "e1"
    epoch.mkdir(parents=True)
    freeze = epoch / "SMART_999_CHAMPION_CHALLENGER_FREEZE.json"
    freeze.write_text(json.dumps({"champion": {"top6": [1, 2, 3, 4, 5, 6]}}), encoding="utf-8")
    fsha = pr._sha256_file(freeze)
    adjudication = {
        "event_type": "ADJUDICATION",
        "target_contest": 999,
        "actual_numbers": [1, 2, 7, 8, 9, 10],
    }
    if reported_hits is not None:
        adjudication["hits"] = reported_hits
    ledger = epoch / "SMART_SIGNAL_LEDGER.json"
    ledger.write_text(json.dumps({"events": [
        {"event_type": "FREEZE", "target_contest": 999, "freeze_sha256": fsha, "top6": [1, 2, 3, 4, 5, 6]},
        adjudication,
    ]}), encoding="utf-8")
    return {
        "target_contest": 999,
        "freeze_authority": {
            "file": str(freeze.relative_to(tmp_path)).replace("\\", "/"),
            "sha256": fsha,
            "target_contest": 999,
            "cutoff_contest": 998,
        },
        "state_paths": {
            "freeze": str(freeze.relative_to(tmp_path)).replace("\\", "/"),
            "ledger": str(ledger.relative_to(tmp_path)).replace("\\", "/"),
        },
    }


def test_report_contains_required_operational_fields(tmp_path: Path) -> None:
    out = pr.emit_post_result_report(tmp_path, _fixture(tmp_path, reported_hits=2))
    report = out["report"]
    assert out["status"] == "EMITTED"
    assert report["contest_number"] == 999
    assert report["official_result"] == [1, 2, 7, 8, 9, 10]
    assert report["generated_card"] == [1, 2, 3, 4, 5, 6]
    assert report["hit_count"] == 2
    assert report["matched_numbers"] == [1, 2]
    assert report["self_analysis"]["single_contest_weight_change_prohibited"] is True
    md = (tmp_path / out["markdown_file"]).read_text(encoding="utf-8")
    assert "Concurso 999" in md
    assert "Número de acertos:** 2/6" in md
    assert "Autoanálise construtiva" in md


def test_report_detects_hit_count_divergence(tmp_path: Path) -> None:
    out = pr.emit_post_result_report(tmp_path, _fixture(tmp_path, reported_hits=5))
    assert out["report"]["status"] == "PASS_WITH_PROCESS_FINDINGS"
    assert any("Divergência de contabilização" in item for item in out["report"]["process_audit"]["findings"])


def test_report_is_idempotent_for_same_evidence(tmp_path: Path) -> None:
    active = _fixture(tmp_path, reported_hits=2)
    first = pr.emit_post_result_report(tmp_path, active)
    second = pr.emit_post_result_report(tmp_path, active)
    assert first["status"] == "EMITTED"
    assert second["status"] == "EXISTING_VALID"
    assert second["report"]["source_fingerprint"] == first["report"]["source_fingerprint"]
'''
atomic_write(TPOST, TEST_MODULE)

run(sys.executable, "-m", "py_compile", OP.name, POST.name, TPOST.name)
run(sys.executable, "-m", "pytest", "-q", TPOST.name)

print("POST_RESULT_REPORT_PATCH_PASS")
print("Backup:", BACKUP)
print("Added: smart_post_result_report.py")
print("Added: test_smart_post_result_report.py")
print("Modified: smart_operator.py")
print("Runtime output: SMART_POST_RESULT_REPORT_<contest>.json + SMART_POST_RESULT_REPORT_<contest>.md")
