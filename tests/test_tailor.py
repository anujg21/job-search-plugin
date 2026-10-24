"""Tests for scoring, truthful tailoring, verify, change classification, render, approval."""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugins" / "job-search" / "scripts"
FIX_PROFILE = ROOT / "tests" / "fixtures" / "profile"
FIX = ROOT / "tests" / "fixtures" / "tailor"
sys.path.insert(0, str(SCRIPTS))

import jslib  # noqa: E402
import resume_lib as rl  # noqa: E402
import verify_resume  # noqa: E402
import classify_changes  # noqa: E402
import save_score  # noqa: E402
import approve  # noqa: E402
import detect_edits  # noqa: E402
import render_resume  # noqa: E402

JOB_ID = "manual-lumen-payments-staff-platform"


def load_fixture(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


class HomeCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        jslib.write_json(self.home / jslib.MARKER, {"schema_version": 1, "created_at": jslib.now_iso(), "plugin_version": "0.1.0"})
        (self.home / "profile").mkdir()
        for f in FIX_PROFILE.glob("*"):
            shutil.copy(str(f), str(self.home / "profile" / f.name))
        (self.home / "memory").mkdir()
        job = jslib.new_job("manual", "staff-platform", "Lumen Payments", "Staff Platform Engineer")
        self.assertEqual(job["id"], JOB_ID)
        jslib.add_job(self.home, job, (FIX / "jd-staff-platform.md").read_text(encoding="utf-8"))
        self.jdir = jslib.job_dir(self.home, JOB_ID)
        self.fb = jslib.load_fact_bank(self.home)
        self.score = load_fixture("score.json")
        self.good = load_fixture("resume-good.json")

    def tearDown(self):
        self.tmp.cleanup()

    def set_pref(self, **kw):
        p = jslib.load_preferences(self.home)
        p.update(kw)
        jslib.write_json(self.home / "profile" / "preferences.json", p)

    def write_resume(self, resume):
        jslib.write_json(self.jdir / "resume.json", resume)

    def put_score(self):
        jslib.write_json(self.jdir / "score.json", dict(self.score, job_id=JOB_ID))

    def verify(self, resume):
        return verify_resume.verify_resume(self.fb, resume, self.score)

    def blocks(self, result):
        return [i for i in result["issues"] if i["severity"] == "block"]

    def signals(self):
        return jslib.read_jsonl(self.home / "memory" / "signals.jsonl")

    def run_cli(self, script, *args, stdin=None):
        return subprocess.run([sys.executable, str(SCRIPTS / script), *args, "--home", str(self.home)],
                              input=stdin, capture_output=True, text=True)


# ---------------------------------------------------------------- numbers / terms

class TestNumberAndTermHelpers(unittest.TestCase):
    def test_normalizes_equivalent_forms(self):
        pool = rl.extract_numbers("handling 5,000 tickets, cutting cost 30%")
        for t in ("5000 tickets", "5k tickets", "30 percent"):
            for n in rl.extract_numbers(t):
                self.assertTrue(rl.number_supported(n, pool), t)

    def test_kind_and_unit_matter(self):
        pool = rl.extract_numbers("40 services, from 2 weeks to 1 day")
        bad = rl.extract_numbers("40% faster, $40 saved, 2 days")
        self.assertEqual([rl.number_supported(n, pool) for n in bad], [False, False, False])

    def test_ignores_identifiers_and_plain_words(self):
        self.assertEqual(rl.extract_numbers("S3, EC2, k8s, OAuth2, 24/7 on-call, one of the best"), [])

    def test_ambiguous_terms_need_capitalized_midsentence_use(self):
        self.assertFalse(rl.term_in_text("go", "to go from 2 weeks to 1 day"))
        self.assertFalse(rl.term_in_text("go", "Go live in a week"))
        self.assertTrue(rl.term_in_text("go", "Wrote services in Go and Python"))
        self.assertFalse(rl.term_in_text("java", "JavaScript tooling"))

    def test_number_word_forms(self):
        def one(text):
            ns = rl.extract_numbers(text)
            self.assertEqual(len(ns), 1, (text, ns))
            return ns[0]
        self.assertEqual((one("cut cost by a third")["kind"], round(one("cut cost by a third")["value"])), ("pct", 33))
        self.assertEqual(one("cut cost in half")["value"], 50)
        self.assertEqual((one("doubled throughput")["kind"], one("doubled throughput")["value"]), ("mult", 2))
        self.assertEqual((one("two decades of work")["value"], one("two decades of work")["unit"]), (20, "year"))
        self.assertTrue(one("5K+ tickets")["lower"])
        self.assertTrue(one("more than 200 engineers")["lower"])
        self.assertEqual(one("5,000 tickets per month")["rate"], "month")
        self.assertEqual(one("2 million transactions daily")["rate"], "day")
        self.assertEqual(rl.extract_numbers("shipped in a quarter, first half of the year"), [])
        self.assertEqual(rl.vague_quantities("dozens of services and hundreds of engineers"), ["dozens", "hundreds"])

    def test_lower_bound_and_rate_support(self):
        pool = rl.extract_numbers("used by 220 engineers, 5,000 tickets per month")
        ok = lambda t: all(rl.number_supported(n, pool) for n in rl.extract_numbers(t))
        self.assertTrue(ok("more than 200 engineers"))
        self.assertTrue(ok("5,000 tickets each month"))
        self.assertFalse(ok("more than 220 engineers"))
        self.assertFalse(ok("over 100 engineers"))  # too far below to be the same number
        self.assertFalse(ok("5,000 tickets per day"))

    def test_verb_ladder(self):
        self.assertEqual(rl.verb_level("Contributed to the migration"), 1)
        self.assertEqual(rl.verb_level("Helped move the ledger"), 1)
        self.assertEqual(rl.verb_level("Built payment APIs"), 3)
        self.assertEqual(rl.verb_level("Led a team"), 4)
        self.assertEqual(rl.verb_level("Headed platform"), 6)
        self.assertIsNone(rl.verb_level("Moved services to managed Kubernetes"))
        self.assertIsNone(rl.verb_level("Mentored 4 junior engineers"))


# ---------------------------------------------------------------- verify

class TestVerify(HomeCase):
    def test_legit_reworded_resume_passes(self):
        res = self.verify(self.good)
        self.assertTrue(res["passed"], self.blocks(res))

    def test_invented_number(self):
        r = copy.deepcopy(self.good)
        r["roles"][0]["bullets"][1]["text"] = "Led migration of 45 services to Kubernetes on AWS EKS, cutting infrastructure cost 30%"
        res = self.verify(r)
        self.assertFalse(res["passed"])
        self.assertTrue(any("45" in i["message"] for i in self.blocks(res)))

    def test_invented_percentage_and_money(self):
        r = copy.deepcopy(self.good)
        r["roles"][0]["bullets"][1]["text"] = "Led migration of 40 services to Kubernetes, cutting cost 40% and saving $2M"
        msgs = " ".join(i["message"] for i in self.blocks(self.verify(r)))
        self.assertIn("40%", msgs)
        self.assertIn("$2M", msgs)

    def test_stuffed_jd_tool(self):
        r = copy.deepcopy(self.good)
        r["roles"][0]["bullets"][1]["text"] = "Led migration of 40 services to Kubernetes on AWS EKS with Terraform, cutting infrastructure cost 30%"
        res = self.verify(r)
        self.assertFalse(res["passed"])
        self.assertTrue(any("terraform" in i["message"] for i in self.blocks(res)))

    def test_stuffed_tool_in_summary_and_skills(self):
        r = copy.deepcopy(self.good)
        r["summary"]["text"] += " Experienced with Prometheus and Grafana."
        r["skills"].append({"name": "Terraform", "source_ids": ["s.aws"]})
        msgs = " ".join(i["message"] for i in self.blocks(self.verify(r)))
        self.assertIn("prometheus", msgs)
        self.assertIn("grafana", msgs)
        self.assertIn("'Terraform' is not backed", msgs)

    def test_fact_bank_tool_moved_to_wrong_bullet(self):
        r = copy.deepcopy(self.good)
        r["roles"][1]["bullets"][2]["text"] = "Mentored 4 junior engineers on Kubernetes"
        self.assertFalse(self.verify(r)["passed"])

    def test_wrong_title(self):
        r = copy.deepcopy(self.good)
        r["roles"][0]["title"] = "Staff Platform Engineer"
        res = self.verify(r)
        self.assertTrue(any(i["path"] == "roles[0].title" for i in self.blocks(res)))

    def test_title_alias_allowed(self):
        r = copy.deepcopy(self.good)
        r["roles"][0]["title"] = "Platform Architect"
        self.assertTrue(self.verify(r)["passed"])

    def test_bad_headline(self):
        r = copy.deepcopy(self.good)
        r["headline"] = "Staff Platform Engineer"
        self.assertTrue(any(i["path"] == "headline" for i in self.blocks(self.verify(r))))

    def test_wrong_company_and_dates(self):
        r = copy.deepcopy(self.good)
        r["roles"][1]["company"] = "Contoso"
        r["roles"][1]["start"] = "2014-01"
        paths = {i["path"] for i in self.blocks(self.verify(r))}
        self.assertIn("roles[1].company", paths)
        self.assertIn("roles[1].start", paths)

    def test_unknown_id(self):
        r = copy.deepcopy(self.good)
        r["roles"][0]["bullets"][0]["source_ids"] = ["r1.b9"]
        self.assertTrue(any("unknown source id" in i["message"] for i in self.blocks(self.verify(r))))

    def test_missing_source_ids(self):
        r = copy.deepcopy(self.good)
        r["roles"][0]["bullets"][0]["source_ids"] = []
        self.assertTrue(any("no source_ids" in i["message"] for i in self.blocks(self.verify(r))))

    def test_cross_role_citation(self):
        r = copy.deepcopy(self.good)
        r["roles"][1]["bullets"].append({"text": "Mentored 4 junior engineers", "source_ids": ["r1.b1"]})
        self.assertFalse(self.verify(r)["passed"])

    def test_unknown_education_and_cert(self):
        r = copy.deepcopy(self.good)
        r["education"] = ["e9"]
        r["certifications"] = ["c1", "c7"]
        self.assertEqual(len(self.blocks(self.verify(r))), 2)

    def test_warnings_do_not_block(self):
        r = copy.deepcopy(self.good)
        r["roles"][0]["bullets"][0]["text"] = ("Owned an internal developer platform for 220 engineers that cut new service "
                                               "setup from 2 weeks to 1 day")
        r["roles"][1]["bullets"][2]["text"] = ("Mentored 4 junior engineers through code reviews, pairing sessions, design discussions "
                                                "and regular one on one conversations about growth")
        res = self.verify(r)
        self.assertTrue(res["passed"], self.blocks(res))
        warns = [i for i in res["issues"] if i["severity"] == "warn"]
        self.assertTrue(any("'Owned' is stronger" in i["message"] for i in warns))
        self.assertTrue(any("longer than its sources" in i["message"] for i in warns))

    def test_heavy_paraphrase_warns_but_wrong_citation_blocks(self):
        r = copy.deepcopy(self.good)
        r["roles"][0]["bullets"][1]["text"] = "Moved 40 workloads off virtual machines onto EKS, which brought spend down 30%"
        res = self.verify(r)
        self.assertTrue(res["passed"], self.blocks(res))
        self.assertTrue(any("low word overlap" in i["message"] for i in res["issues"]))
        r["roles"][0]["bullets"][1] = {"text": "Built an LLM-based support triage service handling tickets", "source_ids": ["r1.b4"]}
        self.assertTrue(any("reads like r1.b3" in i["message"] for i in self.blocks(self.verify(r))))

    def test_jd_phrase_not_in_sources_warns(self):
        r = copy.deepcopy(self.good)
        r["roles"][0]["bullets"][0]["text"] = ("Designed an internal developer platform with golden paths for 220 engineers, "
                                               "cutting new service setup from 2 weeks to 1 day")
        res = self.verify(r)
        self.assertTrue(res["passed"])
        self.assertTrue(any("golden paths" in i["message"] and i["severity"] == "warn" for i in res["issues"]))

    def test_no_false_positive_on_plain_rewording(self):
        r = copy.deepcopy(self.good)
        r["roles"][0]["bullets"][0]["text"] = ("Owned the design of a self-service internal developer platform adopted by "
                                               "220 engineers; new services go from 2 weeks of setup to 1 day")
        res = self.verify(r)
        self.assertTrue(res["passed"], self.blocks(res))

    def test_cli_writes_changes_and_exit_code(self):
        self.put_score()
        self.write_resume(self.good)
        p = self.run_cli("verify_resume.py", JOB_ID, "--json")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(jslib.read_json(self.jdir / "changes.json")["verify"]["passed"])
        bad = copy.deepcopy(self.good)
        bad["roles"][0]["bullets"][0]["text"] += " using Terraform"
        self.write_resume(bad)
        p = self.run_cli("verify_resume.py", JOB_ID)
        self.assertEqual(p.returncode, 1)
        self.assertIn("FAILED", p.stdout)
        self.assertFalse(jslib.read_json(self.jdir / "changes.json")["verify"]["passed"])


# ---------------------------------------------------------------- adversarial table

ADVERSARIAL = load_fixture("adversarial.json")


def _apply_patch(resume, patch):
    for op in patch:
        key = "set" if "set" in op else "append"
        path = op[key]
        cur = resume
        for k in path[:-1]:
            cur = cur[k]
        if key == "set":
            cur[path[-1]] = copy.deepcopy(op["value"])
        else:
            cur[path[-1]].append(copy.deepcopy(op["value"]))


class TestAdversarialResumes(unittest.TestCase):
    """Table-driven red-team cases from tests/fixtures/tailor/adversarial.json.

    block: fabrication the verifier must stop. warn: passes but must be flagged.
    pass: legitimate rewrite that must not be blocked. miss: known gap left to the tailor
    reviewer pass; asserted to pass so a future catch shows up here and the case can move
    to "block".
    """

    @classmethod
    def setUpClass(cls):
        cls.fb = json.loads((FIX_PROFILE / "fact-bank.json").read_text(encoding="utf-8"))
        cls.good = load_fixture("resume-good.json")
        cls.score = load_fixture("score.json")

    def run_case(self, case):
        fb = copy.deepcopy(self.fb)
        if case.get("fact_patch"):
            fp = ADVERSARIAL["fact_patch"]
            fb["roles"][fp["role"]]["bullets"].append(copy.deepcopy(fp["bullet"]))
        r = copy.deepcopy(self.good)
        _apply_patch(r, case["patch"])
        return verify_resume.verify_resume(fb, r, self.score)

    def test_table_has_enough_cases(self):
        kinds = [c["expect"] for c in ADVERSARIAL["cases"]]
        self.assertGreaterEqual(kinds.count("block") + kinds.count("warn"), 30)
        self.assertGreaterEqual(kinds.count("pass"), 15)

    def test_cases(self):
        for case in ADVERSARIAL["cases"]:
            with self.subTest(case=case["name"]):
                res = self.run_case(case)
                blocks = [i for i in res["issues"] if i["severity"] == "block"]
                warns = [i for i in res["issues"] if i["severity"] == "warn"]
                msg = (case.get("msg") or "").lower()
                if case["expect"] == "block":
                    self.assertFalse(res["passed"], "fabrication passed verify")
                    self.assertTrue(any(msg in i["message"].lower() for i in blocks),
                                    "no block mentions %r: %s" % (msg, blocks))
                elif case["expect"] == "warn":
                    self.assertTrue(res["passed"], blocks)
                    self.assertTrue(any(msg in i["message"].lower() for i in warns),
                                    "no warn mentions %r: %s" % (msg, warns))
                else:  # pass, miss
                    self.assertTrue(res["passed"], blocks)


# ---------------------------------------------------------------- classify

class TestClassify(HomeCase):
    def classify(self, resume):
        self.put_score()
        self.write_resume(resume)
        return classify_changes.classify_job(self.home, JOB_ID)

    def test_master_against_itself_has_no_changes(self):
        master = rl.build_master(self.fb, JOB_ID)
        out = self.classify(master)
        self.assertEqual(out["changes"], [])
        self.assertEqual(out["classification"], "minor")

    def test_reword_and_reorder_is_minor_and_auto(self):
        out = self.classify(self.good)
        types = {c["type"] for c in out["changes"]}
        self.assertIn("reword", types)
        self.assertIn("reorder", types)
        self.assertEqual(out["classification"], "minor", out["reasons"])
        self.assertLess(out["rewrite_ratio"], 0.30)
        self.assertEqual(out["approval"], "auto")
        job = jslib.load_job(self.home, JOB_ID)
        self.assertEqual(job["status"], "prepared")
        self.assertEqual(job["approval"], "auto")
        self.assertTrue((self.jdir / "resume.generated.json").exists())
        self.assertEqual(out["generated_hash"], rl.canonical_hash(self.good))
        rw = [c for c in out["changes"] if c["type"] == "reword"][0]
        self.assertTrue(rw["before"] and rw["after"] and rw["source_ids"])

    def test_drop_is_minor(self):
        r = copy.deepcopy(self.good)
        r["roles"][1]["bullets"].pop()  # drop mentoring bullet
        out = self.classify(r)
        self.assertIn("drop", {c["type"] for c in out["changes"]})
        self.assertEqual(out["classification"], "minor")

    def test_minor_needs_approval_when_auto_off(self):
        self.set_pref(auto_approve_minor=False)
        out = self.classify(self.good)
        self.assertEqual(out["classification"], "minor")
        self.assertEqual(out["approval"], "pending")
        self.assertEqual(jslib.load_job(self.home, JOB_ID)["status"], "needs_approval")

    def test_headline_change_is_major(self):
        r = copy.deepcopy(self.good)
        r["headline"] = "Principal Platform Engineer"
        out = self.classify(r)
        self.assertEqual(out["classification"], "major")
        self.assertIn("headline changed", out["reasons"])
        self.assertEqual(out["approval"], "pending")
        self.assertEqual(jslib.load_job(self.home, JOB_ID)["status"], "needs_approval")

    def test_title_change_is_major(self):
        r = copy.deepcopy(self.good)
        r["roles"][0]["title"] = "Platform Architect"
        out = self.classify(r)
        self.assertEqual(out["classification"], "major")
        self.assertIn("title_change", {c["type"] for c in out["changes"]})

    def test_removed_role_is_major(self):
        r = copy.deepcopy(self.good)
        r["roles"] = r["roles"][:1]
        out = self.classify(r)
        self.assertEqual(out["classification"], "major")
        self.assertTrue(any(c["type"] == "remove_section" and c["target"] == "roles[r2]" for c in out["changes"]))

    def test_familiar_skill_promoted_to_summary_is_major(self):
        r = copy.deepcopy(self.good)
        r["summary"]["text"] += " Builds LLM applications."
        r["summary"]["source_ids"].append("s.llm")
        out = self.classify(r)
        self.assertEqual(out["classification"], "major")
        self.assertTrue(any("promoted" in x for x in out["reasons"]))

    def test_expert_skill_in_summary_is_minor(self):
        out = self.classify(self.good)  # summary mentions Kubernetes and AWS (expert)
        promos = [c for c in out["changes"] if c["type"] == "skill_promote"]
        self.assertTrue(promos)
        self.assertEqual(out["classification"], "minor")

    def test_high_rewrite_ratio_is_major(self):
        r = copy.deepcopy(self.good)
        r["roles"][0]["bullets"] = [
            {"text": "Owned developer experience for 220 engineers; setup now takes 1 day instead of 2 weeks", "source_ids": ["r1.b2"]},
            {"text": "Moved 40 workloads off virtual machines onto EKS, which brought spend down 30%", "source_ids": ["r1.b1"]},
            {"text": "Wrote pipeline guardrails in GitHub Actions to satisfy HIPAA", "source_ids": ["r1.b4"]},
            {"text": "Shipped Python triage on AWS Bedrock covering 5,000 support requests monthly", "source_ids": ["r1.b3"]},
        ]
        r["roles"][1]["bullets"] = [
            {"text": "Wrote Java and Spring Boot payment services clearing 2 million transactions daily", "source_ids": ["r2.b1"]},
            {"text": "Brought in Docker plus Jenkins so releases went weekly instead of monthly", "source_ids": ["r2.b2"]},
            {"text": "Coached 4 junior engineers", "source_ids": ["r2.b3"]},
        ]
        self.assertTrue(self.verify(r)["passed"], self.blocks(self.verify(r)))
        out = self.classify(r)
        self.assertGreater(out["rewrite_ratio"], 0.30)
        self.assertEqual(out["classification"], "major")
        self.assertTrue(any("rewrote" in x for x in out["reasons"]))

    def test_verify_failure_forces_needs_approval(self):
        r = copy.deepcopy(self.good)
        r["roles"][0]["bullets"][1]["text"] = "Led migration of 40 services to Kubernetes using Terraform, cutting cost 30%"
        out = self.classify(r)
        self.assertFalse(out["verify"]["passed"])
        self.assertEqual(out["classification"], "major")
        self.assertIn("verify failed", out["reasons"])
        self.assertEqual(out["approval"], "pending")
        job = jslib.load_job(self.home, JOB_ID)
        self.assertEqual(job["status"], "needs_approval")
        self.assertEqual(job["status_history"][-1]["note"], "verify failed")

    def test_preserves_matching_verify_block(self):
        self.put_score()
        self.write_resume(self.good)
        verify_resume.verify_job(self.home, JOB_ID)
        stamp = jslib.read_json(self.jdir / "changes.json")["verify"]["checked_at"]
        out = classify_changes.classify_job(self.home, JOB_ID)
        self.assertEqual(out["verify"]["checked_at"], stamp)

    def test_stale_verify_is_rerun(self):
        self.put_score()
        bad = copy.deepcopy(self.good)
        bad["roles"][0]["bullets"][0]["text"] += " with Terraform"
        self.write_resume(bad)
        verify_resume.verify_job(self.home, JOB_ID)
        self.write_resume(self.good)  # fixed after verify
        out = classify_changes.classify_job(self.home, JOB_ID)
        self.assertTrue(out["verify"]["passed"])

    def test_cli(self):
        self.put_score()
        self.write_resume(self.good)
        p = self.run_cli("classify_changes.py", JOB_ID)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("minor", p.stdout)


# ---------------------------------------------------------------- approve

class TestApprove(HomeCase):
    def major(self):
        r = copy.deepcopy(self.good)
        r["headline"] = "Principal Platform Engineer"
        self.write_resume(r)
        classify_changes.classify_job(self.home, JOB_ID)

    def test_approve(self):
        self.major()
        res = approve.decide(self.home, JOB_ID, "approve")
        self.assertEqual(res["status"], "prepared")
        ch = jslib.read_json(self.jdir / "changes.json")
        self.assertEqual(ch["approval"], "approved")
        self.assertTrue(ch["decided_at"])
        job = jslib.load_job(self.home, JOB_ID)
        self.assertEqual((job["status"], job["approval"]), ("prepared", "approved"))
        sig = self.signals()[-1]
        self.assertEqual(sig["type"], "approve_change")
        self.assertIn("headline_change", sig["detail"])
        self.assertIn("headline changed", sig["detail"])

    def test_reject_goes_back_to_scored(self):
        self.major()
        p = self.run_cli("approve.py", JOB_ID, "reject", "--reason", "keep my real headline")
        self.assertEqual(p.returncode, 0, p.stderr)
        job = jslib.load_job(self.home, JOB_ID)
        self.assertEqual((job["status"], job["approval"]), ("scored", "rejected"))
        self.assertIn("re-tailor", job["status_history"][-1]["note"])
        sig = self.signals()[-1]
        self.assertEqual((sig["type"], sig["text"]), ("reject_change", "keep my real headline"))

    def test_cannot_approve_failed_verify(self):
        r = copy.deepcopy(self.good)
        r["roles"][0]["bullets"][0]["text"] += " with Terraform"
        self.write_resume(r)
        classify_changes.classify_job(self.home, JOB_ID)
        with self.assertRaises(approve.ApproveError):
            approve.decide(self.home, JOB_ID, "approve")
        self.assertEqual(jslib.load_job(self.home, JOB_ID)["status"], "needs_approval")
        # rejecting is still allowed
        approve.decide(self.home, JOB_ID, "reject", "made up terraform")
        self.assertEqual(jslib.load_job(self.home, JOB_ID)["status"], "scored")

    def test_no_changes_file(self):
        p = self.run_cli("approve.py", JOB_ID, "approve")
        self.assertEqual(p.returncode, 1)


# ---------------------------------------------------------------- save_score

class TestSaveScore(HomeCase):
    def test_valid_score(self):
        res = save_score.save(self.home, JOB_ID, self.score)
        self.assertEqual(res["status"], "scored")
        saved = jslib.read_json(self.jdir / "score.json")
        self.assertEqual(saved["job_id"], JOB_ID)
        self.assertTrue(saved["scored_at"])
        job = jslib.load_job(self.home, JOB_ID)
        self.assertEqual((job["score"], job["recommendation"], job["status"]), (4.1, "apply", "scored"))

    def test_drops_unknown_evidence_and_clamps(self):
        raw = dict(self.score, score=7)
        raw["matched"] = [{"requirement": "K8s", "evidence": ["r1.b1", "r9.b9"], "strength": "strong"},
                          {"requirement": "Made up", "evidence": ["nope"]}]
        res = save_score.save(self.home, JOB_ID, raw)
        saved = jslib.read_json(self.jdir / "score.json")
        self.assertEqual(saved["score"], 5.0)
        self.assertEqual(len(saved["matched"]), 1)
        self.assertEqual(saved["matched"][0]["evidence"], ["r1.b1"])
        self.assertTrue(any("r9.b9" in w for w in res["warnings"]))
        self.assertTrue(any("clamped" in w for w in res["warnings"]))

    def test_recommendation_from_min_score(self):
        raw = {k: v for k, v in self.score.items() if k != "recommendation"}
        for s, want in ((3.6, "apply"), (3.1, "maybe"), (2.0, "skip")):
            self.assertEqual(save_score.save(self.home, JOB_ID, dict(raw, score=s))["recommendation"], want)
        self.assertEqual(jslib.load_job(self.home, JOB_ID)["status"], "skipped")

    def test_deal_breaker_skips(self):
        res = save_score.save(self.home, JOB_ID, dict(self.score, deal_breakers_hit=["contract"]))
        self.assertEqual((res["recommendation"], res["status"]), ("skip", "skipped"))

    def test_bad_category_becomes_other(self):
        raw = dict(self.score, missing=[{"item": "Terraform", "category": "infra", "required": True}, "Rust"])
        save_score.save(self.home, JOB_ID, raw)
        saved = jslib.read_json(self.jdir / "score.json")
        self.assertEqual([m["category"] for m in saved["missing"]], ["other", "other"])

    def test_rejects_bad_input(self):
        for bad in ({"score": "high"}, dict(self.score, recommendation="yes"), dict(self.score, job_id="other"),
                    dict(self.score, keywords="k8s")):
            with self.assertRaises(save_score.ScoreError):
                save_score.save(self.home, JOB_ID, bad)
        p = self.run_cli("save_score.py", JOB_ID, "--json", stdin="not json")
        self.assertEqual(p.returncode, 1)
        p = self.run_cli("save_score.py", "nope-job", "--json", stdin=json.dumps(self.score))
        self.assertEqual(p.returncode, 1)

    def test_cli_stdin(self):
        p = self.run_cli("save_score.py", JOB_ID, "--json", stdin=json.dumps(self.score))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(json.loads(p.stdout)["ok"])

    def test_rescore_does_not_regress_status(self):
        jslib.set_status(self.home, JOB_ID, "applied")
        res = save_score.save(self.home, JOB_ID, self.score)
        self.assertEqual(res["status"], "applied")
        self.assertEqual(jslib.load_job(self.home, JOB_ID)["status"], "applied")


# ---------------------------------------------------------------- render

class TestRender(HomeCase):
    def test_render_job(self):
        self.write_resume(self.good)
        p = self.run_cli("render_resume.py", JOB_ID, "--no-pdf", "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        res = json.loads(p.stdout)
        self.assertIsNone(res["pdf"])
        html = (self.jdir / "resume.html").read_text(encoding="utf-8")
        md = (self.jdir / "resume.md").read_text(encoding="utf-8")
        self.assertIn("Jordan Rivera", html)
        self.assertIn("Lead Platform Architect, Northwind Health", html)
        self.assertIn("Mar 2021 - Present", html)
        self.assertIn("University of South Florida", html)
        self.assertIn("@page", html)
        self.assertNotIn("<table", html)
        self.assertNotIn("{{", html)
        self.assertIn("- Mentored 4 junior engineers", md)

    def test_render_escapes_html(self):
        r = copy.deepcopy(self.good)
        r["roles"][1]["bullets"][2]["text"] = "Mentored 4 junior engineers <script>"
        self.write_resume(r)
        render_resume.render(self.home, JOB_ID, False, False)
        self.assertIn("&lt;script&gt;", (self.jdir / "resume.html").read_text(encoding="utf-8"))

    def test_render_master_keeps_user_md(self):
        md = self.home / "profile" / "resume-master.md"
        md.write_text("original", encoding="utf-8")
        res = render_resume.render(self.home, None, True, False)
        self.assertTrue((self.home / "profile" / "resume-master.html").exists())
        self.assertIsNone(res["md"])
        self.assertEqual(md.read_text(encoding="utf-8"), "original")

    def test_no_chrome_skips_pdf(self):
        self.write_resume(self.good)
        old = os.environ.get("JOBSEARCH_CHROME")
        os.environ["JOBSEARCH_CHROME"] = "/nonexistent/chrome"
        try:
            res = render_resume.render(self.home, JOB_ID, False, True)
        finally:
            if old is None:
                del os.environ["JOBSEARCH_CHROME"]
            else:
                os.environ["JOBSEARCH_CHROME"] = old
        self.assertIsNone(res["pdf"])
        self.assertIn("Chrome not found", res["pdf_note"])


# ---------------------------------------------------------------- detect_edits

class TestDetectEdits(HomeCase):
    def test_logs_edit_once(self):
        self.write_resume(self.good)
        classify_changes.classify_job(self.home, JOB_ID)
        self.assertEqual(detect_edits.detect(self.home), [])

        edited = copy.deepcopy(self.good)
        edited["roles"][0]["bullets"][1]["text"] = "Contributed to migration of 40 services to Kubernetes on AWS EKS"
        self.write_resume(edited)
        res = detect_edits.detect(self.home)
        self.assertEqual(len(res), 1)
        edits = [s for s in self.signals() if s["type"] == "edit"]
        self.assertEqual(len(edits), 1)
        self.assertIn("Contributed to", edits[0]["detail"])
        self.assertIn("Led migration", edits[0]["detail"])
        self.assertEqual(edits[0]["job_id"], JOB_ID)

        self.assertEqual(detect_edits.detect(self.home), [])  # same edit not logged twice
        self.assertEqual(len([s for s in self.signals() if s["type"] == "edit"]), 1)

        p = self.run_cli("detect_edits.py")
        self.assertEqual(p.returncode, 0)
        self.assertIn("no new resume edits", p.stdout)


if __name__ == "__main__":
    unittest.main()
