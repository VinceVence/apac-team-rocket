# MintTown application

Use the [root README](../README.md) for setup, the current demo and cost limits.

## Investigation services

- `fraud_desk.py`: customer reports, ledger evidence, analyst review and approved memory. Retains the original deterministic five-step rehearsal for comparison.
- `fraud_agent.py`: durable case state, scoped tools, token accounting and cost/call limits.
- `fraud_adk.py`: a real ADK `LlmAgent` and native function tools, with an injected fake model by default and a separately gated Vertex AI adapter.
- `server.py`: loopback HTTP API, Host/origin checks and session token validation.
- `dist/`: the two-channel UI and original pixel town.

One HTTP step invokes one model generation and executes its single selected function through ADK. The ADK tool response stops that invocation; the next generation receives the saved report, customer replies and actual observations. There is no prescribed tool order. This explicit per-turn boundary supports the UI's step control and makes budget admission and replay protection durable. It does not preserve private reasoning transcripts.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/fraud-desk` | Reports, approved memories, local runtime availability |
| `GET /api/fraud-desk/reports/{id}` | Case, tool trail, current question and budget |
| `POST /api/fraud-agent/start` | Start/reuse a case revision; defaults to fake mode |
| `POST /api/fraud-agent/step` | Execute one generation with an expected-step guard |
| `POST /api/fraud-agent/handoff` | Operator-only handoff after a stopped investigation |
| `POST /api/fraud-desk/reply` | Append a customer reply using the report revision |
| `POST /api/fraud-desk/review` | Operator review, simulated receipt and optional approved memory |

The model has six tools: transaction retrieval, historical comparisons, recipient tracing, reviewed-case search, asking the customer, and submitting a recommendation. Review approval and memory publication are deliberately absent from the model's tools. Related-recipient queries return bounded transaction evidence without other customer profiles. The descriptive behavior checks are not trained fraud classifiers.

## Storage and costs

The 35-table local database retains the existing simulator, historical science/marketing data, fraud cases and `fraud_agent_turns`. Each new turn stores its bounded model input, selected command, tool result, token usage, provider, requested model, reservation, actual or simulated cost, UTC timestamp and failure state. Integer micro-USD accounting rounds upward. Reasoning tokens count as output.

Live fraud-agent usage joins the application's existing Gemini budget. Fake usage is isolated and labeled simulated, but goes through the same reservation and limit checks. Limits are cumulative across all revisions of a report. Failed requests without trustworthy usage keep their reservation; startup marks unfinished reservations uncertain. No automatic retries or model upgrades occur.

The pinned rate is USD $0.30 per million input tokens and $2.50 per million output/reasoning tokens for standard global Gemini 3.5 Flash-Lite. The 16,000-byte request envelope and 512-token output ceiling are conservatively covered by the one-cent admission reservation. Usage outside that envelope stops the run before executing a tool. Re-verify pricing before enabling live mode: https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing

The default fake fixture is transparent scripted test data, not autonomous reasoning. It demonstrates different native tool calls and real service effects. Evaluate live Gemini on held-out scenarios before making any accuracy, speed or financial-outcome claims.
