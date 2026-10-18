<p align="center">
  <img src="docs/figures/resolution-agent.svg" width="96" alt="Resolution Agent logo">
</p>

<h1 align="center">Resolution Agent</h1>

<p align="center">
  <strong>Customer complaint in. A resolution ready for human review.</strong>
</p>

<p align="center">
  An agent that investigates fraud complaints, prepares a resolution,<br>
  and turns approved lessons into protection for the next payment.
</p>

<p align="center">
  <a href="https://minttown-1040017899050.us-central1.run.app/"><strong>Explore the demo ↗</strong></a>
  &nbsp; · &nbsp;
  <a href="#architecture">Architecture</a>
  &nbsp; · &nbsp;
  <a href="#quick-start">Quick start</a>
  &nbsp; · &nbsp;
  <a href="docs/README.md">Documentation</a>
</p>

<p align="center">
  <sub>Google ADK &nbsp; · &nbsp; Gemini on Vertex AI &nbsp; · &nbsp; BigQuery &nbsp; · &nbsp; Cloud Run</sub>
</p>

<br>

<p align="center">
  <img src="docs/figures/mint-town-world-current.png" width="820" alt="Residents transact in Mint Town as a customer reports a scam">
</p>

<p align="center">
  <sub>Mint Town is the simulated environment. Resolution Agent is the product.</sub>
</p>

<br>

<table>
  <tr>
    <td width="33%" align="center"><strong>01 · Investigate</strong><br><br>Connect the complaint to evidence<br>and relevant model tools.</td>
    <td width="34%" align="center"><strong>02 · Resolve</strong><br><br>Prepare the next action<br>for the Fraud Analyst to verify.</td>
    <td width="33%" align="center"><strong>03 · Prevent</strong><br><br>Use approved lessons to check<br>similar attempts before debit.</td>
  </tr>
</table>

## Experience the workflow

Open the prototype, click **Start here**, and follow the quick tour.

| Run demo | Start simulation |
|---|---|
| A **Next / Back** walkthrough of a completed investigation: complaint, evidence, classifier, resolution, analyst review and prevention. | An active world with up to **100 residents**, new payments, scam reports and agent investigations. |
| Browser-only, with no new model calls or API mutations. | Opens **paused and empty**. Only your explicit start generates activity. Cost and safety controls remain active. |

The later scam uses a **different recipient**. An approved safeguard holds it before debit while a legitimate payment proceeds. Restarting the world preserves spending and safety counters.

[Read the demo script →](docs/demo-script.md)

## Architecture

<p align="center">
  <img src="docs/figures/mint-town-investigation-harness.png" width="960" alt="Simulation, data and agent planes with evidence tools, human review and prevention">
</p>

The case lead chooses what to investigate and can request one scoped specialist or critic. Shared checkpoints preserve evidence, model receipts, reviewed knowledge and cost accounting. The payment gate applies active safeguards locally, with **no LLM call per payment**.

<details>
<summary><strong>Explore the components</strong></summary>

| Component | Responsibility |
|---|---|
| Mint Town | Residents generate wallet transactions and complaint events. |
| Data plane | BigQuery stores AE-shaped tables; trusted code freezes customer-scoped evidence at the case cutoff. |
| Resolution Agent | Gemini on Vertex AI and Google ADK choose tools, ask for missing information and draft a cited resolution. |
| Harness and analyst | Local checks validate contracts and references. The human analyst owns approval. |
| Prevention Agent | Tests candidate safeguards against scams and legitimate lookalikes before separate human activation. |
| Payment gate | Applies active safeguards locally before debit. |

A separate scientist/refiner/validator workflow produces advisory model candidates. It does not silently deploy them into payment decisions.

</details>

[Editable diagrams](docs/fraud-agent-mesh.md) · [Learning loops and research](docs/learning-loops.md) · [Model tool contract](docs/model-artifacts.md)

## Quick start

Python **3.12** and [uv](https://docs.astral.sh/uv/getting-started/installation/) are required. The static web interface needs no frontend build.

```sh
uv sync --locked
MINTTOWN_LIVE=0 MINTTOWN_FRAUD_LIVE=0 uv run --locked python -B web/server.py
```

Open **http://localhost:3000/**. Offline investigations use an explicit fake model to exercise tool contracts. For real Vertex AI calls, follow [operations](docs/operations.md) with your own ADC and the shared allowance. Never run local and hosted writers against the shared ledger together.

## Build and extend

<details>
<summary><strong>Data and model contributions</strong></summary>

Gab's [dictionary and data tools](data/README.md) define `customers`, `wallets`, `devices` and `wallet_transactions`. Generation is repeatable and capped at 100 residents. Validation is offline by default. Explicit imports can only fill empty, owned simulator tables; the AE's `minttown_simulated_env` stays protected.

Karlo's [ledger classifier](docs/ledger-model.md) is available through `score_models`. The integration preserves frozen temporal features, bounded exports, JSON inference parity and versioned receipts. Its measured recall is low: a low score cannot clear a complaint. Labels, demographics and label-derived risk scores are excluded from predictor inputs.

</details>

<details>
<summary><strong>Evaluation evidence and prototype boundaries</strong></summary>

- A saved live Gemini case selected the ledger classifier and proposed a resolution. Its reviewed prevention rule held a changed-recipient attempt with zero debit.
- An **offline synthetic** replay held **34/50** scam attempts and allowed **50/50** legitimate controls. These are test-bank results, not production fraud accuracy.
- Residents, payments and bank actions are simulated. Production resolution-time savings, real bank recovery and device-edge deployment remain unvalidated.

[Live results](docs/visual-demo.md) · [Evaluation scope](docs/evaluation.md) · [Model limitations](docs/ledger-model.md). Earlier failures remain documented.

</details>

<details>
<summary><strong>Cost controls and security</strong></summary>

Shared model limits: **$2/day, $0.05/case, $8 lifetime, six calls/case**, one paid call in flight, six-second spacing and no automatic retries. Restarts preserve accounting. BigQuery retains row, byte and scan caps. The $20 project envelope uses delayed shutdown protection, not a guaranteed final-bill ceiling.

Credentials, raw exports, local ledgers and rendered video/audio stay out of Git. CI scans history for credential patterns and runs offline checks. See [SECURITY.md](SECURITY.md), the [release audit](docs/release-audit.md) and [hosting controls](docs/hosting.md).

</details>

<details>
<summary><strong>Development checks and repository map</strong></summary>

```sh
uv run --locked python -B -m unittest discover -s web -p 'test_*.py'
node --test web/test_*.mjs
uv run --locked python -B web/evaluate_harness.py
uv run --locked python -B web/evaluate_cases.py --mode fake
```

| Area | Entry point |
|---|---|
| Simulator, app and agents | [web/README.md](web/README.md) |
| AE data tools | [data/README.md](data/README.md) |
| Deployment | `Dockerfile`, `deploy/`, `scripts/` |
| Editable video source | [demo-video/README.md](demo-video/README.md) |
| Guides and diagrams | [docs/README.md](docs/README.md) |

Use `uv add` and commit `pyproject.toml` with `uv.lock`. Read [AGENTS.md](AGENTS.md) before changing permissions, evidence handling or shared accounting.

</details>

<br>

<p align="center">
  <strong>Team Rocket</strong><br>
  AI Builder Cup · BFSI<br>
  <sub>Team leader: Lanz Vincent Vencer</sub>
</p>
