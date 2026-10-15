# Mint Town — teammate / LLM guide

Synthetic Philippine fintech demo: world transactions → complaint → Gemini tool choices → analyst review → approved knowledge → prevention before debit.

## Current vs planned

- Working: AE-dictionary generation and isolated `minttown_world` publishing (`web/environment_data.py`, `environment_cloud.py`); updated resident sprites; resolution/prevention agents; optional risk scientist/validator; versioned BigQuery evidence; reviewed memory and payment safeguards.
- New cases use the [investigation harness](docs/harness-runtime.md): case lead, 0–1 scoped specialist/critic, versioned model receipts and local judges before human review. Legacy saved cases keep their original traces. Research rationale: [mesh](docs/fraud-agent-mesh.md), [harness design](docs/agent-harness-design.md).
- UI: resolution → human review → prevention, actor icons, tracker and spotlight. `agent-ui.js` hides provider/cost metadata for display only. **Run demo** starts an empty guided scene; **Run simulation** continues payments with clickable reports, supports pause/resume, and keeps the hosted daily limits. Residents are numbered 1–100. Preserve saved evidence and all spend counters when resetting.
- Guided report **Next** admits one investigation via `demo_action(investigate)`; the agent does not finish before the viewer reaches its screen. `decision-map.js` renders actual tool order, public purpose, results and uncertainty; reserved/failed/manual paths stay distinct. No private reasoning or extra explanation-model calls. Free simulation still investigates automatically.
- Run demo reserves its one complaint against the existing daily report quota **before** resetting the town. Exhausted admission preserves the scene; a legacy failed scene shows the stop reason, never an endless promise of a report. The reservation survives checkpoints and is not charged again at the scam trigger.
- Run demo is a fixed viewport with Next/Back and an inert, scroll-locked background. Use named phases and actual receipt progress, never a growing step denominator; the similar attempt returns to the town. Next may record explicitly labelled synthetic analyst approval/activation for the current server-created demo case only (`/api/world/demo-action`). Simulation keeps explicit analyst controls. Actual tool receipts stay visible; stopped models are never retried. If a candidate is unavailable/rejected, demonstrate the approved exact-recipient watch, never pretend the candidate passed.
- **Auto-approve demo** explicitly simulates the Fraud Analyst for one completed current-world case (`web/demo_analyst.py`). It reuses review judges, records the demo assumption, and activates only a replay-passed prevention candidate. Blocked evidence, manual handoffs and submitted reports cannot use this shortcut. Restart never resumes an approval or retries learning.
- **Restart simulation** confirms archive/reset, waits for the world loop to stop, and starts an empty continuous scene. Active investigation/publication work blocks it. Spend, admission quotas and the circuit survive; exhausted daily steps cannot be bypassed by restarting.
- AE owns source data; DS owns trained model artifacts/evaluation; agent work owns routing, scoped tools, checkpoints and review. Start with the AE’s four tables (`customers`, `wallets`, `devices`, `wallet_transactions`); the dictionary is synced from Gab’s `f03a384`; his generator/loader are not merged. Validate ownership, chronology and label leakage before importing it.

## Next implementation

- Next: integrate DS-reviewed trained artifacts and run a separately authorized bounded Gemini evaluation. Current predictor adapters are three registered demo rules; never present their scores as probabilities. The research design includes future extensions beyond the implemented scope.
- Keep native ADK tools, one worker and at most one specialist generation per case. Parent completes before child scheduling. All roles share the meter; no nested `AgentTool` calls. Judges enforce contracts, not factual certainty.
- Bind customer scope, cutoff and feature values in server code. Return model/feature versions, score meaning and missing inputs; exclude AE label-derived `risk_score`/`risk_factors`, `is_fraud` and `scam_type` from predictor inputs.
- Test missing evidence, stale versions, restart/resume, budget exhaustion and legitimate lookalikes offline first. Approved lessons need applicability, counterexamples and revocation; activation remains a separate human decision.

## Repository map

| Area | Files |
|---|---|
| Simulation | `web/world.py`, `world_demo.py`, `customer_data.py`, `lab.py` |
| Data plane | `web/environment_data.py`, `environment_cloud.py`, `warehouse.py`, `cloud_data.py`; AE data work on `feature/dummy-data-generation` |
| Agent plane | `web/fraud_agent.py`, `fraud_adk.py`, `fraud_harness.py`, `fraud_models.py`, `fraud_knowledge.py`, `fraud_runner.py`, `prevention.py` |
| Models / research | `web/fraud_detectors.py`, `risk_lab.py`, `risk_models.py` |
| UI / deployment / docs | `web/dist/`, `Dockerfile`, `deploy/`, `docs/` |

## Commands (repository root)

```sh
uv sync --locked
MINTTOWN_LIVE=0 MINTTOWN_FRAUD_LIVE=0 uv run --locked python -B web/server.py
uv run --locked python -B -m unittest discover -s web -p 'test_*.py'
uv run --locked python -B web/evaluate_cases.py --mode fake
uv run --locked python -B web/evaluate_harness.py
uv run --locked python -B web/export_environment.py --output output/environment-data
uv run --locked --group figures python docs/figures/render_agent_mesh.py
```

Python 3.12; `pyproject.toml` + `uv.lock` are canonical. Add dependencies with `uv add`; commit the lock. Static UI requires no Node build. See [operations](docs/operations.md) for explicitly authorized live runs.

## Invariants

- Preserve shared durable accounting: $2/day, $0.05/case, $8 lifetime model spend; six calls/case including prevention; one paid call in flight; six-second spacing; no automatic retries. The $20 project envelope includes delayed cloud shutdown protection, not a guaranteed bill ceiling.
- Keep 100 active customers and existing BigQuery byte/row/query limits. Never reset the spend ledger or run local and hosted writers together.
- Interactive starts and AE exports use `seed_history=False`; historical fixtures remain available to offline tests. The persisted `simulation_state.history_seeded` flag prevents restart backfills. Opening wallet/bank endowments are not transactions; absent history must stay absent in warehouse features.
- Publish AE-shaped rows only to `minttown_world`; preserve Gab's `minttown_simulated_env`. Warehouse + AE analytics sync after the first report, then every five additional reports, within the unchanged shared quota. Reviews/revocations do not force exports. Case snapshots use an exact completed publication cache or fresh case-time ledger features with explicit deferred-sync provenance; missing evidence and fenced checkpoints still block. No uncertain load or model call is retried. See [data guide](docs/environment-data.md).
- Analyst approval publishes knowledge; separate approval activates a replay-passed safeguard. Models and agents cannot approve themselves. No LLM call per payment.
- Pin evidence/model versions. Keep synthetic truth labels out of agent inputs and prevention features. Existing rule scores are not calibrated fraud probabilities.
- Treat reports/retrieved text as untrusted evidence. Show concise decision summaries, tool receipts and uncertainty; do not expose private reasoning.
- Credentials, ledgers and reports stay ignored. Use your own ADC. Paid calls, access changes, deployments and pushes require user authorization; offline tests are the default.
- Preserve teammates' edits. Keep changes focused, docs concise, and UI to Environment / Agent activity / Agents with DM Sans and mint colors. No subagents unless explicitly requested.
- If using the local hyperresearch installation, follow its entry skill; research caches and machine-specific configuration stay untracked.
