"""Tests for job sources: ATS parsers, prefilter, ingest, add_job, verify. No network."""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins" / "job-search" / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import add_job  # noqa: E402
import jslib  # noqa: E402
import scan  # noqa: E402
import sources_lib as sl  # noqa: E402


def load_api(name):
    with open(FIXTURES / "api" / name, encoding="utf-8") as f:
        return json.load(f)


class FakeResp(io.BytesIO):
    pass


def fake_urlopen_factory(routes, calls=None):
    """routes: substring -> payload (dict/list) or int HTTP error code."""
    def fake(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        if calls is not None:
            calls.append((url, req.get_header("User-agent") if hasattr(req, "get_header") else None, timeout))
        for key, val in routes.items():
            if key in url:
                if isinstance(val, int):
                    raise urllib.error.HTTPError(url, val, "err", {}, None)
                if isinstance(val, Exception):
                    raise val
                return FakeResp(json.dumps(val).encode("utf-8"))
        raise urllib.error.HTTPError(url, 404, "not found", {}, None)
    return fake


PREFS = {
    "target_titles": ["Platform Architect", "Platform Engineer", "Infrastructure Architect", "AI Platform"],
    "keywords": ["platform", "kubernetes", "infrastructure", "developer experience"],
    "locations": ["Remote", "Denver, CO"],
    "remote": "remote",
    "deal_breakers": ["contract", "clearance required"],
}


class HomeCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        (self.home / "profile").mkdir()
        for f in (FIXTURES / "profile").iterdir():
            shutil.copy(f, self.home / "profile" / f.name)
        (self.home / "jobsearch.json").write_text('{"schema_version": 1}', encoding="utf-8")
        # Only the fixture boards we have recorded payloads for.
        jslib.write_json(self.home / "profile" / "sources.json", {
            "schema_version": 1,
            "sources": {
                "greenhouse": {"enabled": True, "has_access": True, "companies": ["stripe"]},
                "lever": {"enabled": True, "has_access": True, "companies": ["spotify"]},
                "ashby": {"enabled": True, "has_access": True, "companies": ["ramp"]},
                "indeed": {"enabled": False, "has_access": False, "queries": [], "max_per_run": 20},
            },
        })
        self.routes = {
            "boards-api.greenhouse.io/v1/boards/stripe/": load_api("greenhouse_stripe.json"),
            "api.lever.co/v0/postings/spotify": load_api("lever_spotify.json"),
            "api.ashbyhq.com/posting-api/job-board/ramp": load_api("ashby_ramp.json"),
        }

    def tearDown(self):
        self._tmp.cleanup()

    def signals(self):
        return jslib.read_jsonl(self.home / "memory" / "signals.jsonl")


class TestHtmlToText(unittest.TestCase):
    def test_greenhouse_double_escaped(self):
        raw = "&lt;h2&gt;About &amp;amp; us&lt;/h2&gt;&lt;p&gt;We &lt;strong&gt;build&lt;/strong&gt; things.&lt;/p&gt;" \
              "&lt;ul&gt;&lt;li&gt;Go&lt;/li&gt;&lt;li&gt;Kubernetes&lt;/li&gt;&lt;/ul&gt;"
        text = sl.html_to_text(raw)
        self.assertIn("## About & us", text)
        self.assertIn("We **build** things.", text)
        self.assertIn("- Go\n- Kubernetes", text)
        self.assertNotIn("&lt;", text)
        self.assertNotIn("<", text)

    def test_nested_and_ordered_lists(self):
        text = sl.html_to_text("<ol><li>One<ul><li>Sub</li></ul></li><li>Two</li></ol><p>a&nbsp;b</p>")
        self.assertIn("1. One", text)
        self.assertIn("  - Sub", text)
        self.assertIn("2. Two", text)
        self.assertIn("a b", text)

    def test_plain_text_passthrough(self):
        self.assertEqual(sl.html_to_text("Just text &amp; more"), "Just text & more\n")


class TestParsers(unittest.TestCase):
    def test_greenhouse(self):
        items = scan.parse_greenhouse(load_api("greenhouse_stripe.json"), "stripe", "Stripe")
        self.assertEqual(len(items), 3)
        be = [i for i in items if i["source_job_id"] == "7292520"][0]
        self.assertEqual(be["company"], "Stripe")
        self.assertEqual(be["remote"], "remote")
        self.assertTrue(be["url"].startswith("https://"))
        self.assertRegex(be["posted_at"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertIn("## Who we are", be["description"])
        self.assertNotIn("&lt;", be["description"])

    def test_lever(self):
        items = scan.parse_lever(load_api("lever_spotify.json"), "spotify", "Spotify")
        self.assertEqual(len(items), 3)
        by_id = {i["source_job_id"]: i for i in items}
        cpp = by_id["813b4b62-429c-42e9-a8f7-59e9412fb287"]
        self.assertEqual(cpp["company"], "Spotify")
        self.assertEqual(cpp["remote"], "remote")
        self.assertIn("jobs.lever.co/spotify", cpp["url"])
        self.assertTrue(cpp["apply_url"].endswith("/apply"))
        self.assertRegex(cpp["posted_at"], r"^20\d\d-\d\d-\d\d$")
        self.assertEqual(by_id["926149ab-6999-4058-b35d-41e302b70e05"]["remote"], "hybrid")
        self.assertIn("Stockholm", by_id["926149ab-6999-4058-b35d-41e302b70e05"]["location"])

    def test_ashby(self):
        items = scan.parse_ashby(load_api("ashby_ramp.json"), "ramp", "Ramp")
        plat = [i for i in items if i["title"] == "Software Engineer, Engineering Platform"][0]
        self.assertEqual(plat["remote"], "hybrid")  # workplaceType wins over isRemote
        self.assertIn("$", plat["salary"])
        self.assertIn("jobs.ashbyhq.com/ramp", plat["url"])
        self.assertIn("New York", plat["location"])
        self.assertIn("## About Ramp", plat["description"])

    def test_ashby_unlisted_skipped(self):
        payload = load_api("ashby_ramp.json")
        payload["jobs"][0]["isListed"] = False
        self.assertEqual(len(scan.parse_ashby(payload, "ramp", "Ramp")), len(payload["jobs"]) - 1)


class TestPrefilter(unittest.TestCase):
    def item(self, **kw):
        base = {"title": "Staff Platform Engineer", "location": "Remote - US", "remote": "remote",
                "description": "Build things.", "employment": ""}
        base.update(kw)
        return base

    def test_title_match(self):
        self.assertTrue(sl.prefilter(self.item(), PREFS)[0])
        self.assertTrue(sl.prefilter(self.item(title="Senior Infrastructure Architect"), PREFS)[0])
        self.assertTrue(sl.prefilter(self.item(title="Software Engineer, Engineering Platforms"), PREFS)[0])
        self.assertTrue(sl.prefilter(self.item(title="Kubernetes Engineer"), PREFS)[0])
        ok, why = sl.prefilter(self.item(title="Account Executive, Platforms"), PREFS)
        self.assertFalse(ok)
        self.assertTrue(why.startswith("title"))
        self.assertFalse(sl.prefilter(self.item(title="Recruiting Coordinator"), PREFS)[0])

    def test_deal_breaker(self):
        ok, why = sl.prefilter(self.item(title="Platform Engineer (Contract)"), PREFS)
        self.assertFalse(ok)
        self.assertIn("contract", why)
        ok, _ = sl.prefilter(self.item(description="This is a 6-month contract role."), PREFS)
        self.assertFalse(ok)
        ok, _ = sl.prefilter(self.item(description="Active TS clearance required."), PREFS)
        self.assertFalse(ok)
        self.assertFalse(sl.prefilter(self.item(employment="Contract"), PREFS)[0])
        # "contract" in an unrelated sense does not drop the job
        self.assertTrue(sl.prefilter(self.item(description="You will own contract renewals and smart contracts."), PREFS)[0])

    def test_country(self):
        self.assertEqual(sl.user_countries(PREFS), {"US"})
        self.assertFalse(sl.prefilter(self.item(location="Paris, France", remote="remote"), PREFS)[0])
        self.assertFalse(sl.prefilter(self.item(location="Remote", offices="Remote - France", remote="remote"), PREFS)[0])
        self.assertTrue(sl.prefilter(self.item(location="New York, NY", offices="Remote - California", remote="remote"), PREFS)[0])
        self.assertTrue(sl.prefilter(self.item(location="Remote", remote="remote"), PREFS)[0])
        self.assertTrue(sl.prefilter(self.item(location="Toronto", remote="remote"), dict(PREFS, countries=["CA"]))[0])

    def test_level_word_alone_is_not_a_match(self):
        # Journey bug: "Senior Data Engineer" let every "Senior ... Engineer" through.
        prefs = dict(PREFS, target_titles=["Senior Data Engineer", "Staff Data Engineer", "ML Platform Engineer"],
                     keywords=["spark", "kafka", "streaming"])
        for t in ("Senior Network Engineer, Office Technology", "Senior Executive IT Support Engineer",
                  "Staff Security Engineer, Incident Response", "Senior Software Engineer - Fullstack"):
            self.assertFalse(sl.title_ok(t, prefs)[0], t)
        for t in ("Senior Staff Data Engineer, Foundational Data", "Sr Data Engineer",
                  "Senior Software Engineer, Streaming Infrastructure", "Staff Platform Engineer, ML"):
            self.assertTrue(sl.title_ok(t, prefs)[0], t)

    def test_title_rank_orders_best_match_first(self):
        prefs = dict(PREFS, target_titles=["Staff Data Engineer", "Data Platform Engineer"], keywords=["streaming"])
        exact = sl.title_rank("Senior Staff Data Engineer, Payments", prefs)
        shuffled = sl.title_rank("Staff Software Engineer, Data Catalog", prefs)
        keyword = sl.title_rank("Senior Software Engineer, Streaming", prefs)
        self.assertGreater(exact, shuffled)
        self.assertGreater(shuffled, sl.title_rank("Senior Software Engineer, Backend", prefs))
        self.assertGreater(keyword, sl.title_rank("Senior Software Engineer, Backend", prefs))
        self.assertEqual(sl.title_rank("", prefs), 0.0)

    def test_remote_only_user_without_cities(self):
        # Journey bug: with locations ["Remote, US"] there are no places, so every
        # city-only posting with unknown remote status got through.
        prefs = dict(PREFS, locations=["Remote, US"], countries=["US"], remote="remote")
        self.assertFalse(sl.prefilter(self.item(location="Mountain View, California", remote="unknown"), prefs)[0])
        self.assertTrue(sl.prefilter(self.item(location="United States", remote="unknown"), prefs)[0])
        self.assertTrue(sl.prefilter(self.item(location="USA", remote="unknown"), prefs)[0])
        self.assertTrue(sl.prefilter(self.item(location="San Francisco, CA", remote="remote"), prefs)[0])
        # A user who also takes hybrid or onsite work is not affected.
        self.assertTrue(sl.prefilter(self.item(location="Mountain View, California", remote="unknown"),
                                     dict(prefs, remote="any"))[0])

    def test_more_countries_filtered(self):
        prefs = dict(PREFS, countries=["US"])
        self.assertFalse(sl.prefilter(self.item(location="Belgrade, Serbia", remote="remote"), prefs)[0])
        self.assertFalse(sl.prefilter(self.item(location="Aarhus, Denmark", remote="remote"), prefs)[0])
        self.assertTrue(sl.prefilter(self.item(location="Rome, GA", remote="remote"), prefs)[0])

    def test_remote_eligible_wording(self):
        desc = "While the position is Remote Eligible, you must live in a state where we have an entity."
        self.assertEqual(sl.infer_remote("San Francisco, CA", "Staff Data Engineer", description=desc), "remote")

    def test_title_synonyms(self):
        prefs = dict(PREFS, target_titles=["ML Platform Engineer"], keywords=[])
        self.assertTrue(sl.prefilter(self.item(title="Machine Learning Platform Engineer"), prefs)[0])
        prefs = dict(PREFS, target_titles=["Machine Learning Platform Engineer"], keywords=[])
        self.assertTrue(sl.prefilter(self.item(title="Sr. ML Platform Engineer"), prefs)[0])
        prefs = dict(PREFS, target_titles=["Site Reliability Engineer"], keywords=[])
        self.assertTrue(sl.prefilter(self.item(title="Staff SRE"), prefs)[0])

    def test_exclude_title_words(self):
        prefs = dict(PREFS, exclude_title_words=["marketing", "ios"])
        self.assertFalse(sl.prefilter(self.item(title="Platform Marketing Lead"), prefs)[0])
        self.assertFalse(sl.prefilter(self.item(title="Senior C++/iOS Engineer - User Platform"), prefs)[0])
        self.assertTrue(sl.prefilter(self.item(title="Staff Platform Engineer"), prefs)[0])

    def test_remote(self):
        # unknown remote status: a named city outside the user's places is skipped
        self.assertFalse(sl.prefilter(self.item(location="New York", remote="unknown"), PREFS)[0])
        self.assertTrue(sl.prefilter(self.item(location="", remote="unknown"), PREFS)[0])
        self.assertTrue(sl.prefilter(self.item(location="Denver, CO", remote="unknown"), PREFS)[0])
        self.assertTrue(sl.prefilter(self.item(location="Multiple locations", remote="unknown"), PREFS)[0])
        ok, why = sl.prefilter(self.item(location="London", remote="hybrid"), PREFS)
        self.assertFalse(ok)
        self.assertTrue(why.startswith("location"))
        self.assertFalse(sl.prefilter(self.item(location="Seattle, WA", remote="onsite"), PREFS)[0])
        self.assertTrue(sl.prefilter(self.item(location="Denver, CO", remote="onsite"), PREFS)[0])
        anyp = dict(PREFS, remote="any")
        self.assertTrue(sl.prefilter(self.item(location="London", remote="onsite"), anyp)[0])

    def test_infer_remote(self):
        self.assertEqual(sl.infer_remote("Remote in US"), "remote")
        self.assertEqual(sl.infer_remote("New York (Hybrid)"), "hybrid")
        self.assertEqual(sl.infer_remote("Seattle"), "unknown")
        self.assertEqual(sl.infer_remote("Seattle", description="This is a fully remote position."), "remote")

    def test_norm_date(self):
        self.assertEqual(sl.norm_date("2026-10-20T09:00:00Z"), "2026-10-20")
        self.assertEqual(sl.norm_date(1792767640768)[:4], "2026")
        self.assertIsNotNone(sl.norm_date("3 days ago"))
        self.assertIsNone(sl.norm_date("sometime"))


class TestScan(HomeCase):
    def test_scan_creates_jobs_and_dedupes(self):
        calls = []
        with mock.patch("urllib.request.urlopen", fake_urlopen_factory(self.routes, calls)):
            res = scan.run_scan(self.home)
        self.assertEqual(res["errors"], [])
        self.assertEqual(res["fetched"], 9)
        self.assertGreater(res["matched"], 0)
        self.assertEqual(res["new"], len(res["new_ids"]))
        self.assertIn("greenhouse-stripe-7292520", res["new_ids"])
        # remote in Sweden/UK is outside the user's country; hybrid NYC is not remote
        self.assertNotIn("lever-spotify-813b4b62-429c-42e9-a8f7-59e9412fb287", res["new_ids"])
        self.assertNotIn("ashby-ramp-198150d6-789a-4ef8-999f-93a49656d4f1", res["new_ids"])
        # sales roles and hybrid London jobs are filtered
        self.assertNotIn("greenhouse-stripe-8129956", res["new_ids"])
        self.assertNotIn("lever-spotify-926149ab-6999-4058-b35d-41e302b70e05", res["new_ids"])
        # user agent and timeout set
        self.assertTrue(all(ua and "job-search-plugin" in ua for _, ua, _ in calls))
        self.assertTrue(all(t == 20 for _, _, t in calls))
        job = jslib.load_job(self.home, "greenhouse-stripe-7292520")
        self.assertEqual(job["status"], "found")
        self.assertEqual(job["company"], "Stripe")
        jd = (jslib.job_dir(self.home, job["id"]) / "jd.md").read_text(encoding="utf-8")
        self.assertIn("# Backend Engineer, Developer & End-user Experience Platform", jd)

        with mock.patch("urllib.request.urlopen", fake_urlopen_factory(self.routes)):
            res2 = scan.run_scan(self.home)
        self.assertEqual(res2["new"], 0)
        self.assertEqual(res2["known"], res["matched"])

    def test_dry_run_writes_nothing(self):
        with mock.patch("urllib.request.urlopen", fake_urlopen_factory(self.routes)):
            res = scan.run_scan(self.home, dry_run=True)
        self.assertGreater(res["new"], 0)
        self.assertFalse((self.home / "jobs").exists())

    def test_source_filter_and_limit(self):
        with mock.patch("urllib.request.urlopen", fake_urlopen_factory(self.routes)):
            res = scan.run_scan(self.home, wanted=["greenhouse"], limit_per_company=1)
        self.assertEqual(res["fetched"], 3)
        self.assertEqual(res["new"], 1)

    def test_error_records_signal_and_continues(self):
        jslib.write_json(self.home / "profile" / "sources.json", {"schema_version": 1, "sources": {
            "greenhouse": {"enabled": True, "has_access": True, "companies": ["nosuchco", "stripe"]},
            "lever": {"enabled": True, "has_access": True, "companies": ["spotify"]},
            "ashby": {"enabled": True, "has_access": True, "companies": ["ramp"]},
        }})
        routes = dict(self.routes)
        routes["boards/nosuchco/"] = 404
        routes["api.lever.co/v0/postings/spotify"] = urllib.error.URLError("timed out")
        with mock.patch("urllib.request.urlopen", fake_urlopen_factory(routes)):
            res = scan.run_scan(self.home)
        self.assertEqual(len(res["errors"]), 2)
        self.assertTrue(any("greenhouse/nosuchco" in e and "404" in e for e in res["errors"]))
        self.assertGreater(res["new"], 0)  # stripe and ramp still scanned
        sigs = [s for s in self.signals() if s["type"] == "source_error"]
        self.assertEqual(len(sigs), 2)
        self.assertEqual(sigs[0]["skill"], "scan")

    def test_all_boards_blocked_reports_network(self):
        routes = {k: urllib.error.URLError(OSError("Tunnel connection failed: 403 Forbidden"))
                  for k in self.routes}
        with mock.patch("urllib.request.urlopen", fake_urlopen_factory(routes)):
            res = scan.run_scan(self.home)
        self.assertTrue(res.get("network_blocked"))
        self.assertIn("Domain allowlist", res["errors"][0])
        # a single blocked board among working ones is just an error
        routes = dict(self.routes)
        routes["boards-api.greenhouse.io/v1/boards/stripe/"] = 403
        with mock.patch("urllib.request.urlopen", fake_urlopen_factory(routes)):
            res = scan.run_scan(self.home)
        self.assertFalse(res.get("network_blocked"))
        self.assertTrue(any("403" in e for e in res["errors"]))

    def test_browser_next_always_keeps_indeed(self):
        cfg = {"sources": {"indeed": {"enabled": True, "has_access": False},
                           "dice": {"enabled": True, "has_access": False},
                           "linkedin": {"enabled": True, "has_access": True},
                           "greenhouse": {"enabled": True, "companies": ["stripe"]}}}
        todo = {b["source"]: b["do"] for b in scan.browser_next(cfg)}
        self.assertEqual(set(todo), {"indeed", "dice", "linkedin"})
        self.assertIn("Fallback without Chrome", todo["indeed"])
        self.assertTrue(todo["dice"].startswith("skip"))
        self.assertIn("Chrome", todo["linkedin"])
        cfg["sources"]["indeed"]["enabled"] = False
        self.assertNotIn("indeed", {b["source"] for b in scan.browser_next(cfg)})

    def test_cli_json(self):
        out = io.StringIO()
        with mock.patch("urllib.request.urlopen", fake_urlopen_factory(self.routes)), \
                mock.patch("sys.stdout", out):
            rc = scan.main(["--home", str(self.home), "--json", "--dry-run"])
        self.assertEqual(rc, 0)
        data = json.loads(out.getvalue())
        for k in ("fetched", "matched", "new", "known", "new_ids", "errors"):
            self.assertIn(k, data)


class TestVerify(HomeCase):
    def test_verify_closes_missing(self):
        prefs = jslib.load_preferences(self.home)
        prefs["remote"] = "any"  # keep every source's jobs so verify has something to check
        prefs["exclude_title_words"] = []
        jslib.write_json(self.home / "profile" / "preferences.json", prefs)
        with mock.patch("urllib.request.urlopen", fake_urlopen_factory(self.routes)):
            res = scan.run_scan(self.home)
        gone = "greenhouse-stripe-7292520"
        lever_gone = "lever-spotify-813b4b62-429c-42e9-a8f7-59e9412fb287"
        self.assertIn(gone, res["new_ids"])
        # A job already applied to is never touched by verify.
        applied = [j for j in res["new_ids"] if j.startswith("ashby-")][0]
        jslib.set_status(self.home, applied, "applied")

        gh = load_api("greenhouse_stripe.json")
        gh["jobs"] = [j for j in gh["jobs"] if str(j["id"]) != "7292520"]
        lv = [j for j in load_api("lever_spotify.json") if j["id"] != lever_gone.split("spotify-", 1)[1]]
        routes = {
            "boards-api.greenhouse.io/v1/boards/stripe/": gh,
            "api.lever.co/v0/postings/spotify": lv,
            "api.ashbyhq.com/posting-api/job-board/ramp": {"jobs": []},
        }
        with mock.patch("urllib.request.urlopen", fake_urlopen_factory(routes)):
            vres = scan.run_verify(self.home)
        self.assertIn(gone, vres["closed_ids"])
        self.assertIn(lever_gone, vres["closed_ids"])
        self.assertNotIn(applied, vres["closed_ids"])
        self.assertEqual(jslib.load_job(self.home, gone)["status"], "closed")
        self.assertEqual(jslib.load_job(self.home, applied)["status"], "applied")
        still = [j for j in res["new_ids"] if j not in vres["closed_ids"] and j != applied]
        for jid in still:
            self.assertEqual(jslib.load_job(self.home, jid)["status"], "found")

    def test_verify_fetch_error_leaves_jobs(self):
        with mock.patch("urllib.request.urlopen", fake_urlopen_factory(self.routes)):
            res = scan.run_scan(self.home)
        with mock.patch("urllib.request.urlopen", fake_urlopen_factory({"greenhouse": 500, "lever": 500, "ashby": 500})):
            vres = scan.run_verify(self.home)
        self.assertEqual(vres["closed"], 0)
        self.assertEqual(vres["unverified"], len(res["new_ids"]))
        self.assertTrue(vres["errors"])


class TestAddJob(HomeCase):
    def entries(self):
        return [
            {"source": "indeed", "company": "Acme Health", "title": "Senior Platform Engineer",
             "location": "Remote", "url": "https://www.indeed.com/viewjob?jk=abc123",
             "salary": "$180,000 - $210,000", "posted_at": "2 days ago",
             "description": "<p>Build our <b>Kubernetes</b> platform.</p><ul><li>Go</li></ul>"},
            {"source": "dice", "source_job_id": "d-9", "company": "Beta", "title": "Platform Architect",
             "location": "Austin, TX", "remote": "onsite", "url": "https://www.dice.com/job-detail/d-9",
             "description": "Onsite only."},
            {"source": "linkedin", "company": "Gamma", "title": "Infrastructure Architect",
             "location": "Remote", "url": "https://www.linkedin.com/jobs/view/42",
             "description": "This is a 12 month contract position."},
            {"source": "indeed", "title": "No company"},
        ]

    def test_ingest_filters_and_derives_id(self):
        res = add_job.run_add(self.home, self.entries())
        self.assertEqual(res["fetched"], 4)
        self.assertEqual(res["matched"], 1)
        self.assertEqual(res["new"], 1)
        self.assertEqual(len(res["errors"]), 1)
        jid = res["new_ids"][0]
        expected = jslib.make_job_id("indeed", "Acme Health", sl.stable_id_from("https://www.indeed.com/viewjob?jk=abc123"))
        self.assertEqual(jid, expected)
        job = jslib.load_job(self.home, jid)
        self.assertEqual(job["remote"], "remote")
        self.assertEqual(job["apply_url"], job["url"])
        self.assertRegex(job["posted_at"], r"^\d{4}-\d{2}-\d{2}$")
        jd = (jslib.job_dir(self.home, jid) / "jd.md").read_text(encoding="utf-8")
        self.assertIn("**Kubernetes**", jd)
        self.assertIn("- Go", jd)
        # same input again: known, not new
        res2 = add_job.run_add(self.home, self.entries()[:1])
        self.assertEqual((res2["new"], res2["known"]), (0, 1))

    def test_no_filter(self):
        res = add_job.run_add(self.home, self.entries()[:3], use_filter=False)
        self.assertEqual(res["new"], 3)

    def test_cli_file(self):
        p = self.home / "in.json"
        p.write_text(json.dumps(self.entries()[0]), encoding="utf-8")
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            rc = add_job.main(["--home", str(self.home), "--file", str(p), "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["new"], 1)



class TestRefilter(HomeCase):
    def test_refilter_skips_found_jobs_that_no_longer_pass(self):
        keep = jslib.new_job("manual", "1", "Acme", "Staff Platform Engineer", location="Remote", remote="remote")
        drop = jslib.new_job("manual", "2", "Acme", "Platform Marketing Lead", location="Remote", remote="remote")
        done = jslib.new_job("manual", "3", "Acme", "Platform Marketing Manager", location="Remote", remote="remote")
        for j in (keep, drop, done):
            jslib.add_job(self.home, j, "Build things.")
        jslib.set_status(self.home, done["id"], "applied")
        prefs = jslib.load_preferences(self.home)
        prefs["exclude_title_words"] = ["marketing"]
        jslib.write_json(self.home / "profile" / "preferences.json", prefs)
        res = scan.run_refilter(self.home, dry_run=True)
        self.assertEqual([x[0] for x in res["skipped"]], [drop["id"]])
        self.assertEqual(jslib.load_job(self.home, drop["id"])["status"], "found")
        scan.run_refilter(self.home)
        self.assertEqual(jslib.load_job(self.home, drop["id"])["status"], "skipped")
        self.assertEqual(jslib.load_job(self.home, keep["id"])["status"], "found")
        self.assertEqual(jslib.load_job(self.home, done["id"])["status"], "applied")

if __name__ == "__main__":
    unittest.main()
