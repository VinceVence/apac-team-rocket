# Repository integration and security audit

Audit date: 18 October 2026. Main baseline: `9a13b61`. The working checkout and its uncommitted files were preserved; this release was prepared from the pinned GitHub tree.

## Contributions reconciled

- **Gab (`f03a384`, PR #5):** dictionary, data model, generator and ingestion workflow. Generation now defaults to 100 numbered residents and 1,000 transactions, with deterministic IDs, chronological records and sender-owned devices. It uses the standard library. CSVs and receipts remain ignored.
- **Karlo (`4858404`):** classifier/model-tool lineage is merged while retaining the newer integration already on main. `ledger-features-v2`, temporal holdouts, model receipts and validation stay intact. The older mutable balance, risk-tier and device-trust feature path was not restored.
- The loader validates offline by default. Explicit imports reject the AE dataset, nonempty destinations, unowned tables and contract drift. They use `CREATE_NEVER`, `WRITE_EMPTY`, deterministic job IDs, bounded rows/bytes and no upload retries. A persistent receipt prevents blind resubmission.
- Retrain/deploy now requires an explicit mode. Calling its shell entry point without arguments prints help and performs no cloud work.
- README and help index describe the current paused world and browser-only walkthrough, with the product logo, actual town image and architecture. Only the separately requested narration, day 1/4/7 labels and 4K export source changes are included; rendered media remains excluded.
- Removed the superseded two-day task plan and omitted the empty upstream SQL placeholder. Video components remain intact. Historical QA and model limitations remain available.

## Credential audit

Gitleaks **8.30.1** scanned **917 distinct historical file versions** across the six branch histories, the closed PR #2 head and the advertised PR #5 merge tree. The scope contains **91 commits** including that merge. No secret matches were detected. A separate scan found no encoded SSH public keys or PEM public/private-key blocks. The published source tree is scanned again before the main update.

The scanner binary came from the official Gitleaks release and its SHA-256 was verified. Scan output is fully redacted. CI pins action commits and the scanner checksum, uses read-only repository permissions and scans history on pushes and PRs. No workflow receives Google Cloud credentials.

A personal contact address was removed from current hosting documentation. Git author attribution and earlier documentation remain in history; this audit did not rewrite shared history or change repository visibility. Project/resource identifiers are not credentials. Pattern scanning is not a guarantee against every possible secret; see [SECURITY.md](../SECURITY.md).

## Validation

- Full Python regression: 221 tests passed. The six data-tool tests were rerun after the final cap/chronology checks.
- Offline data-tool regressions: six checks passed, including empty-only loading, protected source data, no blind retries, caps and foreign-key validation.
- JavaScript: 68 checks passed.
- ADK harness: ten scenarios passed, zero paid model calls.
- Fake case evaluation: ten cases completed.
- Remotion TypeScript check passed for the requested source updates.
- Local fixture round trip: 100 customers, 100 wallets, 100 devices and 1,000 transactions; zero cloud calls.

All 249 intended source files passed the final credential scan, with no secret matches. The shipped UI, active agent loop, prevention path, cost controls and trained artifact remain byte-identical to the baseline. No live Gemini investigation, BigQuery import, model retraining, IAM change or Cloud Run deployment was performed for this repository audit.
