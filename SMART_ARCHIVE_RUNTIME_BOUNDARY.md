# SMART-MEGA Archive and Runtime Boundary

**POLICY_ID=SMART_GITHUB_CANONICAL_EXTERNAL_EXECUTION_NO_ACTIONS_20261021** — canonical `andrebarros78/SMART-MEGA`, branch `main`. GitHub Actions prohibited; external temporary executors authorized for tests, never a permanent production dependency.

Status: CANONICAL_SCOPE_SEAL_POLICY

## Runtime boundary

- `runtime/` contains persisted runtime state, generated state/evidence and data only.
- No tracked `.py`, `.cmd` or `.ps1` file is authorized under `runtime/` in the sealed release.
- Operator/runtime executable code is tracked at the project root and executes for validation on approved isolated temporary external executors.

## Archive boundary

`archive/` is retained only because current evidence lineage and regression tests reference historical artifacts and fixtures.

Archive policy:

- NOT_RUNTIME
- NOT_OPERATOR_ENTRYPOINT
- NO_AUTO_EXECUTION
- NO_PREDICTIVE_AUTHORITY
- NO_FREEZE_AUTHORITY
- NO_DEPLOYMENT_AUTHORITY

Historical absolute paths inside `archive/` are evidence of prior engineering state and are not live bindings. Active portability logic may retain only explicit, fail-closed legacy rebinding contracts covered by tests.

## Deployment boundary

Previous Windows CLI deployment is historical evidence only, without current execution or deployment authority. GitHub is canonical; external execution is approved, but it must not create a permanent operational dependency. GitHub Actions is forbidden.