# SMART-MEGA Archive and Runtime Boundary

**POLICY_ID=SMART_GITHUB_NATIVE_ONLY_20261021** — canonical `andrebarros78/SMART-MEGA`, branch `main`. GitHub-native execution policy supersedes historical local deployment descriptions. Only GitHub Actions on GitHub-hosted runners are authorized; LMCP/VPS and private computers are retired.

Status: CANONICAL_SCOPE_SEAL_POLICY

## Runtime boundary

- `runtime/` contains persisted runtime state, generated state/evidence and data only.
- No tracked `.py`, `.cmd` or `.ps1` file is authorized under `runtime/` in the sealed release.
- Operator/runtime executable code is tracked at the project root and executes exclusively in GitHub-hosted GitHub Actions runners.

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

Previous Windows CLI deployment is historical evidence only, without current execution or deployment authority. Product execution, CI and operations are GitHub-native; no PC or VPS is an operational prerequisite.