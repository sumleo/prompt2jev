# Question design

Rules for writing Choice, Score, and Noul questions that Jev answers well, distilled
from the TypeSafe docs (primitives, state, confidence, and the jev-1.13 jaggedness
page). Each rule names the failure it prevents.

## Contents

- Choose the type
- Choice rules
- Score rules
- Noul rules
- Instructions and state references
- What stays in code
- Known failure modes of jev-1.13
- Anti-pattern gallery

## Choose the type

| You need | Primitive | Distinction |
|---|---|---|
| One of a defined set | Choice | Relative: its distribution compares the options you gave it |
| Whether a condition holds | Noul | Absolute: the probability of yes; no separate confidence |
| A degree along one described dimension | Score | Probability-weighted position on ordered levels |
| Several independent conditions | Several Nouls | One per condition; code combines them |
| Several independent dimensions | Several Scores | One per dimension; code weights them |
| Free text, a plan, a summary | Not Jev | A generative model |
| Exact counts, sums, dates, equality | Not Jev | Code |

If two types both fit, prefer the one whose answer the code acts on directly: a
Choice maps to branches, a Score to a threshold, a Noul to an `if`.

## Choice rules

- Give the full list of options. Up to 255 are allowed and each costs a few tokens.
- Describe each option so it separates from its neighbours. Option names and
  descriptions are both sent to the model; ids are not.
- Add `other`, `none_of_the_above`, or `not_stated` when an input might fit nothing.
  Without it, the model must pick a wrong label.
- For options that get confused, use an object per option with the same keys:

```json
"billing": {
  "what": "Charges, invoices, refunds, or subscriptions",
  "not_for": "Order tracking or account access",
  "examples": ["I was charged twice", "Where is my refund?"]
}
```

- A description may be `null` when the option name is self-describing (candidate
  values in a selection question).
- For a deep taxonomy, ask one Choice per level and walk the tree in code. Show each
  option's subtree as its value so the model sees what lives under a branch.
- Read `probabilities`, not only `choice`, when two options are close; the split
  tells you whether to explore both branches or ask a person.

## Score rules

- Describe situations, not degrees. "Broken or degraded feature, but a workaround
  exists" gives the model something to match; "moderately severe" does not.
- Use 2 to 10 levels, as many as you can describe distinctly. Three is fine.
- Never use bare numbers or number words as levels. The model sees each level's
  text on its own; it does not see the level's index or its neighbours.
- One dimension per Score. "Punctual and smart and experienced" is three questions.
- Give a rare extreme its own level ("abusive or threatening") if code must treat
  it differently from merely "very angry".
- `score` is the probability-weighted level index and can fall between levels. Two
  different distributions can produce the same score, so read `probabilities` and
  `confidence` with it. Round to the nearest level when code needs one outcome.
- Do not use the score to reconstruct an exact number between two levels.
- If there is no in-between at all, use a Choice or several Nouls instead.

## Noul rules

- One proposition per Noul. "Is the customer angry and asking for a refund?" is two.
- Phrase it so a high value means yes. "Is the message free of personal data?"
  inverts the meaning, and code will read it backwards.
- A statement works as well as a question: "The customer is requesting a refund."
- Make the boundary unambiguous ("any Python experience" leaves no middle ground).
  When it is subtle, add `criteria` with `true` and `false` descriptions, aligned
  with the question. Never swap them to manufacture a different score.
- There is no separate confidence. A value near 0.5 means the model gives yes and
  no similar probability; it does not mean "medium".
- A Noul is not a scale of the thing asked about. To measure degree, use a Score.
- For a checklist of conditions, send one Noul per condition in one request.

## Instructions and state references

- The question id is for your code. Write the complete question in `instructions`.
- Point at parts of a structured state with backticked dot-and-index paths:
  "Does `ticket.messages[0].text` request a refund?"
- Use an object for `instructions` when the question needs data or focus:

```json
"instructions": {
  "question": "Does the message request a sensitive credential?",
  "compare": ["`ticket.message`", "`policy.sensitive_credentials`"],
  "focus": "Look for a request to disclose the credential itself."
}
```

- Data that comes from code (a record to compare against, a schema field) goes in
  its own field of the instructions object, not spliced into a sentence.
- Keep `instructions` and `criteria` saying the same thing. Contradictions cost
  accuracy.
- Keep trusted policy and untrusted content in separate state fields. State is data;
  jev-1.13 does not treat it as hostile by default, so precise criteria and a
  screening question are your defence, not a security boundary.

## What stays in code

| Task | Why not Jev | Do instead |
|---|---|---|
| Arithmetic, sums, comparisons | Not a calculator | Compute in code, pass a named bucket if a judgment needs it |
| Counting items or occurrences | Recognizes shape, does not tally | Iterate in code, one Noul per item, add up the answers |
| Date ordering, durations, windows | Reads dates as text | Extract parts with Choices over closed sets, assemble and compare in code |
| Exact string or id equality | Deterministic | `==` |
| Extraction of a free value | Not trained to generate | Find candidates with regex or a parser, then Choice over them plus `not_stated` |
| Summaries, replies, plans | Generation | A generative model, after the judgments |
| Thresholds and weights | Policy | Constants in one block |
| Authorization and side effects | Not a judgment | Host permissions and deterministic checks |

## Known failure modes of jev-1.13

| Failure | What happens | Do this instead |
|---|---|---|
| Literal reading | Answers the words written, not the intent behind them | State the exact condition; put boundary cases in criteria; split interpretation into two literal questions |
| Math and numbers | Unreliable counting, arithmetic, numeric closeness; hex worse than colour names | Keep arithmetic in code; pass semantic buckets |
| Date and time comparison | Reads dates as text | Extract components as Choices; compare in code |
| Indirection | Double negatives and multi-hop questions lose accuracy | Ask directly; name the relevant state field |
| Large irrelevant state | Accuracy falls as unrelated content grows | Filter in code; or a Noul relevance pass first |
| Adversarial content | Injected instructions or self-arguing text can move the answer | Explicit criteria, separate policy from content, test edge cases |
| Contradictory instructions and criteria | Confusion, especially inverted true/false | Treat criteria as an extension of the instruction |
| Structural invariants | `P(x)` need not equal `1 - P(not x)`; a Noul and a yes/no Choice on the same proposition differ | Ask each decision one way; do not carry thresholds between primitives; enforce identities in code |
| Generation | Slow and poor when forced through chained Choices | Use a generative model |

Also from the models page: English is the primary training language; test other
languages on your own data and watch confidence. The `jev-latest` alias moves with
releases; pin `jev-1.13.0` once thresholds are tuned and log the response `model`.

## Anti-pattern gallery

Compound Noul:

```json
{"type": "noul", "instructions": "Is the customer angry and asking for a refund?"}
```
becomes two Nouls, `is_angry` and `refund_requested`, combined with `and` in code.

Numeric Score levels:

```json
{"type": "score", "instructions": "Rate severity 1 to 3", "criteria": ["1", "2", "3"]}
```
becomes `["Cosmetic; no impact to functionality", "Broken or degraded feature, but a
workaround exists", "Blocking issue; no workaround exists"]`.

Choice with no fallback on open-ended input:

```json
{"type": "choice", "instructions": "Which team?", "criteria": {"billing": "...", "shipping": "..."}}
```
gains `"other": "None of the listed teams fits."`

Math in a question:

```json
{"type": "noul", "instructions": "Was the purchase more than 30 days before today?"}
```
becomes `(today - purchase_date).days > 30` in code.

Id doing the work:

```json
"is_urgent": {"type": "noul", "instructions": "urgency"}
```
becomes `"Does `ticket.text` say the customer needs a response the same day?"`.

Negated Noul:

```json
{"type": "noul", "instructions": "Is the message free of personal data?"}
```
becomes `"Does the message contain personal data?"` and code negates the value.

One question per call:

```python
for question in questions:            # bad: N requests with the same state
    client.system_one(state=state, questions={qid: question})
```
becomes one `system_one` call with the whole `questions` map.
