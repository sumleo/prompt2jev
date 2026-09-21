# prompt2jev

An agent skill that converts an LLM prompt, or a plain-language decision
requirement, into a [TypeSafe Jev](https://docs.typesafe.ai) decision: a typed
`state`, atomic `choice` / `score` / `noul` questions, and the code that consumes the
answers. It follows the TypeSafe docs' best practices and ships with a
dependency-free validator, linter, and runner.

Works with Claude Code, Codex, OpenCode, Cursor, Gemini CLI, and any agent that
reads `SKILL.md` files.

## What it does

Give your agent a prompt like this:

```text
You are a support triage assistant. Return JSON with category (billing, shipping,
account, bug, feature_request), urgency 1-5, refund_requested (true/false),
escalate=true if a refund is requested and the amount is over 100 USD and the
purchase is older than 30 days, and a one-sentence summary.
```

With the skill, the agent delivers a five-part **conversion package**:

1. **Decision contract**: the decision, evidence unit, consumers, unknown path, success check.
2. **Split table**: every prompt instruction mapped to `choice`, `noul`, `score`, `code`, `keep-llm`, or `drop`.
3. **Request JSON** in the native `{model, state, questions}` shape, validated before it is shown.
4. **Composition code** with all thresholds and weights in one constants block.
5. **Assumptions and fixtures** to confirm and test before automating.

For the prompt above: `category` becomes a Choice with an `other` fallback, urgency a
five-level Score with described situations, `refund_requested` a Noul, the amount and
date comparisons stay in code, and the summary stays with a generative model. See
[the worked example](skills/prompt2jev/references/playbook.md#worked-example-support-triage-prompt).

## Install

### Claude Code plugin

```bash
claude plugin marketplace add sumleo/prompt2jev
claude plugin install prompt2jev@prompt2jev
```

Invoke with `/prompt2jev:prompt2jev` or by asking to "use the prompt2jev skill".

### Other agents via skills.sh

```bash
npx skills add sumleo/prompt2jev --skill prompt2jev
```

Pick your agent when prompted. Add `-g` for a user-wide install.

### Manual copy

Copy the whole `skills/prompt2jev/` folder (it is self-contained) into your agent's
skills directory:

| Agent | Project-local destination |
|---|---|
| Claude Code | `.claude/skills/prompt2jev/` |
| Codex | `.agents/skills/prompt2jev/` |
| OpenCode | `.opencode/skills/prompt2jev/` |
| Cursor | `.cursor/skills/prompt2jev/` |
| Gemini CLI | `.gemini/skills/prompt2jev/` |

### Let your agent install it

Paste into your coding agent:

```text
Install the prompt2jev skill from
https://raw.githubusercontent.com/sumleo/prompt2jev/main/docs/install.md
into this project. Check my environment, install project-local, verify offline
with a dry run, and do not make a paid call.
```

### CLI (optional)

The skill's script runs with Python 3.10+ and nothing else. To get a `prompt2jev`
command on PATH:

```bash
uv tool install git+https://github.com/sumleo/prompt2jev
# or: pipx install git+https://github.com/sumleo/prompt2jev
```

## Use

Ask your agent, naming the skill:

```text
Use the prompt2jev skill to convert the system prompt in src/triage.py into a Jev
decision. Keep the same downstream behaviour.
```

```text
Use the prompt2jev skill. I need to route incoming emails to sales, support, or
spam, and flag anything that mentions a contract renewal. Design the Jev decision.
```

```text
Use the prompt2jev skill to turn this grading prompt into Jev questions: "Grade the
essay 1-10 on argument, evidence, and clarity."
```

The agent digs for context first (placeholders, the parser, the code that branches on
the output, existing enums), asks only about gaps that change a question's shape, and
otherwise states its assumptions.

## CLI

```bash
prompt2jev setup                                   # which keys are present; prints no values
prompt2jev template classify-route > request.json  # start from an archetype
prompt2jev validate request.json --strict          # contract + best-practice lint
prompt2jev run request.json --dry-run              # print the request that would be sent
prompt2jev run request.json                        # live call to TypeSafe (TYPESAFE_API_KEY)
prompt2jev run request.json --provider openrouter  # or through OpenRouter (OPENROUTER_API_KEY)
```

Without the CLI installed, replace `prompt2jev` with
`python3 skills/prompt2jev/scripts/prompt2jev.py`.

Exit codes: `0` success, `1` invalid request, lint failure under `--strict`, missing
key, or provider error. `run` prints the request, the raw response, and a per-question
report with illustrative confidence bands that you are expected to tune.

Archetypes for `template`: `classify-route`, `checklist-guardrail`,
`rubric-composite`, `extract-select`, `verify-claim`.

Lint checks: missing fallback option on a Choice, numeric or degree-only Score
levels, compound or negated Nouls, arithmetic or date logic inside a question,
instructions too short to stand alone, state fields no question references, state
over the model's budget, and a moving model alias.

## Keys

- `TYPESAFE_API_KEY` from https://console.typesafe.ai/keys for the official API
  (`https://api.typesafe.ai/v1/systemone`, model `jev-latest`).
- `OPENROUTER_API_KEY` from https://openrouter.ai/settings/keys as an alternative
  (model `typesafe/jev-1.13`).

Set the key in the environment that launches the agent or the CLI. Never paste it
into chat, a request file, or a repository. Validation and dry runs need no key; a
live call costs money and sends the state to the provider.

## Best practices the skill enforces

- One judgment per question; compound rules split and recombined in code.
- The question id is not sent to the model; the full question lives in `instructions`.
- State is a named JSON object holding only what the questions need, referenced with backticked paths.
- Choice: every option described, a fallback such as `other` when inputs are open-ended.
- Score: 2 to 10 levels, each a concrete situation, one dimension per question.
- Noul: one proposition, high value means yes, no negations.
- Arithmetic, counting, dates, and thresholds stay in code; extraction becomes selection over candidates.
- All independent questions in one request; a second request only when its state depends on a first answer.
- Confidence bands scaled by the stakes of each action; constants in one block.
- Pin a versioned model id once thresholds are tuned; log the response's `model`.

## Repository layout

```
skills/prompt2jev/
  SKILL.md              the skill
  references/           playbook, question design, API contract, composition, examples
  assets/               five validated archetype requests
  scripts/prompt2jev.py validator, linter, runner (stdlib only)
docs/                   TypeSafe docs mirror used to write the references
docs/install.md         agent-driven install guide
tests/                  unittest suite
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## License

[MIT](LICENSE).
