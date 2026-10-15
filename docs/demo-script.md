# Mint Town — 3-minute guided demo

Use the public app's **Environment**, **Agent activity**, and **Agents** tabs. Run the live case before presenting if latency is uncertain. Saved timelines and the payment proof can be shown without new model calls. Starting a new world or approving a case with a remaining learner call can consume the shared allowance.

## 0:00–0:30 — Run demo

Click **Run demo** (4× speed is useful). A fresh scene begins with 100 numbered residents and zero transactions. Point to purchases and transfers, then the orange **!** above the victim. Use **Next** to move the spotlight through the report and actual recorded agent actions. Each explanation stays on screen until you choose to continue; **Back** revisits the previous step.

> A customer has received a deceptive payment request, transferred money, and filed a complaint. The guided world pauses here so we can follow the investigation. Its evidence is captured in versioned snapshots, and simulator data is published to the isolated BigQuery dataset.

For free exploration, use the separate **Run simulation** button: payments keep flowing, clickable report widgets open investigations, and **Pause / Resume simulation** preserves the same world. Green shield alerts and **Scams stopped** show real recorded holds and link to their reviewed source cases. Both modes retain the existing safety limits.

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

## Optional extension — the risk data science team

Open **Agent activity → Model experiments**. Showing a saved study makes no model call.

> The scientist chooses a hypothesis, feature groups and bounded model recipes—or asks for more labelled data. These are real CPU fits. The amount baseline can fail, and the validator cannot waive the measured gate. Candidate selection uses validation data; the final test can only veto it. A recommendation goes to human model review and does not silently replace payment protection.

Point to the dataset label. A **synthetic benchmark** result must be presented as synthetic. **Curated cases** require separate operator verification and sufficient legitimate controls, customer separation and label timing. Read the actual saved tool choices and measured results rather than promising a particular candidate will pass.
