import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "prompt2jev"
REFERENCES = ("playbook", "question-design", "api", "composition", "examples")
sys.path.insert(0, str(SKILL / "scripts"))
import prompt2jev as p2j  # noqa: E402

ARCHETYPES = p2j.ARCHETYPES


def frontmatter(text):
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return match.group(1) if match else ""


def relative_links(text):
    return re.findall(r"\]\((?!https?://|mailto:)([^)#\s]+)", text)


class SkillFileTests(unittest.TestCase):
    def setUp(self):
        self.text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    def test_frontmatter(self):
        meta = frontmatter(self.text)
        self.assertIn("name: prompt2jev\n", meta)
        description = re.search(r"description: (.*?)\nlicense:", meta, re.S).group(1)
        self.assertLess(len(description), 1024)
        for trigger in ("prompt", "Jev", "TypeSafe", "System One", "script"):
            self.assertIn(trigger, description)
        self.assertNotIn(" I ", description)
        # An unquoted YAML scalar breaks on ": " and on a leading quote or hash.
        self.assertNotIn(": ", description)
        self.assertNotIn(" #", description)
        self.assertFalse(description.startswith(('"', "'", "[", "{", "&", "*", "!", "|", ">", "%", "@", "`")))

    def test_length_and_sections(self):
        self.assertLess(len(self.text.splitlines()), 300)
        for heading in ("## What you deliver", "## Step 0", "## Step 1", "## Step 2", "## Step 3",
                        "## Step 4", "## Step 5", "## Step 6", "## Run", "## References", "## Red flags"):
            self.assertIn(heading, self.text)

    def test_package_parts_and_rules(self):
        lowered = self.text.lower()
        for phrase in ("decision contract", "split table", "request json", "composition code", "assumptions",
                       "one judgment per question", "not sent to the model", "backticked", "fallback",
                       "2 to 10 levels", "high value means yes", "one request", "second request",
                       "three bands", "validate", "--strict", "--dry-run", "typesafe_api_key",
                       "openrouter_api_key", "prompt2jev code", "--lang python", "python-stdlib", "runnable",
                       "typesafe_sdk", "@typesafe-ai/sdk", "http"):
            self.assertIn(phrase, lowered, phrase)

    def test_links_resolve(self):
        for target in relative_links(self.text):
            self.assertTrue((SKILL / target).is_file(), target)
        for name in REFERENCES:
            self.assertIn(f"references/{name}.md", self.text)
        for name in ARCHETYPES:
            self.assertIn(name, self.text)


class ReferenceTests(unittest.TestCase):
    def test_references_exist_and_link_only_to_existing_files(self):
        for name in REFERENCES:
            path = SKILL / "references" / f"{name}.md"
            self.assertTrue(path.is_file(), name)
            text = path.read_text(encoding="utf-8")
            self.assertGreater(len(text.splitlines()), 40, name)
            for target in relative_links(text):
                self.assertTrue((path.parent / target).resolve().is_file(), f"{name}: {target}")

    def test_examples_requests_validate(self):
        text = (SKILL / "references" / "examples.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```json\n(.*?)\n```", text, re.S)
        self.assertGreaterEqual(len(blocks), 3)
        for block in blocks:
            payload = json.loads(block)
            if "questions" in payload:
                findings = p2j.lint_request(p2j.validate_request(payload))
                self.assertEqual([f for f in findings if f["level"] == "warning"], [], block[:80])

    def test_playbook_request_validates(self):
        text = (SKILL / "references" / "playbook.md").read_text(encoding="utf-8")
        blocks = [json.loads(b) for b in re.findall(r"```json\n(.*?)\n```", text, re.S)]
        requests = [b for b in blocks if "questions" in b]
        self.assertGreaterEqual(len(requests), 1)
        for payload in requests:
            findings = p2j.lint_request(p2j.validate_request(payload))
            self.assertEqual([f for f in findings if f["level"] == "warning"], [])


class RepoDocTests(unittest.TestCase):
    def test_readme_and_install_guide(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        install = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")
        for text in (readme, install):
            for phrase in ("skills/prompt2jev", "prompt2jev validate", "--dry-run", "TYPESAFE_API_KEY",
                           ".claude/skills/", ".agents/skills/", ".opencode/skills/", "prompt2jev code"):
                self.assertIn(phrase, text, phrase)
        self.assertIn("npx skills add sumleo/prompt2jev", readme)
        self.assertIn("claude plugin marketplace add sumleo/prompt2jev", readme)
        self.assertIn("(README.zh.md)", readme)
        chinese = (ROOT / "README.zh.md").read_text(encoding="utf-8")
        self.assertIn("(README.md)", chinese)
        for phrase in ("skills/prompt2jev", "prompt2jev validate", "--dry-run", "--allow", "TYPESAFE_API_KEY",
                       ".claude/skills/", ".agents/skills/", ".opencode/skills/", "prompt2jev code",
                       "--lang python", "examples/triage",
                       "npx skills add sumleo/prompt2jev", "claude plugin marketplace add sumleo/prompt2jev"):
            self.assertIn(phrase, chinese, phrase)
        for name in ARCHETYPES:
            self.assertIn(name, chinese, name)
        anchors = re.findall(r'<a id="([^"]+)"></a>', readme)
        self.assertEqual(anchors, re.findall(r'<a id="([^"]+)"></a>', chinese))
        for anchor in ("overview", "contents", "install", "usage", "package", "catalog", "cli", "example",
                       "habits", "pitfalls", "credits"):
            self.assertIn(anchor, anchors)
            self.assertIn(f"](#{anchor})", readme)
        for text in (readme, chinese):
            positions = [text.index(f'<a id="{a}"></a>') for a in ("overview", "contents", "install", "usage")]
            self.assertEqual(positions, sorted(positions))
            blocks = [json.loads(b) for b in re.findall(r"```json\n(.*?)\n```", text, re.S)]
            requests = [b for b in blocks if "questions" in b]
            self.assertGreaterEqual(len(requests), 1)
            for payload in requests:
                findings = p2j.lint_request(p2j.validate_request(payload))
                self.assertEqual([f for f in findings if f["level"] == "warning"], [])
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
        marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual(plugin["name"], "prompt2jev")
        self.assertEqual(marketplace["plugins"][0]["name"], "prompt2jev")


class ExampleTests(unittest.TestCase):
    """examples/triage is the end-to-end walkthrough both READMEs show: request, generated script, real output."""
    folder = ROOT / "examples" / "triage"

    def test_request_is_lint_clean_and_script_is_the_generator_output(self):
        payload = json.loads((self.folder / "request.json").read_text(encoding="utf-8"))
        findings = p2j.lint_request(p2j.validate_request(payload))
        self.assertEqual([f for f in findings if f["level"] == "warning"], [])
        script = (self.folder / "triage.py").read_text(encoding="utf-8")
        self.assertEqual(script, p2j.render_code(payload, "python", source="request.json", script="triage.py"))

    def test_output_matches_the_request_and_is_shown_in_both_readmes(self):
        payload = json.loads((self.folder / "request.json").read_text(encoding="utf-8"))
        output = json.loads((self.folder / "output.json").read_text(encoding="utf-8"))
        self.assertEqual(set(output), {"model", *payload["questions"]})
        self.assertTrue(output["model"].startswith("jev-"))
        for qid, question in payload["questions"].items():
            key = {"choice": "choice", "score": "level", "noul": "band"}[question["type"]]
            self.assertIn(key, output[qid], qid)
        script = (self.folder / "triage.py").read_text(encoding="utf-8").rstrip("\n")
        rendered = json.dumps(output, ensure_ascii=False, indent=2)
        for name in ("README.md", "README.zh.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn(json.dumps(payload, ensure_ascii=False, indent=2), text, f"{name}: request")
            self.assertIn(script, text, f"{name}: script")
            self.assertIn(rendered, text, f"{name}: output")
            self.assertIn("examples/triage", text)


class VideoTests(unittest.TestCase):
    """video/composition/index.html is the source of the README video; its on-screen text must stay the
    example's text, so a change to examples/triage fails here until the video is updated and re-rendered."""
    folder = ROOT / "video"

    @classmethod
    def screen_text(cls):
        html = (cls.folder / "composition" / "index.html").read_text(encoding="utf-8")
        body = html.split("<body>", 1)[1].split("<script>", 1)[0]
        text = re.sub(r"<[^>]+>", "", body)
        for entity, char in (("&gt;", ">"), ("&lt;", "<"), ("&quot;", '"'), ("&amp;", "&")):
            text = text.replace(entity, char)
        return text

    def test_prompt_questions_and_commands_are_on_screen(self):
        text = self.screen_text()
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        prompt = re.search(r'"(Classify the support ticket into .*?Output JSON only\.)"', readme, re.S).group(1)
        self.assertIn(" ".join(prompt.split()), " ".join(text.split()))
        payload = json.loads((self.folder.parent / "examples" / "triage" / "request.json").read_text(encoding="utf-8"))
        for qid, question in payload["questions"].items():
            self.assertIn(qid, text)
            self.assertIn(question["type"], text)
            self.assertIn(question["instructions"], text)
        for option in payload["questions"]["team"]["criteria"]:
            self.assertIn(option, text)
        for command in ("prompt2jev validate request.json --strict",
                        "prompt2jev code request.json --lang python --output triage.py", "python3 triage.py"):
            self.assertIn(command, (self.folder / "composition" / "index.html").read_text(encoding="utf-8"), command)
        for lang in ("--lang python", "javascript", "python-stdlib", "curl"):
            self.assertIn(lang, text)

    def test_script_lines_and_output_values_are_the_example_files(self):
        text = self.screen_text()
        script = (self.folder.parent / "examples" / "triage" / "triage.py").read_text(encoding="utf-8")
        for line in ("# ----- Constants: every threshold in one place -----", "def decide(state) -> dict:",
                     "    response = ask(state)", "    answers = response.answers"):
            self.assertIn(line, script, line)
            self.assertIn(line, text, line)
        for prefix in ("from typesafe_sdk import ", "CONFIDENCE_FLOOR = ", "NOUL_YES = ", "NOUL_NO = "):
            line = next(l for l in script.splitlines() if l.startswith(prefix))
            self.assertIn(line, text, line)
        for qid in ("team", "urgent", "refund_requested"):
            line = next(l for l in script.splitlines() if l.strip().startswith(qid + " = read_"))
            self.assertIn(line, text, line)
        output = json.loads((self.folder.parent / "examples" / "triage" / "output.json").read_text(encoding="utf-8"))
        self.assertIn(output["model"], text)
        team = output["team"]
        self.assertIn(f"P({team['choice']}) {team['probabilities'][team['choice']]:.2f} · confidence {team['confidence']:.2f}", text)
        for qid in ("urgent", "refund_requested"):
            self.assertIn(f"P(yes) {output[qid]['noul']:.2f} · band {output[qid]['band']}", text)

    def test_readmes_link_the_rendered_video(self):
        for name in ("README.md", "README.zh.md"):
            readme = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("](video/prompt2jev-walkthrough-poster.jpg)](video/prompt2jev-walkthrough.mp4)", readme, name)
            self.assertIn("video/README.md", readme, name)
        self.assertTrue((self.folder / "prompt2jev-walkthrough.mp4").stat().st_size > 1_000_000)
        self.assertTrue((self.folder / "prompt2jev-walkthrough-poster.jpg").stat().st_size > 10_000)
        self.assertIn("prompt2jev-walkthrough.mp4", (self.folder / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
