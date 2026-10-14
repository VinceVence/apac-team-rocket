# Risk science extension — 14 October 2026

The full programmatic suite passes **124 tests**, including 11 research checks. No paid SDK is constructed in the fake-model tests. The research path runs actual scikit-learn CPU fits through two tool-limited ADK roles and preserves the existing global meter, six-call fraud-case limit and no-retry policy.

The 1,000-example benchmark separates 100 synthetic customers into 600 training, 200 validation and 200 final-test requests. The fake scientist chooses request + transaction features and both allowlisted recipes. On the final synthetic test (60 scams, 140 legitimate requests), the narrow rule catches 12 scams, the amount-only baseline catches 0, logistic catches 36, and the small boosted tree catches 48. All four have zero false holds on these synthetic controls. This is not production accuracy or calibrated probability evidence.

Logistic and the tree tie on validation recall and false-positive rate, so the fixed selection policy nominates simpler logistic regression. Logistic then fails the final-test 80% recall gate. The validator **rejects the study**; the better-looking tree remains comparison-only. Selecting it after inspecting final-test results would leak the test set into model selection. Tests confirm that changing test labels cannot change the nominee or thresholds, and that the validator cannot override either restriction.

Authorization, immutable operator-curated labels, missing prepayment snapshot quarantine, insufficient-data stops, timeouts, persisted budgets, and scene-reset/cloud-restore behavior are covered. Saved studies do not change payment serving. The hosted Gemini check is recorded below.

## Hosted risk-science check

Cloud Run revision **minttown-00015-425**, application commit **882dcfe**, was verified on October 14. Public research writes without the operator token returned 403. The existing completed fraud scene, its approved knowledge and prevention state remained intact.

The first hosted study, **RISK-e21950a1eb**, ran a fake ADK rehearsal with real CPU fitting and rejected the preselected logistic candidate. The second, **RISK-eb04265233**, used real **Gemini 3.5 Flash-Lite** for both research roles. The scientist called `design_experiment`, choosing transaction + request features and boosted-tree + logistic recipes. Its hypothesis was that combining request behavior and transaction features would outperform amount-only and linear baselines. The bounded tool completed three fits in **4.77 seconds** and retained the rejected candidates.

The validator called `reject_candidates`: the validation-selected logistic model caught only **36/60** synthetic test scams, below the 80% gate. The tree caught **48/60** but was not preselected, so its final-test result could not promote it. No model was deployed and no payment protection changed. Both studies remain visible in **Agent activity → Model experiments**, labelled with the actual provider and benchmark origin.

The live study used **two model calls**, **$0.001602** in application-metered usage, and no retries. Lifetime committed model accounting increased from **$0.055015** to **$0.056617**. These figures use pinned token prices and exclude Cloud Run, Cloud Build, BigQuery, Storage and other infrastructure; they are not a final invoice. The existing limits, single-instance maximum and project shutdown guard were retained. Local receipt: `web/reports/mint-risk-hosted.json` (ignored, with no credentials).

## Earlier guided two-agent demo — 13 October 2026

The current contract suite passes **113 tests**, including fresh scenes, validated detector routing, analyst approval, prevention learning, human activation and local payment protection. A follow-up three-test guided suite also confirms that a cloud-checkpoint restore retains spending, call counts, report admissions and warehouse usage after repeated scene resets. The ten scenario/control fake-model rehearsal still passes. These tests make no paid requests.

The guided fake flow with a fake BigQuery transport uses five resolution turns and one prevention turn from the same case budget. It compares a normal device signal with a suspicious payment-message signal, proposes a safeguard, passes one changed-recipient replay and 20 legitimate controls, and then holds the later simulated transfer before debit while a legitimate payment settles. It makes no additional model call during either payment. A local HTTP/UI walkthrough independently verified review → automatic learner → human activation → protection.

This is contract and synthetic behavior coverage, not evidence of Gemini accuracy or production fraud performance. The first hosted attempt stopped after two calls ($0.001301) because Gemini repeated an already-completed transaction lookup. No retry occurred. This exposed a gap in the offered tool menu, now tightened to remove completed one-time checks and withhold tools with unmet evidence prerequisites. The original failed receipt and spend are retained. The second hosted attempt reached review in six calls ($0.005113), including an unnecessary empty-KB search, leaving no learner allowance. Guided resolution now reserves the sixth call for prevention and does not offer empty-KB searches. Both attempts remain recorded and counted. The completed live learner validation is recorded below. Earlier five-case results remain historical; fresh guided scenes archive their original cases rather than exposing them in the active UI.

## Final hosted two-agent check

The final hosted run completed on **13 October 2026** using Cloud Run revision **minttown-00014-pxg** (application commit `7414499`). Case **SC-f390e6bcd0** began with **Run world**, 100 synthetic customers and a fresh scene. Its pinned BigQuery snapshot contains **5,736 rows** across seven typed table definitions (empty review/memory tables require no load job).

Gemini 3.5 Flash-Lite chose `get_transactions` → `get_customer_features` → `run_fraud_detectors` → `get_complaint_guidance` → `submit_for_review`. It selected **message intent (1.0)** and **payment velocity (0.5)** detectors. These are uncalibrated rule signal scores. It recommended support follow-up and official-channel verification for the **₱900** reported transfer; it did not claim that money was recovered.

An explicitly labelled **programmatic synthetic-analyst approval** published memory **MEM-807a07e626**. The real prevention learner then made one native `propose_prevention_rule` call, selecting **safe-account request AND secrecy request**. Rule **RULE-6715c5da54** passed one changed-recipient replay and 20 synthetic legitimate controls with zero flags. An operator activated it after checking the proposed conditions and replay.

The subsequent **₱900** attempt used a different customer and recipient, `external:variant-10-phishing`. It was held before settlement with a receipt citing the rule, review and source case. A normal merchant payment settled. The ledger remained balanced. These payment checks added **zero model calls and zero metered model cost**.

The successful case used **5 resolution + 1 prevention calls**, totaling **$0.004762** in metered model usage. Across all three new live attempts, model usage increased by **$0.011176**. Conservative lifetime committed model accounting—including older uncertain reservations—ended at **$0.050422**, with **46 calls counted for the UTC day**. These amounts exclude Cloud Run, builds, BigQuery, Storage and other infrastructure, and use the application's pinned token prices rather than a final billing invoice.

The full suite passed 113 tests, and the final guided-call reservation change passed 36 targeted checks afterward. Failed attempts remain in private scene archives and local receipts; starting a fresh scene did not erase their usage. The final live receipt is `web/reports/pallet-guided-live.json`; the two earlier attempts are retained beside it. These synthetic observations do not establish real-world fraud accuracy or analyst time savings.

## Earlier five-case live evaluation

**Five real Gemini investigations reached analyst review.** The run used **25 generations and $0.021283** in metered model usage at the pinned token prices. The prior $0.003470 ledger balance was preserved; cumulative committed usage is $0.024753. These figures exclude BigQuery, Storage and other infrastructure charges.

Two complaints were generated by the actual Run world endpoint; three distinct complaints were staged before the episode so the five-case exercise fit within three warehouse publications. The episode advanced 24 steps, from tick 32 to 56. Cloud Run remained disabled; Python and ADK ran locally.

| Case | Calls | Model usage | Result |
|---|---:|---:|---|
| Bank impersonation | 6 | $0.005114 | Analyst review |
| Account takeover | 4 | $0.003480 | Analyst review |
| Invoice redirection | 5 | $0.004192 | Analyst review |
| Task/job scam | 5 | $0.004440 | Analyst review |
| Investment/advance-fee scam | 5 | $0.004057 | Analyst review |

## Actual choices

- All five called `get_transactions`, `get_customer_features` and `get_complaint_guidance` before submission.
- Account takeover completed in four calls without a memory search. The other cases searched reviewed knowledge. None cited a matching memory in its final proposal.
- Gemini did not choose `train_behavior_model` or `ask_customer` in this live sample. The tool and follow-up paths were exercised with fake-model contract tests, not credited as live choices.
- All five proposed `suspected_scam` for known-positive synthetic fixtures. This is fixture agreement, **not measured real-world accuracy**, and the live run contains no legitimate negative controls.
- No case was approved by the evaluation script, no new memory was published, and no real bank action or refund occurred. All five reached human review at that time; fresh guided scenes now archive those historical cases.

## Failures retained in the evidence

The bank-impersonation draft initially called 90,000 minor units “90,000 PHP” instead of ₱900. We retained that trace, changed tools to return peso values and canonical totals, added a deterministic monetary-value check before submission/approval, and explicitly rechecked the same case using its one remaining generation. Its corrected proposal states ₱900.00. The case consumed six calls in total; its budget was never reset.

The original command-line observer timed out after 240 seconds while the backend episode continued. The episode and both automatic investigations subsequently finished. The observer was changed to persist its episode identity and resume existing cases, with a bounded longer observation period; it did not restart the world or repeat paid model turns. State checkpoint compression and local-only world-tick batching were then improved; these performance changes passed separate durability checks but were not credited as the timing of the original live run.

## Warehouse evidence

The final publication contains **5,896 rows** across seven typed tables for 100 active customers. Table rows carry a snapshot ID and event-date partition. Repeated publication versions are separate snapshots, not independent customers or independent observations.

| Table | Rows in final snapshot |
|---|---:|
| `pallet_complaints` | 9 |
| `pallet_customer_daily` | 2,900 |
| `pallet_customers` | 100 |
| `pallet_memories` | 2 |
| `pallet_merchants` | 9 |
| `pallet_reviews` | 2 |
| `pallet_transactions` | 2,874 |

The existing approved knowledge also held a later ₱900 transfer during the episode. Its receipt cites `MEM-471e7a91d2` and `MEM-5977ccbec9`, both from earlier reviewed cases. This demonstrates reuse of existing knowledge; it is not a claim that an unreviewed case from this run activated prevention.

## Optional model validation

Gemini did not request model training in these five investigations. A separate operator check verified the actual BigQuery → local CPU model path without any additional Gemini call. The corrected daily-aligned recipe trained three k-means clusters on **2,240 daily rows from 80 customers**, with **560 rows from 20 other customers** held out. Five percent of the unlabeled holdout was flagged as unusual; this is not fraud accuracy.

The recipe uses payment count, spend in pesos, average payment and merchant count. Demographics and incompletely recorded historical device/minute signals are excluded. An earlier QA candidate exposed inconsistent daily-versus-history aggregation and was superseded before use. Neither candidate activated a prevention rule. The final receipt is `web/reports/pallet-model-validation.json` (ignored local artifact).

## What remains unproven

- Real customer outcomes, recovery rates, legal liability, reduced analyst handling time and performance outside these synthetic fixtures.
- Live false-positive behavior on the five legitimate lookalikes.
- Whether a particular memory improves a held-out investigation compared with no memory.
- A supervised fraud classifier or real-world generalization. The new prevention learner proposes constrained signal rules; its replay is synthetic. The optional trained model remains a bounded, advisory unsupervised behavior model.
- Complete Philippine legal-policy verification: some BSP PDFs blocked extraction. No statutory deadline or reimbursement entitlement was encoded.

## Reproduce and inspect

The fake evaluation covers ten scenario/control fixtures with injected decisions. It validates execution and scope, not intelligence. Regression checks cover durable budgets, no retries, restart behavior, query/publication limits, monetary units, evidence snapshots and approval boundaries.

Raw synthetic receipts remain in ignored `web/reports/pallet-live-e2e.json`, `pallet-*-automatic.json`, `pallet-peso-recheck.json` and test logs. The observer uses the same run ID to resume saved cases; a new run ID is a new evaluation and consumes current shared allowances. Do not clear the ledger to repeat the demo.
