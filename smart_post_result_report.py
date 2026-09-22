from __future__ import annotations

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

    portfolio_file = freeze.get("portfolio_file") or freezes[0].get("portfolio_file")
    portfolio_sha_expected = freeze.get("portfolio_sha256") or freezes[0].get("portfolio_sha256")
    portfolio_metrics = None
    if isinstance(portfolio_file, str) and portfolio_file:
        portfolio_path = root / portfolio_file
        if not portfolio_path.is_file():
            raise ValueError("portfolio artifact missing")
        portfolio_sha = _sha256_file(portfolio_path)
        if isinstance(portfolio_sha_expected, str) and portfolio_sha != portfolio_sha_expected:
            raise ValueError("portfolio hash mismatch")
        package = _load_json(portfolio_path)
        games = package.get("games") or package.get("portfolio", {}).get("games")
        if not isinstance(games, list) or not games:
            raise ValueError("portfolio games invalid")
        normalized = []
        per_game = []
        exposure = {}
        for game in games:
            nums = _numbers(game)
            if nums is None: raise ValueError("portfolio game invalid")
            normalized.append(nums); per_game.append(len(set(nums) & official_set))
            for n in nums: exposure[str(n)] = exposure.get(str(n), 0) + 1
        union_numbers = sorted({n for g in normalized for n in g})
        portfolio_metrics = {"portfolio_file": portfolio_file, "portfolio_sha256": portfolio_sha, "portfolio_id": package.get("portfolio_id"), "artifact_type": package.get("artifact_type"), "games": normalized, "hits_per_game": per_game, "best_game_hits": max(per_game), "union_numbers": union_numbers, "union_hits": len(set(union_numbers) & official_set), "number_exposure": exposure}

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
        "portfolio_sha256": portfolio_metrics.get("portfolio_sha256") if portfolio_metrics else None,
        "portfolio_hits_per_game": portfolio_metrics.get("hits_per_game") if portfolio_metrics else None,
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
        "champion_hits": hits,
        "portfolio_adjudication": portfolio_metrics,
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
