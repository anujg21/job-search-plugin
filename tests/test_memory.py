"""Tests for jobctl.py and memory.py (home setup, memory, self-improvement)."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins" / "job-search" / "scripts"
FIXTURES = ROOT / "tests" / "fixtures" / "profile"
sys.path.insert(0, str(SCRIPTS))

import jslib  # noqa: E402
import jobctl  # noqa: E402
import memory  # noqa: E402


def run(mod, *argv):
    """Run a script main() and capture stdout. Returns (exit_code, output)."""
    buf = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(buf):
        try:
            code = mod.main(list(argv)) or 0
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
            if not isinstance(e.code, int) and e.code:
                print(e.code)
    return code, buf.getvalue()


def ts(days_ago=0, seconds=0):
    d = datetime.now(timezone.utc) - timedelta(days=days_ago) + timedelta(seconds=seconds)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "JobSearch"
        jobctl.init_home(self.home, str(FIXTURES))
        self.h = ["--home", str(self.home)]

    def tearDown(self):
        self.tmp.cleanup()

    def write_signals(self, sigs):
        p = self.home / "memory" / "signals.jsonl"
        with p.open("a", encoding="utf-8") as f:
            for s in sigs:
                f.write(json.dumps(s) + "\n")

    def add_job(self, cid, score=None, status="found"):
        job = jslib.new_job("greenhouse", cid, "Stripe", "Staff Engineer")
        job["score"] = score
        job["status"] = status
        jslib.add_job(self.home, job)
        return job["id"]


class TestJobctl(Base):
    def test_init_complete(self):
        h = self.home
        for rel in ("jobsearch.json", "README.txt", "profile/preferences.json", "profile/sources.json",
                    "profile/fact-bank.json", "profile/gap-notes.json", "memory/signals.jsonl",
                    "memory/lessons.json", "memory/lessons.md", "memory/proposals.json"):
            self.assertTrue((h / rel).exists(), rel)
        self.assertTrue((h / "jobs").is_dir())
        self.assertTrue((h / "runs").is_dir())
        self.assertEqual(jslib.read_json(h / "jobsearch.json")["schema_version"], 1)

    def test_init_blank_templates(self):
        h = Path(self.tmp.name) / "blank"
        jobctl.init_home(h)
        src = jslib.read_json(h / "profile" / "sources.json")["sources"]
        self.assertEqual(set(src), {"greenhouse", "lever", "ashby", "indeed", "dice", "linkedin"})
        for k in ("greenhouse", "lever", "ashby"):
            self.assertTrue(src[k]["enabled"])
            self.assertTrue(src[k]["has_access"])
            self.assertEqual(src[k]["companies"], [])
        for k in ("indeed", "dice", "linkedin"):
            self.assertFalse(src[k]["enabled"])
        for k in ("indeed", "linkedin"):
            self.assertFalse(src[k]["has_access"])
        self.assertEqual(jslib.read_json(h / "profile" / "gap-notes.json"), {})
        self.assertEqual(jslib.read_json(h / "profile" / "fact-bank.json")["roles"], [])
        self.assertEqual(jslib.read_json(h / "profile" / "preferences.json")["schema_version"], 1)

    def test_init_idempotent_never_overwrites(self):
        prefs = self.home / "profile" / "preferences.json"
        data = jslib.read_json(prefs)
        data["daily_cap"] = 9
        jslib.write_json(prefs, data)
        created = jobctl.init_home(self.home, str(FIXTURES))
        self.assertEqual(created, [])
        self.assertEqual(jslib.read_json(prefs)["daily_cap"], 9)
        # fixtures were copied, not templates
        self.assertEqual(jslib.read_json(self.home / "profile" / "fact-bank.json")["person"]["name"], "Jordan Rivera")

    def test_home_command(self):
        code, out = run(jobctl, "home", *self.h)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), str(self.home.resolve()))
        code, out = run(jobctl, "--home", str(Path(self.tmp.name) / "nope"), "home")
        self.assertEqual(code, 1)
        self.assertIn("onboard", out)

    def test_list_status_signal_gapnote(self):
        a = self.add_job("1", score=4.5)
        b = self.add_job("2", score=3.0)
        code, out = run(jobctl, "list", *self.h, "--json")
        self.assertEqual([j["id"] for j in json.loads(out)], [a, b])
        code, out = run(jobctl, "status", a, "dismissed", "--note", "too junior", *self.h)
        self.assertEqual(code, 0)
        job = jslib.load_job(self.home, a)
        self.assertEqual(job["status"], "dismissed")
        self.assertEqual(job["dismissed_reason"], "too junior")
        code, out = run(jobctl, "list", "--status", "dismissed", "--json", *self.h)
        self.assertEqual(len(json.loads(out)), 1)
        code, out = run(jobctl, "signal", "dismiss", "--skill", "feedback", "--job", a,
                        "--detail", "too junior", "--text", "too junior", *self.h)
        self.assertEqual(code, 0)
        sigs = jslib.read_jsonl(self.home / "memory" / "signals.jsonl")
        self.assertEqual(sigs[-1]["type"], "dismiss")
        self.assertEqual(sigs[-1]["job_id"], a)
        code, out = run(jobctl, "gapnote", "Terraform", "learning", "--note", "course", *self.h)
        notes = jslib.read_json(self.home / "profile" / "gap-notes.json")
        self.assertEqual(notes["terraform"], {"status": "learning", "note": "course"})

    def test_list_rank_puts_best_title_first(self):
        def add(cid, title):
            job = jslib.new_job("greenhouse", cid, "Acme", title)
            jslib.add_job(self.home, job)
            return job["id"]
        a = add("1", "Senior Backend Engineer")
        b = add("2", "Staff Platform Engineer")
        c = add("3", "Senior Software Engineer, Kubernetes")
        code, out = run(jobctl, "list", "--status", "found", "--rank", "--limit", "2", "--json", *self.h)
        self.assertEqual(code, 0)
        got = json.loads(out)
        self.assertEqual([j["id"] for j in got], [b, c])
        self.assertIn("title_rank", got[0])
        self.assertNotIn(a, [j["id"] for j in got])

    def test_list_rank_sends_same_role_copies_to_the_end(self):
        def add(cid, title, status="found"):
            job = jslib.new_job("greenhouse", cid, "Acme", title)
            job["status"] = status
            jslib.add_job(self.home, job)
            return job["id"]
        scored = add("1", "Staff Platform Engineer", status="skipped")
        copy_of_scored = add("2", "Staff Platform Engineer")
        first = add("3", "Senior Platform Engineer")
        second = add("4", "Senior Platform Engineer")
        other = add("5", "Senior Software Engineer, Kubernetes")
        code, out = run(jobctl, "list", "--status", "found", "--rank", "--json", *self.h)
        got = json.loads(out)
        ids = [j["id"] for j in got]
        self.assertEqual(set(ids[:2]), {first, other})
        self.assertEqual(set(ids[2:]), {copy_of_scored, second})
        by_id = {j["id"]: j for j in got}
        self.assertEqual(by_id[copy_of_scored]["duplicate_of"], scored)
        self.assertEqual(by_id[second]["duplicate_of"], first)

    def test_runlog(self):
        code, _ = run(jobctl, "runlog", *self.h, "--kind", "daily", "--found", "12", "--new", "4",
                      "--needs-approval", "1", "--errors", "dice: not signed in", "--errors", "lever: 500")
        self.assertEqual(code, 0)
        entry = jslib.read_jsonl(self.home / "runs" / "run-log.jsonl")[-1]
        self.assertEqual(entry["kind"], "daily")
        self.assertEqual(entry["needs_approval"], 1)
        self.assertEqual(entry["errors"], ["dice: not signed in", "lever: 500"])

    def test_doctor_passes_on_fixtures(self):
        code, out = run(jobctl, "doctor", "--quick", "--json", *self.h)
        res = json.loads(out)
        self.assertTrue(res["ok"], out)
        self.assertEqual(code, 0)

    def test_doctor_catches_broken_fact_bank(self):
        p = self.home / "profile" / "fact-bank.json"
        fb = jslib.read_json(p)
        fb["roles"][0]["bullets"][0]["metrics"].append("45%")
        fb["roles"][1]["bullets"][0]["id"] = "r1.b1"  # duplicate id
        fb["skills"][0]["evidence"].append("r9.b9")
        jslib.write_json(p, fb)
        code, out = run(jobctl, "doctor", "--quick", "--json", *self.h)
        self.assertEqual(code, 1)
        res = json.loads(out)
        fbcheck = [c for c in res["checks"] if c["check"] == "Fact bank sanity"][0]
        self.assertEqual(fbcheck["status"], "fail")
        self.assertIn("45%", fbcheck["detail"])
        self.assertIn("duplicate", fbcheck["detail"])
        self.assertIn("r9.b9", fbcheck["detail"])

    def test_doctor_no_source_enabled_and_bad_json(self):
        p = self.home / "profile" / "sources.json"
        src = jslib.read_json(p)
        for v in src["sources"].values():
            v["enabled"] = False
        jslib.write_json(p, src)
        (self.home / "profile" / "preferences.json").write_text("{bad", encoding="utf-8")
        code, out = run(jobctl, "doctor", "--quick", "--json", *self.h)
        self.assertEqual(code, 1)
        res = {c["check"]: c["status"] for c in json.loads(out)["checks"]}
        self.assertEqual(res["At least one source enabled"], "fail")
        self.assertEqual(res["profile/preferences.json"], "fail")


    def test_doctor_fails_when_no_source_can_find_jobs(self):
        p = self.home / "profile" / "sources.json"
        src = jslib.read_json(p)
        for k, v in src["sources"].items():
            v["enabled"] = k in ("greenhouse", "lever", "ashby")
            v["companies"] = []
        jslib.write_json(p, src)
        code, out = run(jobctl, "doctor", "--quick", "--json", *self.h)
        self.assertEqual(code, 1)
        res = {c["check"]: c["status"] for c in json.loads(out)["checks"]}
        self.assertEqual(res["A source that can find jobs"], "fail")
        src["sources"]["indeed"]["enabled"] = True
        jslib.write_json(p, src)
        code, out = run(jobctl, "doctor", "--quick", "--json", *self.h)
        res = {c["check"]: c["status"] for c in json.loads(out)["checks"]}
        self.assertNotIn("A source that can find jobs", res)

    def test_doctor_warns_until_connector_works(self):
        p = self.home / "profile" / "sources.json"
        src = jslib.read_json(p)
        src["sources"]["indeed"]["enabled"] = True
        jslib.write_json(p, src)
        code, out = run(jobctl, "doctor", "--quick", "--json", *self.h)
        checks = {c["check"]: c for c in json.loads(out)["checks"]}
        self.assertEqual(checks["Connector indeed"]["status"], "warn")
        self.assertIn("Customize, Plugins, Job search, Connectors", checks["Connector indeed"]["detail"])
        code, out = run(jobctl, "connector", "indeed", "ok", *self.h)
        self.assertEqual(code, 0, out)
        self.assertTrue(jslib.read_json(p)["sources"]["indeed"]["connector"])
        code, out = run(jobctl, "doctor", "--quick", "--json", *self.h)
        self.assertNotIn("Connector indeed", {c["check"] for c in json.loads(out)["checks"]})
        run(jobctl, "connector", "indeed", "missing", *self.h)
        code, out = run(jobctl, "doctor", "--quick", "--json", *self.h)
        checks = {c["check"]: c for c in json.loads(out)["checks"]}
        self.assertTrue(checks["Connector indeed"]["detail"].startswith("not connected"))


class TestLessons(Base):
    def test_add_render_touch_retire(self):
        code, out = run(memory, "lesson-add", *self.h, "--text", "Never use the word 'spearheaded'.",
                        "--scope", "tailor", "--evidence", "2026-10-01T00:00:00Z,2026-10-02T00:00:00Z")
        self.assertEqual(code, 0, out)
        md = (self.home / "memory" / "lessons.md").read_text()
        self.assertIn("## Scope: tailor", md)
        self.assertIn("- [L-001] Never use the word 'spearheaded'. (since ", md)
        self.assertIn("from 2 signals)", md)
        self.assertIn("truthfulness", md.lower())
        run(memory, "lesson-touch", "L-001", *self.h)
        l = memory.load_lessons(self.home)["lessons"][0]
        self.assertIsNotNone(l["last_applied"])
        run(memory, "lesson-add", *self.h, "--text", "Skip staffing agencies", "--scope", "scan")
        code, out = run(memory, "lesson-retire", "L-001", "--reason", "user reversed", *self.h)
        self.assertEqual(code, 0)
        md = (self.home / "memory" / "lessons.md").read_text()
        self.assertNotIn("L-001", md)
        self.assertIn("[L-002] Skip staffing agencies", md)
        self.assertEqual(memory.load_lessons(self.home)["lessons"][0]["status"], "retired")

    def test_similar_lesson_merges_evidence(self):
        l1, c1 = memory.add_lesson(self.home, "Never use the word spearheaded", "tailor", evidence=["a"])
        l2, c2 = memory.add_lesson(self.home, "Never use the word 'spearheaded'.", "tailor", evidence=["b"])
        self.assertTrue(c1)
        self.assertFalse(c2)
        self.assertEqual(l2["id"], l1["id"])
        self.assertEqual(memory.load_lessons(self.home)["lessons"][0]["evidence"], ["a", "b"])

    def test_guardrail_rejects_weakening(self):
        bad = [
            "Add skills from the job description to the skills section",
            "Invent metrics when a bullet has none",
            "It is fine to fabricate a certification",
            "Make up numbers to sound stronger",
            "Skip verify for minor jobs",
            "Auto-approve major changes",
            "Don't ask for approval on headline changes",
            "Apply headline changes without approval",
            # Journey finds: these slipped through before.
            "It is fine to round metrics up a bit to sound stronger",
            "Round the cost savings up to the nearest 10k",
            "Bump my titles to Staff where it helps",
        ]
        for text in bad:
            code, out = run(memory, "lesson-add", *self.h, "--text", text, "--scope", "tailor")
            self.assertEqual(code, 2, text)
            self.assertIn("Refused", out)
        self.assertEqual(memory.load_lessons(self.home)["lessons"], [])
        good = [
            "Never add skills the user does not have",
            "Do not invent metrics",
            "Never apply headline changes without approval",
            "Skip agency and staffing roles",
            "Prefer 'built' over 'spearheaded'",
            "Never round numbers up",
            "Keep numbers exactly as the fact states them",
            "Raise min_score to 4.0 for agency roles",
        ]
        for text in good:
            self.assertIsNone(memory.weakening_reason(text), text)

    def test_retire_stale(self):
        data = memory.load_lessons(self.home)
        data["lessons"] = [
            {"id": "L-001", "text": "old", "scope": "all", "kind": "auto", "status": "active",
             "created": ts(90), "last_applied": None, "evidence": [], "source": "retro"},
            {"id": "L-002", "text": "old but used", "scope": "all", "kind": "auto", "status": "active",
             "created": ts(90), "last_applied": ts(5), "evidence": [], "source": "retro"},
            {"id": "L-003", "text": "new", "scope": "all", "kind": "auto", "status": "active",
             "created": ts(3), "last_applied": None, "evidence": [], "source": "retro"},
        ]
        memory.save_lessons(self.home, data)
        code, out = run(memory, "retire-stale", "--days", "60", *self.h)
        status = {l["id"]: l["status"] for l in memory.load_lessons(self.home)["lessons"]}
        self.assertEqual(status, {"L-001": "retired", "L-002": "active", "L-003": "active"})
        self.assertNotIn("L-001", (self.home / "memory" / "lessons.md").read_text())


class TestProposals(Base):
    def test_accept_patches_preferences(self):
        patch = json.dumps({"file": "profile/preferences.json", "set": {"min_score": 4.0},
                            "append": {"deal_breakers": ["agency", "contract"]}})
        code, out = run(memory, "proposal-add", *self.h, "--text", "Raise min_score to 4.0?",
                        "--kind", "preference", "--patch", patch)
        self.assertEqual(code, 0, out)
        code, out = run(memory, "proposal-decide", "P-001", "accept", *self.h)
        self.assertEqual(code, 0, out)
        prefs = jslib.read_json(self.home / "profile" / "preferences.json")
        self.assertEqual(prefs["min_score"], 4.0)
        self.assertEqual(prefs["deal_breakers"], ["contract", "clearance required", "agency"])
        p = memory.load_proposals(self.home)["proposals"][0]
        self.assertEqual(p["status"], "accepted")
        code, out = run(memory, "proposal-decide", "P-001", "accept", *self.h)
        self.assertNotEqual(code, 0)

    def test_sources_dotted_patch_and_decline(self):
        memory.add_proposal(self.home, "Turn off ashby", "source",
                            {"file": "profile/sources.json", "set": {"sources.ashby.enabled": False}})
        memory.add_proposal(self.home, "Watch plaid on greenhouse", "source",
                            {"file": "profile/sources.json", "append": {"sources.greenhouse.companies": "plaid"}})
        memory.decide_proposal(self.home, "P-001", "accept")
        memory.decide_proposal(self.home, "P-002", "decline")
        src = jslib.read_json(self.home / "profile" / "sources.json")["sources"]
        self.assertFalse(src["ashby"]["enabled"])
        self.assertNotIn("plaid", src["greenhouse"]["companies"])

    def test_fact_bank_never_auto_patched(self):
        before = (self.home / "profile" / "fact-bank.json").read_text()
        memory.add_proposal(self.home, "Add Terraform to skills", "fact_bank",
                            {"file": "profile/fact-bank.json", "set": {"headlines": ["CTO"]}})
        prop, msgs = memory.decide_proposal(self.home, "P-001", "accept")
        self.assertEqual((self.home / "profile" / "fact-bank.json").read_text(), before)
        self.assertFalse(prop["applied"])
        self.assertIn("onboard", " ".join(msgs))
        with self.assertRaises(SystemExit):
            memory.apply_patch(self.home, {"file": "profile/fact-bank.json", "set": {"x": 1}})

    def test_protected_keys_refused(self):
        code, out = run(memory, "proposal-add", *self.h, "--text", "Loosen rewrites", "--kind", "preference",
                        "--patch", json.dumps({"file": "profile/preferences.json", "set": {"major_rewrite_ratio": 0.9}}))
        self.assertEqual(code, 2)
        self.assertEqual(memory.load_proposals(self.home)["proposals"], [])

    def test_maintainer_issue_anonymized(self):
        self.write_signals([{"ts": "2026-10-20T10:00:00Z", "type": "source_error", "skill": "scan",
                             "detail": "lever: 500 for Northwind Health board, contact jordan@example.com"}])
        prop, _ = memory.add_proposal(
            self.home, "Lever adapter failed 3 times this week for Jordan Rivera at Northwind Health (Contoso Bank too)",
            "maintainer", evidence=["2026-10-20T10:00:00Z"])
        prop, msgs = memory.decide_proposal(self.home, prop["id"], "accept")
        path = self.home / "memory" / ("maintainer-issue-%s.md" % prop["id"])
        self.assertTrue(path.exists())
        body = path.read_text()
        for secret in ("Jordan", "Rivera", "Northwind", "Contoso", "jordan@example.com", "555-0100"):
            self.assertNotIn(secret, body)
        self.assertIn("Lever adapter failed", body)
        self.assertIn("## Environment", body)


class TestCandidates(Base):
    def test_groups_repeats_and_frustration(self):
        self.write_signals([
            {"ts": "2026-10-20T10:00:00Z", "type": "edit", "skill": "tailor", "detail": "removed word spearheaded"},
            {"ts": "2026-10-21T10:00:00Z", "type": "edit", "skill": "tailor", "detail": "Removed word 'spearheaded'"},
            {"ts": "2026-10-21T11:00:00Z", "type": "edit", "skill": "tailor", "detail": "one-off change"},
            {"ts": "2026-10-22T10:00:00Z", "type": "frustration", "skill": "score", "detail": "scored a contract role high",
             "text": "I ALREADY told you no contract roles"},
            {"ts": "2026-10-22T11:00:00Z", "type": "note", "skill": "feedback", "text": "please stop showing me crypto jobs"},
            {"ts": "2026-10-23T11:00:00Z", "type": "repeat", "skill": "feedback", "text": "Please stop showing me crypto jobs!"},
        ])
        res = memory.analyze(self.home)
        details = {g["detail"]: g for g in res["groups"] if g["group_by"] == "detail"}
        self.assertIn("removed word spearheaded", details)
        self.assertEqual(details["removed word spearheaded"]["count"], 2)
        self.assertNotIn("one off change", details)
        self.assertIn("scored a contract role high", details)
        self.assertTrue(details["scored a contract role high"]["frustration"])
        text_groups = [g for g in res["groups"] if g["group_by"] == "text"]
        self.assertTrue(any(g["count"] == 2 and "crypto" in g["texts"][0] for g in text_groups))
        self.assertTrue(res["groups"][0]["frustration"])

    def test_excludes_groups_covered_by_lesson(self):
        self.write_signals([
            {"ts": "2026-10-20T10:00:00Z", "type": "edit", "skill": "tailor", "detail": "removed spearheaded"},
            {"ts": "2026-10-21T10:00:00Z", "type": "edit", "skill": "tailor", "detail": "removed spearheaded"},
            {"ts": "2026-10-21T12:00:00Z", "type": "reject_change", "skill": "approve", "detail": "headline_change too senior"},
            {"ts": "2026-10-22T12:00:00Z", "type": "reject_change", "skill": "approve", "detail": "headline_change too senior"},
        ])
        memory.add_lesson(self.home, "Never use the word spearheaded", "tailor",
                          evidence=["2026-10-20T10:00:00Z", "2026-10-21T10:00:00Z"])
        res = memory.analyze(self.home)
        details = [g["detail"] for g in res["groups"]]
        self.assertNotIn("removed spearheaded", details)
        self.assertIn("headline change too senior", details)
        self.assertEqual(res["groups_excluded_as_covered"], 1)
        self.assertEqual(res["stats"]["change_decisions"]["headline_change"]["rejected"], 2)

    def test_change_decisions_from_approve_py_detail(self):
        self.write_signals([
            {"ts": "2026-10-20T10:00:00Z", "type": "reject_change", "skill": "approve",
             "detail": "types: headline_change, reword; reasons: headline changed"},
            {"ts": "2026-10-21T10:00:00Z", "type": "approve_change", "skill": "approve",
             "detail": "types: reword; reasons: none"},
        ])
        cd = memory.analyze(self.home)["stats"]["change_decisions"]
        self.assertEqual(cd["headline_change"], {"approved": 0, "rejected": 1, "reject_rate": 1.0})
        self.assertEqual(cd["reword"]["approved"], 1)
        self.assertEqual(cd["reword"]["reject_rate"], 0.5)

    def test_dismiss_vs_score_suggestion(self):
        sigs = []
        for i, score in enumerate([2.5, 3.0, 3.2, 3.6, 3.8, 3.9, 4.4]):
            jid = self.add_job(str(i), score=score)
            sigs.append({"ts": "2026-10-2%dT10:00:00Z" % i, "type": "dismiss", "skill": "feedback",
                         "job_id": jid, "detail": "too junior" if i % 2 else "not my field"})
        jid = self.add_job("99", score=4.6)
        sigs.append({"ts": "2026-10-23T12:00:00Z", "type": "apply", "skill": "apply", "job_id": jid})
        self.write_signals(sigs)
        stats = memory.analyze(self.home)["stats"]
        sug = stats["dismissed_vs_score"]["suggestion"]
        self.assertIsNotNone(sug)
        self.assertEqual(sug["key"], "min_score")
        self.assertEqual(sug["suggested"], 4.0)
        self.assertEqual(sug["patch"]["set"], {"min_score": 4.0})
        self.assertEqual(stats["dismiss_reasons"]["too junior"], 3)

    def test_source_errors_and_overrides_and_since(self):
        self.write_signals([
            {"ts": ts(1), "type": "source_error", "skill": "scan", "detail": "dice: not signed in"},
            {"ts": ts(2), "type": "source_error", "skill": "scan", "detail": "dice: not signed in"},
            {"ts": ts(3), "type": "source_error", "skill": "scan", "detail": "dice: captcha"},
            {"ts": ts(1, 5), "type": "override_score", "skill": "score", "job_id": "x", "detail": "should be 4"},
            {"ts": ts(40), "type": "override_score", "skill": "score", "job_id": "y", "detail": "should be 2"},
        ])
        code, out = run(memory, "candidates", "--json", "--since", "30", *self.h)
        self.assertEqual(code, 0)
        res = json.loads(out)
        rs = res["stats"]["repeated_source_errors"]
        self.assertEqual(rs[0]["source"], "dice")
        self.assertEqual(rs[0]["count"], 3)
        self.assertEqual(rs[0]["hint"], "maintainer proposal")
        self.assertEqual(res["stats"]["override_score_count"], 1)


if __name__ == "__main__":
    unittest.main()
