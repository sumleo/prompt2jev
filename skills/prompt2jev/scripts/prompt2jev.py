#!/usr/bin/env python3
"""Validate, lint, and run TypeSafe Jev requests written by the prompt2jev skill.

Standard library only. Python 3.10+. Commands: validate, run, template, setup.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

VERSION = "0.1.0"

PROVIDERS = {
    "typesafe": {"url": "https://api.typesafe.ai/v1/systemone", "env": "TYPESAFE_API_KEY",
                 "model": "jev-latest"},
    "openrouter": {"url": "https://openrouter.ai/api/alpha/decisions", "env": "OPENROUTER_API_KEY",
                   "model": "typesafe/jev-1.13"},
}
# A request written for one provider can run on the other; only these known ids are rewritten.
MODEL_ALIASES = {
    "openrouter": {"jev-latest": "typesafe/jev-1.13", "jev-1.13.0": "typesafe/jev-1.13"},
    "typesafe": {"typesafe/jev-1.13": "jev-1.13.0"},
}
MOVING_ALIASES = {"jev-latest", "jev-preview"}
QUESTION_TYPES = ("choice", "score", "noul")
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
ARCHETYPES = ("classify-route", "checklist-guardrail", "rubric-composite", "extract-select", "verify-claim")


class RequestError(ValueError):
    """The request does not match the documented TypeSafe contract."""


class ResponseError(ValueError):
    """The provider returned something the contract does not allow."""


class TransportError(RuntimeError):
    """A network or HTTP failure. Never carries the API key or the provider body."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


# ----- JSON helpers -----

def _reject_constant(value):
    raise RequestError(f"Non-finite JSON number: {value}")


def load_json(text: str):
    return json.loads(text, parse_constant=_reject_constant)


def read_json(path: str):
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return load_json(text)


def _is_entry(value) -> bool:
    """instructions and criteria descriptions: nonempty string, object, or array."""
    return isinstance(value, (dict, list)) or (isinstance(value, str) and bool(value.strip()))


# ----- Request validation (the documented contract) -----

def validate_request(payload) -> dict:
    if not isinstance(payload, dict):
        raise RequestError("Request must be a JSON object with model, state, and questions")
    extra = set(payload) - {"model", "state", "questions"}
    if extra:
        raise RequestError(f"Unsupported top-level fields {sorted(extra)}; use only model, state, questions")
    if not isinstance(payload.get("state"), (str, dict, list)):
        raise RequestError("state must be a string, a JSON object, or an array")
    if not isinstance(payload.get("model"), str) or not payload["model"].strip():
        raise RequestError("model must be a nonempty string such as jev-latest")
    questions = payload.get("questions")
    if not isinstance(questions, dict) or not questions:
        raise RequestError("questions must be a nonempty object keyed by question id")
    for qid, question in questions.items():
        if not isinstance(qid, str) or not qid.strip():
            raise RequestError("Every question id must be a nonempty string")
        if not isinstance(question, dict):
            raise RequestError(f"{qid}: question must be an object")
        extra = set(question) - {"type", "instructions", "criteria"}
        if extra:
            raise RequestError(f"{qid}: unsupported fields {sorted(extra)}; use type, instructions, criteria")
        kind = question.get("type")
        if kind not in QUESTION_TYPES:
            raise RequestError(f"{qid}: type must be one of {', '.join(QUESTION_TYPES)}")
        if not _is_entry(question.get("instructions")):
            raise RequestError(f"{qid}: instructions must be a nonempty string, object, or array")
        criteria = question.get("criteria")
        if kind == "choice":
            if not isinstance(criteria, dict) or not 2 <= len(criteria) <= 255:
                raise RequestError(f"{qid}: choice criteria must map 2 to 255 option names to descriptions")
            for label, description in criteria.items():
                if not isinstance(label, str) or not label.strip():
                    raise RequestError(f"{qid}: choice option names must be nonempty strings")
                if description is not None and not _is_entry(description):
                    raise RequestError(f"{qid}: option {label!r} needs a string, object, array, or null description")
        elif kind == "score":
            if not isinstance(criteria, list) or not 2 <= len(criteria) <= 10:
                raise RequestError(f"{qid}: score criteria must be an ordered array of 2 to 10 level descriptions")
            if not all(_is_entry(level) for level in criteria):
                raise RequestError(f"{qid}: every score level needs a nonempty string, object, or array")
        elif "criteria" in question:
            if not isinstance(criteria, dict) or set(criteria) != {"true", "false"}:
                raise RequestError(f"{qid}: noul criteria must have exactly the keys true and false")
            if not all(_is_entry(value) for value in criteria.values()):
                raise RequestError(f"{qid}: noul criteria true and false need nonempty descriptions")
    try:
        json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise RequestError("Request must contain only finite, JSON-compatible values") from error
    return payload


# ----- Best-practice lint (distilled from the TypeSafe docs) -----

FALLBACK_PREFIXES = ("other", "none", "unknown", "not_", "no_", "insufficient", "unclear", "ask_")
STATE_TOKEN_LIMIT = 30_000
NUMBER_WORDS = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"}
MATH_PATTERN = re.compile(
    r"\b(how many|count|sum of|total of|days since|days ago|weeks ago|older than|newer than|"
    r"more than \d+|greater than|less than|at least \d+|at most \d+|percent|average|difference between|"
    r"before \d+|after \d+)\b|%",
    re.IGNORECASE,
)
NEGATION_PATTERN = re.compile(r"\b(not|no|never|without|free of|lacks?|absent)\b", re.IGNORECASE)
COMPOUND_PATTERN = re.compile(r"\sand\s", re.IGNORECASE)


def _question_text(instructions) -> str:
    """The natural-language question inside instructions, for wording checks."""
    if isinstance(instructions, str):
        return instructions
    if isinstance(instructions, dict):
        for key in ("question", "instructions", "ask"):
            if isinstance(instructions.get(key), str):
                return instructions[key]
        return " ".join(value for value in instructions.values() if isinstance(value, str))
    return " ".join(value for value in instructions if isinstance(value, str))


def _all_text(value) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def estimate_tokens(value) -> int:
    return math.ceil(len(_all_text(value)) / 4)


def _has_fallback(criteria: dict) -> bool:
    return any(label.lower().startswith(FALLBACK_PREFIXES) for label in criteria)


def _is_numeric_level(level) -> bool:
    if not isinstance(level, str):
        return False
    text = level.strip().lower()
    return bool(re.fullmatch(r"[\d.+-]+", text)) or text in NUMBER_WORDS


def lint_request(payload: dict) -> list[dict]:
    """Best-practice checks from the TypeSafe docs. Returns findings; never raises."""
    findings: list[dict] = []

    def add(code, message, question=None, level="warning"):
        findings.append({"code": code, "level": level, "question": question, "message": message})

    if payload.get("model") in MOVING_ALIASES:
        add("model-alias", f"{payload['model']} moves with releases; pin a versioned id such as "
            "jev-1.13.0 once thresholds are tuned.", level="info")
    state = payload["state"]
    if estimate_tokens(state) > STATE_TOKEN_LIMIT:
        add("state-too-large", "state is above roughly 30k tokens; filter in code to the fields the "
            "questions need.")
    top_keys = list(state) if isinstance(state, dict) else []
    referenced = False
    for qid, question in payload["questions"].items():
        kind = question["type"]
        text = _question_text(question["instructions"]).strip()
        if any(f"`{key}" in _all_text(question["instructions"]) for key in top_keys):
            referenced = True
        if len(text) < 12 or " " not in text:
            add("instructions-too-short", "write the complete question in instructions; the id is not "
                "sent to the model.", qid)
        if MATH_PATTERN.search(text):
            add("math-in-question", "arithmetic, counting, dates, and numeric comparisons belong in "
                "code; ask only the semantic part.", qid)
        if kind == "choice":
            if not _has_fallback(question["criteria"]):
                add("choice-no-fallback", "add an option such as other or not_stated so the model can "
                    "say nothing fits.", qid)
        elif kind == "score":
            levels = question["criteria"]
            if any(_is_numeric_level(level) for level in levels):
                add("score-numeric-levels", "levels must describe situations; bare numbers give the "
                    "model nothing to match.", qid)
            elif any(isinstance(level, str) and len(level.strip()) < 10 for level in levels):
                add("score-degree-only", "describe each level as a concrete situation, not a degree "
                    "word.", qid)
        else:
            if COMPOUND_PATTERN.search(text):
                add("noul-compound", "a noul judges one proposition; 'and' suggests two conditions, "
                    "split them.", qid)
            if NEGATION_PATTERN.search(text):
                add("noul-negated", "phrase the question so a high value means yes; avoid negations.", qid)
    if len(top_keys) >= 2 and not referenced:
        add("state-field-unreferenced", "state has several fields but no question names one with a "
            "backticked path such as `ticket.text`.")
    return findings


# ----- Response validation and run report -----

# Illustrative defaults for the run report. Tune on held-out data; a band is never permission to act.
THRESHOLDS = {"confidence_high": 0.8, "confidence_low": 0.5, "noul_yes": 0.8, "noul_no": 0.2}


def _number(value, low, high, name):
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            or not low <= value <= high):
        raise ResponseError(f"{name} must be a finite number in [{low}, {high}]")
    return value


def _distribution(answer: dict, labels, qid: str) -> dict:
    probabilities = answer.get("probabilities")
    if not isinstance(probabilities, dict) or set(probabilities) != set(labels):
        raise ResponseError(f"{qid}: probabilities must cover exactly the request's options")
    for value in probabilities.values():
        _number(value, 0, 1, f"{qid} probability")
    if not math.isclose(sum(probabilities.values()), 1, abs_tol=0.02 + 0.001 * len(probabilities)):
        raise ResponseError(f"{qid}: probabilities must sum to 1")
    _number(answer.get("confidence"), 0, 1, f"{qid} confidence")
    return probabilities


def validate_response(payload: dict, response) -> dict:
    if not isinstance(response, dict) or not isinstance(response.get("answers"), dict):
        raise ResponseError("response must be an object with an answers map")
    answers = response["answers"]
    for qid, question in payload["questions"].items():
        answer = answers.get(qid)
        kind = question["type"]
        if not isinstance(answer, dict) or answer.get("type") != kind:
            raise ResponseError(f"{qid}: missing answer or wrong answer type")
        if kind == "choice":
            probabilities = _distribution(answer, question["criteria"], qid)
            choice = answer.get("choice")
            if choice not in probabilities or probabilities[choice] != max(probabilities.values()):
                raise ResponseError(f"{qid}: choice must be the highest-probability option")
        elif kind == "score":
            levels = [str(index) for index in range(len(question["criteria"]))]
            _distribution(answer, levels, qid)
            legend = answer.get("legend")
            if not isinstance(legend, dict) or set(legend) != set(levels):
                raise ResponseError(f"{qid}: legend must map every level index")
            _number(answer.get("score"), 0, len(levels) - 1, f"{qid} score")
        else:
            _number(answer.get("noul"), 0, 1, f"{qid} noul")
    return answers


def _band(value: float) -> str:
    if value >= THRESHOLDS["confidence_high"]:
        return "high"
    return "low" if value < THRESHOLDS["confidence_low"] else "medium"


def build_report(payload: dict, response: dict) -> dict:
    answers = validate_response(payload, response)
    rows = {}
    for qid, question in payload["questions"].items():
        answer, kind = answers[qid], question["type"]
        if kind == "choice":
            ranked = sorted(answer["probabilities"].values(), reverse=True)
            rows[qid] = {"type": kind, "value": answer["choice"],
                         "probability": answer["probabilities"][answer["choice"]],
                         "margin": round(ranked[0] - ranked[1], 4),
                         "confidence": answer["confidence"], "band": _band(answer["confidence"])}
        elif kind == "score":
            nearest = int(round(answer["score"]))
            rows[qid] = {"type": kind, "value": answer["score"], "nearest_level": nearest,
                         "nearest_level_text": answer["legend"][str(nearest)],
                         "confidence": answer["confidence"], "band": _band(answer["confidence"])}
        else:
            noul = answer["noul"]
            band = ("yes" if noul >= THRESHOLDS["noul_yes"]
                    else "no" if noul <= THRESHOLDS["noul_no"] else "uncertain")
            rows[qid] = {"type": kind, "value": noul, "band": band}
    return {"model": response.get("model"), "usage": response.get("usage"), "questions": rows,
            "thresholds": {**THRESHOLDS, "note": "Illustrative defaults. Tune on your own labeled data; "
                                                 "a band is not permission to act."}}


# ----- Transport -----

RETRY_STATUSES = {429, 529}
MAX_ATTEMPTS = 3


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # never forward the Authorization header to another host


_OPENER = urllib.request.build_opener(_NoRedirect)


def _open(request: urllib.request.Request, timeout: float):
    return _OPENER.open(request, timeout=timeout)


def _api_key(provider: str) -> str:
    env = PROVIDERS[provider]["env"]
    key = os.environ.get(env, "").strip()
    if not key:
        raise TransportError(f"Set {env} in the environment that runs this command (see: prompt2jev setup)")
    if any(not 33 <= ord(character) <= 126 for character in key):
        raise TransportError(f"{env} contains whitespace or non-ASCII characters")
    return key


def _backoff(attempt: int, retry_after) -> float:
    try:
        return max(0.0, min(float(retry_after), 60.0))
    except (TypeError, ValueError):
        return float(2 ** (attempt - 1))


def _hint(status: int) -> str:
    return {401: "; check the API key",
            422: "; the request failed server-side validation, re-run validate",
            429: "; rate limited after retries",
            529: "; service overloaded after retries"}.get(status, "")


def send(payload: dict, provider: str = "typesafe", timeout: float = 30.0, sleep=time.sleep) -> dict:
    """POST the request. Retries 429 and 529 with backoff up to MAX_ATTEMPTS; never retries 401 or 422."""
    if provider not in PROVIDERS:
        raise TransportError("provider must be typesafe or openrouter")
    key = _api_key(provider)
    body = json.dumps(payload, allow_nan=False).encode("utf-8")
    for attempt in range(1, MAX_ATTEMPTS + 1):
        request = urllib.request.Request(
            PROVIDERS[provider]["url"], data=body, method="POST",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "User-Agent": f"prompt2jev/{VERSION}"})
        try:
            with _open(request, timeout) as reply:
                result = load_json(reply.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            status = error.code
            retry_after = error.headers.get("retry-after") if error.headers else None
            error.close()
            if status in RETRY_STATUSES and attempt < MAX_ATTEMPTS:
                sleep(_backoff(attempt, retry_after))
                continue
            raise TransportError(f"{provider} returned HTTP {status}{_hint(status)}", status=status) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TransportError(f"{provider} connection failed or timed out") from None
        except (json.JSONDecodeError, UnicodeError, RequestError):
            raise TransportError(f"{provider} returned invalid JSON") from None
        if not isinstance(result, dict) or "error" in result:
            raise TransportError(f"{provider} returned an error object")
        return result
    raise TransportError(f"{provider} did not answer after {MAX_ATTEMPTS} attempts")


def resolve_model(payload: dict, provider: str, override: str | None) -> str:
    if override:
        return override
    model = payload.get("model") or os.environ.get("JEV_MODEL") or PROVIDERS[provider]["model"]
    return MODEL_ALIASES[provider].get(model, model)
