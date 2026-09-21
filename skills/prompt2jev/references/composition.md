# Composition patterns

How code consumes Jev answers. Every pattern here keeps thresholds, weights, and
hard rules in one constants block and keeps side effects outside the model.

## Contents

- Constants block
- Confidence bands
- Speculative fan-out
- Composite scoring
- Intent routing
- Guardrail battery
- Selection instead of extraction
- When a second request is warranted
- JavaScript equivalent
- Logging, pinning, caching

## Constants block

Put the questions, every threshold, every weight, and every hard rule at the top of
the module. A reviewer should be able to audit the whole decision without reading the
function bodies.

```python
from typesafe_sdk import Choice, Noul, NoulCriteria, Score, TypeSafeClient

MODEL = "jev-1.13.0"                     # pinned: thresholds below were tuned on it
QUESTIONS = {...}                        # the converted questions
CONFIDENCE_FLOOR = 0.5                   # below: a person decides
ACT_WITHOUT_CONFIRM = 0.9                # destructive actions need this much
REFUND_YES = 0.7                         # noul thresholds are separate from confidence
WEIGHTS = {"severity": 0.5, "frustration": 0.3, "detail": 0.2}
HARD_EXCLUDE = {"abusive"}               # never outvoted by weights
```

## Confidence bands

Three ranges, and the boundaries move with the stakes of each action.

```python
action = response.answers["action"]

if action.confidence < CONFIDENCE_FLOOR:
    route_to_human(request)                       # the model is telling you it does not know
elif action.choice == "check_balance":
    show_balance(account_id)                      # cheap and reversible: act
elif action.choice == "approve_transfer":
    if action.confidence > ACT_WITHOUT_CONFIRM:
        execute_transfer(account_id)              # costly but the read is clear
    else:
        ask_user_to_confirm(account_id)           # costly and only moderately clear
```

Noul values are thresholded on their own scale. Use 0.5 when yes and no cost the same
to get wrong; raise it when acting on a false yes is expensive; lower it when missing
a true yes is expensive; send the middle to a person.

```python
YES, NO = 0.8, 0.2
value = response.answers["wants_human"].noul
if NO < value < YES:
    send_to_review(message)
elif value >= YES:
    route_to_agent(message)
else:
    route_to_bot(message)
```

Start conservative, plot confidence against accuracy on your own labeled data, then
move the boundaries. Do not carry a threshold from a Noul to a Choice or between
model versions.

## Speculative fan-out

Ask every question the code might need in one request and read only the ones the
branch uses. Extra questions barely change latency and cost only their tokens.

```python
answers = response.answers
category = answers["category"]

if category.choice == "bug_report":
    if answers["bug_severity"].score > 1.5 and answers["has_repro_steps"].noul > 0.6:
        escalate_to_engineering(ticket_id, severity="high")
    else:
        add_to_backlog(ticket_id)
elif category.choice == "billing":
    route_to_billing(ticket_id, refund_likely=answers["refund_requested"].noul > 0.7)
elif category.choice == "feature_request":
    log_feature_request(ticket_id)

if answers["frustration"].score > 1.5:            # useful on every branch
    flag_for_priority_response(ticket_id)
```

## Composite scoring

Score each dimension separately, normalize by the top level index, and weight in
code. Change a weight, not a prompt, when priorities move.

```python
TOP = {"python_depth": 4, "team_leadership": 4, "system_design": 4}
scores = {qid: response.answers[qid].score / top for qid, top in TOP.items()}

senior_ic = 0.40 * scores["python_depth"] + 0.10 * scores["team_leadership"] + 0.50 * scores["system_design"]
manager   = 0.15 * scores["python_depth"] + 0.60 * scores["team_leadership"] + 0.25 * scores["system_design"]
```

A hard exclusion is a separate rule, not a small negative weight:

```python
if response.answers["abusive"].noul >= ABUSE_YES:
    return "reject"                                # regardless of the composite
```

A composite is a utility number, not a probability. Changing weights does not require
another model call if the evidence and the question meanings are unchanged.

## Intent routing

A Choice picks the handler; a Score on complexity decides between automation and a
person. Cheap handlers get most traffic; the expensive ones see only what needs them.

```python
intent, complexity = response.answers["intent"], response.answers["complexity"]

if intent.confidence < 0.5:
    return route_to_human(ticket_id)
if intent.choice == "order_status":
    return handle_order_status(ticket_id)                    # deterministic code
if intent.choice == "product_question":
    return handle_with_llm(ticket_id, PRODUCT_SPECIALIST)    # specialist prompt
if intent.choice == "complaint":
    if complexity.score > 1 or complexity.confidence < 0.5:
        return route_to_human(ticket_id)
    return handle_with_llm(ticket_id, COMPLAINT_RESOLUTION)
return route_to_human(ticket_id)                             # "other"
```

## Guardrail battery

One Noul per hazard plus a severity Score, on the way into and out of an LLM. Two
thresholds per hazard: act, or review. Precedence resolves several hits.

```python
HAZARD_ACTION = {"jailbreak": "block", "harmful_request": "block",
                 "medical_advice": "review", "self_harm": "support"}
PRECEDENCE = ["support", "block", "review", "pass"]
POLICY = {"review": 0.35, "act": 0.70, "severity_block": 2.0}


def route(nouls: dict[str, float], severity: float) -> str:
    triggered = []
    for hazard, probability in nouls.items():
        if probability >= POLICY["act"]:
            triggered.append(HAZARD_ACTION[hazard])
        elif probability >= POLICY["review"]:
            triggered.append("review")
    if severity >= POLICY["severity_block"]:
        triggered = ["block" if action == "review" else action for action in triggered]
    return next((action for action in PRECEDENCE if action in triggered), "pass")
```

## Selection instead of extraction

Find candidates in code, let a Choice pick, copy the original span.

```python
import re

candidates = re.findall(r"\b\d{3,6}\b", source_text)                   # code finds
question = Choice(
    instructions={"field": {"name": "invoice_number", "description": "The identifier printed on the invoice"},
                  "question": "Which option is the value of `field` in `source_text`?"},
    criteria={**{value: None for value in candidates}, "not_stated": "None of the candidates is the invoice number."},
)
answer = response.answers["invoice_number"]
if answer.choice != "not_stated" and answer.confidence >= 0.7:
    invoice_number = answer.choice                                     # verbatim from the source
```

Dates work the same way: one Choice per component over its closed set (month, day,
year) with a `not_stated` option, then `date(...)` in code.

## When a second request is warranted

Only when the second request's state depends on the first answer:

1. **Fetch more evidence.** Rank 182 candidates in one request, then fetch the full
   text of the top three and judge them again (skill suggestion cookbook).
2. **Build new state.** Ask whether each line break split a sentence, merge lines
   into blocks from the answers, then classify the blocks (structure recovery).
3. **Choose the next options.** Use each Choice answer to decide which children the
   next Choice offers (hierarchical classification, with a beam when close).

If the second request's questions could have been asked against the original state,
they belong in the first request.

## JavaScript equivalent

```ts
import { choice, noul, score, TypeSafeClient } from "@typesafe-ai/sdk";

const MODEL = "jev-1.13.0";
const CONFIDENCE_FLOOR = 0.5;
const REFUND_YES = 0.7;
const QUESTIONS = {
  category: choice("Which team should handle `ticket.text`?", {
    billing: "Charges, invoices, refunds, or subscriptions.",
    account: "Login, password, profile, or security.",
    other: "None of the listed teams fits.",
  }),
  refund_requested: noul("Does the customer in `ticket.text` explicitly ask for money back?"),
  frustration: score("How frustrated does the customer appear in `ticket.text`?", [
    "Calm and matter-of-fact; neutral wording.",
    "Frustrated but civil; expresses annoyance.",
    "Very angry; hostile language or threatens to leave.",
  ]),
};

const client = new TypeSafeClient();

export async function triage(ticket: string) {
  const { answers, model } = await client.systemOne({ model: MODEL, state: { ticket: { text: ticket } }, questions: QUESTIONS });
  if (answers.category.confidence < CONFIDENCE_FLOOR || answers.category.choice === "other") {
    return { route: "human_triage", model };
  }
  return {
    route: answers.category.choice,
    refundRequested: answers.refund_requested.noul >= REFUND_YES,
    priority: answers.frustration.score > 1.5 ? "high" : "normal",
    model,
  };
}
```

## Logging, pinning, caching

- Log `response.model` and `response.usage` with every decision so a threshold can
  be traced to the model version it was tuned on.
- Pin a versioned model id once thresholds are tuned; move to a new one on your own
  schedule after re-checking on labeled data.
- Cache by state content, question version, and model id, not by record id alone. A
  judgment made on old evidence is not a fresh observation.
- Keep API keys server-side. Never ship them to a browser.
