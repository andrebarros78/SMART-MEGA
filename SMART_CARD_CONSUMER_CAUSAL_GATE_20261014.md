# SMART-MEGA V6 — Consumer causal integration checkpoint (2026-10-14)

## Scope
- Repository: `andrebarros78/SMART-MEGA`.
- Certified starting main SHA: `f24053210c29275e4afd3240fa3c1e6ddd95e8bb`.
- Engineering branch: `integration/card-consumer-proof-20261014`.
- Historical F11/F12 sources, frozen contest 3070, operator state, productive main: **not mutated**.
- This is **engineering-in-progress**, not production certification and not scientific proof.

## Root cause (verified from source)
`smart_full_process_pipeline.py` generates pre/post agent-skill gates and invokes the champion/challenger freeze and portfolio. The single card is selected by `smart_portfolio_pipeline.py` from `champion.aggregate_scores` after conditional false-negative rescue, using `smart_primary_card_selector.py`. Challenger weights are shadow unless independently promoted. Native skill aliases run probes, not arbitrary third-party code. The previous consumer integration module was not imported into production main.

## Branch construction
Fresh branch from certified main; added the experimental read-only `smart_consumer_integration.py` and `test_smart_consumer_integration.py`; did not cherry-pick changes to frozen predictive pipeline. Changed only these two code/test paths. Enhanced:
- Fail-closed validation of gate self-hashes, primary-card self-hash and epoch identity.
- One-to-one matching of all 37 distinct native skill capabilities to their recorded invocation; reject duplicates/unknown agent owners.
- Explicitly describe SDK check as installed-package presence, not causal influence.
- Test replay of selector from exact frozen champion scores and in-memory counterfactual.
- Tests for forged gate, forged card metadata, epoch mismatch and duplicate skill invocation.

## Observed targeted execution evidence
- Source/test Python syntax compiled with Python 3.12.
- 3070 immutable artifacts read successfully; `16/16` consumer gate checks PASS with **SDK package version lookups stubbed**. This is a structural test, **not evidence that five SDKs are installed in the test executor**.
- Fail-closed negative checks PASS: changed numbers, changed skill source execution claim, altered post-gate status, mismatched epoch, forged post-gate hash, forged primary-card metadata and missing SDK. A duplicate invocation with a recomputed gate self-hash was independently rejected by the matching capability check.
- Selector replay using actual `champion.aggregate_scores` produced exact `[10,11,27,38,43,53]` and matched the frozen selector SHA.
- In-memory score intervention on ball 60 changed the selected card to `[10,11,27,35,38,60]`; no frozen file was modified.
- These checks demonstrate selector input sensitivity, **not** positive predictive benefit or causal contributions from each agent/skill/SDK.

## Incomplete gates — no promotion authorized
- Full `pytest` regression and release JUnit **not run** in this session: isolated Linux Python lacks installed locked dependencies; ordinary pip installation was denied as `installation_requires_signed_typed_admin_operation`; typed admin request returned `admin_operation_not_allowed`. Governed PC Escola remote `process.exec` route returned `network_dispatch_operation_denied`.
- Clean clone status was inconsistent across Linux workers (0 or ~47 EOL-attributed tracked modifications); certify a clean candidate only on a stable authorized executor.
- Must establish all SDK dataflow links to actual final scores, with ablation and OOS nonregression; package presence/adapter probes alone do not qualify.
- Reconcile and run full tests against exact branch SHA; verify immutable historical hashes, F11/F12, certification, integrity and material registry. Only merge to `main` after PASS. Prospective scientific status remains UNPROVEN.

## Next command on a correctly prepared authorized runner
```bash
git fetch origin integration/card-consumer-proof-20261014
git checkout integration/card-consumer-proof-20261014
python -m pytest -q -p no:cacheprovider --disable-warnings --junitxml=SMART_CONSUMER_FULL_REGRESSION.xml
```
Do not run the command in an active frozen operational epoch. Preserve the baseline and audit the exact source SHA, environment, dependencies and JUnit hash.

## 2026-10-14 Windows regression correction (GATE 5)
- First complete run at branch 03ba008: 1,213 passed; five failures (F01, F05, F08 x2, F10) due to two new top-level Python files changing the canonical component graph, not due to a regression of historical predictive scoring.
- Read-only auditor relocated to `test_smart_consumer_audit_support.py`, a test-only component; `test_smart_consumer_integration.py` imports this helper. No production scorer, pipeline, or F11/F12 protected source was edited.
- Canonical snapshots regenerated from actual code by `smart_component_reachability.build_registry`, `smart_canonical_component_registry.build_registry`, and `smart_disconnection_gate.audit_disconnections`. F01/F05/F10 gate statuses PASS.
- Focused corrected retest: **43 passed** including consumer, F01/F05/F08/F10, F11 and F12. Full corrected regression and release certification are separate gates, not implied by this result.

## 2026-10-14 ECC Full EOL closure checkpoint — engineering only
- Isolation branch: `fix/smart-mega-v6-ecc-eol-20261014`, base `f5e89c2c00a46f1eb7562151bf3eaff47acaf9c4`.
- Two minimal `.gitattributes` commits: `647b664fc3b7e40a263de72a59d6b68e78d33907` and `d9ad17a60a7cd3219a83f73a9b220a2603b87054`.
- Git clean-filter fault reproduced: pre-fix worker checkouts sometimes marked raw committed CRLF blobs modified despite unchanged bytes. Added exact `-text` path exceptions for the two new diagnostic consumer test files, 47 archived scripts, and one legacy source script. No source byte or frozen-result changes.
- Three independent fresh Linux worker clones at `d9ad17a...` reported `git status --porcelain` count zero and raw 3070 freeze/portfolio SHA checks PASS.
- ECC Full targeted code rerun on exact `d9ad17a...`: 28/28 direct Python test functions PASS across F01 (4), F05 (4), F08 (2), F10 (4 selected), F11 (9), and F12 (5). Durable command `c_b1d91fd166544ed2a710ffbb032101fe`, exit code 0, clean worktree before and after.
- Consumer negative/replay suite: 10/10 targeted functions PASS using an in-process `pytest` API shim for fixtures/raises and a metadata-version stub (`c_8df126c56a014ed78c7ec9b6ea5de91c`, exit code 0). This does **not** attest real pytest execution or five real SDK installations.
- F11/F12 scientific boundary remains unchanged: no prospective advantage, no proven 6/6, and no authorization to promote challenger weights from shadow.
- Still blocked for release: pinned-dependency environment with real `pytest`, the entire post-fix test collection/JUnit and SDK-to-score causal/out-of-sample tests. None of those missing proofs is represented as PASS.
- No merge to `main`, no mutation of historical freeze, no productive execution or new agent/skill/SDK authority.
