# Application map

Use the [root README](../README.md) for startup and the [help index](../docs/README.md) for architecture, research and extension guidance.

| Responsibility | Files |
|---|---|
| HTTP boundary and local Vertex launcher | `server.py`, `local_vertex.py` |
| Shared limits and paid-call accounting | `settings.py`, `agents.py`, `fraud_agent.py`, `demo_guard.py` |
| Native ADK model/tool adapter | `fraud_adk.py` |
| Shared worker for resolution, prevention and research | `fraud_runner.py` |
| Curated corpus, scientist/validator roles and fixed CPU recipes | `risk_lab.py`, `risk_models.py` |
| Reviewed-case learning, replay and local payment safeguards | `prevention.py` |
| Registered versioned evidence detectors | `fraud_detectors.py` |
| Fresh scenes, private archives and persistent accounting | `demo_reset.py` |
| Complaints, analyst decisions, approved knowledge | `fraud_desk.py` |
| Five realistic scenario families and controls | `fraud_scenarios.py` |
| Philippine complaint-routing checklist | `complaint_guidance.py` |
| Environment and ledger | `world_demo.py`, `world.py`, `lab.py` |
| AE dictionary projections, validation, export and isolated BigQuery mirror | `environment_data.py`, `environment_cloud.py`, `export_environment.py` |
| Typed BigQuery tables and bounded CPU model | `warehouse.py` |
| Durable shared checkpoint and legacy batch export | `cloud_data.py` |
| End-to-end evaluation and regression tests | `evaluate_cases.py`, `test_*.py` |
| Three-tab UI and original pixel art | `dist/` |

The earlier macroeconomics, marketing and model-release modules remain for historical compatibility and regression checks. The active Vertex workflow does not start their training or paid agents. A few offline legacy tests explicitly retain their older 240-person fixture; the current simulator/warehouse cap is 100.

## Main API

| Endpoint | Behavior |
|---|---|
| `GET /api/state` | Environment, current allowance and warehouse publication |
| `GET /api/environment-data` | Six dictionary-shaped table previews and joined ledger, with private fields removed |
| `GET /api/cloud` | Persistence, warehouse and query/publication limits |
| `GET /api/fraud-desk` | Cases, scenario catalogue, runtime and approved memory |
| `GET /api/fraud-desk/reports/{id}` | Complaint, frozen evidence, selected tools, proposed resolution |
| `GET /api/risk-lab` | Public corpus summaries and saved model experiments |
| `GET /api/risk-lab/studies/{id}` | Frozen experiment, agent trail, actual metrics and verdict |
| `POST /api/risk-lab/seed` | Operator-only explicit synthetic benchmark load |
| `POST /api/risk-lab/curate` | Operator-only verified label from a resolved case |
| `POST /api/risk-lab/start` | Operator-only bounded fake or Gemini study; no model activation |
| `POST /api/world/start` | Start a fresh guided scene by default with `expected_run`, `activity`, `speed`; `fresh:false` retains the legacy evaluation episode |
| `POST /api/world/prove` | Test an active safeguard against a changed recipient and a legitimate payment; no model call |
| `POST /api/prevention/learn` | Queue one reviewed-case learner using the source case allowance |
| `POST /api/prevention/activate` | Human enable/disable of a replay-passed, unexpired safeguard |
| `POST /api/world/stop` | Pause that episode; a stale request cannot stop a newer one |
| `POST /api/fraud-desk/demo` | Create/reuse a scenario report; `.control` selects its legitimate lookalike |
| `POST /api/fraud-desk/report` | Record a customer narrative against existing customer-owned payments |
| `POST /api/fraud-agent/start` | Publish required data, freeze evidence and queue an investigation |
| `POST /api/fraud-desk/reply` | Append a reply and continue within the same case allowance |
| `POST /api/fraud-desk/review` | Analyst decision, simulated service receipt and optional memory publication |
| `POST /api/cloud/export` | Publish/reuse the current typed snapshot when warehouse mode is enabled |

Mutation requests require the same-origin session token. The model cannot call approval, billing, arbitrary SQL, deployment or bank-action APIs. Add tools through the [extension guide](../docs/agents.md), not by bypassing `FraudAgent.reserve`.

### Town renderer

`dist/town-art.js` draws the original river-town scenery once into a cached canvas. `dist/town.js` routes residents along streets, displays real payment/report events, and supports resident picking and reduced motion. These visuals do not change data generation or invoke a model.

Run `node web/test_town.mjs` from the repository root for street routing, animation lifecycle, picking and reduced-motion checks. Use the fake model for visual playtests.

The [harness runtime](../docs/harness-runtime.md) documents new-case specialist delegation, model contracts, local judges and reviewed-knowledge lifecycle. `evaluate_harness.py` runs the ten-fixture offline execution report.
