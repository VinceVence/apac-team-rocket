# Pallet Town — 3-minute demo script

Use the **saved episode and investigations**. Leave **Run world**, **Recheck**, and **Start investigation** untouched. This walkthrough requires no new Gemini calls.

## 0:00–0:25 — Environment

*Show the town and its completed activity feed.*

> This is Pallet Town, a simulated fintech economy with 100 customers. People make purchases and transfers, producing transaction histories and daily customer features in BigQuery.
>
> When a customer reports a suspected scam, those records become evidence for an investigation. Today we’re walking through saved results, so we won’t make new Gemini calls.

## 0:25–1:10 — Gemini’s investigation

*Open **Agent activity**, select **Invoice redirection**, and expand **Tools called**.*

> Here, a customer reports paying a changed beneficiary. Gemini receives the complaint and chooses which tools to call through Google ADK.
>
> In this investigation, it checked the disputed transactions, queried customer behavior from BigQuery, consulted Philippine complaint guidance, and searched approved case knowledge before submitting its recommendation.
>
> Each tool entry exposes the returned evidence. We can inspect what the agent actually used instead of relying only on its final explanation.

*Expand the BigQuery tool’s evidence.*

> The customer query is scoped to this case and a saved data snapshot. Gemini cannot freely query another customer or run arbitrary SQL.

## 1:10–1:35 — Show a different tool choice

*Switch to **Account takeover**.*

> This case completed in four model calls and skipped the memory search. The investigation path can vary with the evidence.
>
> Gemini also has tools for asking the customer a question or training a small behavior model. It didn’t choose those tools in these five live cases, so we don’t present them as observed decisions.

## 1:35–2:10 — Analyst approval

*Return to **Invoice redirection**. Show **Expected resolution**, then expand **Review notes**.*

> Gemini proposes a resolution and a lesson. The analyst checks the evidence, uncertainty, disposition and next action.
>
> Approval is the human decision. It doesn’t mean money has been recovered or that the system has determined legal fault.

*Review the lesson, leave **Remember and protect future payments** checked, then click **Approve & remember**.*

> This publishes reviewed knowledge that subsequent payments and investigations can use.

## 2:10–2:45 — Prevention from approved knowledge

*Return to **Environment**. Find **Held by approved knowledge**, then open **View knowledge**.*

> Here is a saved later scam attempt that was held using knowledge from an earlier approved case.
>
> This is separate from the approval we just performed. The receipt identifies the reviewed memories responsible for the hold.
>
> Matching the approved recipient prevents settlement in the simulator without another Gemini call.

## 2:45–3:00 — Close

> Our demonstration connects three things: evidence from a working economy, Gemini choosing investigation tools, and analyst-approved knowledge affecting future payments. Today’s prevention uses recipient matching; broader scam-pattern learning is the next extension.
