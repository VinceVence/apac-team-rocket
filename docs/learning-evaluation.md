# Live learning-loop evaluation — 16 October 2026 (Manila)

**Later verification:** [The new visual demo](visual-demo.md) completed a real second investigation with memory and predictions under the unchanged context cap. Cloud Run was explicitly restarted by the owner. The earlier results and failures below remain preserved.

Runtime: `cb84f17` on Cloud Run. Synthetic customer data; real Gemini tool choices and real CPU model fits. This is a bounded prototype evaluation, not production fraud accuracy. The runtime was deployed successfully and was scaled to zero at the owner's request for the night. Do not restart it or schedule more paid tests without authorization.

## What worked end to end

Fresh world run **28** generated case **SC-6fd0d81c6e**. Gemini chose `get_case_evidence → score_models → submit_case_resolution`. The evidence tool used a parameterized BigQuery aggregation over `minttown_world.customers`, `wallets`, `devices`, and `wallet_transactions`; the query billed 40 MiB, below its 50 MiB cap. This fresh customer had no historical baseline, which remained explicitly missing.

After explicitly assumed demo analyst approval, a real prevention generation proposed **PB-2b7f50c3f2bb** and **RULE-7aebcf8454**: safe-account instructions together with secrecy. Human demo activation followed replay checks. A later **₱900 attempted payment to a different recipient was held before debit**, and the legitimate control settled. The candidate's paired replay improved interception from **0/3 to 3/3** tested scam variants without additional holds on six legitimate controls. These small, constructed replay results are not population-level accuracy.

No exact-recipient fallback was used. The source investigation and prevention together used **four paid generations**. The payment gateway used **zero LLM calls per payment**.

## Real Scientist → Refiner → Validator

Study **RISK-ec403be59a** used three actual Gemini generations. The scientist selected word features plus payment behavior, alongside a behavior-only reference. Trusted CPU tools fitted both models. The refiner saw validation errors and component ablations and chose **keep the winner**; it did not perform a refinement fit in this live run. The validator rejected payment release.

| Candidate | Validation scams detected | Final-test scams detected | Final-test legitimate flags | Release |
|---|---:|---:|---:|---|
| Payment behavior | 7/60 | 6/60 | 4/140 | Rejected |
| Word request + behavior | 41/60 | 44/60 | 20/140 | Rejected |

The word model was explicitly registered **for advisory investigation only** as `request-21ef1d9d470f`. A subsequent real Gemini investigator selected it, received a versioned prediction receipt and produced a review-ready proposal. Registration did not activate payment blocking. The earlier offline, predetermined word+character refinement improved validation detection to 44/60; do not present that offline choice as this live refiner's decision.

## Memory comparison and retained failures

Each pair used the same disputed transactions and customer report. Reviewed knowledge was available or withheld. The investigator remained free to retrieve it.

| Fixture | Knowledge | Calls | Actual outcome |
|---|---|---:|---|
| Scam | Withheld | 3 | Suspected scam; ready for review |
| Scam | Available | 3 | Retrieved playbook and scored models; stopped at the input-context cap before synthesis |
| Legitimate lookalike | Withheld | 3 | Likely legitimate; ready for review |
| Legitimate lookalike | Available | 2 | Likely legitimate; chose not to retrieve memory |

**Memory retrieval and prevention improvement were demonstrated; better investigation accuracy from memory was not established.** The remaining context-limit case is **SC-f5b049705f**. It requires analyst handling; no request was retried. A follow-up should compact the memory + predictor context and test that combination offline before another authorized live test. Do not increase the dollar caps to work around it.

An earlier comparison, **SC-70966adbd2**, cited memory it had not retrieved. The harness rejected the draft. Commit `cb84f17` constrains memory and prediction citations to retrieved/recorded IDs and removes knowledge-derived recipient alerts from the withheld condition. Its 20 targeted offline tests passed. The failed case remains in the audit trail.

## Spend and verification

This learning-loop batch used **21 paid generations and $0.018786 in recorded model charges**, including failed attempts. The shared lifetime model ledger ended at **$0.173994**; UTC-day model spend was **$0.112659**. These figures exclude Cloud Run, builds, BigQuery and storage. Six earlier baseline-comparison generations are recorded separately and are included in the shared lifetime ledger.

Dollar limits remain **$2/day, $0.05/case, $8 lifetime model spend**, within the existing $20 project envelope. One paid call in flight, six-second spacing, six calls/case including prevention, and no automatic retries remain enforced. Daily count quotas were removed; payload/row/byte bounds and HTTP throttles remain. No counters were reset.

The implementation passed **197 Python tests and 36 JavaScript tests** before deployment. The citation fix then passed **20 targeted Python tests**, including the new regression cases. Saved source traces, study candidates, replays, failures and reservations remain in durable application storage. Raw operator evaluation files stay ignored.

[Architecture and implementation](learning-loops.md) · [Model contract](model-artifacts.md)
