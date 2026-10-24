import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "job-search" / "scripts"))
import jslib  # noqa: E402
import memory  # noqa: E402
import radar  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "profile"


def good_radar():
    sig = [{"text": "Seen at 6 employers in 2026", "url": "https://example.com/report"}]
    return {
        "as_of": "2026-10-24",
        "verdict": "Best fit now: Platform Architect. Top bet: AI Platform Engineer.",
        "actions": [{"text": "Apply to X", "url": "https://job-boards.greenhouse.io/mercury/jobs/6221407004"},
                    {"text": "Apply to Y", "url": "https://jobs.lever.co/acme/123"},
                    {"text": "Already scanned", "url": "https://boards.greenhouse.io/stripe/jobs/1"}],
        "titles_now": [
            {"title": "Platform Architect", "fit": "high", "momentum": "medium"},
            {"title": "Staff Infrastructure Engineer", "fit": "H", "momentum": "high"},
            {"title": "Data Engineer", "fit": "low", "momentum": "high"},
        ],
        "skill_demand": [{"skill": "Kubernetes", "count": 14, "sample": 18, "required": 11, "you": "have"},
                         {"skill": "Terraform", "count": 9, "sample": 18, "required": 6, "you": "bogus"}],
        "rising_skills": [{"skill": "LLM evaluation", "confidence": "high", "signals": sig},
                          {"skill": "Vibes", "confidence": "high", "signals": [{"text": "trust me"}]}],
        "emerging_titles": [{"title": "ML Platform Engineer", "confidence": "medium", "horizon_months": 24,
                             "fit": "high", "signals": sig}],
        "jd_shifts": [],
        "titles_at_risk": [{"title": "Release Engineer", "why": "automation", "signals": sig}],
        "resume_language": [{"market_term": "internal developer platform", "your_term": "developer platform",
                             "fact_ids": ["r1.b2"]},
                            {"market_term": "MLOps", "your_term": "", "fact_ids": ["nope"]}],
        "sources": [{"title": "Report", "url": "https://example.com/report"}, {"title": "no url"}],
    }


class RadarTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / jslib.MARKER).write_text("{}")
        shutil.copytree(FIX, self.home / "profile")

    def tearDown(self):
        self.tmp.cleanup()

    def test_validate_drops_uncited_and_unbacked(self):
        out, notes = radar.validate(good_radar(), jslib.load_fact_bank(self.home))
        self.assertEqual([r["skill"] for r in out["rising_skills"]], ["LLM evaluation"])
        self.assertEqual([r["market_term"] for r in out["resume_language"]], ["internal developer platform"])
        self.assertEqual(out["titles_now"][1]["fit"], "high")  # "H" normalized
        self.assertEqual(out["skill_demand"][1]["you"], "gap")
        self.assertEqual(len(out["sources"]), 1)
        self.assertTrue(any("Vibes" in n for n in notes))
        self.assertTrue(any("MLOps" in n for n in notes))

    def test_verdict_required(self):
        r = good_radar()
        r["verdict"] = ""
        with self.assertRaises(SystemExit):
            radar.validate(r, {})

    def test_save_and_status(self):
        path, _ = radar.save(self.home, good_radar(), "radar/radar-2026-10-24.md")
        self.assertTrue(path.exists())
        latest = radar.load_latest(self.home)
        self.assertEqual(latest["report"], "radar/radar-2026-10-24.md")
        s = radar.status(self.home, today="2026-10-30")
        self.assertEqual(s["age_days"], 6)
        self.assertFalse(s["due"])
        self.assertTrue(radar.status(self.home, today="2026-12-01")["due"])
        prefs = jslib.load_preferences(self.home)
        prefs["radar_every_days"] = 0
        jslib.write_json(self.home / "profile" / "preferences.json", prefs)
        self.assertFalse(radar.status(self.home, today="2027-06-01")["due"])

    def test_unfinished_run_is_flagged_until_saved(self):
        today = jslib.today()
        radar.mark_start(self.home)
        s = radar.status(self.home, today=today)
        self.assertTrue(s["started_today_unfinished"])
        self.assertEqual(s["last_started"], today)
        self.assertFalse(radar.status(self.home, today="2099-01-01")["started_today_unfinished"])
        r = good_radar()
        r["as_of"] = today
        radar.save(self.home, r)
        s = radar.status(self.home, today=today)
        self.assertFalse(s["started_today_unfinished"])
        self.assertEqual(s["last_finished"], today)
        self.assertEqual(s["age_days"], 0)
        self.assertTrue(s["verdict"])

    def test_unconfigured_boards(self):
        self.assertEqual(radar.unconfigured_boards(self.home), [])
        radar.save(self.home, good_radar())
        tokens = sorted(b["token"] for b in radar.unconfigured_boards(self.home))
        self.assertEqual(tokens, ["acme", "mercury"])

    def test_status_without_radar(self):
        s = radar.status(self.home)
        self.assertFalse(s["exists"])
        self.assertTrue(s["due"])

    def test_propose_adds_only_new_high_fit_titles_once(self):
        radar.save(self.home, good_radar())
        made = radar.propose(self.home)
        boards = [p for p in made if p["kind"] == "source"]
        made = [p for p in made if p["kind"] == "preference"]
        self.assertEqual(sorted(list(p["patch"]["append"].values())[0][0] for p in boards), ["acme", "mercury"])
        titles = sorted(p["patch"]["append"]["target_titles"][0] for p in made)
        # Platform Architect is already a target; Data Engineer is low fit
        self.assertEqual(titles, ["ML Platform Engineer", "Staff Infrastructure Engineer"])
        self.assertEqual(radar.propose(self.home), [])  # pending ones are not repeated
        pid = made[0]["id"]
        memory.decide_proposal(self.home, pid, "decline")
        self.assertEqual(radar.propose(self.home), [])  # declined ones are not proposed again
        # accepting appends to target_titles and never touches anything else
        other = made[1]["id"]
        memory.decide_proposal(self.home, other, "accept")
        prefs = jslib.load_preferences(self.home)
        self.assertIn(made[1]["patch"]["append"]["target_titles"][0], prefs["target_titles"])

    def test_accepting_board_proposal_adds_company(self):
        radar.save(self.home, good_radar())
        board = [p for p in radar.propose(self.home) if "mercury" in p["text"]][0]
        memory.decide_proposal(self.home, board["id"], "accept")
        gh = jslib.load_sources(self.home)["sources"]["greenhouse"]
        self.assertIn("mercury", gh["companies"])
        self.assertTrue(gh["enabled"])

    def test_local_tally(self):
        sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
        import make_demo_home
        demo = Path(self.tmp.name) / "demo"
        make_demo_home.main([str(demo), "--today", "2026-10-24"]) if hasattr(make_demo_home, "main") else None
        if not (demo / jslib.MARKER).exists():
            self.skipTest("make_demo_home has no main()")
        t = radar.local_tally(demo, days=90, today="2026-10-24")
        self.assertGreater(t["sample"], 5)
        top = {r["skill"].lower(): r for r in t["skill_demand"]}
        self.assertIn("terraform", top)
        self.assertEqual(top["terraform"]["you"], "gap")
        self.assertTrue(all(r["sample"] == t["sample"] for r in t["skill_demand"]))


if __name__ == "__main__":
    unittest.main()
