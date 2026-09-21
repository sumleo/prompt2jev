# API contract

The request and response shapes the conversion targets, plus models, limits, and
errors. Checked against the TypeSafe docs mirrored on 2026-09-20 and against live
calls through `typesafe-sdk` 0.7.0, `@typesafe-ai/sdk` 0.6.0, and plain HTTP on
2026-09-21; the live docs at https://docs.typesafe.ai/api.md win when they differ.

## Contents

- Endpoint and auth
- Request
- Response
- Models, price, limits
- Errors and retries
- SDK quick shapes
- curl

## Endpoint and auth

```http
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer <TYPESAFE_API_KEY>
Content-Type: application/json
```

`TYPESAFE_BASE_URL` overrides the host for both SDKs and for the code
`prompt2jev code` writes (useful for a local stub in tests).

OpenRouter also serves Jev, with the same request body, at
`POST https://openrouter.ai/api/alpha/decisions` using `OPENROUTER_API_KEY` and the
model id `typesafe/jev-1.13`. The bundled CLI selects it with `--provider openrouter`
and rewrites the known model ids. OpenRouter's own limits, pricing, and response
metadata apply there and are not covered by the TypeSafe docs; check its model page.

## Request

```json
{
  "model": "jev-latest",
  "state": "string | object | array",
  "questions": {
    "<id you choose>": {"type": "choice | score | noul", "instructions": "...", "criteria": "..."}
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `model` | string | `jev-latest`, `jev-preview`, or a versioned id such as `jev-1.13.0` |
| `state` | string, object, or array | Text only. Use an object with named fields for anything with parts |
| `questions` | map of id to question | Ids are yours; answers come back under them; ids are not sent to the model |

Per question:

| Type | `instructions` | `criteria` |
|---|---|---|
| `choice` | string, object, or array | required map of option name to description (string, object, array, or `null`); 2 to 255 options |
| `score` | string, object, or array | required ordered array of level descriptions (string, object, or array); 2 to 10 levels |
| `noul` | string, object, or array | optional object with `true` and `false` descriptions |

An `instructions` object puts the question in one field and its supporting data in
others; refer to those fields by name in backticks, the same way you point at a
nested `state` value.

## Response

```json
{
  "model": "jev-1.13.0",
  "answers": {"<id>": {"type": "...", "...": "..."}},
  "usage": {"input_tokens": 392, "output_tokens": 65}
}
```

| Type | Answer fields | Reading |
|---|---|---|
| `choice` | `choice`, `probabilities`, `confidence` | `choice` is the highest-probability option; `probabilities` sums to 1 over your options |
| `score` | `score`, `legend`, `probabilities`, `confidence` | `score` is the probability-weighted level index and can fall between levels; `legend` and `probabilities` are keyed by the string index `"0"`, `"1"`, ... |
| `noul` | `noul` | Probability of yes, 0 to 1. No confidence field |

`confidence` is computed from the spread of `probabilities`: concentrated on one
option means high, spread out means low. The full distribution is returned so you
can use a different measure if you need one. `model` is the versioned id that
answered; log it.

## Models, price, limits

| | `jev-1.13.0` |
|---|---|
| Aliases | `jev-latest` and `jev-preview` both point here today |
| Price | $0.042 per million input tokens; output tokens are free |
| Rate limits | 250,000 tokens per second and 1,200 requests per minute, adjusting dynamically |
| Context | 64k tokens per request for state plus all questions; 32k for state plus the longest question |
| Input | Text only: string, object, or array of text. Preprocess images, audio, and binaries in code |
| Language | English is primary; other languages work with lower accuracy, so test them |

Aliases move when a release ships. Pin the versioned id once thresholds are tuned.
`GET /v1/models` lists the names your account can send.

## Errors and retries

| Status | Meaning | Action |
|---|---|---|
| 401 | Missing or invalid key | Fix the environment; do not retry |
| 422 | Request failed validation; body names the field | Re-run `prompt2jev validate`; do not retry unchanged |
| 429 | Rate limit exceeded | Exponential backoff; honour `retry-after` |
| 529 | Temporarily overloaded | Exponential backoff |

The official SDKs retry by default with backoff and honour `Retry-After`: the
Python and JavaScript clients retry 408, 429, and every 5xx status, plus connection
and timeout errors. The bundled CLI is narrower: up to three attempts on 429 and
529 only, and it surfaces the provider's error body (truncated) on anything else.

## SDK quick shapes

`prompt2jev code request.json --lang python|javascript` writes a complete program in
these shapes from a validated request; the snippets below are the call and the reads.

Python (`pip install typesafe-sdk`, reads `TYPESAFE_API_KEY`, defaults to `jev-latest`):

```python
from typesafe_sdk import Choice, Noul, NoulCriteria, Score, TypeSafeClient

with TypeSafeClient() as client:
    response = client.system_one(
        state={"ticket": {"text": "My card was charged twice."}},
        questions={
            "team": Choice(instructions="Which team should handle `ticket.text`?",
                           criteria={"billing": "Charges and refunds", "other": "Anything else"}),
            "frustration": Score(instructions="How frustrated does the customer appear in `ticket.text`?",
                                 criteria=["Calm and matter-of-fact", "Frustrated but civil", "Very angry"]),
            "refund": Noul(instructions="Does `ticket.text` ask for money back?",
                           criteria=NoulCriteria(true="Asks for a refund or credit", false="Does not")),
        },
    )
answers = response.answers
answers["team"].choice, answers["team"].confidence, answers["team"].probabilities
answers["frustration"].score, answers["frustration"].legend
answers["refund"].noul
response.model, response.usage
```

`response.answers` is a plain dict of typed answers; `response.choices`,
`response.scores`, and `response.nouls` are the same answers filtered by type. The
Python SDK keys Score `probabilities` and `legend` by integer level (raw HTTP and the
JavaScript SDK use the string index). Async use is `AsyncTypeSafeClient` with
`await client.system_one(...)`.

JavaScript (`npm install @typesafe-ai/sdk`, Node 20+):

```ts
import { choice, noul, score, TypeSafeClient } from "@typesafe-ai/sdk";

const client = new TypeSafeClient();
const response = await client.systemOne({
  state: { ticket: { text: "My card was charged twice." } },
  questions: {
    team: choice("Which team should handle `ticket.text`?", { billing: "Charges and refunds", other: "Anything else" }),
    frustration: score("How frustrated does the customer appear in `ticket.text`?",
      ["Calm and matter-of-fact", "Frustrated but civil", "Very angry"]),
    refund: noul("Does `ticket.text` ask for money back?"),
  },
});
response.answers.team.choice;        // typed from the question
response.answers.frustration.score;
response.answers.refund.noul;
```

## curl

```bash
curl -sS https://api.typesafe.ai/v1/systemone \
  -H "Authorization: Bearer $TYPESAFE_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @request.json
```

`prompt2jev code request.json --lang curl` writes this command with the request
embedded, and `--lang python-stdlib` is the same request as a dependency-free Python
program with bounded retries: the two references for a language without an SDK. The
bundled CLI does the same call with validation, lint, a report, and bounded retries:
`prompt2jev run request.json`.
