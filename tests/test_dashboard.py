"""Tests for the skills-gap ledger (gaps.py) and the static dashboard (build_dashboard.py)."""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "plugins" / "job-search" / "scripts"
FIXTURES = REPO / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(FIXTURES))

import jslib  # noqa: E402
import gaps  # noqa: E402
import build_dashboard  # noqa: E402
import serve_dashboard  # noqa: E402
import make_demo_home  # noqa: E402

TODAY = "2026-10-24"


def make_home(tmp: str) -> Path:
    home = Path(tmp) / "home"
    shutil.copytree(str(FIXTURES / "profile"), str(home / "profile"))
    jslib.write_json(home / jslib.MARKER, {"schema_version": 1, "created_at": "2026-10-01T00:00:00Z",
                                           "plugin_version": jslib.PLUGIN_VERSION})
    return home


def add_scored(home: Path, sid: str, missing, scored_at="2026-10-22T10:00:00Z", title=None,
               company="Acme", status="scored"):
    # A distinct title per job by default: the same company and title counts as one role.
    title = title or "Platform Engineer, Team %s" % sid
    job = jslib.new_job("greenhouse", sid, company, title, url="https://example.com/jobs/%s" % sid)
    job["status"] = status
    jslib.add_job(home, job)
    jslib.write_json(jslib.job_dir(home, job["id"]) / "score.json", {
        "schema_version": 1, "job_id": job["id"], "score": 4.0, "recommendation": "apply",
        "summary": "ok", "matched": [], "keywords": [], "deal_breakers_hit": [],
        "missing": [{"item": i, "category": c, "required": r} for i, c, r in missing],
        "scored_at": scored_at,
    })
    return job["id"]


def extract_payload(html: str) -> dict:
    m = re.search(r'<script type="application/json" id="dashboard-data">(.*?)</script>', html, re.S)
    assert m, "payload tag missing"
    return json.loads(m.group(1))


class GapsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = make_home(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_home(self):
        data = gaps.build_gaps(self.home, today=TODAY)
        self.assertEqual(data["total_jds"], 0)
        self.assertEqual(data["items"], {})
        self.assertEqual(data["ranking"], [])
        self.assertIn("No gaps yet", gaps.format_table(data, 10))
        self.assertIn("No skills gaps", gaps.format_nudge(data))

    def test_counts_aliases_required_and_weekly(self):
        a = add_scored(self.home, "1", [("Terraform", "tool", True), ("K8s", "tool", False), ("Go", "hard_skill", True)],
                       scored_at="2026-10-22T10:00:00Z")
        b = add_scored(self.home, "2", [("Terraform (IaC)", "tool", False), ("Kubernetes", "tool", True)],
                       scored_at="2026-10-14T10:00:00Z")
        add_scored(self.home, "3", [("terraform", "tool", True), ("GCP", "tool", False), ("Google Cloud", "tool", True)],
                   scored_at="2026-10-23T10:00:00Z")
        add_scored(self.home, "4", [("LLMs", "hard_skill", True)], scored_at="2026-10-23T10:00:00Z")
        add_scored(self.home, "5", [("LLM", "hard_skill", False)], scored_at="2026-10-23T10:00:00Z")
        data = gaps.build_gaps(self.home, today=TODAY)
        items = data["items"]
        self.assertEqual(data["total_jds"], 5)

        tf = items["terraform"]
        self.assertEqual(tf["count"], 3)
        self.assertEqual(tf["required_count"], 2)
        self.assertEqual(tf["name"], "Terraform")  # most common display form... ties broken alphabetically
        self.assertEqual(tf["first_seen"], "2026-10-14")
        self.assertEqual(tf["last_seen"], "2026-10-23")
        self.assertEqual(tf["weekly"], {"2026-W42": 1, "2026-W43": 2})
        self.assertIn(a, tf["job_ids"])
        self.assertIn(b, tf["job_ids"])

        self.assertNotIn("k8s", items)
        self.assertEqual(items["kubernetes"]["count"], 2)
        self.assertEqual(items["kubernetes"]["required_count"], 1)
        # GCP and Google Cloud in the same job count once, required if either was required
        self.assertEqual(items["google-cloud"]["count"], 1)
        self.assertEqual(items["google-cloud"]["required_count"], 1)
        self.assertNotIn("gcp", items)
        self.assertEqual(items["llm"]["count"], 2)
        self.assertNotIn("llms", items)

        rank = {r["key"]: r for r in data["ranking"]}
        self.assertAlmostEqual(rank["terraform"]["share"], 0.6)
        self.assertAlmostEqual(rank["terraform"]["required_ratio"], round(2 / 3.0, 4))
        # kubernetes relates to preferences.keywords, so it gets the 1.2 boost
        self.assertTrue(rank["kubernetes"]["related"])
        self.assertAlmostEqual(rank["kubernetes"]["score"], round(0.4 * 0.75 * 1.0 * 1.2, 4))
        self.assertAlmostEqual(rank["terraform"]["score"], round(0.6 * (0.5 + 0.5 * 2 / 3.0) * 1.0, 4))
        self.assertEqual(data["ranking"][0]["key"], "terraform")

    def test_ignore_and_done_excluded_from_ranking_but_kept(self):
        add_scored(self.home, "1", [("Terraform", "tool", True), ("Go", "hard_skill", True), ("Kafka", "tool", False)])
        jslib.write_json(self.home / "profile" / "gap-notes.json", {
            "terraform": {"status": "ignore", "note": ""},
            "golang": {"status": "done", "note": "alias key still applies"},
            "kafka": {"status": "learning", "note": ""},
        })
        data = gaps.build_gaps(self.home, today=TODAY)
        ranked = [r["key"] for r in data["ranking"]]
        self.assertNotIn("terraform", ranked)
        self.assertNotIn("go", ranked)
        self.assertIn("kafka", ranked)
        self.assertIn("terraform", data["items"])
        self.assertEqual(data["items"]["go"]["note_status"], "done")

    def test_recency_decay(self):
        self.assertEqual(gaps.recency_factor("2026-10-20", TODAY), 1.0)
        self.assertEqual(gaps.recency_factor("2026-07-01", TODAY), 0.5)
        mid = gaps.recency_factor("2026-09-01", TODAY)  # 53 days old
        self.assertTrue(0.5 < mid < 1.0)

    def test_idempotent_rebuild_and_cli(self):
        add_scored(self.home, "1", [("Terraform", "tool", True)])
        out = io.StringIO()
        with redirect_stdout(out):
            gaps.main(["--home", str(self.home), "--today", TODAY])
        first = jslib.read_json(self.home / "gaps.json")
        with redirect_stdout(io.StringIO()):
            gaps.main(["--home", str(self.home), "--today", TODAY])
        second = jslib.read_json(self.home / "gaps.json")
        first.pop("updated_at"); second.pop("updated_at")
        self.assertEqual(first, second)
        self.assertIn("Terraform", out.getvalue())
        nudge = io.StringIO()
        with redirect_stdout(nudge):
            gaps.main(["--home", str(self.home), "--nudge", "--today", TODAY])
        self.assertIn("/job-search:feedback gap terraform learning", nudge.getvalue())
        self.assertIn("required in 1", nudge.getvalue())


def write_radar(home: Path, **over):
    sig = [{"text": "seen in postings", "url": "https://example.com/r"}]
    radar = {
        "schema_version": 1, "as_of": "2026-10-20", "report": "radar/radar-2026-10-20.md",
        "verdict": "Best fit now: Platform Engineer.",
        "actions": [{"text": "Apply: Staff Platform Engineer", "url": "https://example.com/apply"}],
        "titles_now": [{"title": "Platform Engineer", "fit": "high", "momentum": "high", "why": "core match"},
                       {"title": "SRE", "fit": "medium", "momentum": "low", "why": "on-call"}],
        "skill_demand": [{"skill": "Kubernetes", "count": 9, "sample": 12, "required": 8, "you": "have"},
                         {"skill": "Kafka", "count": 4, "sample": 12, "required": 2, "you": "gap"}],
        "rising_skills": [{"skill": "Terraform / IaC", "confidence": "high", "signals": sig},
                          {"skill": "LLM evaluation", "confidence": "medium", "signals": sig},
                          {"skill": "Python", "confidence": "low", "signals": sig}],
        "emerging_titles": [{"title": "AI Platform Engineer", "confidence": "medium", "horizon_months": 24,
                             "fit": "high", "signals": sig, "fit_note": "k8s plus LLM", "watch_for": "x"}],
        "jd_shifts": [{"change": "Terraform moves to required", "confidence": "medium", "horizon_months": 12, "signals": sig}],
        "titles_at_risk": [{"title": "Release Engineer", "why": "automation", "signals": sig}],
        "resume_language": [{"market_term": "internal developer platform", "your_term": "developer platform", "fact_ids": ["r1.b2"]}],
        "sources": [{"title": "Report", "publisher": "Pub", "date": "2026-09", "url": "https://example.com/r"}],
    }
    radar.update(over)
    jslib.write_json(home / "radar" / "latest.json", radar)
    return radar


class GapsRadarTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = make_home(self.tmp.name)
        add_scored(self.home, "1", [("Terraform", "tool", True), ("Kafka", "tool", True), ("Rust", "hard_skill", True)])
        add_scored(self.home, "2", [("Terraform (IaC)", "tool", True), ("Kafka", "tool", True), ("Rust", "hard_skill", True)])

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_radar_changes_nothing(self):
        data = gaps.build_gaps(self.home, today=TODAY)
        self.assertFalse(any(it.get("rising") for it in data["items"].values()))
        self.assertEqual(data["radar_only_rising"], [])
        self.assertIsNone(data["radar_as_of"])
        self.assertEqual({r["score"] for r in data["ranking"]}, {1.0})

    def test_rising_flag_and_boost(self):
        write_radar(self.home)
        data = gaps.build_gaps(self.home, today=TODAY)
        it = data["items"]
        self.assertTrue(it["terraform"]["rising"])  # "Terraform / IaC" matched through its parts
        self.assertEqual(it["terraform"]["rising_confidence"], "high")
        self.assertTrue(it["kafka"]["rising"])  # skill_demand gap
        self.assertEqual(it["kafka"]["rising_confidence"], "medium")
        self.assertNotIn("rising", it["rust"])
        rank = {r["key"]: r for r in data["ranking"]}
        self.assertAlmostEqual(rank["terraform"]["score"], 1.15)
        self.assertAlmostEqual(rank["kafka"]["score"], 1.08)
        self.assertAlmostEqual(rank["rust"]["score"], 1.0)
        self.assertEqual([r["key"] for r in data["ranking"]], ["terraform", "kafka", "rust"])
        self.assertEqual(data["radar_as_of"], "2026-10-20")
        # LLM evaluation is in no scored job and not in the fact bank; Python is in the fact bank
        self.assertEqual([e["skill"] for e in data["radar_only_rising"]], ["LLM evaluation"])
        self.assertEqual(data["radar_only_rising"][0]["url"], "https://example.com/r")
        self.assertIn("^ rising", gaps.format_table(data, 10))
        self.assertIn("career radar marks it as rising", gaps.format_nudge(data))

    def test_radar_only_skips_skills_named_inside_a_ledger_gap(self):
        add_scored(self.home, "3", [("Observability platforms", "tool", False)])
        sig = [{"text": "x", "url": "https://example.com/r"}]
        write_radar(self.home, rising_skills=[{"skill": "Observability", "confidence": "low", "signals": sig},
                                              {"skill": "Go", "confidence": "low", "signals": sig},
                                              {"skill": "Agent sandboxing", "confidence": "low", "signals": sig}])
        data = gaps.build_gaps(self.home, today=TODAY)
        # Observability is part of a gap the user's jobs asked for; Go is a fact bank skill
        self.assertEqual([e["skill"] for e in data["radar_only_rising"]], ["Agent sandboxing"])
        # the rising flag itself stays on exact keys
        self.assertNotIn("rising", data["items"]["observability-platforms"])

    def test_bad_radar_file_is_ignored(self):
        (self.home / "radar").mkdir()
        (self.home / "radar" / "latest.json").write_text("{nope", encoding="utf-8")
        data = gaps.build_gaps(self.home, today=TODAY)
        self.assertEqual(data["radar_only_rising"], [])


class GapsDedupeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = make_home(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_same_role_in_two_cities_counts_once(self):
        # Journey bug: one Databricks role posted in Mountain View and San Francisco made
        # its gaps count double and pushed them to the top of the ranking.
        add_scored(self.home, "1", [("Java", "hard_skill", True)], title="Staff Software Engineer - Data Systems",
                   company="Databricks")
        add_scored(self.home, "2", [("Java", "hard_skill", True)], title="Staff Software Engineer - Data Systems",
                   company="Databricks")
        add_scored(self.home, "3", [("dbt", "tool", True)], title="Senior Data Engineer", company="Databricks")
        data = gaps.build_gaps(self.home, today=TODAY)
        self.assertEqual(data["total_jds"], 2)
        self.assertEqual(data["items"]["java"]["count"], 1)


class DashboardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = make_home(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def assert_no_external_loads(self, html: str):
        patterns = [
            r'<script[^>]+src\s*=',
            r'<link[^>]+href\s*=\s*["\']?(https?:)?//',
            r'<img[^>]+src\s*=\s*["\']?(https?:)?//',
            r'<iframe',
            r'@import',
            r'url\(\s*["\']?(https?:)?//',
            r'(src|href)\s*=\s*["\']https?://',
        ]
        for p in patterns:
            self.assertIsNone(re.search(p, html, re.I), "external resource pattern %r found" % p)

    def test_builds_on_empty_home(self):
        out = build_dashboard.build(self.home)
        self.assertEqual(out, self.home / "dashboard.html")
        html = out.read_text(encoding="utf-8")
        self.assertNotIn(build_dashboard.PLACEHOLDER, html)
        data = extract_payload(html)
        self.assertEqual(data["jobs"], [])
        self.assertEqual(data["runs"], [])
        self.assertIn("No jobs yet.", html)
        self.assertIn("Run /job-search:run in Claude", html)
        self.assert_no_external_loads(html)

    def test_builds_on_populated_demo_home(self):
        demo = Path(self.tmp.name) / "demo"
        make_demo_home.make(demo, TODAY)
        html_path = build_dashboard.build(demo)
        html = html_path.read_text(encoding="utf-8")
        self.assert_no_external_loads(html)
        data = extract_payload(html)
        self.assertGreaterEqual(len(data["jobs"]), 20)
        self.assertTrue(0 < len(data["runs"]) <= build_dashboard.RUN_LOG_LIMIT)
        statuses = {j["status"] for j in data["jobs"]}
        for s in ("found", "prepared", "needs_approval", "applied", "interview", "dismissed"):
            self.assertIn(s, statuses)
        pending = [j for j in data["jobs"] if j["approval"] == "pending"]
        self.assertTrue(pending)
        self.assertTrue(any(j["changes"]["verify"]["issues"] for j in pending))
        with_resume = [j for j in data["jobs"] if j["files"].get("resume_html")]
        self.assertTrue(with_resume)
        rel = with_resume[0]["files"]["resume_html"]
        self.assertTrue(rel.startswith("jobs/") and rel.endswith("/resume.html"))
        self.assertTrue((demo / rel).exists())
        self.assertTrue(data["gaps"]["ranking"])
        self.assertEqual(len([l for l in data["lessons"] if l["status"] == "active"]), 3)
        self.assertEqual(len([p for p in data["proposals"] if p["status"] == "pending"]), 2)
        self.assertTrue(data["signal_counts"])
        self.assertEqual(len(data["weeks"]), build_dashboard.TREND_WEEKS)

    def test_out_path_elsewhere_uses_relative_links(self):
        jid = add_scored(self.home, "9", [("Go", "hard_skill", True)])
        (jslib.job_dir(self.home, jid) / "resume.html").write_text("<p>x</p>", encoding="utf-8")
        out = Path(self.tmp.name) / "elsewhere" / "dash.html"
        build_dashboard.build(self.home, out)
        data = extract_payload(out.read_text(encoding="utf-8"))
        link = data["jobs"][0]["files"]["resume_html"]
        self.assertTrue((out.parent / link).resolve().exists(), link)

    def test_script_injection_is_escaped(self):
        evil = 'Engineer</script><img src=x onerror="alert(1)"><!-- &  '
        jid = add_scored(self.home, "666", [("</script><b>Go</b>", "tool", True)], title=evil, company="Evil & Co")
        html = build_dashboard.build(self.home).read_text(encoding="utf-8")
        # exactly two closing script tags: the JSON tag and the app script
        self.assertEqual(html.lower().count("</script"), 2)
        self.assertNotIn("<img src=x", html)
        self.assertNotIn("onerror=\"alert", html)
        data = extract_payload(html)
        job = [j for j in data["jobs"] if j["id"] == jid][0]
        self.assertEqual(job["title"], evil)
        self.assertEqual(job["company"], "Evil & Co")

    def test_template_never_uses_innerhtml_or_dialogs(self):
        tpl = build_dashboard.TEMPLATE.read_text(encoding="utf-8")
        script = tpl.split('<script>', 1)[1]
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("outerHTML", script)
        self.assertNotIn("insertAdjacentHTML", script)
        self.assertIsNone(re.search(r"\b(alert|confirm|prompt)\s*\(", script))
        self.assertIn("localStorage", script)
        for cmd in ("dismiss ", "applied ", "approve ", "reject ", "wrong ", "outcome ", " gap ", " lesson ", " proposal "):
            self.assertIn(cmd, script)

    def test_bad_json_file_does_not_break_build(self):
        jid = add_scored(self.home, "7", [("Go", "hard_skill", True)])
        (jslib.job_dir(self.home, jid) / "changes.json").write_text("{not json", encoding="utf-8")
        data = extract_payload(build_dashboard.build(self.home).read_text(encoding="utf-8"))
        self.assertIsNone(data["jobs"][0]["changes"])

    def test_radar_absent(self):
        data = extract_payload(build_dashboard.build(self.home).read_text(encoding="utf-8"))
        self.assertIsNone(data["radar"])
        tpl = build_dashboard.TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("No career radar yet.", tpl)
        self.assertIn("Run /job-search:radar in Claude", tpl)

    def test_radar_present_with_report_link_and_age(self):
        write_radar(self.home)
        (self.home / "radar" / "radar-2026-10-20.md").write_text("# report", encoding="utf-8")
        data = extract_payload(build_dashboard.build(self.home).read_text(encoding="utf-8"))
        r = data["radar"]
        self.assertEqual(r["verdict"], "Best fit now: Platform Engineer.")
        self.assertEqual(r["report_href"], "radar/radar-2026-10-20.md")
        self.assertEqual(r["every_days"], 30)
        self.assertIsInstance(r["age_days"], int)
        # the served path must be allowed
        self.assertTrue(serve_dashboard.ALLOWED.match("/" + r["report_href"]))

    def test_radar_staleness_and_bad_report_path(self):
        write_radar(self.home, as_of="2020-01-01", report="../profile/fact-bank.json")
        r = build_dashboard.summarize_radar(self.home, "", TODAY)
        self.assertTrue(r["stale"])
        self.assertIsNone(r["report_href"])
        prefs = jslib.load_preferences(self.home)
        prefs["radar_every_days"] = 0
        jslib.write_json(self.home / "profile" / "preferences.json", prefs)
        self.assertFalse(build_dashboard.summarize_radar(self.home, "", TODAY)["stale"])
        write_radar(self.home, as_of="2026-10-20", report="radar/radar-2026-10-20.md")  # file missing: no link
        self.assertIsNone(build_dashboard.summarize_radar(self.home, "", TODAY)["report_href"])

    def test_radar_script_injection_is_escaped(self):
        evil = '</script><img src=x onerror="alert(1)"><!--'
        write_radar(self.home, verdict=evil, titles_now=[{"title": evil, "fit": "high", "momentum": "high"}],
                    actions=[{"text": evil, "url": "javascript:alert(1)"}])
        html = build_dashboard.build(self.home).read_text(encoding="utf-8")
        self.assertEqual(html.lower().count("</script"), 2)
        self.assertNotIn("<img src=x", html)
        data = extract_payload(html)
        self.assertEqual(data["radar"]["verdict"], evil)
        self.assertEqual(data["radar"]["titles_now"][0]["title"], evil)
        self.assert_no_external_loads(html)

    def test_radar_report_markdown_is_inlined_safely(self):
        write_radar(self.home)
        md = "# Career Trend Radar: X\n\n## Your action plan\n- [ ] **Apply** [job](https://example.com/j)\n" \
             "</script><img src=x onerror=alert(1)>\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
        (self.home / "radar" / "radar-2026-10-20.md").write_text(md, encoding="utf-8")
        html = build_dashboard.build(self.home).read_text(encoding="utf-8")
        self.assertEqual(html.lower().count("</script"), 2)
        self.assertNotIn("<img src=x", html)
        self.assertEqual(extract_payload(html)["radar"]["report_md"], md)

    def test_radar_report_not_inlined_for_bad_path(self):
        write_radar(self.home, report="../profile/fact-bank.json")
        self.assertIsNone(build_dashboard.summarize_radar(self.home, "", TODAY)["report_md"])

    def test_markdown_renderer_is_text_only(self):
        tpl = build_dashboard.TEMPLATE.read_text(encoding="utf-8")
        body = tpl.split("// ---------- markdown (radar report)", 1)[1].split("function renderRadar", 1)[0]
        self.assertNotIn("innerHTML", body)
        self.assertNotIn("insertAdjacentHTML", body)
        self.assertIn("link(", body)  # links go through safeHref

    def test_radar_renderer_uses_text_only_and_safe_links(self):
        tpl = build_dashboard.TEMPLATE.read_text(encoding="utf-8")
        script = tpl.split('<script>', 1)[1]
        body = script.split("function renderRadar", 1)[1].split("// ---------- learned", 1)[0]
        self.assertNotIn("innerHTML", body)
        self.assertNotIn("setAttribute(\"href\"", body)
        self.assertIn('label: "Career radar"', script)
        self.assertIn('CMD + " radar"', script)
        self.assertIn("Trending but not in your JDs yet", script)
        self.assertIn('"rising"', script)

    def test_gaps_payload_carries_rising(self):
        write_radar(self.home)
        add_scored(self.home, "1", [("Terraform", "tool", True)])
        data = extract_payload(build_dashboard.build(self.home).read_text(encoding="utf-8"))
        # gaps.json absent: the dashboard computes it in memory, radar included
        self.assertTrue(data["gaps"]["items"]["terraform"]["rising"])
        self.assertEqual([e["skill"] for e in data["gaps"]["radar_only_rising"]], ["LLM evaluation"])

    def _script(self):
        return build_dashboard.TEMPLATE.read_text(encoding="utf-8").split('<script>', 1)[1]

    def _fn_body(self, script, name):
        start = script.index("function %s(" % name)
        nxt = script.find("\n  function ", start + 1)
        return script[start:nxt if nxt > 0 else len(script)]

    def test_visual_render_functions_exist_and_are_text_only(self):
        script = self._script()
        for name in ("renderFunnel", "scoreMeter", "fitMeter", "fitSplit", "rewriteBar", "confDots", "icon",
                     "radarPicks", "actionCard", "forecast", "runsChart", "changeDiff"):
            body = self._fn_body(script, name)
            self.assertNotIn("innerHTML", body, name)
            self.assertNotIn("insertAdjacentHTML", body, name)
        # every visual carries a text equivalent
        for name in ("fitMeter", "fitSplit", "confDots", "runsChart"):
            self.assertIn("aria-label", self._fn_body(script, name), name)
        self.assertIn('"aria-hidden": "true"', self._fn_body(script, "icon"))

    def test_radar_is_one_page_with_collapsed_report(self):
        script = self._script()
        self.assertNotIn("jobsearch.radarView", script)  # no Full report / At a glance toggle
        report = self._fn_body(script, "renderReport")
        self.assertNotIn("open: true", report)
        radar = self._fn_body(script, "renderRadar")
        self.assertIn("renderReport(R.report_md, true)", radar)
        self.assertIn("Open the report file", radar)
        self.assertIn('"Best fit now"', radar)
        self.assertIn('"Top bet"', radar)

    def test_pipeline_funnel_filters_and_keeps_status_chips(self):
        script = self._script()
        for label in ('"Found"', '"Scored"', '"Prepared"', '"Needs approval"', '"Applied"', '"Replies"', '"Interviews"'):
            self.assertIn("label: " + label, script)
        self.assertIn("funnelStep(pipeState.status)", script)
        self.assertIn('chip("all", "All"', script)

    def test_template_copy_has_no_long_dashes(self):
        tpl = build_dashboard.TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn("—", tpl)
        self.assertNotIn("–", tpl)

    def test_payload_carries_prefs_and_weekly_found(self):
        add_scored(self.home, "1", [("Go", "hard_skill", True)])
        prefs = jslib.load_preferences(self.home)
        prefs["min_score"] = 4.0
        prefs["major_rewrite_ratio"] = "lots"  # not a number: falls back to the default
        jslib.write_json(self.home / "profile" / "preferences.json", prefs)
        data = extract_payload(build_dashboard.build(self.home).read_text(encoding="utf-8"))
        self.assertEqual(data["prefs"]["min_score"], 4.0)
        self.assertEqual(data["prefs"]["major_rewrite_ratio"], build_dashboard.DEFAULT_MAJOR_RATIO)
        self.assertEqual(sum(data["found_weekly"].values()), 1)
        self.assertTrue(all(re.match(r"^\d{4}-W\d{2}$", k) for k in data["found_weekly"]))

    def test_cli(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "build_dashboard.py"), "--home", str(self.home), "--json"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["jobs"], 0)


class ServeTest(unittest.TestCase):
    def test_check_and_allowlist(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        try:
            self.assertTrue(serve_dashboard.port_in_use(port))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(serve_dashboard.main(["--port", str(port), "--check"]), 0)
        finally:
            s.close()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(serve_dashboard.main(["--port", str(port), "--check"]), 1)
        allowed = serve_dashboard.ALLOWED
        self.assertTrue(allowed.match("/dashboard.html"))
        self.assertTrue(allowed.match("/jobs/greenhouse-x-1/resume.html"))
        self.assertFalse(allowed.match("/profile/fact-bank.json"))
        self.assertFalse(allowed.match("/jobs/x/score.json"))
        self.assertFalse(allowed.match("/memory/signals.jsonl"))
        self.assertTrue(allowed.match("/radar/radar-2026-10-24.md"))
        for bad in ("/radar/latest.json", "/radar/radar-2026-10-24.json", "/radar/notes.md",
                    "/radar/radar-2026-10-24.md.bak", "/radar/../profile/fact-bank.json", "/radar/"):
            self.assertFalse(allowed.match(bad), bad)


if __name__ == "__main__":
    unittest.main()
