# Mint Town — two-day competition plan

Implementation update: [shipped upgrades, measured results and remaining DS/live-evaluation work](competition-upgrades.md). The assessment below records the pre-upgrade baseline.

Reviewed 15 October 2026 against application `5b5a107`, the three earlier research reports, saved evaluations, and current official competition pages. This is a focused review and implementation proposal; it is not a new Hyperresearch run or a claim that the proposed upgrades already work. No subagents or new paid model evaluations were used for this review.

**The strongest proposition:** Mint Town helps an analyst investigate a scam, then turns the reviewed finding into a tested prevention control. The simulator makes both the benefit and the mistakes observable: an unseen-recipient scam should be held, while a legitimate lookalike should still settle.

The Google stack and animation establish a working prototype. Winning differentiation needs evidence that the agent selects useful checks, handles ambiguity, and improves later decisions. Agent count is not a result.

**Optimize for the actual rubric.** The official weights are technical/GenAI implementation 40%, problem alignment/impact 25%, innovation 25%, and UX 10%. Our BFSI fit is fraud investigation and mitigation with better customer handling. [Official theme and rubric](https://aibuildercup.com/themes.html)

| Criterion | Evidence to put in front of judges | Current gap |
|---|---|---|
| Technical / GenAI, 40% | Actual Gemini choices, versioned BQ features, a real trained predictor, complete tool receipts and reliable transitions | Recent live citation rejection; runtime predictors are still three demo rules |
| Alignment / impact, 25% | A reviewable case packet, a useful follow-up question, measured preparation time, fewer unnecessary holds | No measured analyst time savings or real-world fraud performance |
| Innovation, 25% | Reviewed lessons with exceptions; candidate rejection; before/after replay on unseen recipients and legitimate controls | Learning works in narrow examples; incremental benefit is not yet established |
| UX, 10% | Under-three-minute narrative; readable Next-only flow; clear live/replay and analyst boundaries | Avoid shrinking the world to a sliver on narrow screens; freeze other redesign work |

The official deadline is **18 October 2026**; the public page does not establish the exact cutoff timezone. Use **16 October for integration and 17 October for evaluation/recording**, with a submission buffer. [Official timeline](https://aibuildercup.com/)

**What is actually implemented.** The current app has a real synthetic ledger, immutable evidence, a Gemini/ADK tool loop, one optional scoped specialist, deterministic contract judges, reviewed knowledge, and a local pre-debit gateway. It also has a separate bounded scientist/validator workflow with actual CPU fits and rejected experiments. New-case aggregate features currently come from Python/SQLite; BigQuery is a batched mirror, although legacy BQ query tools exist. The scientist's models are not yet integrated into payment serving. The recorded demonstration uses genuine saved Gemini receipts and a separately recorded gateway test; it is not fresh inference. See [runtime](harness-runtime.md), [evaluation](evaluation.md), and [operations](operations.md).

The last live case read evidence and scored signals, then failed its citation contract after three calls. That is evidence that the guard rejected an invalid draft; it is also a reliability defect to fix before the competition. Earlier five-positive-case runs do not establish accuracy. The saved prevention replay held **9/10 changed-recipient scam transactions** and allowed **5/5 legitimate payments**; the small investment-fee variant escaped a rule requiring a large amount. Keep that failure visible.

**Three adaptations worth shipping.** These combine prior methods for this use case; global novelty has not been established.

1. **Investigate model disagreement.** A familiar device can look normal while the customer describes a deceptive transfer. Keep each detector's target explicit. The lead decides which missing fact to inspect, whether a specialist adds value, or which customer question resolves the ambiguity. Show the question, selected tool, returned fact, and changed conclusion. Never average unrelated scores into an invented fraud probability. ToolOrchestra motivates useful, cost-aware selection; its RL-trained orchestrator is not a two-day dependency. [NVIDIA / HKU, ToolOrchestra](https://arxiv.org/abs/2511.21689)
2. **Test a lesson against its counterexamples.** A reviewed entry carries the mechanism, required observations, exceptions, source receipts, version, expiry and revocation. The prevention learner proposes a bounded control. The validator checks a changed recipient, alternate wording, a negated warning, an independently verified transfer, and missing context. Only a passed candidate can be activated by the analyst. ACE supports structured incremental playbooks; our added financial-domain design is review plus explicit falsification before serving. [ACE](https://arxiv.org/abs/2510.04618)
3. **Let the scientist test one useful hypothesis.** Example: does recipient-history information improve the existing detector at the same legitimate-hold rate? Choose one feature ablation and compare a simple baseline with one trained candidate. The validator can reject it or ask for more labels. MLE-STAR supports targeted ablation/refinement, not blindly fitting more models. Reuse the existing scientist/validator and Karlo's artifact; no new orchestration platform or GPU is needed. [Google Research, MLE-STAR](https://arxiv.org/abs/2506.15692)

Use one lead, at most one conditional specialist, and prevention after review. The scientist/validator is an explicitly started research lane. A model pack, feature query and payment gateway are tools, not extra agents. Controlled research finds that coordination can help or hurt depending on task structure, so compare selective delegation with the same model and tools in a single-agent baseline. [Google / DeepMind / MIT, scaling agent systems](https://arxiv.org/abs/2512.08296)

**Build order and ownership.** Assignments below are proposed work ownership, not messages sent to teammates.

| Priority / time | Owner | Concrete deliverable and exit check |
|---|---|---|
| P0, first 4 hours | Agent work | Reproduce the failed citation from its saved request. Use short scoped evidence references or a constrained selection schema, and assemble canonical references in trusted code. Never silently accept an unknown citation. Regression checks must catch foreign/stale IDs, missing evidence and duplicate actions. |
| P0, hours 4–12 | Gab + agent work | One parameterized BigQuery feature query over the four AE tables, with customer/event scope, partition filter, explicit cutoff, units and missingness. Save the job ID, feature version and values in the case snapshot. Compare SQL results with local reference calculations. Reuse the cache when needed and label that provenance. Preserve Gab's source dataset. |
| P0, hours 4–12 | Karlo | One reviewed CPU model artifact, deterministic feature builder, target/score semantics, version/hash, training cutoff, split definition and example predictions. A second model is optional. Keep label-derived fields and demographics out of predictor inputs. |
| P0, hours 12–20 | Agent + DS work | Wire the artifact into the existing model registry. Demonstrate that a different evidence gap changes the selected check or follow-up. Unavailable inputs must produce `not_available`, not a zero-risk result. |
| P1, hours 20–28 | Agent + validator work | Add paired-policy replay: identical transaction/context under the previous policy and candidate policy. Show the scam, legitimate control, and one rejected broad baseline. Pin the accepted version; test revocation. No LLM per payment. |
| P1, hours 28–36 | Team | Run the frozen comparison set, keep every attempt, report outcomes/cost/latency and inspect false positives. Fix contract defects offline; do not tune on the final test set. |
| P0, hours 36–48 | Team | Freeze the build. Produce a 2:45 video, PDF deck, architecture page and evidence table. Test the public URL without owner login. Leave time to submit. |

If the artifact is not ready at hour 12, ship the existing rule-based prevention honestly and demonstrate the scientist's measured rejection. If the optional specialist does not outperform the single-agent baseline, use the simpler successful configuration. Do not hold submission hostage to a full autonomous data science department.

**Make BigQuery and the data matter.** Keep the AE's `customers`, `wallets`, `devices`, and `wallet_transactions` contract. Start with spend count/value, amount versus history, recipient novelty, transfer velocity, and device ownership. Return an observable source → feature → model receipt → recommendation chain. Require both `event_time <= decision_time` and `available_at <= decision_time` for prevention; a later complaint cannot be treated as a signal the payment gateway already knew. Labels also need a training cutoff. A new customer legitimately lacks history.

Demonstrate one feature's contribution with an ablation. The goal is to show why the customer history changes the investigation, not to show that a table exists. Train on operator-curated labels, not arbitrary public demo approvals or the agent's own guesses. Keep hidden simulator truth for evaluation only.

**Evaluation that can fit the remaining time and existing meter.** All numbers below are a proposed evaluation allocation, not achieved results or permission to start a paid run.

| Question | Experiment | Report |
|---|---|---|
| Does agency help? | Fixed rule workflow versus Gemini lead versus lead with selective specialist, with identical tools, fixtures and limits | Supported review-ready packets / all attempts; correct abstentions; invalid citations; unnecessary calls |
| Does the trained model help? | Rule baseline versus Karlo's frozen artifact on untouched later-time/customer/template groups | Confusion counts, precision/recall, PR-AUC if appropriate, false holds; calibration only when justified |
| Does approved knowledge help? | Previous versus learned policy on identical held-out payment attempts | Newly intercepted scams, newly held legitimate payments, unchanged cases, missing-input behavior |
| Is the agent robust? | Missing device/context, unrelated/revoked memory, misleading complaint, wrong IDs, stale model, duplicate Next and restart | Rejected unsafe actions; preserved state/spend; appropriate questions or handoff |
| Is it efficient? | Same model and generation cap across agent arms | Median and tail time to review-ready packet, generations, token cost, tool count; local gate latency separately from HTTP/cold-start latency |
| Is it useful to an analyst? | Small timed synthetic case-packet task, reviewed with a frozen rubric | Preparation time, corrections and acceptance counts; disclose reviewers/sample size |

Use **12 core cases**: five scam families each paired with a legitimate lookalike, one missing-evidence case, and one adversarial report. Compare the two agent configurations: **24 total runs**, capped at six shared calls and $0.05 each. Split into at most 12 runs per UTC day: at most **72 calls/day and $1.20 total model spend** across two days, leaving room within the existing 100/day limit. These are ceilings, not estimates; all attempts and specialist/prevention calls count. Use the same durable meter and one writer. No automatic retries, budget resets or paid LLM judges. Reserve the remaining daily allowance for demonstrations and existing bounded research jobs.

Separately run **100 cheap payment replays**: five families × ten scam variants and ten legitimate controls. Include the known small investment-fee miss. Hold out wording/templates as well as recipients; changing only names is a weak test. Keep this test bank separate from examples used to propose or tune a rule. Report raw counts and synthetic scope; correlated simulated examples cannot establish a bank's real-world false-positive rate.

ADK offers tool-order and quality evaluation. Prefer invariant-based `ANY_ORDER`/`IN_ORDER` checks over requiring one exact route, and verify availability in our pinned ADK version. Tau-bench's final-state approach is particularly relevant: assert zero debit for a held payment, settled legitimate controls, and no activation without approval. [ADK evaluation](https://adk.dev/evaluate/criteria/), [Tau-bench](https://arxiv.org/abs/2406.12045)

**The 2:45 judging story:** 0:00–0:20 show the customer problem and live town; 0:20–1:00 show normal authorization conflicting with a deceptive request and the agent's actual chosen check/question; 1:00–1:25 show the cited proposal and analyst decision; 1:25–2:00 show the learned candidate, a rejected broad baseline and legitimate controls; 2:00–2:25 show the changed-recipient scam held and normal payment settled; 2:25–2:45 show the measured comparison, Google architecture, and limitations. Use saved results openly when appropriate. Do not claim recovered money, perfect detection, production bank integration, or days of time savings without evidence.

**Submission status:** Cloud Run hosting is restored. The FAQ requires a deployed prototype, a public GitHub repository, a video under three minutes and a deck. The repo is currently private; the owner has explicitly deferred making it public. Review source/history before that later visibility change. The theme page calls for the deck as PDF and English submission materials. [Official FAQ](https://aibuildercup.com/Faqs.html), [submission requirements](https://aibuildercup.com/themes.html)

Prior research reviewed: [investigation harness](../research/notes/final_report_mint-fraud-agent-harness-8960d2.md), [risk science mesh](../research/notes/final_report_pallet-risk-science-mesh-85175f.md), [resolution/prevention](../research/notes/final_report_pallet-resolution-prevention-9a5799.md). Their architectural ideas remain useful; historical budgets, data paths and deployment claims must be read against the current code and operation guide.
