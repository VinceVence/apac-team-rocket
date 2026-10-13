# Agent roles and extension guide

## What is active

**Resolution agent:** `fraud_agent.py` and `fraud_adk.py`. Gemini chooses one native function call per turn. The next turn receives actual observations, remaining case allowance, the complaint and any customer reply. A final proposal includes evidence IDs, uncertainties, a customer-facing draft, a case-specific lesson and a future follow-up question.

| Tool | Allowed work |
|---|---|
| `get_transactions` | Verify only disputed IDs belonging to this customer |
| `get_customer_features` | Query this customer's pinned BigQuery feature snapshot |
| `run_fraud_detectors` | Run selected registered detectors on frozen disputed payments; report availability and version |
| `compare_behavior` | Compare bounded historical spending in frozen ledger evidence |
| `trace_recipient` | Read bounded transfers to a recipient already in the case |
| `search_reviewed_cases` | Retrieve at most three approved memories |
| `train_behavior_model` | Train/reuse a bounded, advisory local model from BigQuery features |
| `get_complaint_guidance` | Read curated Philippine routing and evidence guidance |
| `ask_customer` | Ask one useful question and pause |
| `submit_for_review` | Propose a resolution and lesson; cannot approve or move funds |

Reading disputed transactions is required before submission. When the warehouse is enabled, BigQuery customer features are required too. These are evidence prerequisites; the remaining path and whether a model is useful are Gemini's decisions. Valid tool order need not be identical across cases. Completed one-time checks disappear from the model's next tool menu; tools with unmet evidence prerequisites are withheld. The server still validates every returned call.

**Guided investigation:** disputed transactions, a pinned customer feature query when BigQuery is enabled, and detector evidence are prerequisites for submission. Gemini chooses the detector IDs, order of other tools, follow-up question and resolution. The guided example deliberately creates conflicting evidence: a known device and recorded authorization alongside a deceptive safe-account request. Authorization alone does not establish informed intent.

## Prevention agent and payment gate

`prevention.py` receives an immutable artifact only after an analyst confirms the case and publishes knowledge. Through the same ADK adapter, Gemini chooses `propose_prevention_rule` or `decline_prevention_rule`. It has one remaining call from the **same six-call case allowance**, not a separate budget.

A proposal selects 2–4 allowlisted prepayment signals that must all match. It cannot generate executable code, SQL, a new recipient watchlist or a permanent ban. The server replays the source with a changed recipient and 20 legitimate controls. A failed replay is rejected. A passed replay still requires **Enable safeguard** from the analyst. Each rule records the reviewed source, version, provenance, replay, activation state and seven-day expiry.

```mermaid
flowchart LR
    Resolution[Resolution agent proposal] --> Human[Human case approval]
    Human --> Artifact[Frozen reviewed case + memory]
    Artifact --> Learner[Gemini prevention learner: one call]
    Learner --> Candidate[Typed signal rule or decline]
    Candidate --> Replay[Changed recipient + legitimate controls]
    Replay --> Gate[Human activation]
    Gate --> Serving[Local payment check before debit]
    Serving --> Hold[Request verification with rule receipt]
```

The payment gate evaluates active rules locally alongside the existing exact-recipient watch. It makes no Gemini call per transaction. General matches hold the simulated transfer for verification before ledger posting. Real device-edge infrastructure is not deployed; the gate currently runs inside the Cloud Run payment simulator.

Neither agent may approve its own output, decide legal fault, promise recovery or treat demographics/sentiment as proof. Prior knowledge is a lead to verify. The public timeline shows concise decision purposes, evidence, tool validation and results—not private chain of thought.

## Detector registry

`fraud_detectors.py` exposes device integrity, payment velocity and payment-request intent. They are **versioned rule detectors**, not trained or calibrated fraud probabilities. Missing inputs are reported as unavailable. Scores describe matched signals only. Detectors read prepayment metadata, not later complaints, hidden scenario labels or future case outcomes.

The optional `train_behavior_model` tool fits a small real k-means model from BigQuery features. Its distance is an anomaly score, not a fraud diagnosis. A bank's existing validated classifier can replace/add a registry adapter with a fixed input schema, model version, missing-data rules and evaluation evidence; no extra conversational agent is necessary.

## Add a tool

1. Implement a small scoped operation in a dedicated module, following `warehouse.py` or `complaint_guidance.py`. Use case-derived customer IDs, fixed queries and explicit limits. Never accept arbitrary SQL or code from the model.
2. Add the function to `fraud_adk.tools_for`, its name to `TOOLS`, and the exact argument set to `ARG_FIELDS`.
3. Validate the operation in `FraudAgent.tool`; record its source references and public finding. Keep large datasets out of model context.
4. Bump the prompt/tool contract when its meaning changes. Old traces remain intact and case spending never resets.
5. Exercise the tool with an injected fake choice, then evaluate a small live sample through the shared ledger.

## Add another agent

Use the existing shared meter and worker. Prevention demonstrates a distinct role, a typed reviewed-case handoff and role-specific tools without an unbounded agent conversation. Extend only when a new decision boundary needs its own tool contract. Test changed recipients, legitimate lookalikes, missing evidence, stale approvals, exhausted allowance and provider failure. See [research](research.md) for the original design sources and [evaluation](evaluation.md) for measured coverage.
