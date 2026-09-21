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
        for trigger in ("prompt", "Jev", "TypeSafe", "System One"):
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
                       "openrouter_api_key"):
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
                           ".claude/skills/", ".agents/skills/", ".opencode/skills/"):
                self.assertIn(phrase, text, phrase)
        self.assertIn("npx skills add sumleo/prompt2jev", readme)
        self.assertIn("claude plugin marketplace add sumleo/prompt2jev", readme)
        self.assertIn("(README.zh.md)", readme)
        chinese = (ROOT / "README.zh.md").read_text(encoding="utf-8")
        self.assertIn("(README.md)", chinese)
        for phrase in ("skills/prompt2jev", "prompt2jev validate", "--dry-run", "--allow", "TYPESAFE_API_KEY",
                       ".claude/skills/", ".agents/skills/", ".opencode/skills/",
                       "npx skills add sumleo/prompt2jev", "claude plugin marketplace add sumleo/prompt2jev"):
            self.assertIn(phrase, chinese, phrase)
        for name in ARCHETYPES:
            self.assertIn(name, chinese, name)
        anchors = re.findall(r'<a id="([^"]+)"></a>', readme)
        self.assertEqual(anchors, re.findall(r'<a id="([^"]+)"></a>', chinese))
        for anchor in ("overview", "contents", "install", "usage", "package", "catalog", "cli", "io",
                       "habits", "pitfalls", "credits"):
            self.assertIn(anchor, anchors)
            self.assertIn(f"](#{anchor})", readme)
        for text in (readme, chinese):
            positions = [text.index(f'<a id="{a}"></a>') for a in ("overview", "contents", "install", "usage")]
            self.assertEqual(positions, sorted(positions))
            blocks = re.findall(r"```json\n(.*?)\n```", text, re.S)
            for block in blocks:
                payload = json.loads(block)
                findings = p2j.lint_request(p2j.validate_request(payload))
                self.assertEqual([f for f in findings if f["level"] == "warning"], [])
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
        marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual(plugin["name"], "prompt2jev")
        self.assertEqual(marketplace["plugins"][0]["name"], "prompt2jev")


if __name__ == "__main__":
    unittest.main()
