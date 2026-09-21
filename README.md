<div align="center">

# ⚡ prompt2jev

**Turn an LLM prompt into a TypeSafe Jev decision your code can branch on.**

[![Skill](https://img.shields.io/badge/skill-prompt2jev-7c3aed?style=flat-square)](#install) [![Archetypes](https://img.shields.io/badge/archetypes-5-0d9488?style=flat-square)](#catalog) [![Tests](https://github.com/sumleo/prompt2jev/actions/workflows/test.yml/badge.svg)](https://github.com/sumleo/prompt2jev/actions/workflows/test.yml) [![MIT](https://img.shields.io/badge/license-MIT-ea580c?style=flat-square)](LICENSE)

English · [简体中文](README.zh.md)

[Overview](#overview) · [Contents](#contents) · [Install](#install)

</div>

<a id="overview"></a>
## Overview

Jev judges; your code decides. This skill teaches a coding agent to take a prompt that
returns labels, scores, booleans, or JSON fields and rebuild it as typed
[TypeSafe Jev](https://docs.typesafe.ai) questions plus the code around them:

- **Convert:** a system prompt, a prompt template, or a plain-language requirement
  becomes a `state`, atomic `choice` / `score` / `noul` questions, and a constants block.
- **Verify:** a bundled, dependency-free CLI validates the request against the API
  contract and lints it against the TypeSafe docs' best practices before you see it.
- **Adapt:** five archetype requests cover routing, guardrails, rubrics, extraction,
  and claim checks; copy one and edit.

**New here?** [Give the install prompt to your agent](#install), then
[paste one of the usage prompts](#usage). You do not need to write JSON yourself.

<a id="contents"></a>
## Table of contents

| Get started | Explore | Go deeper |
|---|---|---|
| [📦 Install](#install) | [🧪 What goes in, what comes out](#io) | [🧯 Pitfalls the skill guards against](#pitfalls) |
| [🚀 How to use](#usage) | [🗂 Pick an archetype](#catalog) | [⚡ Two habits that make Jev useful](#habits) |
| [⌨️ Command line](#cli) | [📐 The conversion package](#package) | [🔗 Sources & credits](#credits) |

Works with Claude Code, Codex, OpenCode, Cursor, Gemini CLI, and any agent that reads
`SKILL.md` files.

<a id="install"></a>
## 📦 Install: give this to your agent

Paste this into **Claude Code, Codex, OpenCode, Cursor, or Gemini CLI**:

```text
Install the prompt2jev skill from
https://raw.githubusercontent.com/sumleo/prompt2jev/main/docs/install.md
into this project. Check my environment, install project-local, verify offline
with a dry run, and do not make a paid call.
```

Your agent copies the self-contained `skills/prompt2jev/` folder into the right place,
runs an offline dry run, and reports what still needs you (usually just an API key).
[Agent installation guide](docs/install.md)

<details>
<summary>Prefer to install it yourself?</summary>

**Claude Code plugin**

```bash
claude plugin marketplace add sumleo/prompt2jev
claude plugin install prompt2jev@prompt2jev
```

Invoke with `/prompt2jev:prompt2jev` or by asking to "use the prompt2jev skill".

**Other agents via skills.sh**

```bash
npx skills add sumleo/prompt2jev --skill prompt2jev
```

Pick your agent when prompted. Add `-g` for a user-wide install.

**Manual copy** of the whole `skills/prompt2jev/` folder:

| Agent | Project-local destination |
|---|---|
| Claude Code | `.claude/skills/prompt2jev/` |
| Codex | `.agents/skills/prompt2jev/` |
| OpenCode | `.opencode/skills/prompt2jev/` |
| Cursor | `.cursor/skills/prompt2jev/` |
| Gemini CLI | `.gemini/skills/prompt2jev/` |

**Optional command on PATH** (the script itself needs only Python 3.10+):

```bash
uv tool install git+https://github.com/sumleo/prompt2jev
# or: pipx install git+https://github.com/sumleo/prompt2jev
```

</details>

<a id="usage"></a>
## 🚀 Installed it? Here is how to use it

**Send one of these prompts to your agent.** Name the skill and point at the prompt
or the requirement; the agent does the digging.

### Convert a prompt that lives in your code

```text
Use the prompt2jev skill to convert the system prompt in src/triage.py into a Jev
decision. Keep the same downstream behavior. Validate the request before showing
it and do not make a live call yet.
```

### Convert a prompt you paste in

Replace the quoted text with your own:

```text
Use the prompt2jev skill to convert this LLM prompt into a Jev decision:
"Classify the support ticket into billing, shipping, or account. Set urgent=true
if the customer cannot use the product or has a deadline today. If they ask for a
refund, add refund=true. Output JSON only."
```

### Start from a requirement instead of a prompt

```text
Use the prompt2jev skill. I need to route incoming emails to sales, support, or
spam, and flag anything that mentions a contract renewal. Design the Jev decision
and the code that consumes it.
```

The agent first collects context (placeholders, the parser, the code that branches on
each output field, existing enums), asks only about gaps that change a question's
shape, and states the rest as assumptions.

<a id="package"></a>
### 📐 What you get back

Every conversion is a five-part package, in this order:

1. **Decision contract**: the decision, evidence unit, consumer of each answer, unknown path, success check.
2. **Split table**: every prompt instruction mapped to `choice`, `noul`, `score`, `code`, `keep-llm`, or `drop`.
3. **Request JSON** in the native `{model, state, questions}` shape, validated with `prompt2jev validate --strict` first.
4. **Composition code** in your project's language, with all thresholds and weights in one constants block.
5. **Assumptions and fixtures** to confirm and test before anything is automated.

For the ticket prompt above: the category becomes a Choice with an `other` fallback,
"urgent" and "refund" become Nouls with the prompt's own definitions moved into
`criteria`, the deadline check stays with the model but the JSON formatting rule is
dropped. The [playbook](skills/prompt2jev/references/playbook.md) walks through a full
example including the arithmetic and date rules that move into code.

<a id="catalog"></a>
### 🗂 Pick an archetype

| Your prompt does this… | Start from | What it shows |
|---|---|---|
| Classifies into a fixed set and flags a few things | `classify-route` | Intent Choice with fallback, speculative Nouls, a Score read on every branch |
| Screens messages against a list of rules | `checklist-guardrail` | One Noul per hazard plus a severity Score; precedence in code |
| Grades on a rubric or a 1 to 10 scale | `rubric-composite` | One Score per dimension, weights in code, a hard-rule Noul |
| Extracts values from text | `extract-select` | Candidates found by regex, a Choice over them with `not_stated` |
| Checks a claim against a source | `verify-claim` | Support Choice plus contextual Nouls; verbatim matching stays in code |

`prompt2jev template <name>` prints any of them; the files live in
[`skills/prompt2jev/assets/`](skills/prompt2jev/assets/). Each is a validated
request to copy, not a recorded model result.

<a id="cli"></a>
### ⌨️ Prefer the command line? (Optional)

The agent runs these for you; you can also run them yourself.

```bash
prompt2jev setup                                   # which keys are present; prints no values
prompt2jev template classify-route > request.json  # start from an archetype
prompt2jev validate request.json --strict          # contract check + best-practice lint
prompt2jev run request.json --dry-run              # print exactly what would be sent
prompt2jev run request.json                        # live call to TypeSafe (TYPESAFE_API_KEY)
prompt2jev run request.json --provider openrouter  # or through OpenRouter (OPENROUTER_API_KEY)
```

Without the command installed, replace `prompt2jev` with
`python3 skills/prompt2jev/scripts/prompt2jev.py`.

Exit codes: `0` success; `1` invalid request, lint failure under `--strict`, missing key,
or provider error. `run` prints the request, the raw response, and a per-question report
whose confidence bands are illustrative defaults for you to tune. A response that does
not match the documented contract is still printed in full before the error, so a paid
call is never lost. `--allow CODE` suppresses a lint code you have judged a false
positive for one request.

**Keys.** `TYPESAFE_API_KEY` from https://console.typesafe.ai/keys for the official API
(model `jev-latest`), or `OPENROUTER_API_KEY` from https://openrouter.ai/settings/keys
(model `typesafe/jev-1.13`). Set it in the environment that launches the agent or the
CLI; never paste it into chat, a request file, or a repository. Validation and dry runs
need no key. A live call costs money and sends the state to the provider.

<a id="io"></a>
## 🧪 What goes in, what comes out

The request below is the shape every conversion produces. The answer is the documented
example from the [TypeSafe quick start](docs/introduction/quickstart.md); this
repository has not made a live call.

| 📥 Input excerpt | 📤 Documented output |
|---|---|
| State: “Hi, I've been trying to connect my Stripe account for 3 days and the integration keeps failing. I'm losing sales. Please help ASAP.”<br />Questions: which team (`billing` / `technical` / `sales`), how frustrated (three described levels), is it urgent (Noul). | `department = technical`, probability `0.85`, confidence `0.78`<br />`frustration = 1.0 / 2` (“Frustrated but civil”), confidence `1.0`<br />`is_urgent = 1.0` |

<details>
<summary>The request, as the skill would write it</summary>

```json
{
  "model": "jev-latest",
  "state": {
    "ticket": {
      "text": "Hi, I've been trying to connect my Stripe account for 3 days and the integration keeps failing. I'm losing sales. Please help ASAP."
    }
  },
  "questions": {
    "department": {
      "type": "choice",
      "instructions": "Which team should handle `ticket.text`?",
      "criteria": {
        "billing": "Payment or subscription issues",
        "technical": "Bugs or integration problems",
        "sales": "Pricing or account questions",
        "other": "None of the listed teams fits."
      }
    },
    "frustration": {
      "type": "score",
      "instructions": "How frustrated does the customer appear in `ticket.text`?",
      "criteria": ["Calm, just stating facts", "Frustrated but civil", "Very angry, strong language"]
    },
    "is_urgent": {
      "type": "noul",
      "instructions": "Does `ticket.text` convey urgency or time-sensitivity?"
    }
  }
}
```

`prompt2jev run` wraps the raw answers in a report: the chosen option, its probability,
the margin over the runner-up, the confidence band, the nearest Score level and its
text, and a yes / uncertain / no band for each Noul. A `noul` value is P(yes) even when
the band says no; a Score such as `1.0 / 2` is a position on your levels, not a
probability.

</details>

<a id="habits"></a>
## ⚡ Two habits that make Jev useful

- **Split the prompt, then ask everything at once.** One judgment per question, every
  independent question in the same request, speculative ones included. Questions run in
  parallel and cannot see each other's answers; a second request is only for state that
  depends on a first answer.
- **Keep the rules in code.** Arithmetic, dates, counting, thresholds, and exact matching
  never go to the model. Extraction becomes selection over candidates code found.
  Thresholds live in one constants block and scale with the cost of a wrong action.

<a id="pitfalls"></a>
## 🧯 Pitfalls the skill guards against

Each row is a rule from the TypeSafe docs, the failure it prevents, and how this repo
enforces it.

| Rule | Failure it prevents | Enforced by |
|---|---|---|
| Full list of options plus a fallback such as `other` | The model is forced to pick a wrong label | lint `choice-no-fallback` |
| Score levels describe situations, 2 to 10 of them | Bare numbers give the model nothing to match | lint `score-numeric-levels`, `score-degree-only` |
| One proposition per Noul, high value means yes | Compound or inverted questions read backwards in code | lint `noul-compound`, `noul-negated` |
| Numbers, dates, and counts stay in code | Jev is not a calculator | lint `math-in-question`, playbook split table |
| Full question in `instructions`; ids are not sent | The id was doing the work | lint `instructions-too-short` |
| State holds only what the questions use, referenced by backticked path | Unrelated detail lowers accuracy | lint `state-field-unreferenced`, `state-too-large` |
| Pin a versioned model once thresholds are tuned | `jev-latest` moves between releases | lint `model-alias` (info) |
| Confidence bands scaled by risk; Noul thresholds are separate | One number used for every action | SKILL.md Step 5, `references/composition.md` |

Every lint rule is a heuristic with a documented `--allow` escape hatch. The full rule
set with sources is in [question-design.md](skills/prompt2jev/references/question-design.md).

<a id="layout"></a>
## 🧭 Where things live

```
skills/prompt2jev/
  SKILL.md              the skill (what to deliver, six steps, red flags)
  references/           playbook, question design, API contract, composition, examples
  assets/               five validated archetype requests
  scripts/prompt2jev.py validator, linter, runner (Python standard library only)
docs/                   TypeSafe docs mirror the references were written from
docs/install.md         the agent-driven install guide
tests/                  unittest suite: python3 -m unittest discover -s tests -v
```

<a id="credits"></a>
## 🔗 Sources & credits

- [TypeSafe docs](https://docs.typesafe.ai): the API contract, primitives, confidence,
  patterns, and the jev-1.13 jaggedness page the rules come from. A mirror is in `docs/`.
- [typesafe-ai/skills](https://github.com/typesafe-ai/skills): the official TypeSafe agent
  skill; use it alongside this one when building a new integration from scratch.
- [wuyoscar/jev-skill](https://github.com/wuyoscar/jev-skill): the collection whose repo
  layout, install flow, and README shape this project follows.

[MIT](LICENSE).
