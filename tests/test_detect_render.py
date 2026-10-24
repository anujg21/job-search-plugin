"""detect_edits.py re-renders a resume the user edited by hand. No network, no Chrome."""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins" / "job-search" / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import classify_changes  # noqa: E402
import detect_edits  # noqa: E402
import jslib  # noqa: E402
import render_resume  # noqa: E402
import resume_lib as rl  # noqa: E402

JOB_ID = "greenhouse-acme-1"


class DetectRenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / "profile").mkdir()
        for p in (FIXTURES / "profile").iterdir():
            shutil.copy(p, self.home / "profile" / p.name)
        jslib.write_json(self.home / jslib.MARKER, {"schema_version": 1})
        jslib.add_job(self.home, jslib.new_job("greenhouse", "1", "Acme", "Staff Platform Engineer"))
        fb = jslib.load_fact_bank(self.home)
        self.resume = rl.build_master(fb, JOB_ID)
        jslib.write_json(jslib.job_dir(self.home, JOB_ID) / "resume.json", self.resume)
        classify_changes.classify_job(self.home, JOB_ID)
        render_resume.render(self.home, JOB_ID, False, False)

    def tearDown(self):
        self.tmp.cleanup()

    def test_edited_resume_is_rendered_again(self):
        # Journey bug: after a hand edit the PDF and HTML still showed the old wording.
        new_text = "Ran the move of 40 services to Kubernetes on AWS EKS, which cut infrastructure cost 30%"
        self.resume["roles"][0]["bullets"][0]["text"] = new_text
        jslib.write_json(jslib.job_dir(self.home, JOB_ID) / "resume.json", self.resume)
        html = jslib.job_dir(self.home, JOB_ID) / "resume.html"
        self.assertNotIn("Ran the move", html.read_text(encoding="utf-8"))

        res = detect_edits.detect(self.home, render=True, pdf=False)
        self.assertEqual(len(res), 1)
        self.assertTrue(res[0]["rendered"].endswith("resume.html"))
        self.assertIn("Ran the move", html.read_text(encoding="utf-8"))

    def test_no_render_leaves_files(self):
        self.resume["roles"][0]["bullets"][0]["text"] = "Ran the move of 40 services to Kubernetes"
        jslib.write_json(jslib.job_dir(self.home, JOB_ID) / "resume.json", self.resume)
        res = detect_edits.detect(self.home)
        self.assertNotIn("rendered", res[0])


if __name__ == "__main__":
    unittest.main()
