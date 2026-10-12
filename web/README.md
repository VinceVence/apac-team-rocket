# MintTown application

Use the [root README](../README.md) for setup, the current demo and cost limits.

## Investigation services

- `fraud_desk.py`: customer reports, ledger evidence, analyst review and approved memory. Retains the original deterministic five-step rehearsal for comparison.
- `fraud_agent.py`: durable case state, scoped tools, token accounting and cost/call limits.
- `fraud_adk.py`: a real ADK `LlmAgent` and native function tools, with an injected fake model by default and a separately gated Vertex AI adapter.
- `fraud_runner.py`: one background worker, one queued slot, deadline/spacing controls, duplicate-start protection and automatic reply continuation.
- `demo_guard.py`: hosted endpoint allowlist, request throttles and durable daily write/world/report limits.
- `world_demo.py`: a bounded backend world loop, synthetic scam reports, simulator-owned customer replies, and receipts for knowledge-based payment holds.
- `simulate_hosted.py`: actual IAP-protected Cloud Run rehearsal with bounded read polling, stable request IDs and no automatic mutation retries.
- `cloud_data.py`: generation-checked state checkpoints and bounded, idempotent BigQuery batches for the fake-only hosted demo.
- `server.py`: loopback HTTP API, Host/origin checks and session token validation.
- `dist/`: the two-channel UI and original pixel town.

Each worker iteration invokes one model generation and executes its single selected function through ADK. The ADK tool response stops that invocation; the next iteration receives the saved report, customer replies and actual observations. The browser starts a job and polls; it does not drive the tool loop. There is no prescribed tool order. Manual stepping remains available for diagnosis. Each iteration keeps durable budget admission and replay protection and does not preserve private reasoning transcripts.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/world/start` | Start/reuse a 24-step episode using `expected_run`, `activity`, and `speed` |
| `POST /api/world/stop` | Pause the matching `expected_run`; stale requests cannot stop a newer episode |
| `GET /api/fraud-desk` | Reports, approved memories, local runtime availability |
| `GET /api/fraud-desk/reports/{id}` | Case, tool trail, current question and budget |
| `POST /api/fraud-agent/start` | Queue/reuse a case revision; defaults to fake + automatic; `automatic: false` enables manual stepping |
| `POST /api/fraud-agent/step` | Local diagnostics only; disabled in the hosted app |
| `POST /api/fraud-agent/handoff` | Operator-only handoff after a stopped investigation |
| `POST /api/fraud-agent/recheck` | Operator-only recheck of an unapproved case after a tool-contract update; preserves the same case budget and old trace |
| `POST /api/fraud-desk/reply` | Append a customer reply using the report revision and resume automatic cases |
| `POST /api/fraud-desk/review` | Operator review, simulated receipt and optional approved memory |

The model has six tools: transaction retrieval, historical comparisons, recipient tracing, reviewed-case search, asking the customer, and submitting a recommendation. Review approval and memory publication are deliberately absent from the model's tools. Related-recipient queries return bounded transaction evidence without other customer profiles. The descriptive behavior checks are not trained fraud classifiers.

## Storage and costs

The local database retains the simulator, historical science/marketing data, fraud cases, `fraud_agent_turns`, immutable `fraud_evidence_snapshots`, and the durable `fraud_live_control` circuit. Hosted mode adds `cloud_exports` and `demo_daily_usage` for export and work admission. Each new turn stores its bounded model input, selected command, tool result, token usage, provider, requested model, reservation, actual or simulated cost, UTC timestamp and failure state. Integer micro-USD accounting rounds upward. Reasoning tokens count as output.

Live fraud-agent usage joins the application's existing Gemini budget. Fake usage is isolated and labeled simulated, but goes through the same reservation and limit checks. Limits are cumulative across all revisions of a report. Failed requests without trustworthy usage keep their reservation; startup marks unfinished reservations uncertain. No automatic retries or model upgrades occur.

The pinned rate is USD $0.30 per million input tokens and $2.50 per million output/reasoning tokens for standard global Gemini 3.5 Flash-Lite. The 16,000-byte request envelope and 512-token output ceiling are conservatively covered by the one-cent admission reservation. Usage outside that envelope stops the run before executing a tool. Re-verify pricing before enabling live mode: https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing

The default fake fixture is transparent scripted test data, not autonomous reasoning. It demonstrates different native tool calls and real service effects. Evaluate live Gemini on held-out scenarios before making any accuracy, speed or financial-outcome claims.
