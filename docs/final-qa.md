# Release audit and QA — 16 October 2026

This is a code review and functional release check, not a guarantee that no future bugs, model failures or cloud outages can occur. No subagents were used. Teammate changes, archived cases, data ownership and all spend counters were preserved.

## Fixes and cleanup

- **Evidence preparation:** the guided demo now identifies the data pipeline and its recorded progress. It no longer depicts an idle resolution agent before that agent exists. No invented model activity or progress percentage is shown.
- **Protection navigation:** the headline button follows the blocked incident even when a later legitimate payment is first in the activity list. Browser QA verified that it opens the correct knowledge section.
- **Static HTTP boundary:** GET and HEAD now share an explicit file allowlist; unknown files and directory listings are rejected. HEAD responses have no body. Incomplete HTTP uploads have a bounded timeout.
- **Dead code:** removed the unused customer/marketing UI, old playbook UI, obsolete JavaScript economy engine and its standalone check. The Python simulation, historical ledgers and offline diagnostic backends remain intact. Legacy paid endpoints remain disabled by the hosted guard.
- **Configuration/docs:** removed the obsolete 100-call default from `.env.example`, corrected stale count quotas and BigQuery descriptions, made the local launcher explicitly start without history, and condensed `AGENTS.md`. Live launches still require explicit authorization and a paused hosted shared-ledger writer.

## Offline verification

| Check | Result |
|---|---|
| Complete Python suite | 200 tests passed |
| Complete JavaScript suite | 38 tests passed |
| Harness scenarios | 10/10 passed; zero paid calls |
| Package consistency | 57 installed packages compatible, Python 3.12 |
| Python syntax | 77 modules parsed successfully |
| Frontend dependency graph | All remaining browser modules reachable from the app entry point |
| Credential-pattern scan | No matching credential patterns in the release source surface |
| Packaging | Runtime allowlist excludes credentials, local data, reports, caches and output directories |
| Remote/local source comparison | Only intended changes differed from the starting GitHub revision |

Functional coverage includes missing/stale evidence, customer follow-ups, invalid model/tool inputs, analyst approval gates, changed-recipient prevention, legitimate lookalikes, revocation, restart/accounting preservation, bounded queues, unknown execution, budget exhaustion and no automatic retries. Fake choices test execution contracts, not Gemini quality.

## Browser QA

The isolated normal demo completed payments → complaint → real tool execution with a fake model → demo analyst review → knowledge → safeguard → changed-recipient hold. Back/Next, Finish, the knowledge link, pause/resume and the restart confirmation were exercised. Restart visibly returned to zero transactions. No browser-console errors were observed.

At 375 × 812, the tool diagram and protection scene remained readable and Next/Finish stayed in the viewport. The background was inert and scroll-locked; keyboard focus wrapped inside the dialog. The viewport override was reset afterward.

An exhausted-budget instance used the clearly labelled saved Gemini replay. It completed entirely in the browser and returned to the underlying world with zero transactions, zero reports and zero model calls. Screenshots and raw QA receipts are retained in ignored `output/final-qa/`.

## Hosted verification

Release `0291de7` deployed successfully to Cloud Run revision `minttown-00040-rrg`. Fresh case **SC-18e89835be**, world run **30**, completed with real Gemini: pinned BigQuery evidence → model tools → proposal → explicit demo analyst approval → Gemini safeguard/playbook → separate activation → changed-recipient hold. The SQL query billed 40 MiB inside the 50 MiB cap.

The durable ledger independently confirms **zero journal entries and zero debit** for the held attempt; the legitimate control settled. No exact-recipient or recorded-demo fallback was used. The hosted static checks returned 200 for `HEAD /app.js` and 404 for the font directory and retired clients.

The live check used **4 model calls costing $0.00385**. Shared lifetime model accounting ended at **$0.185896**. These figures exclude hosting, storage, builds and BigQuery. Existing $2/day, $0.05/case and $8 lifetime caps, six case calls, one paid call in flight, six-second spacing and no automatic retries were unchanged. No model training or IAM changes were performed during this audit.

The hosted world is paused with the completed case retained. Offline preview servers were stopped and temporary viewport overrides reset. No release-blocking failure was observed in the tested paths.

## Practical limits

This is a shared synthetic demonstration, not a production multi-tenant banking service. Demo analyst approval is explicitly assumed; a real analyst must independently verify testimony and resolve actual cases. Model scores remain uncalibrated advisory signals, and rejected research candidates cannot authorize payment blocking. Small synthetic replay banks are not fraud-accuracy evidence. Provider/network failures stop safely or offer a labelled recording. Cloud billing controls are delayed; the app meter does not cap teammate builds, training or hostile hosting traffic.
