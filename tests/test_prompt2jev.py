import contextlib
import email.message
import http.server
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import types
import unittest
import urllib.error
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "prompt2jev"
ASSETS = SKILL / "assets"
sys.path.insert(0, str(SKILL / "scripts"))
import prompt2jev as p2j  # noqa: E402


def request(kind="choice", **overrides):
    question: dict = {"type": kind, "instructions": "Does `ticket.text` ask for a refund?"}
    if kind == "choice":
        question["criteria"] = {"refund": "Wants money back", "other": "Anything else"}
    elif kind == "score":
        question["criteria"] = ["Calm and matter-of-fact wording", "Frustrated but civil",
                                "Hostile or threatening language"]
    payload = {"model": "jev-latest", "state": {"ticket": {"text": "Please refund me."}},
               "questions": {"q": question}}
    payload.update(overrides)
    return payload


class ValidateRequestTests(unittest.TestCase):
    def test_accepts_each_type(self):
        for kind in p2j.QUESTION_TYPES:
            self.assertEqual(p2j.validate_request(request(kind)), request(kind))

    def test_noul_criteria_needs_true_and_false(self):
        payload = request("noul")
        payload["questions"]["q"]["criteria"] = {"true": "Asks for money back", "false": "Does not"}
        p2j.validate_request(payload)
        payload["questions"]["q"]["criteria"] = {"true": "Asks"}
        with self.assertRaises(p2j.RequestError):
            p2j.validate_request(payload)

    def test_rejects_bad_top_level(self):
        bad = [[], {}, {**request(), "messages": []}, {**request(), "questions": {}},
               {**request(), "state": None}, {**request(), "state": 3}, {**request(), "model": " "}]
        for payload in bad:
            with self.subTest(payload=payload), self.assertRaises(p2j.RequestError):
                p2j.validate_request(payload)

    def test_rejects_bad_questions(self):
        cases = [("choice", {"only": "one"}), ("choice", []), ("score", ["one"]),
                 ("score", [str(i) for i in range(11)]), ("noul", ["x"]), ("text", {}),
                 ("choice", {"a": 1, "b": 2}), ("score", [1, 2])]
        for kind, criteria in cases:
            payload = request()
            payload["questions"]["q"].update(type=kind, criteria=criteria)
            with self.subTest(kind=kind, criteria=criteria), self.assertRaises(p2j.RequestError):
                p2j.validate_request(payload)
        payload = request()
        payload["questions"]["q"]["instructions"] = ""
        with self.assertRaises(p2j.RequestError):
            p2j.validate_request(payload)
        payload = request()
        payload["questions"]["q"]["extra"] = 1
        with self.assertRaises(p2j.RequestError):
            p2j.validate_request(payload)

    def test_choice_allows_null_descriptions(self):
        payload = request()
        payload["questions"]["q"]["criteria"] = {"4471": None, "8812": None, "not_stated": "None fits"}
        p2j.validate_request(payload)

    def test_rejects_nonfinite_json(self):
        for text in ('{"a": NaN}', '{"a": Infinity}'):
            with self.assertRaises(p2j.RequestError):
                p2j.load_json(text)

    def test_rejects_empty_entries_and_empty_state(self):
        bad = [request(state={}), request(state=""), request(state=[])]
        payload = request("score")
        payload["questions"]["q"]["criteria"] = [{}, []]
        bad.append(payload)
        payload = request("noul")
        payload["questions"]["q"]["criteria"] = {"true": {}, "false": "No"}
        bad.append(payload)
        payload = request()
        payload["questions"]["q"]["criteria"] = {"refund": [], "other": "Else"}
        bad.append(payload)
        payload = request()
        payload["questions"]["q"]["instructions"] = {}
        bad.append(payload)
        for payload in bad:
            with self.subTest(payload=payload), self.assertRaises(p2j.RequestError):
                p2j.validate_request(payload)

    def test_pathological_json_is_a_request_error(self):
        for text in ("1" * 5000, "[" * 100_000):
            with self.subTest(text=text[:5]), self.assertRaises(p2j.RequestError):
                p2j.load_json(text)


class LintTests(unittest.TestCase):
    def codes(self, payload):
        return {f["code"] for f in p2j.lint_request(p2j.validate_request(payload))}

    def test_clean_request_only_reports_alias(self):
        self.assertEqual(self.codes(request()), {"model-alias"})
        self.assertEqual(self.codes(request(model="jev-1.13.0")), set())

    def test_choice_without_fallback(self):
        payload = request()
        payload["questions"]["q"]["criteria"] = {"billing": "Charges", "shipping": "Delivery"}
        self.assertIn("choice-no-fallback", self.codes(payload))
        for label in ("other", "none_of_the_above", "not_stated", "unknown", "no_match",
                      "insufficient_evidence"):
            payload["questions"]["q"]["criteria"] = {"billing": "Charges", label: "Nothing fits"}
            self.assertNotIn("choice-no-fallback", self.codes(payload), label)

    def test_score_levels(self):
        payload = request("score")
        payload["questions"]["q"]["criteria"] = ["1", "2", "3"]
        self.assertIn("score-numeric-levels", self.codes(payload))
        payload["questions"]["q"]["criteria"] = ["Low", "Medium", "High"]
        self.assertIn("score-degree-only", self.codes(payload))
        payload["questions"]["q"]["criteria"] = [{"summary": "One change"}, {"summary": "Several changes"}]
        self.assertNotIn("score-degree-only", self.codes(payload))

    def test_noul_wording(self):
        payload = request("noul")
        payload["questions"]["q"]["instructions"] = "Is the customer in `ticket.text` angry and asking for a refund?"
        self.assertIn("noul-compound", self.codes(payload))
        payload["questions"]["q"]["instructions"] = "Is `ticket.text` free of personal data?"
        self.assertIn("noul-negated", self.codes(payload))
        payload["questions"]["q"]["instructions"] = {
            "question": "Does `ticket.text` ask for a password or PIN?",
            "focus": "Look for a request to send it.",
        }
        self.assertEqual(self.codes(payload), {"model-alias"})

    def test_math_and_short_instructions(self):
        payload = request("noul")
        payload["questions"]["q"]["instructions"] = "Was `order.purchase_date` more than 30 days before `today`?"
        self.assertIn("math-in-question", self.codes(payload))
        payload["questions"]["q"]["instructions"] = "urgency"
        self.assertIn("instructions-too-short", self.codes(payload))

    def test_fallback_needs_an_exact_fallback_name(self):
        payload = request()
        for label in ("not_interested", "no_refund", "none_found_yet"):
            payload["questions"]["q"]["criteria"] = {"billing": "Charges", label: "A real class"}
            self.assertIn("choice-no-fallback", self.codes(payload), label)
        payload["questions"]["q"]["criteria"] = {"billing": "Charges", "other_team": "Some other team"}
        self.assertNotIn("choice-no-fallback", self.codes(payload))

    def test_math_pattern_edges(self):
        payload = request("noul")
        for text in ("Is the order amount in `ticket.text` over 100 USD?",
                     "Did the purchase in `ticket.text` happen within the last 30 days?",
                     "Does `ticket.text` mention at least three separate orders?"):
            payload["questions"]["q"]["instructions"] = text
            self.assertIn("math-in-question", self.codes(payload), text)
        for text in ("Does `ticket.text` mention more than three separate orders?",
                     "Does `ticket.text` ask for a credit of at least $50?"):
            payload["questions"]["q"]["instructions"] = text
            self.assertIn("math-in-question", self.codes(payload), text)
        for text in ("Does `ticket.text` describe an average user experience?",
                     "Does `ticket.text` say the request should count as a complaint?",
                     "Does `ticket.text` mention at least one of the listed products?"):
            payload["questions"]["q"]["instructions"] = text
            self.assertNotIn("math-in-question", self.codes(payload), text)

    def test_negation_pattern_edges(self):
        payload = request("noul")
        for text in ("Is `ticket.text` clean of personal data?",
                     "Does `ticket.text` exclude any mention of a refund?"):
            payload["questions"]["q"]["instructions"] = text
            self.assertIn("noul-negated", self.codes(payload), text)
        for text in ("Does `ticket.text` not mention a refund?",
                     "Does `ticket.text` contain no personal data?",
                     "Is there no mention of a refund in `ticket.text`?",
                     "Isn\u2019t the customer in `ticket.text` asking for a refund?"):
            payload["questions"]["q"]["instructions"] = text
            self.assertIn("noul-negated", self.codes(payload), text)
        for text in ("Does `ticket.text` mention a no-show at the appointment?",
                     "Does `ticket.text` say the customer cannot log in?"):
            payload["questions"]["q"]["instructions"] = text
            self.assertNotIn("noul-negated", self.codes(payload), text)

    def test_state_reference_needs_a_path_boundary(self):
        payload = request("noul", state={"ticket": {"text": "hi"}, "policy": "Refunds within 30 days."})
        payload["questions"]["q"]["instructions"] = "Does `ticket_id` look valid?"
        self.assertIn("state-field-unreferenced", self.codes(payload))

    def test_state_field_unreferenced_and_size(self):
        payload = request("noul", state={"ticket": {"text": "hi"}, "policy": "Refunds within 30 days."})
        payload["questions"]["q"]["instructions"] = "Does the customer ask for a refund?"
        self.assertIn("state-field-unreferenced", self.codes(payload))
        payload["questions"]["q"]["instructions"] = "Does `policy` allow the refund requested in `ticket.text`?"
        self.assertNotIn("state-field-unreferenced", self.codes(payload))
        payload = request(state={"doc": "x" * 130_000})
        self.assertIn("state-too-large", self.codes(payload))


def choice_response(label="refund", probability=0.9, confidence=0.8):
    return {"model": "jev-1.13.0", "usage": {"input_tokens": 10, "output_tokens": 2},
            "answers": {"q": {"type": "choice", "choice": label,
                              "probabilities": {"refund": probability, "other": round(1 - probability, 4)},
                              "confidence": confidence}}}


class ReportTests(unittest.TestCase):
    def test_choice_report(self):
        report = p2j.build_report(request(), choice_response())
        row = report["questions"]["q"]
        self.assertEqual((row["value"], row["probability"], row["band"]), ("refund", 0.9, "high"))
        self.assertAlmostEqual(row["margin"], 0.8)
        self.assertEqual(report["model"], "jev-1.13.0")
        self.assertIn("Tune", report["thresholds"]["note"])

    def test_bands(self):
        medium = p2j.build_report(request(), choice_response(confidence=0.6))["questions"]["q"]["band"]
        low = p2j.build_report(request(), choice_response(confidence=0.2))["questions"]["q"]["band"]
        self.assertEqual((medium, low), ("medium", "low"))

    def test_score_report(self):
        response = {"model": "jev-1.13.0", "answers": {"q": {"type": "score", "score": 1.43, "confidence": 0.35,
                                      "legend": {"0": "a", "1": "b", "2": "c"},
                                      "probabilities": {"0": 0.0, "1": 0.57, "2": 0.43}}}}
        row = p2j.build_report(request("score"), response)["questions"]["q"]
        self.assertEqual((row["value"], row["nearest_level"], row["nearest_level_text"], row["band"]),
                         (1.43, 1, "b", "low"))

    def test_score_nearest_level_rounds_half_up(self):
        response = {"model": "jev-1.13.0", "answers": {"q": {"type": "score", "score": 0.5, "confidence": 0.0,
                                      "legend": {"0": "a", "1": "b", "2": "c"},
                                      "probabilities": {"0": 0.5, "1": 0.5, "2": 0.0}}}}
        self.assertEqual(p2j.build_report(request("score"), response)["questions"]["q"]["nearest_level"], 1)

    def test_noul_report(self):
        for value, band in ((0.95, "yes"), (0.5, "uncertain"), (0.1, "no")):
            response = {"model": "jev-1.13.0", "answers": {"q": {"type": "noul", "noul": value}}}
            self.assertEqual(p2j.build_report(request("noul"), response)["questions"]["q"]["band"], band)

    def test_rejects_bad_responses(self):
        bad = [{}, {"answers": {}}, {"answers": {"q": {"type": "score"}}}, choice_response("missing"),
               choice_response(probability=float("nan")), choice_response(probability=1.5),
               choice_response("other", 0.9)]
        for response in bad:
            with self.subTest(response=response), self.assertRaises(p2j.ResponseError):
                p2j.build_report(request(), response)
        response = choice_response()
        response["answers"]["q"]["probabilities"] = {"refund": 1.0, "other": 0.5}
        with self.assertRaises(p2j.ResponseError):
            p2j.build_report(request(), response)
        response = choice_response()
        del response["answers"]["q"]["probabilities"]["other"]
        with self.assertRaises(p2j.ResponseError):
            p2j.build_report(request(), response)

    def test_malformed_provider_values_are_response_errors(self):
        response = choice_response()
        response["answers"]["q"]["choice"] = ["refund"]
        with self.assertRaises(p2j.ResponseError):
            p2j.build_report(request(), response)
        response = {"model": "jev-1.13.0", "answers": {"q": {"type": "noul", "noul": 10 ** 400}}}
        with self.assertRaises(p2j.ResponseError):
            p2j.build_report(request("noul"), response)
        response = choice_response()
        response["model"] = None
        with self.assertRaises(p2j.ResponseError):
            p2j.build_report(request(), response)
        response = {"model": "jev-1.13.0", "answers": {"q": {"type": "score", "score": 1.0, "confidence": 1.0,
                                                           "legend": {"0": None, "1": 7, "2": []},
                                                           "probabilities": {"0": 0.0, "1": 1.0, "2": 0.0}}}}
        with self.assertRaises(p2j.ResponseError):
            p2j.build_report(request("score"), response)

    def test_probability_sum_tolerance_is_capped(self):
        payload = request()
        payload["questions"]["q"]["criteria"] = {f"c{i}": "Candidate" for i in range(255)}
        probabilities = {f"c{i}": 0.73 if i == 0 else 0.0 for i in range(255)}
        response = {"model": "jev-1.13.0", "answers": {"q": {"type": "choice", "choice": "c0",
                                                           "probabilities": probabilities, "confidence": 1.0}}}
        with self.assertRaises(p2j.ResponseError):
            p2j.build_report(payload, response)


FakeReply = io.BytesIO


def http_error(status, retry_after=None):
    headers = email.message.Message()
    if retry_after is not None:
        headers["retry-after"] = str(retry_after)
    return urllib.error.HTTPError("https://api.typesafe.ai/v1/systemone", status, "err", headers,
                                  io.BytesIO(b"{}"))


class TransportTests(unittest.TestCase):
    def test_requires_key_and_never_prints_it(self):
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(p2j.TransportError) as caught:
            p2j.send(request())
        self.assertIn("TYPESAFE_API_KEY", str(caught.exception))
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "sk-secret"}, clear=True), \
                patch.object(p2j, "_open", side_effect=http_error(401)), \
                self.assertRaises(p2j.TransportError) as caught:
            p2j.send(request())
        self.assertNotIn("sk-secret", str(caught.exception))
        self.assertEqual(caught.exception.status, 401)

    def test_retries_429_and_honours_retry_after(self):
        waits = []
        replies = [http_error(429, retry_after=2), FakeReply(json.dumps(choice_response()).encode())]
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "k"}, clear=True), \
                patch.object(p2j, "_open", side_effect=replies) as opened:
            result = p2j.send(request(), sleep=waits.append)
        self.assertEqual(result["answers"]["q"]["choice"], "refund")
        self.assertEqual((opened.call_count, waits), (2, [2.0]))

    def test_gives_up_after_three_attempts(self):
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "k"}, clear=True), \
                patch.object(p2j, "_open", side_effect=[http_error(529)] * 3) as opened, \
                self.assertRaises(p2j.TransportError):
            p2j.send(request(), sleep=lambda _: None)
        self.assertEqual(opened.call_count, 3)

    def test_does_not_retry_401_or_connection_errors(self):
        for failure in (http_error(401), urllib.error.URLError("refused")):
            with patch.dict("os.environ", {"TYPESAFE_API_KEY": "k"}, clear=True), \
                    patch.object(p2j, "_open", side_effect=[failure] * 3) as opened, \
                    self.assertRaises(p2j.TransportError):
                p2j.send(request(), sleep=lambda _: None)
            self.assertEqual(opened.call_count, 1, failure)

    def test_non_numeric_retry_after_uses_exponential_backoff(self):
        waits = []
        replies = [http_error(429, retry_after="soon"), http_error(529),
                   FakeReply(json.dumps(choice_response()).encode())]
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "k"}, clear=True), \
                patch.object(p2j, "_open", side_effect=replies):
            p2j.send(request(), sleep=waits.append)
        self.assertEqual(waits, [1.0, 2.0])

    def test_error_bodies_are_surfaced_without_the_key(self):
        body = io.BytesIO(b'{"detail": "questions.q.criteria: field required"}')
        error = urllib.error.HTTPError("https://api.typesafe.ai/v1/systemone", 422, "err",
                                       email.message.Message(), body)
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "sk-secret"}, clear=True), \
                patch.object(p2j, "_open", side_effect=[error]), \
                self.assertRaises(p2j.TransportError) as caught:
            p2j.send(request())
        self.assertIn("criteria: field required", str(caught.exception))
        self.assertNotIn("sk-secret", str(caught.exception))
        reply = FakeReply(b'{"error": {"message": "model not found"}}')
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "k"}, clear=True), \
                patch.object(p2j, "_open", return_value=reply), \
                self.assertRaises(p2j.TransportError) as caught:
            p2j.send(request())
        self.assertIn("model not found", str(caught.exception))

    def test_does_not_retry_422(self):
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "k"}, clear=True), \
                patch.object(p2j, "_open", side_effect=[http_error(422)]) as opened, \
                self.assertRaises(p2j.TransportError):
            p2j.send(request(), sleep=lambda _: None)
        self.assertEqual(opened.call_count, 1)

    def test_openrouter_uses_its_key_and_url(self):
        reply = FakeReply(json.dumps(choice_response()).encode())
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "k"}, clear=True), \
                patch.object(p2j, "_open", return_value=reply) as opened:
            p2j.send(request(), provider="openrouter")
        sent = opened.call_args.args[0]
        self.assertEqual(sent.full_url, p2j.PROVIDERS["openrouter"]["url"])
        self.assertEqual(sent.get_header("Authorization"), "Bearer k")

    def test_resolve_model(self):
        self.assertEqual(p2j.resolve_model(request(), "openrouter", None), "typesafe/jev-1.13")
        self.assertEqual(p2j.resolve_model(request(model="typesafe/jev-1.13"), "typesafe", None), "jev-1.13.0")
        self.assertEqual(p2j.resolve_model(request(), "typesafe", "jev-1.13.0"), "jev-1.13.0")
        self.assertEqual(p2j.resolve_model(request(model="custom"), "openrouter", None), "custom")
        self.assertEqual(p2j.resolve_model(request(), "openrouter", "jev-1.13.0"), "typesafe/jev-1.13")
        self.assertEqual(p2j.resolve_model(request(model="jev-preview"), "openrouter", None), "typesafe/jev-1.13")
        with self.assertRaises(p2j.RequestError):
            p2j.resolve_model(request(), "typesafe", "   ")

    def test_http_client_failures_become_transport_errors(self):
        import http.client
        for failure in (http.client.IncompleteRead(b""), http.client.BadStatusLine("garbage")):
            with patch.dict("os.environ", {"TYPESAFE_API_KEY": "k"}, clear=True), \
                    patch.object(p2j, "_open", side_effect=failure), \
                    self.assertRaises(p2j.TransportError):
                p2j.send(request(), sleep=lambda _: None)

    def test_error_body_redacts_the_key(self):
        body = io.BytesIO(b'{"detail": "bad token sk-secret in header"}')
        error = urllib.error.HTTPError("https://api.typesafe.ai/v1/systemone", 401, "err",
                                       email.message.Message(), body)
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "sk-secret"}, clear=True), \
                patch.object(p2j, "_open", side_effect=[error]), \
                self.assertRaises(p2j.TransportError) as caught:
            p2j.send(request())
        self.assertIn("bad token", str(caught.exception))
        self.assertNotIn("sk-secret", str(caught.exception))


class AssetTests(unittest.TestCase):
    def test_every_archetype_is_valid_and_lint_clean(self):
        for name in p2j.ARCHETYPES:
            with self.subTest(asset=name):
                payload = json.loads((ASSETS / f"{name}.json").read_text(encoding="utf-8"))
                findings = p2j.lint_request(p2j.validate_request(payload))
                self.assertEqual([f for f in findings if f["level"] != "info"], [], findings)
                self.assertGreaterEqual(len(payload["questions"]), 3)
                self.assertIsInstance(payload["state"], dict)
                referenced = json.dumps(payload["questions"])
                for key, value in payload["state"].items():
                    nested = value.keys() if isinstance(value, dict) else [None]
                    for sub in nested:
                        path = f"`{key}" if sub is None else f"`{key}.{sub}"
                        self.assertIn(path, referenced, f"{name}: state field {path} is unused")

    def test_bundled_templates_match_asset_files(self):
        self.assertEqual(tuple(p2j.TEMPLATES), p2j.ARCHETYPES)
        self.assertEqual(sorted(path.stem for path in ASSETS.glob("*.json")), sorted(p2j.ARCHETYPES))
        for name in p2j.ARCHETYPES:
            payload = json.loads((ASSETS / f"{name}.json").read_text(encoding="utf-8"))
            self.assertEqual(p2j.TEMPLATES[name], payload, name)

    def test_version_is_consistent(self):
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["version"], p2j.VERSION)
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('dynamic = ["version"]', pyproject)
        self.assertIn('attr = "prompt2jev.VERSION"', pyproject)


def run_cli(argv, env=None, open_side_effect=None):
    out, err = io.StringIO(), io.StringIO()
    with patch.dict("os.environ", env or {}, clear=True), \
            patch.object(p2j, "_open", side_effect=open_side_effect or AssertionError("network")), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = p2j.main(argv)
    return status, out.getvalue(), err.getvalue()


def fake_response(payload):
    """A contract-valid response for any request: first option, level 1, noul 0.9."""
    answers = {}
    for qid, question in payload["questions"].items():
        kind = question["type"]
        if kind == "choice":
            labels = list(question["criteria"])
            probabilities = {label: 0.0 for label in labels}
            probabilities[labels[0]] = 1.0
            answers[qid] = {"type": kind, "choice": labels[0], "probabilities": probabilities, "confidence": 1.0}
        elif kind == "score":
            levels = question["criteria"]
            probabilities = {str(i): 0.0 for i in range(len(levels))}
            probabilities["1"] = 1.0
            answers[qid] = {"type": kind, "score": 1.0, "legend": {str(i): level for i, level in enumerate(levels)},
                            "probabilities": probabilities, "confidence": 1.0}
        else:
            answers[qid] = {"type": kind, "noul": 0.9}
    return {"model": "jev-1.13.0", "answers": answers, "usage": {"input_tokens": 10, "output_tokens": 2}}


class _JevHandler(http.server.BaseHTTPRequestHandler):
    seen: ClassVar[list] = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        type(self).seen.append((self.path, self.headers.get("Authorization"), body))
        reply = json.dumps(fake_response(body)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, *args):
        pass


def stub_sdk(calls):
    """A stand-in for typesafe_sdk 0.7 with the shapes the real package exposes."""
    module = types.ModuleType("typesafe_sdk")

    def question(kind):
        class Question(dict):
            type = kind

            def __init__(self, **fields):
                super().__init__(fields)
        return Question

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def system_one(self, state, questions, *, model=None, **kwargs):
            payload = {"model": model, "state": state,
                       "questions": {qid: {"type": q.type, **q} for qid, q in questions.items()}}
            calls.append(payload)
            raw = fake_response(payload)
            answers = {}
            for qid, answer in raw["answers"].items():
                if answer["type"] == "score":  # the Python SDK keys these by int
                    answer = {**answer, "legend": {int(k): v for k, v in answer["legend"].items()},
                              "probabilities": {int(k): v for k, v in answer["probabilities"].items()}}
                answers[qid] = types.SimpleNamespace(**answer)
            return types.SimpleNamespace(model=raw["model"], usage=types.SimpleNamespace(**raw["usage"]),
                                         answers=answers)

    module.Choice, module.Score, module.Noul = question("choice"), question("score"), question("noul")
    module.NoulCriteria, module.TypeSafeClient = dict, Client
    return module


JS_STUB_SDK = """
export const choice = (instructions, criteria) => ({ type: "choice", instructions, criteria });
export const score = (instructions, criteria) => ({ type: "score", instructions, criteria });
export const noul = (instructions, criteria) =>
  criteria === undefined ? { type: "noul", instructions } : { type: "noul", instructions, criteria };
export class TypeSafeClient {
  async systemOne(request) {
    process.stderr.write(JSON.stringify(request));
    const answers = {};
    for (const [id, q] of Object.entries(request.questions)) {
      if (q.type === "choice") {
        const labels = Object.keys(q.criteria);
        const probabilities = Object.fromEntries(labels.map((l) => [l, 0]));
        probabilities[labels[0]] = 1;
        answers[id] = { type: "choice", choice: labels[0], probabilities, confidence: 1 };
      } else if (q.type === "score") {
        const legend = Object.fromEntries(q.criteria.map((c, i) => [String(i), c]));
        const probabilities = Object.fromEntries(q.criteria.map((c, i) => [String(i), i === 1 ? 1 : 0]));
        answers[id] = { type: "score", score: 1, legend, probabilities, confidence: 1 };
      } else {
        answers[id] = { type: "noul", noul: 0.9 };
      }
    }
    return { model: "jev-1.13.0", answers, usage: { input_tokens: 10, output_tokens: 2 } };
  }
}
"""

class CodeTests(unittest.TestCase):
    payload = p2j.TEMPLATES["classify-route"]

    def test_python_script_sends_the_request_and_reads_typed_answers(self):
        source = p2j.render_code(self.payload, "python")
        calls = []
        namespace = {"__name__": "decide"}
        with patch.dict(sys.modules, {"typesafe_sdk": stub_sdk(calls)}):
            exec(compile(source, "decide.py", "exec"), namespace)
            decision = namespace["decide"](namespace["EXAMPLE_STATE"])
        self.assertEqual(calls, [self.payload])
        self.assertEqual(decision["model"], "jev-1.13.0")
        self.assertEqual(decision["category"]["choice"], "billing")
        self.assertEqual(decision["refund_requested"]["band"], "yes")
        self.assertEqual(decision["frustration"]["level"], 1)
        self.assertEqual(decision["frustration"]["label"], self.payload["questions"]["frustration"]["criteria"][1])
        self.assertIn("TYPESAFE_API_KEY", source)
        self.assertIn("pip install typesafe-sdk", source)

    def test_python_script_routes_low_confidence_to_review(self):
        source = p2j.render_code(self.payload, "python")
        namespace = {"__name__": "decide"}
        with patch.dict(sys.modules, {"typesafe_sdk": stub_sdk([])}):
            exec(compile(source, "decide.py", "exec"), namespace)
        flat = types.SimpleNamespace(choice="billing", confidence=0.2, probabilities={"billing": 0.4, "other": 0.6})
        self.assertEqual(namespace["read_choice"](flat)["choice"], "needs_review")
        self.assertEqual(namespace["read_noul"](types.SimpleNamespace(noul=0.5))["band"], "uncertain")
        self.assertEqual(namespace["read_noul"](types.SimpleNamespace(noul=0.1))["band"], "no")

    def test_python_stdlib_script_runs_end_to_end_against_a_local_server(self):
        server = http.server.HTTPServer(("127.0.0.1", 0), _JevHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        folder = Path(tempfile.mkdtemp())
        script = folder / "decide.py"
        script.write_text(p2j.render_code(self.payload, "python-stdlib"), encoding="utf-8")
        state = {"ticket": {"text": "Where is my package? It is a week late."}}
        (folder / "state.json").write_text(json.dumps(state), encoding="utf-8")
        env = {"PATH": os.environ.get("PATH", ""), "TYPESAFE_API_KEY": "test-key",
               "TYPESAFE_BASE_URL": f"http://127.0.0.1:{server.server_port}"}
        for argv, expected_state in (([], self.payload["state"]), ([str(folder / "state.json")], state)):
            completed = subprocess.run([sys.executable, str(script), *argv], capture_output=True, text=True, env=env)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            path, auth, body = _JevHandler.seen[-1]
            self.assertEqual((path, auth), ("/v1/systemone", "Bearer test-key"))
            self.assertEqual(body, {**self.payload, "state": expected_state})
            decision = json.loads(completed.stdout)
            self.assertEqual(decision["category"]["choice"], "billing")
            self.assertEqual(decision["blocks_work"]["band"], "yes")
            self.assertEqual(decision["frustration"]["level"], 1)
        completed = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                                   env={"PATH": os.environ.get("PATH", "")})
        self.assertEqual(completed.returncode, 1)
        self.assertIn("TYPESAFE_API_KEY", completed.stderr)

    def test_javascript_and_curl_outputs(self):
        source = p2j.render_code(self.payload, "javascript")
        self.assertIn('from "@typesafe-ai/sdk"', source)
        self.assertIn("systemOne", source)
        self.assertIn("npm install @typesafe-ai/sdk", source)
        for qid in self.payload["questions"]:
            self.assertIn(f'"{qid}"', source)
        if shutil.which("node"):
            script = Path(tempfile.mkdtemp()) / "decide.mjs"
            script.write_text(source, encoding="utf-8")
            completed = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
        shell = p2j.render_code(self.payload, "curl")
        self.assertIn("/v1/systemone", shell)
        self.assertIn("Authorization: Bearer", shell)
        body = shell.split("<<'JSON'\n", 1)[1].split("\nJSON", 1)[0]
        self.assertEqual(json.loads(body), self.payload)

    def test_every_archetype_renders_in_every_language(self):
        for name in p2j.ARCHETYPES:
            for lang in p2j.CODE_LANGS:
                with self.subTest(archetype=name, lang=lang):
                    source = p2j.render_code(p2j.TEMPLATES[name], lang)
                    if lang.startswith("python"):
                        compile(source, "decide.py", "exec")
                    self.assertIn("jev-latest", source)

    def test_python_script_imports_only_the_sdk_names_it_uses(self):
        source = p2j.render_code(self.payload, "python")  # choice, score, noul with and without criteria
        self.assertIn("from typesafe_sdk import Choice, Noul, NoulCriteria, Score, TypeSafeClient\n", source)
        self.assertIn("from typesafe_sdk import Noul, TypeSafeClient\n", p2j.render_code(request("noul"), "python"))
        self.assertIn("from typesafe_sdk import Choice, TypeSafeClient\n", p2j.render_code(request("choice"), "python"))
        self.assertIn("from typesafe_sdk import Score, TypeSafeClient\n", p2j.render_code(request("score"), "python"))

    HOSTILE_IDS = ("customer-name", "2nd", "class", "model", "jev_model", "MODEL", "QUESTIONS", "package",
                   "q\u00b2", "__debug__", "a b", "a_b", "answers", "readChoice", "eval")

    def hostile_payload(self):
        payload = request("noul")
        payload["questions"] = {qid: dict(payload["questions"]["q"]) for qid in self.HOSTILE_IDS}
        return payload

    def test_question_ids_become_safe_python_identifiers(self):
        payload = self.hostile_payload()
        source = p2j.render_code(payload, "python")
        namespace = {"__name__": "decide"}
        with patch.dict(sys.modules, {"typesafe_sdk": stub_sdk([])}):
            exec(compile(source, "decide.py", "exec"), namespace)
            decision = namespace["decide"](namespace["EXAMPLE_STATE"])
        self.assertEqual(set(decision), {*self.HOSTILE_IDS, "jev_model_2"})  # model id kept under a free key
        self.assertEqual(decision["jev_model_2"], "jev-1.13.0")
        self.assertTrue(all(decision[qid]["band"] == "yes" for qid in self.HOSTILE_IDS))
        # "model" is a safe Python local (the script reads response.model); only the JS side must rename it
        for name in ("customer_name", "q_2nd", "class_", "model", "MODEL_", "a_b_2", "__debug___", "q_"):
            self.assertIn(f"    {name} = read_noul(", source, name)
        self.assertNotIn("q\u00b2 =", source)
        compile(p2j.render_code(payload, "python-stdlib"), "decide.py", "exec")
        with self.assertRaises(p2j.RequestError):
            p2j.render_code(payload, "cobol")

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_question_ids_become_safe_javascript_identifiers(self):
        source = p2j.render_code(self.hostile_payload(), "javascript")
        script = Path(tempfile.mkdtemp()) / "decide.mjs"
        script.write_text(source, encoding="utf-8")
        completed = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        for name in ("MODEL_", "QUESTIONS_", "package_", "eval_", "answers_", "readChoice_"):
            self.assertIn(f"  const {name} = read", source, name)
        self.assertIn('"jev_model_2": model,', source)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_javascript_script_runs_end_to_end_against_a_stub_sdk(self):
        folder = Path(tempfile.mkdtemp())
        package = folder / "node_modules" / "@typesafe-ai" / "sdk"
        package.mkdir(parents=True)
        (package / "package.json").write_text(json.dumps({"name": "@typesafe-ai/sdk", "type": "module",
                                                          "main": "index.mjs"}), encoding="utf-8")
        (package / "index.mjs").write_text(JS_STUB_SDK, encoding="utf-8")
        script = folder / "decide.mjs"
        script.write_text(p2j.render_code(self.payload, "javascript"), encoding="utf-8")
        state = {"ticket": {"text": "Where is my package?"}}
        (folder / "state.json").write_text(json.dumps(state), encoding="utf-8")
        for argv, expected_state in (([], self.payload["state"]), (["state.json"], state)):
            completed = subprocess.run(["node", "decide.mjs", *argv], capture_output=True, text=True, cwd=folder,
                                       env={"PATH": os.environ.get("PATH", ""), "TYPESAFE_API_KEY": "k"})
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stderr), {**self.payload, "state": expected_state})
            decision = json.loads(completed.stdout)
            self.assertEqual(decision["category"]["choice"], "billing")
            self.assertEqual(decision["frustration"]["label"], self.payload["questions"]["frustration"]["criteria"][1])
            self.assertEqual(decision["refund_requested"]["band"], "yes")

    def test_deeply_nested_values_render_quickly(self):
        state = {"ticket": {"text": "x"}}
        for _ in range(60):
            state = {"level": state}
        payload = request(state=state)
        payload["questions"]["q"]["instructions"] = "Does `level` ask for a refund?"
        for lang in ("python", "python-stdlib"):
            compile(p2j.render_code(payload, lang), "decide.py", "exec")

    def test_stdlib_script_reports_unreachable_hosts_without_a_traceback(self):
        script = Path(tempfile.mkdtemp()) / "decide.py"
        script.write_text(p2j.render_code(self.payload, "python-stdlib"), encoding="utf-8")
        completed = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                                   env={"PATH": os.environ.get("PATH", ""), "TYPESAFE_API_KEY": "k",
                                        "TYPESAFE_BASE_URL": "http://127.0.0.1:1"})
        self.assertEqual(completed.returncode, 1)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertIn("127.0.0.1:1", completed.stderr)

    def test_javascript_output_name_should_be_mjs(self):
        path = Path(tempfile.mkdtemp())
        (path / "request.json").write_text(json.dumps(request(model="jev-1.13.0")), encoding="utf-8")
        status, _, err = run_cli(["code", str(path / "request.json"), "--lang", "javascript",
                                 "--output", str(path / "decide.js")])
        self.assertEqual(status, 0)
        self.assertIn(".mjs", err)
        status, _, err = run_cli(["code", str(path / "request.json"), "--lang", "javascript",
                                 "--output", str(path / "decide.mjs")])
        self.assertEqual((status, err), (0, ""))

    def test_code_command_prints_or_writes_the_script(self):
        path = str(Path(tempfile.mkdtemp()) / "request.json")
        Path(path).write_text(json.dumps(request(model="jev-1.13.0")), encoding="utf-8")
        status, out, err = run_cli(["code", path, "--lang", "python"])
        self.assertEqual((status, err), (0, ""))
        compile(out, "decide.py", "exec")
        target = Path(tempfile.mkdtemp()) / "decide.py"
        status, out, _ = run_cli(["code", path, "--lang", "python-stdlib", "--output", str(target)])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(out)["written"], str(target))
        compile(target.read_text(encoding="utf-8"), "decide.py", "exec")
        status, out, err = run_cli(["code", path, "--lang", "python"], env={})
        self.assertEqual(status, 0)
        status, out, err = run_cli(["code", str(Path(path).with_name("missing.json"))])
        self.assertEqual((status, out), (1, ""))
        self.assertIn("error", err)

    def test_code_command_lints_but_still_generates(self):
        payload = request()
        payload["questions"]["q"]["criteria"] = {"a": "A", "b": "B"}
        path = Path(tempfile.mkdtemp()) / "request.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        status, out, err = run_cli(["code", str(path)])
        self.assertEqual(status, 0)
        self.assertIn("choice-no-fallback", err)
        compile(out, "decide.py", "exec")
        status, _, err = run_cli(["code", str(path), "--allow", "choice-no-fallback", "--allow", "model-alias"])
        self.assertEqual((status, err), (0, ""))


class CliTests(unittest.TestCase):
    def write(self, payload):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = Path(folder) / "request.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return str(path)

    def test_validate_prints_request_and_findings(self):
        payload = request()
        payload["questions"]["q"]["criteria"] = {"a": "A", "b": "B"}
        status, out, err = run_cli(["validate", self.write(payload)])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(out), payload)
        self.assertIn("choice-no-fallback", err)
        status, _, err = run_cli(["validate", self.write(payload), "--strict"])
        self.assertEqual(status, 1)
        self.assertIn("--strict", err)

    def test_validate_reads_stdin(self):
        payload = request(model="jev-1.13.0")
        with patch("sys.stdin", io.StringIO(json.dumps(payload))):
            status, out, err = run_cli(["validate", "-", "--strict"])
        self.assertEqual((status, json.loads(out), err), (0, payload, ""))

    def test_validate_reports_schema_errors(self):
        status, out, err = run_cli(["validate", self.write({"model": "x"})])
        self.assertEqual((status, out), (1, ""))
        self.assertIn("error", json.loads(err.strip().splitlines()[-1]))

    def test_run_dry_run_needs_no_key_and_maps_model(self):
        status, out, _ = run_cli(["run", self.write(request()), "--dry-run", "--provider", "openrouter"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(out)["model"], "typesafe/jev-1.13")

    def test_run_live_writes_report(self):
        output = Path(tempfile.mkdtemp()) / "result.json"
        reply = FakeReply(json.dumps(choice_response()).encode())
        status, out, _ = run_cli(["run", self.write(request()), "--output", str(output)],
                                 env={"TYPESAFE_API_KEY": "k"}, open_side_effect=[reply])
        self.assertEqual(status, 0)
        result = json.loads(out)
        self.assertEqual(result["report"]["questions"]["q"]["value"], "refund")
        self.assertEqual(result["report"]["provider"], "typesafe")
        self.assertEqual(json.loads(output.read_text())["response"], choice_response())

    def test_output_path_is_checked_before_sending(self):
        missing_dir = Path(tempfile.mkdtemp()) / "missing" / "result.json"
        with patch.object(p2j, "_open", side_effect=AssertionError("network")) as opened:
            out, err = io.StringIO(), io.StringIO()
            with patch.dict("os.environ", {"TYPESAFE_API_KEY": "k"}, clear=True), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                status = p2j.main(["run", self.write(request()), "--output", str(missing_dir)])
        self.assertEqual((status, out.getvalue(), opened.call_count), (1, "", 0))
        self.assertIn("--output", err.getvalue())

    def test_run_prints_response_even_when_output_file_fails(self):
        reply = FakeReply(json.dumps(choice_response()).encode())
        target = Path(tempfile.mkdtemp()) / "result.json"
        request_file = self.write(request())
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            status, out, err = run_cli(["run", request_file, "--output", str(target)],
                                       env={"TYPESAFE_API_KEY": "k"}, open_side_effect=[reply])
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(out)["report"]["questions"]["q"]["value"], "refund")
        self.assertIn("disk full", err)

    def test_output_file_survives_a_broken_stdout(self):
        class Broken(io.StringIO):
            def write(self, _text):
                raise BrokenPipeError(32, "Broken pipe")

        reply = FakeReply(json.dumps(choice_response()).encode())
        target = Path(tempfile.mkdtemp()) / "result.json"
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "k"}, clear=True), \
                patch.object(p2j, "_open", side_effect=[reply]), \
                contextlib.redirect_stdout(Broken()), contextlib.redirect_stderr(io.StringIO()):
            status = p2j.main(["run", self.write(request()), "--output", str(target)])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(target.read_text())["response"], choice_response())

    def test_allow_suppresses_a_lint_code(self):
        payload = request("noul")
        payload["questions"]["q"]["instructions"] = "Does `ticket.text` accept the terms and conditions?"
        status, _, err = run_cli(["validate", self.write(payload), "--strict"])
        self.assertEqual(status, 1)
        self.assertIn("noul-compound", err)
        status, _, err = run_cli(["validate", self.write(payload), "--strict", "--allow", "noul-compound"])
        self.assertEqual(status, 0)
        self.assertNotIn("noul-compound", err)
        status, _, _ = run_cli(["validate", self.write(payload), "--strict", "--allow", "not-a-code"])
        self.assertEqual(status, 1)

    def test_run_prints_raw_response_when_report_fails(self):
        response = choice_response()
        del response["answers"]["q"]["confidence"]
        reply = io.BytesIO(json.dumps(response).encode())
        status, out, err = run_cli(["run", self.write(request())], env={"TYPESAFE_API_KEY": "k"},
                                   open_side_effect=[reply])
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(out)["response"], response)
        self.assertIn("confidence", err)

    def test_run_lints_the_original_model(self):
        status, _, err = run_cli(["run", self.write(request()), "--dry-run", "--provider", "openrouter"])
        self.assertEqual(status, 0)
        self.assertIn("model-alias", err)

    def test_setup_agrees_with_key_rules(self):
        status, out, _ = run_cli(["setup"], env={"TYPESAFE_API_KEY": "sk key", "OPENROUTER_API_KEY": "ok"})
        report = json.loads(out)
        self.assertEqual((status, report["keys_present"], report["default_provider"]),
                         (0, {"typesafe": False, "openrouter": True}, "openrouter"))
        self.assertNotIn("sk key", out)

    def test_validate_accepts_utf8_bom(self):
        path = Path(tempfile.mkdtemp()) / "bom.json"
        path.write_bytes(b"\xef\xbb\xbf" + json.dumps(request(model="jev-1.13.0")).encode())
        status, out, _ = run_cli(["validate", str(path), "--strict"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(out)["model"], "jev-1.13.0")

    def test_pathological_input_files_exit_one(self):
        for text in ("1" * 5000, "[" * 100_000):
            path = Path(tempfile.mkdtemp()) / "bad.json"
            path.write_text(text, encoding="utf-8")
            command = [sys.executable, str(SKILL / "scripts" / "prompt2jev.py"), "validate", str(path)]
            env = {"PATH": os.environ.get("PATH", "")}
            completed = subprocess.run(command, capture_output=True, text=True, env=env)
            self.assertEqual(completed.returncode, 1, completed.stderr[-300:])
            self.assertIn("error", json.loads(completed.stderr.strip().splitlines()[-1]))

    def test_printing_survives_unencodable_text(self):
        payload = request(model="jev-1.13.0", state={"ticket": {"text": "emoji \ud83d and 中文"}})
        path = Path(tempfile.mkdtemp()) / "surrogate.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        for env in ({}, {"PYTHONIOENCODING": "cp1252"}):
            command = [sys.executable, str(SKILL / "scripts" / "prompt2jev.py"), "validate", str(path)]
            completed = subprocess.run(command, capture_output=True, env={"PATH": os.environ.get("PATH", ""), **env})
            self.assertEqual(completed.returncode, 0, completed.stderr[-300:])
            self.assertIn(b"questions", completed.stdout)

    def test_run_without_key_fails_cleanly(self):
        status, out, err = run_cli(["run", self.write(request())])
        self.assertEqual((status, out), (1, ""))
        self.assertIn("TYPESAFE_API_KEY", err)

    def test_template_and_setup(self):
        for name in p2j.ARCHETYPES:
            status, out, _ = run_cli(["template", name])
            self.assertEqual(status, 0)
            p2j.validate_request(json.loads(out))
        status, out, _ = run_cli(["setup"], env={"OPENROUTER_API_KEY": "sk-secret"})
        report = json.loads(out)
        self.assertEqual((status, report["keys_present"], report["default_provider"]),
                         (0, {"typesafe": False, "openrouter": True}, "openrouter"))
        self.assertNotIn("sk-secret", out)

    def test_template_works_without_asset_files(self):
        target = Path(tempfile.mkdtemp())
        shutil.copy(SKILL / "scripts" / "prompt2jev.py", target / "prompt2jev.py")
        completed = subprocess.run(
            [sys.executable, str(target / "prompt2jev.py"), "template", "extract-select"],
            capture_output=True, text=True, env={"PATH": os.environ.get("PATH", "")})
        self.assertEqual(completed.returncode, 0, completed.stderr)
        p2j.validate_request(json.loads(completed.stdout))

    def test_copied_skill_dir_still_runs(self):
        target = Path(tempfile.mkdtemp()) / "prompt2jev"
        shutil.copytree(SKILL, target, ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
        completed = subprocess.run(
            [sys.executable, str(target / "scripts" / "prompt2jev.py"), "run",
             str(target / "assets" / "classify-route.json"), "--dry-run"],
            capture_output=True, text=True, env={"PATH": os.environ.get("PATH", "")})
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("questions", completed.stdout)


if __name__ == "__main__":
    unittest.main()
