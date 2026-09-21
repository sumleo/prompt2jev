# Conversion playbook

How to take an LLM prompt (or a bare requirement) and turn it into a Jev request plus
the code around it. Read this once end to end; the worked example is the template.

## Contents

- The conversion in six moves
- Digging in a codebase
- Worked example: support triage prompt
- When the input is only a requirement
- Handing over the package

## The conversion in six moves

1. **Read and dig.** Get the prompt, its placeholders, the parser, the code that
   branches on the output, and any labeled examples. Decide what the code will do
   with each answer before writing a question.
2. **Split.** Classify every instruction: `choice`, `noul`, `score`, `code`,
   `keep-llm`, or `drop`. Compound rules split into one question per condition plus
   code. Anything computable stays in code.
3. **State.** Name a field for each input the questions need. Keep untrusted text
   separate from trusted policy. Leave out what no question uses.
4. **Questions.** One judgment each, full question in `instructions`, backticked
   paths into the state, criteria that separate neighbours, a fallback option on
   open-ended Choices, described Score levels, Nouls where yes is the high value.
5. **One request.** All independent questions together, speculative ones included.
   A second request only when its state depends on a first answer.
6. **Compose.** Constants block, confidence bands scaled by stakes, weights you own,
   hard exclusions as separate rules, speculative answers read only on their branch.

## Digging in a codebase

Before asking the user anything, look for:

```bash
grep -rn "system_prompt\|SYSTEM_PROMPT\|You are a" --include=*.py --include=*.ts .
grep -rn "response_format\|json.loads\|JSON.parse" --include=*.py --include=*.ts .
grep -rn "enum\|Literal\[" --include=*.py .            # existing label sets
grep -rln "fixtures\|golden\|expected_label" tests/     # labeled examples
```

Read the code that consumes each output field. That code tells you the decision,
the consumer, and the stakes. The prompt only tells you the wording.

Ask the user one question at a time, and only when the answer changes a question's
shape: the label set, what an answer triggers, or the cost of a wrong answer.

## Worked example: support triage prompt

The prompt as it runs today, with placeholders filled by code:

```text
You are a support triage assistant. Read the customer ticket and return JSON only.

Ticket: {ticket}
Customer plan: {plan}
Order amount: {amount}
Purchase date: {purchase_date}
Today: {today}

Rules:
- category must be one of: billing, shipping, account, bug, feature_request
- urgency is an integer 1-5 (5 = most urgent)
- refund_requested is true if the customer asks for their money back
- If the customer is asking for a refund AND the order amount is over 100 USD AND
  the purchase was more than 30 days ago, set escalate=true, otherwise false
- If the message is abusive or threatening, set escalate=true regardless
- If the customer is on the enterprise plan and urgency >= 4, set priority="p0";
  if urgency >= 3 set priority="p1"; else "p2"
- sentiment is one of: positive, neutral, negative
- summary: one sentence summary of the issue

Return: {"category": ..., "urgency": ..., "refund_requested": ..., "escalate": ...,
         "priority": ..., "sentiment": ..., "summary": ...}
```

### 1. Decision contract

- **Decision:** route the ticket to a team queue with a priority, and flag it for
  escalation.
- **Evidence unit:** one ticket's text. Plan, amount, and dates are known to code.
- **Consumers:** `category` picks the queue; `urgency` and the plan set priority;
  `refund_requested`, amount, purchase age, and `abusive` set `escalate`;
  `sentiment` is stored for reporting.
- **Unknown path:** category `other` or low confidence goes to a human triage queue.
- **Success check:** queue and priority agree with the current labels on the last
  200 tickets; escalations are reviewed weekly for false positives.

### 2. Split table

| Prompt instruction | Becomes | Note |
|---|---|---|
| category must be one of five labels | `choice` `category` + `other` | Fallback added |
| urgency 1 to 5 | `score` `urgency`, five described levels | Numbers replaced by situations |
| refund_requested if asks for money back | `noul` `refund_requested` | Criteria pin the boundary |
| amount over 100 USD | `code` | Comparison |
| purchase more than 30 days ago | `code` | Date arithmetic |
| abusive or threatening | `noul` `abusive` | Separate proposition |
| escalate = refund and amount and age, or abusive | `code` | Boolean over answers and facts |
| priority from plan and urgency | `code` | Plan is a code value, urgency a score |
| sentiment positive/neutral/negative | `score` `sentiment`, three described levels | Ordered, so a Score |
| one-sentence summary | `keep-llm` | Generation, not a judgment |
| Return JSON only | `drop` | Answers are typed |
| plan, amount, purchase_date, today placeholders | `code` | No question needs them |

### 3. Request

```json
{
  "model": "jev-latest",
  "state": {
    "ticket": {
      "text": "I was charged twice for order #98423 three weeks ago and nobody answers my emails. I want my money back today or I'm disputing the charge."
    }
  },
  "questions": {
    "category": {
      "type": "choice",
      "instructions": {
        "question": "Which team should handle `ticket.text`?",
        "focus": "Classify the customer's primary request, not every topic mentioned."
      },
      "criteria": {
        "billing": "Charges, invoices, refunds, or subscriptions.",
        "shipping": "Delivery status, delays, lost or damaged packages.",
        "account": "Login, password, profile, permissions, or security.",
        "bug": "A product feature that is broken or producing errors.",
        "feature_request": "A request for functionality that does not exist yet.",
        "other": "None of the listed teams fits, or the message is not a support request."
      }
    },
    "urgency": {
      "type": "score",
      "instructions": "How urgently does `ticket.text` need a response, judged from what the customer says is at stake?",
      "criteria": [
        "General question or feedback with nothing pending.",
        "A request the customer wants handled but nothing is blocked.",
        "An active problem the customer wants fixed soon; work continues around it.",
        "Work or purchases are blocked, or the customer sets a same-day deadline.",
        "Ongoing loss of money or data, or a threat to dispute, cancel, or escalate publicly."
      ]
    },
    "refund_requested": {
      "type": "noul",
      "instructions": "Does the customer in `ticket.text` explicitly ask for money back or an account credit?",
      "criteria": {
        "true": "Directly asks for a refund, a reversal of a charge, or a credit.",
        "false": "Complains about a charge without asking for money back, or asks about something else."
      }
    },
    "abusive": {
      "type": "noul",
      "instructions": "Does `ticket.text` contain abusive, insulting, or threatening language directed at staff or the company?",
      "criteria": {
        "true": "Insults, slurs, or threats of harm or retaliation aimed at people or the company.",
        "false": "Frustration, strong words about the problem, or a threat to cancel or dispute a charge."
      }
    },
    "sentiment": {
      "type": "score",
      "instructions": "How does the customer feel about the company, as expressed in `ticket.text`?",
      "criteria": [
        "Expresses dissatisfaction, complaint, or anger.",
        "Neutral: states facts or asks a question without expressed feeling.",
        "Expresses satisfaction, thanks, or praise."
      ]
    }
  }
}
```

`abusive` says explicitly that a threat to dispute a charge is not abuse, because the
example ticket contains one. Boundary cases go in the criteria, not in your head.

### 4. Composition code

```python
from datetime import date

from typesafe_sdk import Choice, Noul, NoulCriteria, Score, TypeSafeClient

# ----- constants: everything a reviewer needs to see in one place -----
MODEL = "jev-latest"  # pin to jev-1.13.0 once the thresholds below are tuned
QUESTIONS = {
    "category": Choice(
        instructions={"question": "Which team should handle `ticket.text`?",
                      "focus": "Classify the customer's primary request, not every topic mentioned."},
        criteria={
            "billing": "Charges, invoices, refunds, or subscriptions.",
            "shipping": "Delivery status, delays, lost or damaged packages.",
            "account": "Login, password, profile, permissions, or security.",
            "bug": "A product feature that is broken or producing errors.",
            "feature_request": "A request for functionality that does not exist yet.",
            "other": "None of the listed teams fits, or the message is not a support request.",
        },
    ),
    "urgency": Score(
        instructions="How urgently does `ticket.text` need a response, judged from what the customer says is at stake?",
        criteria=[
            "General question or feedback with nothing pending.",
            "A request the customer wants handled but nothing is blocked.",
            "An active problem the customer wants fixed soon; work continues around it.",
            "Work or purchases are blocked, or the customer sets a same-day deadline.",
            "Ongoing loss of money or data, or a threat to dispute, cancel, or escalate publicly.",
        ],
    ),
    "refund_requested": Noul(
        instructions="Does the customer in `ticket.text` explicitly ask for money back or an account credit?",
        criteria=NoulCriteria(
            true="Directly asks for a refund, a reversal of a charge, or a credit.",
            false="Complains about a charge without asking for money back, or asks about something else.",
        ),
    ),
    "abusive": Noul(
        instructions="Does `ticket.text` contain abusive, insulting, or threatening language directed at staff or the company?",
        criteria=NoulCriteria(
            true="Insults, slurs, or threats of harm or retaliation aimed at people or the company.",
            false="Frustration, strong words about the problem, or a threat to cancel or dispute a charge.",
        ),
    ),
    "sentiment": Score(
        instructions="How does the customer feel about the company, as expressed in `ticket.text`?",
        criteria=[
            "Expresses dissatisfaction, complaint, or anger.",
            "Neutral: states facts or asks a question without expressed feeling.",
            "Expresses satisfaction, thanks, or praise.",
        ],
    ),
}
CATEGORY_CONFIDENCE_FLOOR = 0.5   # below this, a person picks the queue
REFUND_YES = 0.7                  # noul threshold; raise if false escalations are costly
ABUSE_YES = 0.6                   # noul threshold; lower if missing abuse is the costlier mistake
ESCALATION_AMOUNT_USD = 100
ESCALATION_AGE_DAYS = 30
URGENCY_P0 = 3.0                  # score index on the 0..4 scale; the old "4 of 5"
URGENCY_P1 = 2.0                  # the old "3 of 5"
SENTIMENT_LABELS = ["negative", "neutral", "positive"]


def triage(ticket: str, plan: str, amount_usd: float, purchase_date: date, today: date) -> dict:
    with TypeSafeClient() as client:
        response = client.system_one(model=MODEL, state={"ticket": {"text": ticket}}, questions=QUESTIONS)
    answers = response.answers

    category = answers["category"]
    if category.choice == "other" or category.confidence < CATEGORY_CONFIDENCE_FLOOR:
        return {"route": "human_triage", "reason": "uncertain category", "model": response.model}

    refund = answers["refund_requested"].noul >= REFUND_YES
    old_enough = (today - purchase_date).days > ESCALATION_AGE_DAYS      # code, not Jev
    escalate = (refund and amount_usd > ESCALATION_AMOUNT_USD and old_enough) \
        or answers["abusive"].noul >= ABUSE_YES

    urgency = answers["urgency"].score
    if plan == "enterprise" and urgency >= URGENCY_P0:
        priority = "p0"
    elif urgency >= URGENCY_P1:
        priority = "p1"
    else:
        priority = "p2"

    sentiment = SENTIMENT_LABELS[round(answers["sentiment"].score)]
    return {"route": category.choice, "priority": priority, "escalate": escalate,
            "refund_requested": refund, "sentiment": sentiment, "model": response.model}
```

The one-sentence summary is not in this function. If a consumer still needs it, call
the generative model after triage, only for tickets that reach a human.

### 5. Assumptions and fixtures

- Thresholds above are starting points. Tune on the last 200 labeled tickets and
  check on a held-out set before automating escalation.
- "Urgency 4 of 5" maps to score index 3 on a five-level scale. Confirm the levels
  match what the team means by urgent.
- `abusive` treats "I will dispute the charge" as not abusive. Confirm.
- Fixtures: a refund over the amount and age limits (escalate), a refund under the
  amount (no escalation), an abusive ticket with no refund (escalate), a calm
  feature request (p2, no escalation), an empty or off-topic message (`other`,
  human triage), a ticket that argues for its own urgency without stating a
  problem (should stay low).

## When the input is only a requirement

"Classify incoming tickets and flag refunds" has no prompt to split. Write the
decision contract first, propose label sets from any enums or queues already in the
code, and present the draft request with the assumptions marked. The rest of the
playbook applies unchanged.

## Handing over the package

Show the five parts in order: contract, split table, validated request JSON,
composition code, assumptions and fixtures. State which validation ran
(`validate --strict`, `run --dry-run`, or a live sample) and what it found. Do not
report a request as ready until the validator has passed on the saved file.
