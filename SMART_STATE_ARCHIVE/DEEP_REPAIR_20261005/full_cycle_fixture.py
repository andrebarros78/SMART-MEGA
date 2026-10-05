"""Execute the existing full pipeline against explicitly synthetic test inputs.
Core functions are executed directly; production state and scientific claims are preserved.
Run from this repository with its certified Python environment.
"""
from __future__ import annotations
import datetime, hashlib, json, math, os, shutil, subprocess, sys, tempfile, time, traceback, zipfile
from pathlib import Path

project = Path.cwd()
sys.path.insert(0, str(project))
archive = project / "SMART_STATE_ARCHIVE" / "DEEP_REPAIR_20261005"
root = Path(tempfile.mkdtemp(prefix="pytest-cycle-", dir=project))
artifacts = archive / "full_cycle_fixture_artifacts.zip"
record = {"schema": "SMART_FULL_CYCLE_FIXTURE_V1", "status": "RUNNING",
          "test_only": True, "production_authority": False,
          "scientific_advantage_proven": False, "core_function_mocks": [],
          "sandbox_contracts": ["existing pytest identity/startup sandbox allowance"],
          "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
          "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "steps": []}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def invoke(name, action):
    started = time.perf_counter()
    result = action()
    record["steps"].append({"function": name, "status": "PASS",
                            "seconds": round(time.perf_counter() - started, 6)})
    return result

def make_pdf(path, line):
    # Minimal, uncompressed PDF used only as a calendar parser fixture.
    stream = ("BT /F1 12 Tf 50 750 Td (" + line + ") Tj ET").encode("ascii")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    raw = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(raw))
        raw.extend(str(number).encode() + b" 0 obj\n" + obj + b"\nendobj\n")
    xref = len(raw)
    raw.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        raw.extend(f"{offset:010d} 00000 n \n".encode())
    raw.extend(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    path.write_bytes(raw)

tracked = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
for relative in tracked:
    if relative and ("/" not in relative or relative.startswith("SMART_EXPERIMENT_REGISTRY/")) and not relative.startswith("."):
        path = project / relative
        if path.is_file():
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, root / relative)
before = {p.relative_to(root).as_posix(): sha(p) for p in root.rglob("*") if p.is_file()}
failure = None
try:
    os.chdir(root)
    sys.path.insert(0, str(root))
    record["working_directory_is_fixture_root"] = True
    record["module_import_root_is_fixture_root"] = True
    import numpy as np
    import pandas as pd
    import smart_operator as op
    import smart_operational_lifecycle as lc
    import smart_full_process_pipeline as fp
    import smart_3054_terminal_executor as terminal_engine
    import smart_terminal_executor as terminal
    import smart_v2_engine as engine
    from smart_official_result_ingest import ingest
    from smart_canonical_history_advance import advance_completed_epoch
    from smart_champion_challenger import load_ledger
    from smart_github_operator import _verified_freeze_publication
    from smart_learning_epoch_reset import verify_active_epoch
    from smart_product_certification import verify_product_certification

    certificate = invoke("verify_product_certification(current code/JUnit/source)",
                         lambda: verify_product_certification(root / "SMART_PRODUCT_CERTIFICATION.json", root=root, require_current_code=True))
    rng = np.random.default_rng(999)
    rows = []
    for contest in range(1, 121):
        values = sorted(int(x) for x in rng.choice(np.arange(1, 61), 6, replace=False))
        row = {"Concurso": contest, "Data do Sorteio": pd.Timestamp("2020-01-01") + pd.Timedelta(days=contest)}
        row.update({f"Bola{i}": n for i, n in enumerate(values, 1)})
        rows.append(row)
    pd.DataFrame(rows).to_excel(root / "Mega-Sena.xlsx", index=False)
    input_sha = sha(root / "Mega-Sena.xlsx")
    calendar = root / "runtime" / "procedural_sources" / "cronogramas_caixa"
    calendar.mkdir(parents=True)
    make_pdf(calendar / "TEST_ONLY_CALENDAR.pdf", "03/11/2026 TERCA 121")
    (root / "SMART_NEXT_CYCLE_AUTHORITY.json").unlink(missing_ok=True)
    (root / "SMART_SIGNAL_LEDGER.json").write_text(json.dumps({"schema": "SMART_SIGNAL_LEDGER_1", "events": []}), encoding="utf-8")
    review_name = "SMART_POST_RESULT_REVIEW_120.json"
    op._write_operator_hashed_doc(root / review_name, {
        "schema": "SMART_POST_RESULT_REVIEW_1", "status": "POST_RESULT_REVIEW_COMPLETE",
        "target_contest": 120, "next_target": 121, "test_only": True,
        "canonical_history": {"sha256": input_sha, "history_max": 120}})
    prior_hold = op._load_operator_hashed_doc(root / op.POST_RESULT_HOLD_PATH, op.NEXT_CYCLE_HOLD_SCHEMA)
    op._write_operator_hashed_doc(root / op.POST_RESULT_HOLD_PATH, {
        "schema": op.NEXT_CYCLE_HOLD_SCHEMA, "status": "AWAITING_OPERATOR_APPLY_OR_GENERATE",
        "test_only": True, "completed_contest": 120, "next_target": 121,
        "automatic_prepare_forbidden": True, "prepare_allowed": False, "generation_allowed": False,
        "review_file": review_name, "review_file_sha256": sha(root / review_name),
        "canonical_sha256_at_review": input_sha}, expected_sha256=prior_hold["sha256"])
    prior_life = lc.load_lifecycle(root)
    fixture_life = {**prior_life, "state": "HOLD", "target_contest": 121, "completed_contest": 120,
                    "test_only": True, "transition_actor": "isolated_full_cycle_fixture"}
    lc._atomic_write(lc.lifecycle_path(root), fixture_life,
                     expected_revision=prior_life["revision"], expected_sha256=prior_life["sha256"])
    invoke("authorize_next_cycle_operation(TEST_ONLY)", lambda: op.authorize_next_cycle_operation(root, 121))
    prepared = invoke("prepare_operation", lambda: op.prepare_operation(root, 121))
    invoke("authorize_generation_operation(TEST_ONLY)", lambda: op.authorize_generation_operation(root, 121))
    frozen = invoke("run_full_process(all core stages, start=30)",
                    lambda: fp.run_full_process(root, start=30, manual_generation_authorized=True))
    proof = frozen["proof"]
    assert proof["status"] == "PASS" and all(proof["trace_checks"].values())
    assert proof["result_used"] is False and proof["target_contest"] == 121 and proof["cutoff_contest"] == 120
    published = invoke("verified primary-card consumer", lambda: _verified_freeze_publication(
        root, frozen, [proof["primary_card_file"]], "121"))
    active = verify_active_epoch(root / "SMART_ACTIVE_EPOCH.json")
    freeze_path = root / active["state_paths"]["freeze"]
    ledger_path = root / active["state_paths"]["ledger"]
    frozen_bytes = freeze_path.read_bytes()
    generation_event = dict(load_ledger(ledger_path)["events"][0])
    replay = invoke("freeze_operation(idempotent replay)", lambda: op.freeze_operation(root, 121))
    assert replay["idempotent_replay"] is True and freeze_path.read_bytes() == frozen_bytes
    actual = [4, 13, 22, 31, 40, 59]
    epoch = ledger_path.parent
    through = epoch / "Mega-Sena_through_121.xlsx"
    ingestion = invoke("ingest(explicit synthetic result payload)", lambda: ingest(
        root / active["data_file"], through, epoch / "SMART_OFFICIAL_RESULT_INGEST_121.json", 121,
        payload={"numero": 121, "dataApuracao": "03/11/2026", "listaDezenas": [f"{x:02d}" for x in actual], "acumulado": False, "test_only": True}))
    scored = invoke("adjudicate_operation", lambda: op.adjudicate_operation(root, 121, through))
    sequence = invoke("complete_adjudicated_sequence(actual learning/replay/proof)",
                      lambda: terminal.complete_adjudicated_sequence(root, 121))
    advanced = invoke("advance_completed_epoch", lambda: advance_completed_epoch(root, active))
    ledger = load_ledger(ledger_path)
    assert ledger["events"][0] == generation_event and freeze_path.read_bytes() == frozen_bytes
    assert sequence["learned_state_last_contest"] == 121 and sequence["sequence"]["valid"] is True
    learned = json.loads((epoch / "SMART_SIGNAL_STATE_121_LEARNED.json").read_text(encoding="utf-8"))
    agent = terminal_engine._agent_from_prestate(learned)
    draws, contests = engine.load_draws(through)
    next_prediction, _ = invoke("predict_next(after observed result/learning)",
                               lambda: agent.predict_next(draws, contests, target_contest=122))
    probabilities = next_prediction.rank_score_calibration["probabilities_by_number"]
    assert next_prediction.cutoff_contest == 121
    assert len(probabilities) == 60 and all(math.isfinite(v) and 0 <= v <= 1 for v in probabilities.values())
    assert abs(sum(probabilities.values()) - 6.0) < 1e-9
    assert all(math.isfinite(v) and v > 0 for v in next_prediction.weights.values())
    assert abs(sum(next_prediction.weights.values()) - 1.0) < 1e-9
    calibration = next(ev for ev in ledger["events"] if ev["event_type"] == "RANK_SCORE_CALIBRATION")
    record.update({
        "status": "PASS", "input": {"draws": 120, "seed": 999, "sha256": input_sha, "calendar_is_synthetic": True, "result_is_synthetic": True},
        "full_process_trace_checks": proof["trace_checks"], "full_process_prechecks": proof.get("pre_checks"),
        "run_id": published["run_id"], "primary_card": published["numbers"], "confidence": published["confidence"],
        "actual_numbers": actual, "primary_card_hits": len(set(published["numbers"]) & set(actual)),
        "brier": calibration["analysis"]["brier"], "uniform_brier": calibration["analysis"]["uniform_brier"],
        "freeze_unchanged_after_result": True, "ledger_prefix_unchanged": True,
        "learned_last_contest": sequence["learned_state_last_contest"], "sequential_proof_valid": True,
        "canonical_history_advance": advanced["status"], "next_prediction_target": next_prediction.target_contest,
        "next_prediction_cutoff": next_prediction.cutoff_contest, "next_weights_sum": sum(next_prediction.weights.values()),
        "next_probability_sum": sum(probabilities.values()), "certification_sha256": certificate["sha256"]})
except Exception:
    failure = traceback.format_exc()
    record.update({"status": "FAIL", "error": failure})
finally:
    os.chdir(project)
    files = {}
    with zipfile.ZipFile(artifacts, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in root.rglob("*"):
            if not path.is_file() or path.name.startswith("."):
                continue
            relative = path.relative_to(root).as_posix()
            observed = sha(path)
            if before.get(relative) != observed:
                bundle.write(path, relative)
                files[relative] = observed
    record["artifact_files_sha256"] = files
    record["artifact_bundle"] = artifacts.name
    record["artifact_bundle_sha256"] = sha(artifacts)
    record["completed_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (archive / "SMART_FULL_CYCLE_FIXTURE.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(root)
    print(json.dumps(record, ensure_ascii=False))
if failure:
    raise RuntimeError(failure)
