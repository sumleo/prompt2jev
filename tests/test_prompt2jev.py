import contextlib
import io
import json
import os
import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()
