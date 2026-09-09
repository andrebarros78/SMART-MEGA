# SMART-MEGA v6.3.1 â€” Portable Restore Maintenance R2

## Scope

R2 is an engineering portability and recovery maintenance release built on `SMART-MEGA-v6.3.1-PORTABLE-RESTORE-R1`. It does not change the lottery prediction/scoring contract, signal semantics, dynamic weighting rules, Top-6 authority, or the scientific terminal rule.

The historical sealed tag `SMART-MEGA-v6.3.1-SCOPE-SEALED` remains immutable.

## Corrections

- Normalize active-context project-local freeze, data and state paths to project-relative form after safe legacy rebinding.
- Preserve strict fail-closed legacy rebinding: only descendants of the explicitly trusted historical root `C:\New Projet\SMART-MEGA` can be rebound; arbitrary absolute paths, traversal and filesystem escapes remain rejected.
- Separate immutable WMCP artifact-binding validation from live-runtime freshness. Historical signed execution evidence can be validated portably; `require_fresh=True` still requires current canonical live WMCP state.
- Package the verified CAIXA cronogram archive as `portable_evidence/cronogramas_caixa` with 60 PDFs and a self-hashed per-file SHA-256 manifest.
- Make target-schedule resolution use the packaged CAIXA archive only when the operational runtime overlay is absent.
- Fail closed on portable cronogram manifest tampering, unexpected files, size mismatch or PDF SHA-256 mismatch.
- Harden `smart_python.cmd` as the canonical Windows launcher: scrub `PYTHONPATH` and `PYTHONHOME`, invoke Python with `-E`, support paths containing spaces, and fail closed if the local `.venv` is missing.
- Preserve the existing third-party skill quarantine and non-execution policy.

## Candidate verification before clean B2 restore

- Full regression through `smart_python.cmd`: 706 passed, 0 failed, 0 errors, 0 skipped.
- Runtime guard through the canonical launcher: PASS.
- `pip check` through the canonical launcher: PASS.
- OR-Tools functional integer optimization: PASS using SCIP 10.0.0.
- Total integration: PASS / HEALTHY with all 9 gate groups green.
- Portable CAIXA archive: 60/60 files bound to the tracked manifest.
- Hostile external Python environment isolation: verified by automated tests.

Evidence is retained under `release_evidence/` and is hash-bound by `R2_ENGINEERING_PROOF.json`.

## Restore contract

1. Extract the release into any ordinary Windows project directory.
2. Create `.venv` with a compatible Python 3.13 runtime.
3. Install `requirements.lock.txt`.
4. Execute Python/pytest/pip operations through `smart_python.cmd`.
5. Run `smart_runtime_guard.py`, `python -m pip check`, the regression suite and the total-integration gate before operational use.

## Scientific boundary

Engineering portability closure is not evidence that Mega-Sena is predictable and does not satisfy the project's prospective scientific terminal rule. `SMART_MISSION_STATUS.json` remains `MISSION_ACTIVE` until a future pre-result frozen Top-6 and the other scientific requirements are satisfied prospectively.