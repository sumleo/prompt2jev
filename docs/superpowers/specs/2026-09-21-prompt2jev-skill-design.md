# prompt2jev skill design

Date: 2026-09-21. Status: approved for implementation under the `/goal` autonomous directive.

## Goal

Ship one installable agent skill, `prompt2jev`, that a coding agent (Claude Code, Codex, OpenCode, Cursor, Gemini CLI, Copilot) loads when a user asks it to convert an LLM prompt, or a plain-language decision requirement, into a TypeSafe Jev decision. The skill must follow the best practices in the TypeSafe docs (mirrored under `docs/`), work out of the box with no dependencies beyond Python 3.10, and be easy to store: one folder, copyable, versioned, with a plugin manifest and an install prompt.

The repo layout mirrors the reference repo `wuyoscar/jev-skill` (skills/, docs/, tests/, pyproject, CI, agent install guide), reduced to a single skill.

## Input contract

The skill's input is a user query in one of these shapes:

1. An LLM prompt (system prompt, prompt template, prompt-and-parse step, judge or router prompt) plus, optionally, the code that consumes its output.
2. A plain-language requirement ("classify tickets by team and flag refunds", "grade essays on three rubrics").
3. A pointer into a codebase ("convert the classifier in `triage.py`").

If the query is clear, convert it. If it is unclear, the agent first digs: find the prompt, its input placeholders, the parser, the code that branches on the output, existing label sets or enums, and tests. Only then ask the user, one question at a time, and only about gaps that change the decision shape (label set, stakes, what the code does with each answer). Gaps that do not change the shape become stated assumptions in the output.

## Output contract: the conversion package

The skill produces these parts, in this order. Every part is required.

1. **Decision contract** (5 lines): decision, evidence unit, consumer of each answer, unknown path, success check.
2. **Split table**: each fragment of the original prompt mapped to one of: `choice` question, `noul` question, `score` question, `code` (arithmetic, dates, counting, exact matching, thresholds), `keep-LLM` (generation such as summaries or replies), or `drop` (formatting instructions that no longer apply).
3. **Request JSON**: `{model, state, questions}` in the native TypeSafe shape, with `jev-latest` as the model, a named-field object state, and one request holding every independent question (speculative ones included).
4. **Composition code**: constants block (thresholds, weights, hard-exclusion rules) in one place, then a function that calls the API through the official SDK (Python by default, JavaScript when the project is JS) and branches on answers. Confidence bands scale with the stakes of each action.
5. **Assumptions and open questions**: what was assumed, what the user should confirm, and which fixtures to test (positive, negative, ambiguous, missing evidence, adversarial).

The request JSON is saved to a file and validated with the bundled script before it is shown.

## Conversion rules (from the docs)

These are the rules the skill body and the linter encode. Source pages are in `docs/`.

- One judgment per question. Compound conditions become several questions combined in code. (primitives, how-to-build)
- Question IDs are not sent to the model. The full question lives in `instructions`. (primitives)
- State is a named JSON object with only the fields the questions need. Reference fields from instructions with backticked paths such as `` `ticket.text` ``. (state, how-to-build)
- Choice: full option list, descriptive criteria that separate neighbours, an `other` or `none` option when the list may not cover every input, up to 255 options. Use contrastive objects (`what`, `not_for`, `examples`) for confusable labels. (choice, advanced)
- Score: 2 to 10 levels, each a concrete situation, one dimension per question, never bare numbers. (score)
- Noul: one yes/no proposition, phrased so a high value means yes, no negations, optional `true`/`false` criteria aligned with the question. (noul)
- Everything code can compute exactly stays in code: arithmetic, comparisons, dates, counting, thresholds, regex extraction. Extraction becomes selection over candidates found in code. (jaggedness)
- Ask all independent questions in one request; a second request only when its state depends on a first answer. (fan-out, primitives)
- Thresholds are constants in code, scaled by risk, with a low-confidence floor that routes to a person. Noul thresholds and Choice confidence thresholds are not interchangeable. (confidence, jaggedness)
- Pin a versioned model ID once thresholds are tuned; `jev-latest` moves. (models)
- Generation, summaries, and free text stay with a generative model. (jaggedness)
- English is the best-supported language; non-English workloads need their own test. (models)

## Repository layout

```
prompt2jev/
  README.md                       # overview, install, usage, example prompts
  LICENSE                         # MIT
  pyproject.toml                  # console script `prompt2jev`, no dependencies
  .gitignore
  .github/workflows/test.yml      # unittest on 3.10 / 3.12 / 3.14 + dry-run of assets
  .claude-plugin/plugin.json      # Claude Code plugin manifest
  .claude-plugin/marketplace.json
  docs/                           # TypeSafe docs mirror (existing, unchanged)
  docs/install.md                 # copyable install prompt + agent install steps
  docs/superpowers/specs/         # this spec
  skills/prompt2jev/
    SKILL.md                      # the skill (under 300 lines)
    references/
      playbook.md                 # step-by-step conversion method with a worked example
      question-design.md          # rules per primitive, anti-patterns, jaggedness table
      api.md                      # request/response contract, endpoints, models, limits, errors
      composition.md              # code patterns: bands, weights, fan-out, SDK snippets py/js
      examples.md                 # before (prompt) / after (request + code) pairs
    assets/
      classify-route.json         # intent routing with speculative fan-out
      checklist-guardrail.json    # Noul battery + severity Score
      rubric-composite.json       # several Scores combined with weights
      extract-select.json         # selection over pre-parsed candidates
      verify-claim.json           # citation / claim support check
    scripts/
      prompt2jev.py               # stdlib CLI
  tests/
    test_prompt2jev.py            # validator, linter, report, retry, CLI
    test_skill.py                 # skill files, frontmatter, links, assets validate clean
```

## The CLI (`scripts/prompt2jev.py`)

Standard library only, Python 3.10+. Commands:

- `validate <request.json> [--strict]`: schema validation against the documented contract, then best-practice lint. Prints the normalized request. Exit 0 when valid; lint warnings go to stderr; `--strict` turns warnings into exit 1.
- `run <request.json> [--provider typesafe|openrouter] [--model ID] [--dry-run] [--timeout S] [--output FILE]`: sends the request and prints the raw response plus a per-question report. `--dry-run` validates and prints the request without a network call.
- `template <archetype>`: prints a bundled asset (`classify-route`, `checklist-guardrail`, `rubric-composite`, `extract-select`, `verify-claim`) as a starting point.
- `setup`: reports key presence (never values) and the provider each key enables.

Lint checks (warnings unless noted):

| Check | Trigger |
|---|---|
| `choice-no-fallback` | Choice with no option named `other`, `none`, `unknown`, `not_stated`, `insufficient_evidence`, `none_of_the_above`, or `not_applicable` |
| `score-numeric-levels` | Any Score level whose text is only digits or a bare number word |
| `score-degree-only` | Score level shorter than 12 characters (for example "Low", "High") |
| `noul-compound` | Noul instructions containing " and " or " or " between two clauses |
| `noul-negated` | Noul instructions containing "not ", "free of", "without", "no " as the main verb phrase |
| `instructions-too-short` | Instructions under 12 characters, or a single word |
| `state-field-unreferenced` | Object state with 2+ top-level fields, and no question references any field by backticked path (soft) |
| `state-too-large` | Estimated tokens of state above 30,000 (4 chars per token) |
| `math-in-question` | Instructions containing "sum", "count how many", "days since", "more than \d+", "greater than", "less than", "percent" |
| `criteria-mismatch` | Noul criteria keys other than exactly `true` and `false` (error) |
| `model-alias` | Model is `jev-latest` or `jev-preview` (info: pin once thresholds are tuned) |

Run report per question: type, value (`choice` / rounded `score` / `noul`), top probability, confidence (Choice and Score), and a band (`high`, `medium`, `low`) from illustrative defaults (0.8 and 0.5 for confidence, 0.8 and 0.2 for Noul) that the report labels as defaults to be tuned. The report never treats a value as permission to act.

Network: TypeSafe endpoint `https://api.typesafe.ai/v1/systemone` with `TYPESAFE_API_KEY`; OpenRouter endpoint `https://openrouter.ai/api/alpha/decisions` with `OPENROUTER_API_KEY` and model `typesafe/jev-1.13`. Bounded retry (3 attempts, exponential backoff, honours `retry-after`) on 429 and 529 only, matching the API reference. No retry on 401 or 422. Keys are read from the environment only and never printed.

## SKILL.md structure

Frontmatter: `name: prompt2jev`, third-person `description` limited to triggering conditions, `license: MIT`, `metadata.requirements`.

Body sections, in order: what you produce (the package, as a recipe), when to dig versus ask, the split step with a mapping table, the state step, the question-writing rules, fan-out, composition, validate and test, running (keys, providers, CLI), reference router table, red flags. Target under 300 lines so it loads cheaply; heavy material lives in `references/`.

## Tests

- Validator accepts every bundled asset; every asset passes lint with zero warnings other than `model-alias`.
- Each lint rule fires on a crafted bad request and stays silent on a good one.
- Report reads Choice, Score, Noul answers and rejects malformed responses (missing answer, probabilities not summing to 1, choice not the arg-max, score out of range).
- `run --dry-run` from a copied skill directory works with no key and no network (urlopen patched to fail).
- Retry: 429 with `retry-after` is retried and succeeds; 401 is not retried.
- `template` prints valid JSON for each archetype.
- Skill files: SKILL.md frontmatter parses, `name` matches folder, every relative link resolves, README and install guide mention the skill and the CLI commands.

## Install surfaces

- Claude Code plugin: `claude plugin marketplace add <owner>/prompt2jev` then `claude plugin install prompt2jev@prompt2jev`.
- skills.sh: `npx skills add <owner>/prompt2jev --skill prompt2jev`.
- Manual: copy `skills/prompt2jev/` into `.claude/skills/`, `.agents/skills/` (Codex), or `.opencode/skills/`.
- CLI: `uv tool install .` or `pipx install .` gives `prompt2jev`; the bundled script also runs with `python3` alone.
- `docs/install.md` carries a paste-into-agent install prompt like the reference repo's.

## Validation of the skill itself

Following the writing-skills method: a baseline subagent converts a realistic triage prompt without the skill. Its failures (expected: compound questions, numeric levels, arithmetic sent to the model, no fallback option, invented fields) are recorded and addressed in the skill body and the linter. The same task is rerun with the skill installed; the result must pass `validate --strict` and match the package contract.

## Out of scope

- Multiple scenario skills, community catalogues, evals against live models, calibration studies.
- Any simulation mode that fakes Jev output. When no key is present the skill stops at a validated request and tells the user how to get a key.
- Changing the agent's own model, editing shell profiles, or storing keys.
