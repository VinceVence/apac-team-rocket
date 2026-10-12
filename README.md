# MintTown

A local fintech simulation and fraud-resolution workbench. Residents transact in a pixel town; a customer report opens an investigation, an analyst reviews the findings, and approved cases become retrievable memory.

The investigation uses **Google ADK 2.11.0** with native function calls. **Live Gemini is off.** The default model is an explicitly labeled fake used to demonstrate and test branching, follow-up questions and budget enforcement. These tests establish the execution contract, not live AI accuracy.

## Run locally

Use Python 3.12.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r web/requirements-google.txt
MINTTOWN_LIVE=0 MINTTOWN_FRAUD_LIVE=0 .venv/bin/python -B web/server.py
```

Open http://localhost:3000. The UI has two channels: **Town** and **Scam desk**. DM Sans, the mint palette and original canvas pixel art are self-hosted.

## Demo

1. Start a scam demo from the town, then choose **Investigate**.
2. Inspect the ADK tool trail and submit an analyst review with a saved lesson.
3. Create a **Similar report**. The fake model chooses memory retrieval first, verifies the transfer and asks a targeted question.
4. Answer the question and continue. The same case budget survives the reply and the investigation proposes a resolution for review.
5. Use **More scenarios** for a benign payment. It takes a shorter tool path.

All transfers, recall requests and customer messages are simulated. No real money is moved. Only the operator can approve a case or publish memory.

## Programmatic verification

```sh
.venv/bin/python -B -m unittest discover -s web -p 'test_*.py'
.venv/bin/python -B web/simulate_adk.py
```

The HTTP rehearsal uses a temporary database, exercises the actual ADK runner and function tools, and forbids constructing a Gemini client. Its JSON report is written under `web/reports/`.

## Budget controls

- Up to **6 model generations per case**, including follow-ups and re-investigations.
- **$0.02 per case**, **$0.10 per UTC day**, **$1 lifetime** and **10 calls per UTC day** by default.
- Reserve **$0.01 before a generation**, then reconcile reported input, output and reasoning tokens. Ambiguous failures retain their reservation.
- Fake calls use a separate simulated-spend ledger; actual API cost remains zero. The HTTP rehearsal raises only its isolated fake call-count allowance to exercise all examples.
- Invalid tools, out-of-scope accounts, fabricated citations, stale evidence and repeated requests cannot bypass the server checks. A stopped run can be handed to the analyst explicitly.

The local application assumes one server process owns its SQLite database. A distributed deployment needs database-level atomic reservations across service instances.

## Gemini integration

The guarded Vertex AI adapter targets `gemini-3.5-flash-lite`. It remains disabled unless the server is explicitly configured with **both** `MINTTOWN_LIVE=1` and `MINTTOWN_FRAUD_LIVE=1`, a `GOOGLE_CLOUD_PROJECT`, supported `GOOGLE_CLOUD_LOCATION` (default `global`), and Application Default Credentials. The UI currently creates fake-mode investigations. No credentials belong in browser code or committed files.

Live model behavior, endpoint access and real token consumption still require an explicitly enabled evaluation. No fine-tuning, external MCP service or paid cloud deployment is required for the local demo.

See [the investigation implementation](web/fraud_agent.py), [ADK adapter and fake model](web/fraud_adk.py), and [tests](web/test_fraud_agent.py).
