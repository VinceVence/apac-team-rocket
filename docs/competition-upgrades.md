# Competition upgrades — implementation and evidence

Mint Town now connects scoped transaction features, optional model tools, a bounded investigator and reviewed prevention. The contribution is the **auditable handoff from a disputed payment to a tested future safeguard**. These are adaptations of established methods, not a claim of globally novel research.

| Upgrade | Implemented behavior | Boundary |
|---|---|---|
| Evidence-driven investigation | Lead sees each predictor's distinct target, conflicting observations and missing evidence; can choose one specialist or a customer question | No averaging incompatible scores; no private reasoning exposed |
| Safer citations | Short case-bound transaction aliases are constrained in native ADK tool schemas and checked again at execution | Snapshot IDs cannot substitute for transaction citations; invalid drafts stop without retry |
| BigQuery evidence | Parameterized query joins the AE's four tables, pins the customer/cutoff and compares returned rows/aggregates with canonical simulator records | Only completed, matching `minttown_world` publications qualify; stale/unpublished data falls back to labelled local evidence |
| Trained model tool | Hash-checked JSON logistic/tree adapter; one real CPU-trained synthetic advisory baseline registered alongside the three rules | Karlo's artifact is not ready. This baseline failed the prevention release gate; scores are uncalibrated and cannot activate a hold |
| Scientist ablation | Scientist can remove one feature group and compare the same recipe, plus an amount-only baseline: at most three CPU fits | Validation selects the nominee; test results can veto, never promote a different candidate |
| Paired prevention | Same requests tested under previous and proposed policy, including changed recipients, small amounts, paraphrases, missing context and legitimate controls | Counterexamples can reject a lesson-derived rule. Human activation remains separate |
| Comparison harness | Twelve fixtures, single lead versus selective specialist, plus 100 paired payment attempts | Offline agent choices are fake. Hosted live comparison is operator-only, resumable and subject to the existing meter |

The new Agents panel shows saved results and failures. Agent activity shows actual data provenance and conflicting signals. Prevention shows before/after counts and its rejected broad baseline. Research lab shows feature-ablation effects in saved studies. The Next-only walkthrough and three top-level tabs remain.

## Measured offline results

Run `uv run --locked python -B web/evaluate_upgrade.py --mode fake`. It writes full receipts to ignored `output/upgrades/evaluation.json` and a small public `web/dist/evaluation-summary.json`.

- **24/24 review packets** passed execution-contract checks. Single lead: 39 fake generations; selective specialist: 51. Both arms use the same payment evidence. This establishes execution behavior, not superior Gemini judgment.
- **100 synthetic payment attempts**, each run before and after learning: scam holds increased from **0/50 to 34/50**; **50/50 legitimate payments settled**; every held payment had **zero debit**. The investment policy was rejected because a legitimate control matched. Sixteen scam variants remained unblocked. Recipients and some wording/amounts vary; this correlated bank is not a real-world accuracy estimate.
- **Real fitted advisory baseline:** validation 48/60 scam examples and 0/140 legitimate flags; final test 36/60 scams and 0/140 legitimate flags. The final-test recall missed the 80% demo release gate. A different candidate passing the test does not override validation-only preselection.
- **Ablation:** in the fixed synthetic benchmark, including request features increased validation recall by 60 percentage points with no additional legitimate holds versus the same logistic recipe without them. Test comparison is diagnostic, not a tuning loop. Legitimate templates are reused across splits, so do not claim independent language generalization.
- **BigQuery SQL dry-run:** valid against all four deployed `minttown_world` tables, estimated 102,441 bytes at verification time. No billed data query was executed for this upgrade. Full value parity is covered with mocked BQ responses; a fresh live query still needs publication/query allowance.

The upgrade test run made **zero paid model calls**. A live 24-run comparison remains pending; its runner reserves 20 daily calls for demos, admits at most 12 new runs/day, and keeps all attempts. See [operations](operations.md). Do not claim a measured agent-quality improvement until this comparison is complete.

## Teammate handoff

Karlo supplies the reviewed target, feature builder, artifact, evaluation and operating range using [the artifact contract](model-artifacts.md). Gab's original dataset stays read-only. The current SQL features inform the investigation; the synthetic trained adapter consumes the separately frozen prepayment feature vector, **not** the later complaint or BQ snapshot. A new BQ-trained artifact needs its own matching feature contract and parity tests before registration.

The repository stays private until the owner authorizes publication. The submission video/deck and real analyst usability study are still separate deliverables; code tests are not evidence of time saved in an actual bank.
