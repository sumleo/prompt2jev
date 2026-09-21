---
name: prompt2jev
description: Use when a user asks to convert an LLM prompt, system prompt, prompt template, or prompt-and-parse step (classifier, router, judge, grader, extractor, guardrail) into TypeSafe Jev decisions, wants to replace an LLM call that returns labels, scores, booleans, or JSON fields with typed questions, or describes a decision requirement with no prompt yet. Also use when a request mentions Jev, TypeSafe, System One, "turn this prompt into questions", or "make this decision structured".
license: MIT
metadata:
  requirements: Python 3.10+ runs the bundled validator with no third-party packages. Live calls need TYPESAFE_API_KEY (official API) or OPENROUTER_API_KEY and cost money; validation and dry runs need neither.
---

# Convert an LLM prompt into a Jev decision

Jev is TypeSafe's System One model. It evaluates typed questions against a `state`
and returns probabilities, not prose. Code owns control flow. Converting a prompt
means moving each judgment in it into its own question, moving every rule code can
compute into code, and leaving generation with a generative model. The bundled
references distill the TypeSafe docs; when live docs are reachable,
https://docs.typesafe.ai/llms.txt is the source of truth for the API contract.

## What you deliver

Produce the conversion package. It has five parts, in this order, every time:

1. **Decision contract** (five lines): the decision the code takes, the evidence
   unit (what one request judges), the consumer of each answer, the unknown path
   (what happens when nothing fits or evidence is missing), and the success check.
2. **Split table**: every instruction in the original prompt mapped to one of
   `choice`, `noul`, `score`, `code`, `keep-llm`, or `drop`, with the question id or
   the code rule it became. Nothing in the prompt goes unaccounted for.
3. **Request JSON** in the native shape `{"model", "state", "questions"}`, saved to
   a file and validated with `prompt2jev validate --strict` before it is shown.
4. **Composition code** in the project's language (Python with `typesafe_sdk` by
   default, `@typesafe-ai/sdk` for JavaScript): a constants block holding every
   threshold, weight, and hard rule, then one function that sends the request and
   branches on the answers.
5. **Assumptions and fixtures**: what was assumed, what the user should confirm,
   and the test cases to run before automating (positive, negative, ambiguous,
   missing evidence, adversarial).

## Step 0: read the prompt, dig before asking

Collect before designing: the prompt text, every placeholder and where its value
comes from, the parser or schema that reads the output, the code that branches on
each output field, existing enums or label lists, and any tests or labeled
examples. In a codebase, grep for the prompt string, the output field names, and
the API call that sends it.

Ask the user only when a gap changes the shape of a question: the label set, what
the code does with an answer, or the stakes of a wrong answer. Ask one question at
a time. A gap that does not change the shape becomes a stated assumption in part 5.
Never stop with nothing delivered; a validated draft with assumptions beats a
question.

## Step 1: split the prompt into judgments

Read the prompt sentence by sentence and classify each instruction:

| Instruction in the prompt | Becomes | Why |
|---|---|---|
| "X must be one of: a, b, c" | `choice` with those options plus a fallback | One option from a known set |
| "Set flag if the message ..." | `noul` | One yes/no proposition |
| "Rate ... from 1 to 5", "how severe" | `score` with described levels | A position on a spectrum |
| "If A and B then ..." | one question per condition, combined in `code` | Compound conditions hide judgments |
| Arithmetic, comparisons, dates, counting, thresholds | `code` | Jev is not a calculator |
| "Extract the invoice number" | candidates found in `code`, then `choice` over them | Select, never generate |
| "Summarize", "write a reply", "explain" | `keep-llm` | Generation stays with a generative model |
| "Return JSON only", output format rules | `drop` | The answer is already typed |
| Policy text, reference material, examples | `state` fields or structured `criteria` | Evidence and boundaries, not questions |

"Escalate if a refund is requested and the amount is over 100 and the purchase is
older than 30 days" becomes one `noul` (refund requested) plus two comparisons in
code. "Priority is p0 when the plan is enterprise and urgency is at least 4" is
entirely code once urgency is a `score`.

## Step 2: build the state

`state` is a JSON object with a named field for each input the questions need and
nothing else. Placeholders in the prompt become fields. Reference material the
prompt inlined (a refund policy, a rubric the model compares against) becomes a
field. Values the code already knows (plan, amount, dates) go in only if a question
needs them; otherwise they stay in code. Keep untrusted content (tickets, pages,
pasted text) in fields separate from trusted policy. Jev does not see the
conversation, so each request must be self-contained.

Mind the size: the state plus the longest question must stay under 32k tokens, and
everything together under 64k. Filter in code first; unrelated detail lowers
accuracy.

## Step 3: write the questions

Rules for every question:

- One judgment per question. Split "angry and asking for a refund" into two.
- The id is not sent to the model. Write the full question in `instructions`.
- Point at state fields with backticked paths: "Does `ticket.text` ask for a refund?"
- Put boundary cases in `criteria`, and keep `criteria` aligned with `instructions`.
- Use an object for `instructions` when the question needs data or focus:
  `{"question": "...", "focus": "Classify the primary request only."}`.

Per type:

- **Choice**: list every option, describe each so neighbours separate, and add a
  fallback such as `other` or `not_stated` when the list may not cover every input.
  Use `{"what", "not_for", "examples"}` objects for options that get confused.
- **Score**: 2 to 10 levels, each a concrete situation ("Broken, but a workaround
  exists"), never bare numbers or degree words. One dimension per Score. Give a
  rare extreme its own level.
- **Noul**: one proposition, phrased so a high value means yes, no negations. Add
  `criteria.true` and `criteria.false` when the boundary is subtle. A Noul near 0.5
  means unsure, not "medium".

A Choice is relative (which option is best); a Noul is absolute (does this hold).
Use both when "best candidate" and "any acceptable candidate" are different
questions.

## Step 4: one request

Put every independent question in one request, including speculative ones whose
answers only matter on some branches (bug severity when the category might not be
bug). Questions run in parallel and cannot see one another's answers. Make a
second request only when its state depends on a first answer: fetching more
evidence, building new state, or choosing the next options.

## Step 5: compose in code

Constants live in one block at the top of the file so a reviewer can read every
question and threshold in one place. Then:

- Gate on confidence with three bands. Route low-confidence answers to a person or
  a reasoning model. Raise the acting threshold for costly actions and lower it for
  cheap, reversible ones.
- Threshold `noul` values in code; a Noul has no separate confidence. Do not reuse
  a Choice confidence threshold for a Noul.
- Combine Scores with weights you own; normalize by the top level index. Keep hard
  exclusions as separate rules, not small negative weights.
- Read speculative answers only on the branch they belong to.
- Log the response's `model` field. Pin a versioned id once thresholds are tuned.

See [composition.md](references/composition.md) for SDK call shapes and a full
routing example.

## Step 6: validate and test

```bash
python3 <skill-dir>/scripts/prompt2jev.py validate request.json --strict
python3 <skill-dir>/scripts/prompt2jev.py run request.json --dry-run
```

`validate` checks the contract and lints against the rules above (fallback option,
numeric levels, compound or negated Nouls, math in a question, unreferenced state
fields, oversized state). The lint is heuristic: fix every warning, or when a
question is right as written (a closed set such as months needs no fallback; "terms
and conditions" is one phrase), suppress that code with `--allow CODE` and say why
in part 5. With a key present
and the user's approval, run a small labeled sample, then tune thresholds on it and
evaluate on held-out cases. Write fixtures for each branch, including inputs where
the model should abstain.

## Run

Resolve `<skill-dir>` to the folder containing this file. The script needs only
Python 3.10+. After `uv tool install` or `pipx install` of the repository,
`prompt2jev` is on PATH and replaces `python3 <skill-dir>/scripts/prompt2jev.py`.

```bash
prompt2jev setup                                   # which keys are present; prints no values
prompt2jev template classify-route > request.json  # start from an archetype
prompt2jev validate request.json --strict
prompt2jev run request.json --dry-run
prompt2jev run request.json                        # live call: TYPESAFE_API_KEY, model jev-latest
prompt2jev run request.json --provider openrouter  # OPENROUTER_API_KEY, model typesafe/jev-1.13
```

Keys come from the process environment only; never paste one into chat, a request
file, or a repository. A live call costs money and sends the state to the provider,
so confirm before the first one. Without a key, stop at a validated request and
point the user to https://console.typesafe.ai/keys. Do not simulate Jev output.

Archetypes: `classify-route`, `checklist-guardrail`, `rubric-composite`,
`extract-select`, `verify-claim`. Each is a validated request to copy and edit.

## References

| Need | Read |
|---|---|
| Worked conversion, start to finish | [playbook.md](references/playbook.md) |
| Rules and anti-patterns per primitive, known failure modes | [question-design.md](references/question-design.md) |
| Request and response fields, endpoints, models, limits, errors | [api.md](references/api.md) |
| Confidence bands, weights, fan-out, SDK code in Python and JS | [composition.md](references/composition.md) |
| Before and after pairs for common prompt shapes | [examples.md](references/examples.md) |

## Red flags

Stop and rework if you notice any of these:

- A question asks for a number, a count, a date comparison, or a sum.
- A Score's levels are `["1", "2", "3"]` or "low / medium / high".
- A Noul contains "and", or is phrased so that yes means the bad thing is absent.
- A Choice has no fallback and the inputs are open-ended.
- One request per question, or a second request whose state did not change.
- A summary or reply is being requested from Jev.
- Thresholds scattered through the code, or a Noul threshold applied to confidence.
- The package is missing a part, or the request was shown before it was validated.
