"""Skill files: frontmatter that every Claude app accepts."""
import re
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / "plugins" / "job-search" / "skills"


def frontmatter(path):
    text = path.read_text()
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return dict(line.split(": ", 1) for line in m.group(1).splitlines() if ": " in line) if m else {}


class SkillFrontmatterTest(unittest.TestCase):
    def test_every_skill_has_name_and_description(self):
        files = sorted(SKILLS.glob("*/SKILL.md"))
        self.assertGreaterEqual(len(files), 14)
        for f in files:
            fm = frontmatter(f)
            self.assertEqual(fm.get("name"), f.parent.name, f)
            self.assertTrue(fm.get("description"), f)

    def test_descriptions_have_no_angle_brackets(self):
        # claude.ai rejects XML-like tags in descriptions and strips the brackets on sync
        for f in SKILLS.glob("*/SKILL.md"):
            desc = frontmatter(f).get("description", "")
            self.assertNotRegex(desc, r"[<>]", f)


if __name__ == "__main__":
    unittest.main()
