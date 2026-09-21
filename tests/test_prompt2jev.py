import contextlib
import email.message
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
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
            completed = subprocess.run([sys.executable, str(SKILL / "scripts" / "prompt2jev.py"), "validate", str(path)],
                                       capture_output=True, text=True, env={"PATH": os.environ.get("PATH", "")})
            self.assertEqual(completed.returncode, 1, completed.stderr[-300:])
            self.assertIn("error", json.loads(completed.stderr.strip().splitlines()[-1]))

    def test_printing_survives_unencodable_text(self):
        payload = request(model="jev-1.13.0", state={"ticket": {"text": "emoji \ud83d and 中文"}})
        path = Path(tempfile.mkdtemp()) / "surrogate.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        for env in ({}, {"PYTHONIOENCODING": "cp1252"}):
            completed = subprocess.run([sys.executable, str(SKILL / "scripts" / "prompt2jev.py"), "validate", str(path)],
                                       capture_output=True, env={"PATH": os.environ.get("PATH", ""), **env})
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
