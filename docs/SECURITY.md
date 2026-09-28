# Single-owner security model

As requested, there are no viewer/analyst/reviewer roles or per-case grants in version 2. One owner key can read, add and edit all workspace cases. Authentication remains so another machine cannot access the workspace merely by knowing its URL. Default binding is loopback. The browser stores the key in memory only.

Upgrade keeps a former reviewer/admin key and disables other keys. Bootstrap saves the previous credential configuration locally for rollback. Protect both files; do not share or commit secrets. Restart API replicas after key changes. Multiple people sharing this key are indistinguishable in the audit trail; this package is not a multi-user attribution system.

Included: request size/schema validation, parameterized SQLAlchemy operations, escaped DOM text, strict local-only content policy, immutable source content, audit history for mutations and source reads, revision checks on relationships, transactional imports. Database administrators can alter audit records; they are not cryptographically tamper-evident. Text hashes are not signatures or proof that a source is true.

Not included: institutional SSO/MFA, TLS provisioning, encryption at rest/key management, per-user quotas, signed audit storage, malware scanning, retention/deletion governance or production security certification. PostgreSQL/SQLite direct write access bypasses application validation. Real authorized sensitive-data use requires a separate deployment/security review. Suggested links must not be treated as automatic enforcement decisions.


## V3 review and export controls

All added routes use the same owner and case-existence checks. Identity reviews require a fingerprint, revision and reason. Canonical maps never delete originals; dependent merge undo is blocked. Hypothesis review uses compare-and-swap and cannot write evidence edges. HTML reports escape all source text, names, audit payloads and titles. Frontend labels use textContent; Cytoscape renders labels on canvas. Bundled graph code needs no CDN. File names are not used as filesystem paths by import conversion.

New tests exercise identity stale state/case boundaries, worker rollback, immutable provenance, rejected-claim exclusion, unsupported types, path-like IDs and HTML escaping. This is not an independent penetration test. SQLite writes should use one worker. PostgreSQL concurrent import/edit/merge interleavings need integration testing; the fingerprint is not a global serializable lock across every kind of mutation. Owner access is intentionally broad. Source hashes detect changed bytes but are not digital signatures, trusted timestamps or tamper-proof custody. Audit is application-level history, not an externally anchored ledger.

Research model artifacts are generated locally. Do not load arbitrary downloaded pickle/model files. The included checkpoints are for reproducing the synthetic experiment only.
