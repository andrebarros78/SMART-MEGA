# SMART-MEGA v6.3.1 â€” Portable Restore Maintenance R1

## Scope

This maintenance release preserves the predictive/scoring behavior of the historical SMART-MEGA v6.3.1 baseline and corrects release portability and recovery defects discovered by an independent restore audit.

Historical sealed tag `SMART-MEGA-v6.3.1-SCOPE-SEALED` is immutable and is not moved or rewritten.

## Corrections

- Persist project-local freeze/state/portfolio paths as project-relative paths for new runtime state.
- Rebind legacy v6.3.1 absolute project-local paths only when they are descendants of the explicitly trusted historical root `C:\New Projet\SMART-MEGA`.
- Keep arbitrary absolute paths, traversal and filesystem escape fail-closed.
- Remove runtime dependence on ignored `.external_skills_acquired` payloads.
- Add tracked `SMART_EXTERNAL_SKILLS_QUARANTINE_MANIFEST.json` containing the verified 21 skill-source metadata records while keeping third-party code quarantined and non-executable.
- Preserve all existing prediction, scoring, signal weighting and lottery-decision logic.

## Verification boundary

Engineering closure does not prove lottery predictability or scientific terminal 6/6. The prospective scientific mission remains independent and active until supported by future out-of-sample evidence.

## Operational state preserved

Contest 3055 remains frozen with cutoff 3054. No result for contest 3055 is used by this maintenance release and the historical freeze artifact is not rewritten.
