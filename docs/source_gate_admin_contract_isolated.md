# Source Gate Administrative Contract — isolated design

This branch is an isolated prototype, not a production release. No trust key from the test harness is authorized in production. The current source gate remains BLOCKED.

The Ed25519 signed canonical JSON envelope requires schema, operation RELEASE/ROLLBACK, source CAIXA_OFFICIAL_VIDEO, expected state/generation/head, authority_id, unique nonce, issue/expiry timestamps, approval_id and access_proof_sha256. Fail closed on invalid signatures, expired approval, stale state, nonce reuse and untrusted keys. Repeated identical requests are idempotent.

The contract implementation is a **pure transition function**, not an executor. Production integration must validate the referenced approval and independently verify the access proof (a digest alone is insufficient), load the trust registry from governed authority, acquire the official queue exclusive lock, persist a fsynced append-only audit event, then atomically compare-and-swap the gate pointer. A crash between audit and pointer update requires recovery reconciliation. Rollback is a separately signed BLOCKED transition, not deletion of audit history. A release must not change predictive weights or imply that physical frames were observed.

The original smart_video_source_access.py currently validates only BLOCKED documents. Do not replace its pointer with RELEASED until a compatible versioned reader, migration, backup, crash recovery, and consumer integration have passed independent tests. Never bypass YouTube login or source ACL. The original branch and main remain untouched by this prototype.
