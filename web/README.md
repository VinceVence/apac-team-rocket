# Application map

Use the [root README](../README.md) for startup and the [help index](../docs/README.md) for architecture, research and extension guidance.

| Responsibility | Files |
|---|---|
| HTTP boundary and local Vertex launcher | `server.py`, `local_vertex.py` |
| Shared limits and paid-call accounting | `settings.py`, `agents.py`, `fraud_agent.py`, `demo_guard.py` |
| Native ADK model/tool adapter | `fraud_adk.py` |
| One bounded background investigator | `fraud_runner.py` |
| Complaints, analyst decisions, approved knowledge | `fraud_desk.py` |
| Five realistic scenario families and controls | `fraud_scenarios.py` |
| Philippine complaint-routing checklist | `complaint_guidance.py` |
| Environment and ledger | `world_demo.py`, `world.py`, `lab.py` |
| Typed BigQuery tables and bounded CPU model | `warehouse.py` |
| Durable shared checkpoint and legacy batch export | `cloud_data.py` |
| End-to-end evaluation and regression tests | `evaluate_cases.py`, `test_*.py` |
| Three-tab UI and original pixel art | `dist/` |

The earlier macroeconomics, marketing and model-release modules remain for historical compatibility and regression checks. The active Vertex workflow does not start their training or paid agents. A few offline legacy tests explicitly retain their older 240-person fixture; the current simulator/warehouse cap is 100.

## Main API

| Endpoint | Behavior |
|---|---|
| `GET /api/state` | Environment, current allowance and warehouse publication |
| `GET /api/cloud` | Persistence, warehouse and query/publication limits |
| `GET /api/fraud-desk` | Cases, scenario catalogue, runtime and approved memory |
| `GET /api/fraud-desk/reports/{id}` | Complaint, frozen evidence, selected tools, proposed resolution |
| `POST /api/world/start` | Start/reuse a bounded episode with `expected_run`, `activity`, `speed` |
| `POST /api/world/stop` | Pause that episode; a stale request cannot stop a newer one |
| `POST /api/fraud-desk/demo` | Create/reuse a scenario report; `.control` selects its legitimate lookalike |
| `POST /api/fraud-desk/report` | Record a customer narrative against existing customer-owned payments |
| `POST /api/fraud-agent/start` | Publish required data, freeze evidence and queue an investigation |
| `POST /api/fraud-desk/reply` | Append a reply and continue within the same case allowance |
| `POST /api/fraud-desk/review` | Analyst decision, simulated service receipt and optional memory publication |
| `POST /api/cloud/export` | Publish/reuse the current typed snapshot when warehouse mode is enabled |

Mutation requests require the same-origin session token. The model cannot call approval, billing, arbitrary SQL, deployment or bank-action APIs. Add tools through the [extension guide](../docs/agents.md), not by bypassing `FraudAgent.reserve`.
