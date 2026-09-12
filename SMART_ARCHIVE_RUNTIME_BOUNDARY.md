# SMART-MEGA Archive and Runtime Boundary

Status: CANONICAL_SCOPE_SEAL_POLICY

## Runtime boundary

- `runtime/` contains persisted runtime state, generated state/evidence and data only.
- No tracked `.py`, `.cmd` or `.ps1` file is authorized under `runtime/` in the sealed release.
- Operator/runtime executable code is tracked at project root and is exercised through the local isolated Python environment.

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

The sealed Windows deployment is a local CLI artifact. It does not expose an HTTP service, listening socket or database by itself. Network/API authentication, rate limiting and server-side tenancy controls are therefore NOT_APPLICABLE to this artifact unless a future release adds a network service.