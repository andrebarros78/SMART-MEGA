from __future__ import annotations

import hashlib
import json
import os
import re
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




MAX_IMMUTABLE_LEDGER_BYTES = 16 * 1024 * 1024


def _preserve_ledger_evidence(root: Path, target: int, ledger: Path, expected_sha: str) -> None:
    # Create-only, byte-exact witness after adjudication, before later mutations.
    if isinstance(target, bool) or not isinstance(target, int) or target < 1:
        raise ValueError("invalid immutable ledger contest")
    if not isinstance(expected_sha, str) or re.fullmatch(r"[0-9a-f]{64}", expected_sha) is None:
        raise ValueError("invalid immutable ledger digest")
    root = Path(root).resolve()
    ledger = Path(ledger)
    if (ledger.is_symlink() or not ledger.is_file()
            or not ledger.resolve().is_relative_to(root)):
        raise ValueError("immutable ledger must be a regular file within the project")
    if ledger.stat().st_size > MAX_IMMUTABLE_LEDGER_BYTES:
        raise ValueError("immutable ledger exceeds reader safety limit")
    destination = (root / "SMART_STATE_ARCHIVE" / "hash-bound-learning" / str(target)
                   / f"SMART_SIGNAL_LEDGER.{expected_sha}.json")
    if destination.exists():
        if destination.is_symlink() or _sha256_file(destination) != expected_sha:
            raise ValueError("post-result ledger archive hash mismatch")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.parent.resolve().is_relative_to(root):
        raise ValueError("immutable ledger archive escapes project root")
    fd, temporary = tempfile.mkstemp(prefix=destination.name + ".", suffix=".tmp",
                                    dir=str(destination.parent))
    try:
        with os.fdopen(fd, "wb") as out, ledger.open("rb") as inp:
            for chunk in iter(lambda: inp.read(1024 * 1024), b""):
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        temp_path = Path(temporary)
        if _sha256_file(temp_path) != expected_sha:
            raise ValueError("ledger changed while capturing post-result evidence")
        try:
            os.link(temp_path, destination)
        except FileExistsError:
            if destination.is_symlink() or _sha256_file(destination) != expected_sha:
                raise ValueError("concurrent ledger archive hash mismatch")
    finally:
        Path(temporary).unlink(missing_ok=True)


def _numbers(value: Any) -> list[int] | None:
    if isinstance(value, dict):
        value = value.get("numbers")
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


def _signal_diagnostic(freeze: dict[str, Any], actual: list[int]) -> dict[str, Any]:
    """Explain a *frozen* challenger's real score contributions after the result.

    No prediction, weight, or primary card is recalibrated or persisted here.
    Existing sealed reports are never rewritten by this extension.
    """
    snapshot = freeze.get("challenger")
    if not isinstance(snapshot, dict) or not ({"raw_signals", "weights"} & snapshot.keys()):
        return {"status": "UNAVAILABLE_LEGACY_FREEZE", "predictive_promotion_authorized": False}

    from smart_signal_attribution import analyze_attribution

    analysis = analyze_attribution(snapshot, actual, max_coalition_removal=2)
    declared = _numbers(snapshot.get("top6"))
    reconstructed = analysis["base"]["top6"]
    if declared is None or set(declared) != set(reconstructed):
        raise ValueError("signal diagnostic does not reproduce frozen challenger")

    rows = sorted(({
        "signal": name,
        "weight_before_result": float(row["weight_before_result"]),
        "leave_one_out_delta_hits": int(row["marginal_hit_contribution"]),
        "leave_one_out_hits": int(row["leave_one_out_hits"]),
        "mean_abs_redundancy": float(row["redundancy"]["mean_abs_correlation"]),
        "most_redundant_peer": row["redundancy"]["most_redundant_peer"],
    } for name, row in analysis["per_signal"].items()),
        key=lambda item: (-item["weight_before_result"], item["signal"]))
    return {
        "status": "PASS",
        "prediction_role": "FROZEN_CHALLENGER_NOT_RETROACTIVE_PRIMARY",
        "attribution_sha256": analysis["attribution_sha256"],
        "challenger_top6": reconstructed,
        "challenger_hits": int(analysis["base"]["hits"]),
        "signal_count": len(rows),
        "top_two_weight_share": sum(item["weight_before_result"] for item in rows[:2]),
        "per_signal": rows,
        "leave_one_out_improving_signals": [r["signal"] for r in rows if r["leave_one_out_delta_hits"] < 0],
        "coalition_max_removed": int(analysis["coalition_analysis"]["max_removal_size"]),
        "coalition_tested": int(analysis["coalition_analysis"]["coalitions_tested"]),
        "minimal_retrospective_improving_removal_size": analysis["coalition_analysis"]["minimal_improving_removal_size"],
        "result_used_only_after_freeze": True,
        "predictive_promotion_authorized": False,
        "retrospective_gain_is_not_predictive_evidence": True,
    }


def _primary_card_diagnostic(freeze: dict[str, Any], actual: list[int],
                             selected_card: list[int], primary_record: dict[str, Any] | None,
                             challenger_diagnostic: dict[str, Any]) -> dict[str, Any]:
    """Attribute the *production Champion* and record final selector deviations.

    The frozen Challenger raw vectors also contain the Champion's 12 shared
    signal vectors. Champion weights are independent and must reproduce its
    frozen top six. Actual primary selection stays immutable.
    """
    champion = freeze.get("champion")
    challenger = freeze.get("challenger")
    if (not isinstance(champion, dict) or not isinstance(challenger, dict)
            or "expert_weights" not in champion or "raw_signals" not in challenger):
        return {"status": "UNAVAILABLE_LEGACY_FREEZE", "predictive_promotion_authorized": False}
    from smart_signal_attribution import analyze_attribution
    analysis = analyze_attribution({"raw_signals": challenger["raw_signals"],
                                    "weights": champion["expert_weights"]}, actual,
                                   max_coalition_removal=2)
    original = _numbers(champion.get("top6"))
    if original is None or set(analysis["base"]["top6"]) != set(original):
        raise ValueError("Champion attribution does not reproduce frozen Champion")
    scores = champion.get("aggregate_scores")
    if isinstance(scores, dict):
        import math
        weights = champion["expert_weights"]
        raw = challenger["raw_signals"]
        for number in range(1, 61):
            reproduced = sum(float(weights[k]) * float(raw[k]["values"][str(number)]) for k in weights)
            if not math.isclose(reproduced, float(scores[str(number)]), abs_tol=1e-8, rel_tol=1e-8):
                raise ValueError("Champion signal scores do not reproduce frozen aggregate scores")
    per_signal = sorted(({
        "signal": name, "weight_before_result": float(row["weight_before_result"]),
        "leave_one_out_delta_hits": int(row["marginal_hit_contribution"]),
        "mean_abs_redundancy": float(row["redundancy"]["mean_abs_correlation"]),
    } for name, row in analysis["per_signal"].items()),
        key=lambda x: (-x["weight_before_result"], x["signal"]))
    selected = set(selected_card)
    champion_numbers = set(original)
    change = {
        "added_by_final_selection": sorted(selected - champion_numbers),
        "removed_from_champion": sorted(champion_numbers - selected),
        "champion_hits": int(analysis["base"]["hits"]),
        "actual_primary_hits": len(selected & set(actual)),
        "decision_changed": selected != champion_numbers,
        "cause_scope": "SELECTOR_PLUS_RESCUE_NOT_ISOLATED",
        "frozen_primary_record_present": primary_record is not None,
    }
    return {
        "status": "PASS", "model": "FROZEN_PRODUCTION_CHAMPION",
        "attribution_sha256": analysis["attribution_sha256"],
        "signal_count": len(per_signal), "champion_top6": original,
        "top_two_weight_share": sum(row["weight_before_result"] for row in per_signal[:2]),
        "per_signal": per_signal,
        "leave_one_out_improving_signals": [row["signal"] for row in per_signal if row["leave_one_out_delta_hits"] < 0],
        "minimal_retrospective_improving_removal_size": analysis["coalition_analysis"]["minimal_improving_removal_size"],
        "final_decision": change,
        "challenger_diagnostic_status": challenger_diagnostic.get("status"),
        "result_used_only_after_freeze": True,
        "predictive_promotion_authorized": False,
        "retrospective_gain_is_not_predictive_evidence": True,
    }


def _operational_capability_consumption(freeze: dict[str, Any], actual: list[int]) -> dict[str, Any]:
    """Consume existing native skill methodologies on the *real frozen* prediction.

    This is not execution of the named third-party skills. It proves that
    quality, weight replay, calibration and learning diagnostics each consume
    the actual immutable pre-result snapshot and the post-result adjudication.
    No learning state, weight, freeze or generated card is mutated.
    """
    challenger = freeze.get("challenger")
    if not isinstance(challenger, dict) or not all(
        key in challenger for key in ("raw_signals", "weights", "quality_metrics", "rank_score_calibration")
    ):
        return {"status": "UNAVAILABLE_LEGACY_FREEZE", "native_capabilities_consumed": [],
                "named_external_skill_executed": False, "predictive_weight_authorized": False}

    import math
    from smart_signal_weights import dynamic_weights
    from smart_signal_marginal_utility import analyze_marginal_utility_snapshot
    from smart_rank_score_calibration import brier_score
    from smart_agent_skill_orchestration import LANES

    raw = challenger["raw_signals"]
    previous_weights = challenger["weights"]
    quality = challenger["quality_metrics"]
    if not isinstance(raw, dict) or set(raw) != set(previous_weights) or set(raw) != set(quality):
        raise ValueError("operational capabilities require identical real signal ids")
    families = {name: record["family"] for name, record in raw.items()}
    for name, record in raw.items():
        if record.get("causal") is not True or record.get("target_contest") != freeze.get("target_contest"):
            raise ValueError("operational capability input has noncausal/foreign signal")
        if record.get("cutoff_contest") != freeze.get("cutoff_contest"):
            raise ValueError("operational capability input cutoff mismatch")
        for k in ("oos_mean_hits", "confidence", "quality", "stability", "freshness"):
            if k in quality[name] and not math.isfinite(float(quality[name][k])):
                raise ValueError(f"nonfinite signal quality metric: {name}.{k}")

    # A functional replay, not a manifest/adapter probe: dynamic quality-driven
    # weights must exactly reproduce the weights consumed before the result.
    recomputed, _components = dynamic_weights(quality, families)
    max_weight_error = max(abs(float(recomputed[n]) - float(previous_weights[n])) for n in recomputed)
    if max_weight_error > 1e-9:
        raise ValueError("native dynamic_weights does not reproduce frozen Challenger weights")

    # Genuine result consumption: leave-one-out incremental utility is measured
    # against the official numbers strictly *after* adjudication.
    marginal = analyze_marginal_utility_snapshot(challenger, actual)
    per_signal = marginal["per_signal"]
    if set(per_signal) != set(raw):
        raise ValueError("marginal utility omitted one or more frozen signals")
    improving_removal = sorted(n for n, r in per_signal.items()
                                if r.get("available") and int(r["delta_hits"]) < 0)
    helpful_signal_count = sum(bool(r.get("available")) and int(r["delta_hits"]) > 0
                               for r in per_signal.values())

    # Real rank calibration audit: compute proper scoring loss of the *frozen*
    # probabilities and compare with the uniform reference. This does not
    # recalibrate from the current target or turn this one draw into evidence
    # of future superiority.
    calibration = challenger["rank_score_calibration"]
    probabilities = calibration.get("probabilities_by_number")
    if not isinstance(probabilities, dict) or set(probabilities) != {str(n) for n in range(1, 61)}:
        raise ValueError("frozen calibration must contain exactly 60 marginal probabilities")
    total_probability = sum(float(p) for p in probabilities.values())
    if abs(total_probability - 6.0) > 1e-8:
        raise ValueError("frozen calibration probability mass does not sum to six")
    calibrated_brier = brier_score(probabilities, actual)
    uniform_brier = brier_score({str(n): 0.1 for n in range(1, 61)}, actual)
    if not math.isfinite(calibrated_brier):
        raise ValueError("calibration proper score is not finite")

    drifted = sorted(n for n, v in quality.items() if bool(v.get("drift_active")))
    context = challenger.get("context_regime", {})
    if not isinstance(context, dict):
        raise ValueError("context regime audit must be an object")
    quality_signal_counts = {"signals": len(raw), "drifted": len(drifted),
                             "drifted_ids": drifted,
                             "context_regime_active": bool(context.get("active", False)),
                             "context_l1_score": context.get("l1_score")}

    # These are *methodology aliases*, not counterfeit claims that Pandera,
    # Optuna, OpenAI skills or autonomous external agents were executed.
    consumed = {
        "openai-validate-data": "validated causal, finite, 60-value frozen signals",
        "openai-analyze-data-quality": "consumed per-signal quality and drift observations",
        "pandera-data-contracts": "validated native signal schema; Pandera library NOT executed",
        "statistical-analysis": "computed measured leave-one-out hit contributions",
        "machine-learning-model-validation": "reproduced actual dynamic weights from frozen quality",
        "model-drift-management": "consumed measured drift flags and context regime",
        "regime-detection": "consumed frozen context regime metrics",
        "superforecasting": "measured Brier loss against uniform probabilities",
        "benchmarking-uncertainty-calibration-long-form": "computed calibrated-vs-uniform proper-score delta",
        "evo-memory": "created read-only post-result signal utility feedback",
        "experiment-design": "kept result-only evaluation separate from pre-result freeze",
    }
    named_capabilities = {n for lane in LANES.values() for n in lane["capabilities"]}
    if not set(consumed) <= named_capabilities:
        raise ValueError("operational capability binding absent from native registry")
    if not all(0 <= float(v) <= 1 for v in probabilities.values()):
        raise ValueError("calibration probabilities outside 0..1")
    output = {
        "status": "PASS", "scope": "REAL_FROZEN_INPUT_POST_RESULT_NATIVE_METHODS",
        "native_methodology_aliases_consumed": sorted(consumed),
        "native_capabilities_consumed": {k:consumed[k] for k in sorted(consumed)},
        "named_external_skill_executed": False,
        "signal_quality": quality_signal_counts,
        "dynamic_weight_replay": {"signals": len(recomputed),
                                  "max_abs_weight_error": max_weight_error,
                                  "reproduces_frozen_weights": True},
        "post_result_marginal_utility": {
            "full_hits": int(marginal["full_ensemble"]["hits"]),
            "helpful_signal_count": helpful_signal_count,
            "removal_would_help_signal_ids": improving_removal,
            "marginal_utility_sha256": marginal["marginal_utility_sha256"],
            "learning_state_written": False,
        },
        "proper_scoring": {"frozen_calibrated_brier": calibrated_brier,
                           "uniform_brier": uniform_brier,
                           "delta_vs_uniform": calibrated_brier - uniform_brier,
                           "calibration_neutralized": bool(calibration.get("neutralized")),
                           "probability_sum": total_probability},
        "actual_result_used_only_after_freeze": True,
        "predictive_weight_authorized": False,
        "prospective_superiority_proven": False,
    }
    # Call each corresponding native operation through the actual skill
    # execution layer. The report consumes and verifies each distinct receipt;
    # a probe/manifest alone is not allowed to satisfy this contract.
    from smart_skill_runtime import invoke_live_native
    receipts = {}
    for capability in sorted(consumed):
        receipt = invoke_live_native(capability, freeze, actual)
        observed = receipt.get("execution_sha256")
        unsigned = dict(receipt)
        unsigned.pop("execution_sha256", None)
        if observed != _sha256_json(unsigned) or receipt.get("capability") != capability:
            raise ValueError(f"native capability receipt invalid: {capability}")
        if receipt.get("consumer") != "smart_post_result_report._operational_capability_consumption":
            raise ValueError(f"native capability receipt not bound to consumer: {capability}")
        if receipt.get("external_skill_code_executed") is not False:
            raise ValueError("native method receipt cannot assert third-party skill execution")
        receipts[capability] = receipt
    if receipts["machine-learning-model-validation"]["observed_output"]["max_abs_weight_error"] != max_weight_error:
        raise ValueError("skill weight receipt differs from consumed scores")
    if receipts["statistical-analysis"]["observed_output"]["marginal_utility_sha256"] != marginal["marginal_utility_sha256"]:
        raise ValueError("skill marginal utility receipt differs from post-result analysis")
    if receipts["superforecasting"]["observed_output"]["brier"] != calibrated_brier:
        raise ValueError("skill calibration receipt differs from consumed probabilities")
    if receipts["model-drift-management"]["observed_output"]["drift_active_count"] != len(drifted):
        raise ValueError("skill drift receipt differs from consumed quality metrics")
    output["native_execution_receipts"] = receipts
    output["native_execution_receipts_verified"] = len(receipts) == len(consumed)
    output["execution_receipt_count"] = len(receipts)
    output["sha256"] = _sha256_json(output)
    return output


def _structural_capability_diagnostic(freeze: dict[str, Any], root: Path) -> dict[str, Any]:
    """Consume independently bound pre-result library evidence, never target results."""
    from smart_skill_runtime import consume_frozen_structural_capabilities
    payload = consume_frozen_structural_capabilities(freeze, root)
    if payload.get("status") != "PASS":
        return payload
    observed = payload.get("sha256")
    unsigned = dict(payload)
    unsigned.pop("sha256", None)
    if observed != _sha256_json(unsigned):
        raise ValueError("structural capability aggregate receipt hash invalid")
    rows = payload.get("receipts", {})
    if payload.get("execution_receipts_count") != len(rows) or not rows:
        raise ValueError("structural capability receipt coverage incomplete")
    for capability, receipt in rows.items():
        local = dict(receipt)
        receipt_hash = local.pop("execution_sha256", None)
        if receipt_hash != _sha256_json(local) or receipt.get("capability") != capability:
            raise ValueError("structural capability receipt hash invalid")
        if receipt.get("consumer") != "smart_post_result_report._structural_capability_diagnostic":
            raise ValueError("structural capability did not reach intended consumer")
        if receipt.get("frozen_source_sha256") != freeze.get("data_sha256"):
            raise ValueError("structural receipt not bound to frozen data")
        if receipt.get("predictive_weight_authorized") is not False:
            raise ValueError("structural evidence cannot alter predictive weights")
    return payload


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
    diagnostic = report.get("signal_diagnostic")
    if isinstance(diagnostic, dict) and diagnostic.get("status") == "PASS":
        lines += ["", "### Diagnóstico dos pesos realmente consumidos", "",
                  f"- **Modelo auditado:** challenger congelado; acertos: {diagnostic['challenger_hits']}/6",
                  f"- **Participação dos dois maiores pesos:** {100 * diagnostic['top_two_weight_share']:.2f}%",
                  f"- **Sinais cuja remoção isolada teria aumentado acertos neste resultado:** {', '.join(diagnostic['leave_one_out_improving_signals']) or 'nenhum'}",
                  f"- **Remoções em pares investigadas:** {diagnostic['coalition_tested'] - diagnostic['signal_count']}",
                  "- **Limite:** resultado retrospectivo; não autoriza alterar pesos nem demonstra capacidade preditiva.", ""]
        lines += [f"- {row['signal']}: peso={100 * row['weight_before_result']:.2f}%; variação de acertos sem sinal={-row['leave_one_out_delta_hits']:+d}; redundância média={row['mean_abs_redundancy']:.3f}"
                  for row in diagnostic["per_signal"]]
    elif isinstance(diagnostic, dict):
        lines += ["", "### Diagnóstico dos sinais", "", "- Indisponível: o freeze antigo não possui snapshot completo dos sinais."]
    structures = report.get("structural_capability_consumption")
    if isinstance(structures, dict) and structures.get("status") == "PASS":
        lines += ["", "### Execuções estruturais vinculadas ao histórico congelado", "",
                  f"- **Operações nativas registradas:** {structures['execution_receipts_count']}",
                  f"- **Histórico verificado:** {structures['data_quality']['rows']} concursos até {structures['data_quality']['cutoff']}",
                  "- **Bibliotecas realmente chamadas:** " + ", ".join(structures['third_party_libraries_actually_called']),
                  "- **Autoridade:** somente diagnóstico/controle do portfólio; nenhuma previsão, score ou peso recalibrado."]
    ops = report.get("operational_capability_consumption")
    if isinstance(ops, dict) and ops.get("status") == "PASS":
        score = ops["proper_scoring"]
        lines += ["", "### Consumo efetivo de competências nativas", "",
                  f"- **Capacidades com dados reais consumidos:** {len(ops['native_capabilities_consumed'])}",
                  f"- **Reprodução dos pesos dinâmicos:** erro máximo {ops['dynamic_weight_replay']['max_abs_weight_error']:.3g}",
                  f"- **Brier congelado contra uniforme:** {score['frozen_calibrated_brier']:.7f} contra {score['uniform_brier']:.7f}",
                  f"- **Sinais com ganho marginal de acertos:** {ops['post_result_marginal_utility']['helpful_signal_count']}",
                  "- **Escopo:** funções nativas com dados reais; nenhum código de skill externa executado, nenhuma mudança de pesos autorizada."]
    primary = report.get("primary_card_diagnostic")
    if isinstance(primary, dict) and primary.get("status") == "PASS":
        final = primary["final_decision"]
        lines += ["", "### Atribuição do Champion e do cartão principal", "",
                  f"- **Sinais do Champion:** {primary['signal_count']}",
                  f"- **Dois maiores pesos do Champion:** {100 * primary['top_two_weight_share']:.2f}%",
                  f"- **Card final alterado pelo pós-processamento:** {'sim' if final['decision_changed'] else 'não'}",
                  f"- **Acertos Champion → cartão real:** {final['champion_hits']} → {final['actual_primary_hits']}",
                  "- **Limite de atribuição:** seletor e resgate combinados; ganho retrospectivo não demonstra poder preditivo."]
    elif isinstance(primary, dict):
        lines += ["", "### Atribuição do cartão principal", "",
                  "- Não disponível: o freeze não contém vetores/pesos suficientes ou há constatações de integridade."]
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
    champion_card = _extract_numbers(freeze, ("frozen_top6", "top6", "champion_top6"))
    if champion_card is None:
        raise ValueError("post-result report champion freeze card unavailable")
    primary_record = freezes[0].get("primary_card")
    primary_card = _numbers(primary_record) if primary_record is not None else None
    if primary_record is not None and primary_card is None:
        raise ValueError("frozen primary card evidence invalid")
    # Preserve byte-compatible legacy reports if the selected primary and champion
    # use the same six numbers. Otherwise evaluate the actual primary product.
    if primary_card is not None and set(primary_card) != set(champion_card):
        card = primary_card

    official_set, card_set = set(official), set(card)
    champion_hits = len(official_set & set(champion_card))
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
        if primary_card is not None and _numbers(package.get("primary_card")) != primary_card:
            raise ValueError("frozen primary card differs from bound portfolio")
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
    if isinstance(reported_hits, int) and reported_hits != champion_hits:
        process_findings.append(f"Divergência de contabilização: adjudicação informou {reported_hits} acertos do champion, recomputação independente encontrou {champion_hits}.")

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
        "A previsão congelada foi confrontada com o resultado oficial sem alterar o cartão emitido.",
        "Os acertos foram recomputados a partir das seis dezenas efetivamente selecionadas.",
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

    # The attribution is computed from pre-result frozen signal vectors; the
    # official outcome is consumed strictly here, after adjudication.
    # If present but inconsistent, fail closed rather than manufacture a diagnosis.
    diagnostic = _signal_diagnostic(freeze, official) if not process_findings else {
        "status": "UNAVAILABLE_PROCESS_INTEGRITY_FINDING",
        "predictive_promotion_authorized": False,
    }

    primary_diagnostic = _primary_card_diagnostic(
        freeze, official, card, primary_record if isinstance(primary_record, dict) else None,
        diagnostic,
    ) if not process_findings else {
        "status": "UNAVAILABLE_PROCESS_INTEGRITY_FINDING", "predictive_promotion_authorized": False,
    }

    capability_consumption = _operational_capability_consumption(freeze, official) if not process_findings else {
        "status": "UNAVAILABLE_PROCESS_INTEGRITY_FINDING",
        "named_external_skill_executed": False, "predictive_weight_authorized": False,
    }

    structural_diagnostic = _structural_capability_diagnostic(freeze, root) if not process_findings else {
        "status": "UNAVAILABLE_PROCESS_INTEGRITY_FINDING",
        "predictive_weight_authorized": False,
    }

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
        "champion_hits": champion_hits,
        "signal_diagnostic": diagnostic,
        "primary_card_diagnostic": primary_diagnostic,
        "operational_capability_consumption": capability_consumption,
        "structural_capability_consumption": structural_diagnostic,
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
        _preserve_ledger_evidence(root, target, ledger_path, ledger_sha)
        return {
            "status": "EXISTING_VALID",
            "report_file": json_path.name,
            "report_sha256": _sha256_file(json_path),
            "markdown_file": md_path.name if md_path.is_file() else None,
            "report": existing,
        }

    _preserve_ledger_evidence(root, target, ledger_path, ledger_sha)
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
