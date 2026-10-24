"""Tests for check_answers.py (cover note and screening answers check). No network."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins" / "job-search" / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import check_answers  # noqa: E402
import jslib  # noqa: E402

GOOD = """# Acme: Staff Platform Engineer II

## Cover note
I have spent 14 years building cloud platforms. At my current job I led the migration of
40 services to Kubernetes, cutting infrastructure cost 30%.

## Screening answers
- Work authorization: [fill in]
- Salary expectation: [fill in] (your floor is $170,000 base; many people answer with a range above it)
"""


class AnswersCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / "profile").mkdir()
        for p in (FIXTURES / "profile").iterdir():
            shutil.copy(p, self.home / "profile" / p.name)
        jslib.write_json(self.home / jslib.MARKER, {"schema_version": 1})
        self.fb = jslib.load_fact_bank(self.home)
        self.prefs = jslib.load_preferences(self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def test_numbers_from_facts_and_preferences_pass(self):
        self.assertEqual(check_answers.check_text(GOOD, self.fb, self.prefs), [])

    def test_invented_number_and_dashes_fail(self):
        bad = GOOD.replace("cutting infrastructure cost 30%", "cutting infrastructure cost 45%")
        bad += "\nI am ready to start now — and I bring 20 years of Go.\n"
        issues = check_answers.check_text(bad, self.fb, self.prefs)
        text = json.dumps(issues)
        self.assertIn("45%", text)
        self.assertIn("20", text)
        self.assertIn("em dash", text)
        self.assertNotIn("30%", text)

    def test_cli_exit_codes(self):
        jid = "greenhouse-acme-1"
        d = jslib.job_dir(self.home, jid)
        d.mkdir(parents=True)
        (d / "answers.md").write_text(GOOD, encoding="utf-8")
        self.assertEqual(check_answers.main([jid, "--home", str(self.home)]), 0)
        (d / "answers.md").write_text(GOOD.replace("40 services", "400 services"), encoding="utf-8")
        self.assertEqual(check_answers.main([jid, "--home", str(self.home), "--json"]), 1)


if __name__ == "__main__":
    unittest.main()
