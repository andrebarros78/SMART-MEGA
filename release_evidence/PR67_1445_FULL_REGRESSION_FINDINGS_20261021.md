# SMART-MEGA V6 — Full regression gate: first-run findings and controlled repair

Date: 2026-10-21. Canonical repository: `andrebarros78/SMART-MEGA`. **GitHub Actions forbidden and unused.** Production `main` remains protected from unverified PR changes.

## First real full regression (SHA `3dda83920315e88dde7df67110d90288fab677cc`)

- Executor: authorized transient Windows PC Casa (S-WMCP), Python 3.12.10, 75/75 pinned dependencies installed into isolated virtual environment OUTSIDE source checkout.
- 1,445 collected pytest test items; JUnit records 1,453 cases including 8 subtests.
- Terminal result: **FAIL — 1,411 passed, 34 failed, 0 errors, 42 warnings, 8 subtests passed** in 960.79 seconds. Exit code 1.
- JUnit SHA-256: `dea2a7fa335c14aad81e1484917159b14953ca35c2fb6cdb6af541187fd0e71f`.
- Log SHA-256: `b4b397d4a1d0bedaf84b29bebfa00f316f160d56fb937d26c807a872057839f1`.
- Source checkout was clean before and after the full test. JUnit and logs were stored outside tracked source.

## Diagnosed causes

1. **Static reachability stale after GitHub Actions retirement:** F01/F03/F05/F08/F10 still bound to `.github/workflows/*.yml`. The approved repair enumerates GitHub-canonical external entrypoints, refuses executable GitHub Actions manifests, includes the external CI runner and execution policy, and regenerates self-consistent F01/F05/F10 registries rather than suppressing gates.
2. **Environment self-interference:** During the first full run, a second `SMART-MEGA-V6-*` sibling checkout was created to diagnose code. The canonical-identity guard correctly rejected the resulting ambiguous operational roots. This is NOT a reason to change the fail-closed identity guard. The next full run must place its only tested checkout under a separate parent with no competing SMART-MEGA roots.
3. **Two stale negative-test message assertions:** The operator correctly rejects unsigned preceding lifecycle evidence before issuing any contingency card; the terminal correctly rejects the absence of a hash-bound current freeze before fetching results. Tests now assert those stronger fail-closed behaviors without weakening the guards.

## Isolated post-fix evidence, not full-suite approval

- **25 passed**, one warning, for F01, F03, F05, F08, F10: repaired externally authorized reachability and linked scientific safety/retirement boundaries. Separate **2 passed**, one warning, for authenticated preceding lifecycle and current freeze gate tests.
- Regenerated `SMART_COMPONENT_REACHABILITY_REGISTRY.json`, `SMART_CANONICAL_COMPONENT_REGISTRY.json`, and `SMART_F10_DISCONNECTION_GATE.json`; gate statuses **PASS**.
- Exact Git blob SHA verification on all seven candidate files before promotion to the PR; `main` not changed.
- No GitHub Actions runs or invented certifications.

## Release policy

**THIS IS NOT PRODUCTION HOMOLOGATION.** Full suite must be rerun against the FINAL GitHub candidate SHA in a single clean isolated workspace, with JUnit, zero failures and errors, verified source identity, and no active GitHub Actions workflows. Independent prospective predictive performance is a separate scientific requirement; 6/6 or MISSION_PROVEN cannot be inferred from software tests.
