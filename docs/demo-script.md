# Mint Town — 3-minute guided demo

Use the public app's **Environment**, **Agent activity**, and **Agents** tabs. The guided case starts its investigator only when you click Next from the customer report. Saved timelines and the payment proof can be shown without new model calls. Starting a new world or approving a case with a remaining learner call can consume the shared allowance.

## 0:00–0:30 — Run demo

Click **Run demo** (4× speed is useful). A fresh scene begins with 100 numbered residents and zero transactions. Point to purchases and transfers, then the orange **!** above the victim. Use **Next** to move the spotlight through the report and actual recorded agent actions. Each explanation stays on screen until you choose to continue; **Back** revisits the previous step.

> A customer has received a deceptive payment request, transferred money, and filed a complaint. The guided world pauses here so we can follow the investigation. Its evidence is captured in versioned snapshots, and analytics is batched to the isolated BigQuery dataset without blocking investigation when its quota is exhausted.

For free exploration, use the separate **Run simulation** button: payments keep flowing, clickable report widgets open investigations, and **Pause / Resume simulation** preserves the same world. Green shield alerts and **Scams stopped** show real recorded holds and link to their reviewed source cases. Both modes retain the existing safety limits.

## 0:30–1:25 — Watch the resolution agent

Click **Next** from the report to start the agent. Watch the decision map: agent → chosen tool → recorded result → agent. Next reviews each recorded choice at your pace; it never substitutes a scripted route. The right panel shows the agent’s public purpose from its tool call, while the map shows returned evidence and unresolved facts. This is a decision trail, not private chain-of-thought.

> Gemini chooses the next tool through Google ADK. We record its purpose, validate the tool and arguments, and show the actual result. The device check can look normal while the payment message contains strong scam signals. A recorded authorization is not the same as informed intent.
>
> The agent combines the complaint, this customer's transaction evidence and frozen behavior features. It can trace a recipient, compare behavior, choose registered signal checks, retrieve reviewed cases, or ask a follow-up question. We only claim the choices visible in this saved trace.

The registered detector scores are rule signals, not calibrated fraud probabilities. A fake-model rehearsal is explicitly labelled and must not be presented as Gemini.

## 1:25–1:55 — Analyst review

Read the expected resolution, evidence and uncertainty. Click **Next**. The guided demo assumes the synthetic risk analyst has approved the case; the server records this as a demo assumption. Normal simulation still requires explicit analyst review.

> The agent recommends; this demo assumes the synthetic risk analyst verified the case. Approval publishes the reviewed case. This is a synthetic recall request, not a promise that money has been recovered.

The prevention learner may consume one remaining model call from the same six-call allowance.

## 1:55–2:25 — Learn a safeguard

Show the prevention signals and replay results. Click **Next** to apply the assumed demo activation. If the live candidate is unavailable or rejected, Next offers the labelled saved Gemini walkthrough; it does not activate the rejected candidate.

> A second role converts the approved resolution into a narrow, versioned safeguard. It can also decline. The proposal must catch the changed-recipient example and avoid the legitimate replay controls, then a human decides whether to activate it. These are synthetic checks, not production accuracy measurements.

## 2:25–3:00 — Prove future prevention

Click **Next** to test the similar payment. Show the green protection marker and the two outcomes.

> The approved behavioral safeguard checks a scam with a different recipient. The local payment gate holds it before any debit, while the normal payment passes. Neither payment makes a Gemini call. A recorded fallback shows these original outcomes and is explicitly labelled.
>
> The contribution is the complete feedback loop: evidence-driven investigation, human-reviewed knowledge, a tested prevention proposal, and an observable effect on the next transaction—all within one shared cost budget.

Leave the completed scene visible. **Run demo** archives it and clears its active lessons, but never resets spend or daily counters. To replay without paid calls, inspect the saved trace and use the already-completed payment proof; do not start a new world or new learner.

## Optional extension — the risk data science team

Open **Agent activity → Model experiments**. Showing a saved study makes no model call.

> The scientist chooses a hypothesis, feature groups and bounded model recipes—or asks for more labelled data. These are real CPU fits. The amount baseline can fail, and the validator cannot waive the measured gate. Candidate selection uses validation data; the final test can only veto it. A recommendation goes to human model review and does not silently replace payment protection.

Point to the dataset label. A **synthetic benchmark** result must be presented as synthetic. **Curated cases** require separate operator verification and sufficient legitimate controls, customer separation and label timing. Read the actual saved tool choices and measured results rather than promising a particular candidate will pass.

## Classifier spotlight in Run demo

Use only **Next**. After the evidence check, pause on **The agent calls a classifier**: the diagram shows the actual `score_models` request and the agent’s saved purpose. **Read the classifier result** shows one trained-model receipt per screen, its exact score against the operating threshold, the payment count and receipt ID. Scores are advisory signals, not fraud probabilities. Missing inputs are shown as unavailable.

Next shows **The agent weighs the evidence**, pairing the model result and whether it was cited with the actual recorded resolution and uncertainty. Validation follows, then the simulated Fraud Analyst approval, shared knowledge, prevention activation and the town’s changed-recipient payment check. A rejected draft cannot be auto-approved; Next can open the labelled saved Gemini walkthrough without retrying a model.

Fresh guided cases require a cited AE ledger-classifier receipt, inside the unchanged six-call allowance. Continuous simulation retains discretionary model selection. The cost-free fallback now uses successful Gemini case **SC-a1a870cc4e** from October 17, 2026. Karlo's `ledger_transaction_v1` returned **0.705251 / 0.700**, and the agent cited its receipt before the simulated analyst approved the case. Gemini's prevention role proposed `safe_account_request` + `secrecy_request`; the approved rule held the original hosted **₱900** attempt to a different recipient, with **zero debit and zero ledger entries**, while the legitimate control settled.

The original run used four Gemini calls ($0.004152). Replaying it adds no model calls or current-world actions. The fallback preserves the original hosted tool, review and payment receipts; exporting it did not generate another payment, rerun inference or regenerate the resolution. Follow **Next** from an empty recorded scene through the classifier, review, knowledge and protection. **Back** only revisits saved facts. The live cost caps remain unchanged.
