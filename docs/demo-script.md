# Pallet Town — 3-minute guided demo

Use the public app's **Environment**, **Agent activity**, and **Agents** tabs. Run the live case before presenting if latency is uncertain. Saved timelines and the payment proof can be shown without new model calls. Starting a new world or approving a case with a remaining learner call can consume the shared allowance.

## 0:00–0:30 — Run world

Click **Run world** (4× speed is useful). A fresh scene begins with 100 synthetic customers and seeded transaction history. Point to purchases and transfers, then the orange **!** above the victim.

> A customer has received a deceptive payment request, transferred money, and filed a complaint. The world pauses here so we can follow the investigation. Its evidence is captured and customer features are published to seven bounded BigQuery tables.

Open **Follow the case** or **Agent activity**.

## 0:30–1:25 — Watch the resolution agent

Show the actual tool timeline and detector cards. Expand one evidence entry.

> Gemini chooses the next tool through Google ADK. We record its purpose, validate the tool and arguments, and show the actual result. The device check can look normal while the payment message contains strong scam signals. A recorded authorization is not the same as informed intent.
>
> The agent combines the complaint, this customer's transaction evidence and BigQuery features. It can trace a recipient, compare behavior, request a bounded anomaly model, retrieve reviewed cases, or ask a follow-up question. We only claim the choices visible in this saved trace.

The registered detector scores are rule signals, not calibrated fraud probabilities. A fake-model rehearsal is explicitly labelled and must not be presented as Gemini.

## 1:25–1:55 — Analyst review

Read the expected resolution, evidence and uncertainty. Review the lesson and click **Approve & learn** only if supported.

> The agent recommends; the risk analyst verifies. Approval publishes the reviewed case. This is a synthetic recall request, not a promise that money has been recovered.

The prevention learner may consume one remaining model call from the same six-call allowance.

## 1:55–2:25 — Learn a safeguard

Show the **Prevention agent** panel, its selected signals and replay results. Click **Enable safeguard** after inspecting the source and controls.

> A second role converts the approved resolution into a narrow, versioned safeguard. It can also decline. The proposal must catch the changed-recipient example and avoid the legitimate replay controls, then a human decides whether to activate it. These are synthetic checks, not production accuracy measurements.

## 2:25–3:00 — Prove future prevention

Click **Test a similar payment**. Show the green protection marker and the two outcomes.

> The scam now uses a different recipient. The local payment gate requests verification before any debit, while the normal payment passes. Neither payment makes a Gemini call.
>
> The contribution is the complete feedback loop: evidence-driven investigation, human-reviewed knowledge, a tested prevention proposal, and an observable effect on the next transaction—all within one shared cost budget.

Leave the completed scene visible. **Run new world** archives it and clears its active lessons, but never resets spend or daily counters. To replay without paid calls, inspect the saved trace and use the already-completed payment proof; do not start a new world or new learner.
