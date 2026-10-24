import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "job-search" / "scripts"))
import jslib  # noqa: E402


class JslibTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / jslib.MARKER).write_text("{}")

    def tearDown(self):
        self.tmp.cleanup()

    def test_resolve_home_order(self):
        self.assertEqual(jslib.resolve_home(str(self.home)), self.home.resolve())
        old = os.environ.get("JOBSEARCH_HOME")
        os.environ["JOBSEARCH_HOME"] = str(self.home)
        try:
            self.assertEqual(jslib.resolve_home(None), self.home.resolve())
        finally:
            if old is None:
                del os.environ["JOBSEARCH_HOME"]
            else:
                os.environ["JOBSEARCH_HOME"] = old

    def test_job_id_and_keys(self):
        self.assertEqual(jslib.make_job_id("greenhouse", "Stripe, Inc.", "123"), "greenhouse-stripe-inc-123")
        self.assertEqual(jslib.norm_key("Node.js"), "nodejs")
        self.assertEqual(jslib.norm_key("C++"), "cplusplus")
        self.assertEqual(jslib.iso_week("2026-10-24"), "2026-W43")

    def test_job_lifecycle(self):
        job = jslib.new_job("lever", "abc", "Plaid", "Staff Engineer", location="Remote")
        self.assertTrue(jslib.add_job(self.home, job, "desc"))
        self.assertFalse(jslib.add_job(self.home, job))
        jslib.set_status(self.home, job["id"], "applied")
        j = jslib.load_job(self.home, job["id"])
        self.assertEqual(j["status"], "applied")
        self.assertIsNotNone(j["applied_at"])
        self.assertEqual(len(j["status_history"]), 2)
        with self.assertRaises(SystemExit):
            jslib.set_status(self.home, job["id"], "bogus")
        self.assertEqual([x["id"] for x in jslib.iter_jobs(self.home)], [job["id"]])

    def test_signals_and_atomic_write(self):
        jslib.add_signal(self.home, "dismiss", job_id="x", detail="too junior")
        rows = jslib.read_jsonl(self.home / "memory" / "signals.jsonl")
        self.assertEqual(rows[0]["type"], "dismiss")
        with self.assertRaises(SystemExit):
            jslib.add_signal(self.home, "nope")
        p = self.home / "a.json"
        jslib.write_json(p, {"x": 1})
        self.assertEqual(json.loads(p.read_text()), {"x": 1})
        self.assertEqual([f for f in os.listdir(self.home) if f.startswith(".tmp-")], [])

    def test_fact_index(self):
        fb = json.loads((Path(__file__).parent / "fixtures" / "profile" / "fact-bank.json").read_text())
        idx = jslib.fact_index(fb)
        for k in ("sum.1", "r1", "r1.b3", "s.python", "e1", "c1", "p1"):
            self.assertIn(k, idx)


if __name__ == "__main__":
    unittest.main()
