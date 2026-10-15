# Investigation harness

Implemented in the current app for **new investigations**. Older saved cases retain their original trace. The Google model and all budgets stay unchanged. There are no new dependencies or agent servers.

## One case, shared control

The case lead chooses evidence, registered model tools, a customer question, an optional specialist, or a review proposal. It can finish without delegation. The four selectable helpers are **transactions**, **device/identity**, **scam context**, and **resolution critic**; at most one runs per case.

A delegated question pins the case revision, snapshot, evidence IDs and model receipts. The parent generation finishes before the worker executes the child's one bounded generation. Its cited finding returns to the lead. There is one worker, not a nested `AgentTool` call or an extra queue waiting on itself.

A five-generation example is `case evidence → chosen predictors → delegate → specialist finding → submit`. Prevention can then use the sixth generation after approval. This is an allowance example, not a compulsory order. Questions and additional checks consume the same allowance; insufficient evidence or budget ends in human review.

`get_case_evidence` reads verified payments, the existing pinned BigQuery behavior snapshot when enabled, and the complaint checklist. The raw AE-shaped `minttown_world` mirror remains separate; it is not an unrestricted SQL tool. Predictors use frozen prepayment inputs. Historical event IDs are replaced by opaque case-bound aliases in model prompts so simulator IDs cannot reveal scenario names.

## Judges

| Judge | Checks | Failure behavior |
|---|---|---|
| Evidence | Customer/revision binding, verified citations, frozen evidence, PHP amounts, completed delegation, current reviewed lessons | Withhold the draft or stop an invalid tool |
| Model contracts | Registered model and feature versions, artifact digest, receipt ownership and evidence snapshot; explicit missing inputs | Missing/stale inputs remain unavailable; stale cited inferences block approval |
| Resolution | Valid proposed action, uncertainty, specific unsupported refund/guarantee/liability/probability claims | Preserve rejection reasons; correction uses remaining case calls |
| Tool boundary | Exact function/argument schema, role permissions, customer scope, no authentication-secret collection, budgets | Deny execution, save the reason and retain the paid reservation |

The first three are **local deterministic checks**, not paid LLM judges or proof of fraud. Their semantic coverage is limited. The optional **Gemini resolution critic** can challenge interpretations using its scoped facts; it shares the same case meter and cannot approve. Only an analyst publishes a resolution, and safeguard activation remains a separate decision after replay.

## Models as tools

`fraud_models.py` wraps three existing demo rule predictors, not trained fraud probabilities. Each manifest declares its target, score kind, input requirements, feature/model versions, artifact digest, release status and missing-input behavior. Model receipts retain inputs' hashes, snapshot/cutoff, per-event availability and results. Unknown IDs/foreign events fail closed; missing values never become zero risk.

The DS teammate should provide a reviewed predictor adapter, feature builder, artifact digest, manifest, calibration evidence when claiming probabilities, and temporal/customer-separated evaluations. Add it to the trusted registry with contract tests. The agent cannot download executables, install models, choose arbitrary endpoints or promote an artifact. MCP can be added at that gateway when a real independently hosted model service exists.

## Saved work and knowledge

Full receipts, task state, judge results and costs stay in SQLite and the existing generation-checked cloud checkpoint. Prompts receive a compact relevant projection. A customer reply preserves the same case allowance and compatible receipts. Explicit **Resume saved work** can continue an interrupted checkpoint only when previous requests finished, evidence is unchanged and allowance remains. An uncertain paid response is never replayed automatically.

Approved lessons include applicability, legitimate counterexamples, source receipts, version and seven-day expiry. Prior customer names/IDs are redacted from retrieved lesson text. Revocation removes a lesson from retrieval and recipient screening and disables its associated safeguards. A model cannot publish, revoke or activate knowledge. A manual handoff discards automated inferences and clearly records that the analyst must inspect the saved facts.

## Demo and evaluation

Choose **Run simulation**, then open **Agent activity**. Each fresh scene starts with numbered residents and zero transactions. Payments arrive before a resident jumps, calls for help and files a scam report. A clickable tracker follows **Resolution agent → Human review → Prevention agent**. The full-width sections show the tool trail, validation checks, proposal and replay results. Knowledge cards link to the reviewed case and offer explicit revocation. Provider names, pricing and call accounting are omitted from the UI; original receipts and enforced limits remain on the server. The Agents page separates case handling, supporting roles and optional research.

Each fresh world automatically opens a spotlight guide. It follows the resident's report into **Report → Evidence → Agent → Review**, then highlights actual tool receipts, any specialist finding and judge checks as they arrive. **Pause/Play** controls playback; **Back** pauses it. Playback never starts a model, answers a customer question, approves a resolution or activates protection. Human decisions and explicit start/refresh actions remain manual. Close it with **Esc** or **Hide guide**, reopen it with **Guide demo**; a new world starts a new guide.

The UI watches the report before an investigation exists. Durable `fraud_case_preparation` records distinguish data publication, evidence freezing, dispatch and failures. The bounded five-minute watcher offers **Refresh status** if it stops; a failed or interrupted preparation is visible and never automatically retried. Test presentation logic with `node --test web/test_demo_guide.mjs`.

UI state, receipt and alarm checks: `node --test web/test_agent_ui.mjs web/test_demo_guide.mjs web/test_resident_alerts.mjs`. These use Node's built-in test runner; the static app still needs no build. New worlds use Resident 1–100; existing evidence and exported snapshots stay unchanged. The alarm animates briefly even when payments pause, stops off-screen, and becomes static under reduced motion.

```sh
uv run --locked python -B -m unittest discover -s web -p 'test_*.py'
uv run --locked python -B web/evaluate_harness.py
```

The offline report covers five reported scam mechanisms and five legitimate lookalikes. Fake choices exercise execution and final state; they do **not** measure Gemini accuracy. Some lookalikes deliberately end with a request for more information. Separate falsification tests cover wrong citations, model drift, unsupported recovery, forbidden secrets, restart/resume, budget exhaustion and revocation. Paid evaluation requires a separately bounded run within the existing allowance.

Limits remain **six calls/case including prevention, $0.05/case, $2/day, $8 lifetime model spend**, one paid call in flight, six-second spacing, no automatic retries and the existing data/query/export limits. Research scientist/validator jobs remain separate and bounded. No LLM runs per payment.
