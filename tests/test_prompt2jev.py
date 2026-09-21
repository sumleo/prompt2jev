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
        response = {"answers": {"q": {"type": "score", "score": 1.43, "confidence": 0.35,
                                      "legend": {"0": "a", "1": "b", "2": "c"},
                                      "probabilities": {"0": 0.0, "1": 0.57, "2": 0.43}}}}
        row = p2j.build_report(request("score"), response)["questions"]["q"]
        self.assertEqual((row["value"], row["nearest_level"], row["nearest_level_text"], row["band"]),
                         (1.43, 1, "b", "low"))

    def test_noul_report(self):
        for value, band in ((0.95, "yes"), (0.5, "uncertain"), (0.1, "no")):
            response = {"answers": {"q": {"type": "noul", "noul": value}}}
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


class FakeReply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


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


class AssetTests(unittest.TestCase):
    def test_every_archetype_is_valid_and_lint_clean(self):
        for name in p2j.ARCHETYPES:
            with self.subTest(asset=name):
                payload = json.loads((p2j.ASSETS_DIR / f"{name}.json").read_text(encoding="utf-8"))
                findings = p2j.lint_request(p2j.validate_request(payload))
                self.assertEqual([f for f in findings if f["level"] != "info"], [], findings)
                self.assertGreaterEqual(len(payload["questions"]), 3)
                self.assertIsInstance(payload["state"], dict)


def run_cli(argv, env=None, open_side_effect=None):
    out, err = io.StringIO(), io.StringIO()
    with patch.dict("os.environ", env or {}, clear=True), \
            patch.object(p2j, "_open", side_effect=open_side_effect or AssertionError("network")), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = p2j.main(argv)
    return status, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def write(self, payload):
        path = Path(tempfile.mkdtemp()) / "request.json"
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

    def test_copied_skill_dir_still_runs(self):
        target = Path(tempfile.mkdtemp()) / "prompt2jev"
        shutil.copytree(SKILL, target)
        completed = subprocess.run(
            [sys.executable, str(target / "scripts" / "prompt2jev.py"), "run",
             str(target / "assets" / "classify-route.json"), "--dry-run"],
            capture_output=True, text=True, env={"PATH": os.environ.get("PATH", "")})
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("questions", completed.stdout)


if __name__ == "__main__":
    unittest.main()
