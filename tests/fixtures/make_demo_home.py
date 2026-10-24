#!/usr/bin/env python3
"""Build a realistic demo home for dashboard, end-to-end and browser testing.

Usage:
  make_demo_home.py <dir> [--today YYYY-MM-DD] [--force]

Copies tests/fixtures/profile into <dir>/profile, writes the marker, and generates
about 25 jobs across sources and statuses with score.json, a few changes.json
(minor, major, one pending with verify issues), memory files, gap notes and three
weeks of run-log entries. Dates are relative to --today (default: today, UTC) so the
"this week" numbers on the dashboard are always populated. Output is deterministic
for a given --today.
"""
from __future__ import annotations

import argparse
import os
import random
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
REPO = HERE.parent.parent
SCRIPTS = REPO / "plugins" / "job-search" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import jslib  # noqa: E402

# (source, company, source_job_id, title, location, remote, days_ago_found, status, score, missing)
# missing items: (item, category, required)
JOBS = [
    ("greenhouse", "Stripe", "6543210", "Staff Platform Engineer, Developer Infrastructure", "Remote - US", "remote", 1, "needs_approval", 4.4,
     [("Terraform", "tool", True), ("Go", "hard_skill", True), ("Bazel", "tool", False)]),
    ("greenhouse", "Datadog", "7711002", "Principal Platform Architect", "Remote - US", "remote", 1, "prepared", 4.6,
     [("Go", "hard_skill", True), ("Kafka", "tool", False)]),
    ("lever", "Plaid", "a1b2c3d4", "Senior Platform Engineer", "Remote - US", "remote", 2, "scored", 3.9,
     [("Terraform (IaC)", "tool", True), ("GCP", "tool", False), ("PCI DSS", "domain", True)]),
    ("ashby", "Ramp", "f0e1d2c3", "Lead Infrastructure Architect", "New York, NY", "hybrid", 2, "prepared", 4.1,
     [("Terraform", "tool", True), ("Kafka", "tool", True), ("Go", "hard_skill", False)]),
    ("indeed", "Humana", "jk-55120", "AI Platform Architect", "Denver, CO", "hybrid", 3, "needs_approval", 4.2,
     [("MLOps", "hard_skill", True), ("Kubeflow", "tool", False), ("LLMs", "hard_skill", True)]),
    ("greenhouse", "Stripe", "6543999", "Engineering Manager, Platform", "Remote - US", "remote", 3, "skipped", 2.6,
     [("People management", "seniority", True), ("Go", "hard_skill", False)]),
    ("dice", "Optum", "dice-90311", "Senior Cloud Platform Engineer (Contract)", "Remote", "remote", 4, "dismissed", 3.1,
     [("Azure", "tool", True), ("Terraform", "tool", True)]),
    ("linkedin", "GitLab", "3988123456", "Staff Infrastructure Engineer", "Remote", "remote", 5, "applied", 4.3,
     [("Go", "hard_skill", True), ("GCP", "tool", True), ("Terraform", "tool", False)]),
    ("lever", "Plaid", "z9y8x7w6", "Staff Software Engineer, Platform & Reliability", "San Francisco, CA", "hybrid", 6, "applied", 4.0,
     [("Kafka", "tool", True), ("Go", "hard_skill", True), ("SRE practices", "hard_skill", False)]),
    ("greenhouse", "Datadog", "7711555", "Senior Software Engineer, Kubernetes Operators", "Remote - US", "remote", 8, "replied", 4.5,
     [("Go", "hard_skill", True), ("Kubernetes operators", "hard_skill", False)]),
    ("ashby", "Vanta", "v-2231", "Platform Architect", "Remote - US", "remote", 9, "interview", 4.7,
     [("SOC 2", "domain", False), ("Terraform", "tool", True)]),
    ("indeed", "Raymond James", "jk-77001", "Infrastructure Architect", "St. Petersburg, FL", "onsite", 10, "rejected", 3.7,
     [("VMware", "tool", True), ("Azure", "tool", False), ("ITIL", "cert", False)]),
    ("greenhouse", "Airbnb", "5550001", "Staff Engineer, Developer Platform", "Remote - US", "remote", 11, "applied", 4.2,
     [("Kafka", "tool", False), ("Scala", "hard_skill", False), ("Terraform", "tool", True)]),
    ("lever", "Netflix", "nflx-4451", "Senior Platform Engineer, Compute", "Los Gatos, CA", "onsite", 12, "closed", 3.8,
     [("Titus", "tool", False), ("Go", "hard_skill", True)]),
    ("greenhouse", "Cloudflare", "cf-90112", "Principal Systems Engineer, Edge Platform", "Remote - US", "remote", 13, "offer", 4.8,
     [("Rust", "hard_skill", False), ("Go", "hard_skill", True)]),
    ("dice", "Leidos", "dice-11823", "Cloud Infrastructure Architect (Clearance required)", "Reston, VA", "onsite", 14, "skipped", 2.1,
     [("Security clearance", "other", True), ("Azure", "tool", True)]),
    ("ashby", "Ramp", "f0e1d2zz", "Senior Software Engineer, AI Platform", "Remote - US", "remote", 15, "prepared", 3.9,
     [("LLM", "hard_skill", True), ("Vector databases", "tool", False), ("Kafka", "tool", False)]),
    ("indeed", "Front Range Health", "jk-30210", "Lead DevOps Engineer", "Denver, CO", "hybrid", 16, "dismissed", 3.4,
     [("Azure", "tool", True), ("Terraform", "tool", True)]),
    ("greenhouse", "Datadog", "7711900", "Staff Engineer, Internal Developer Platform", "Remote - US", "remote", 17, "applied", 4.4,
     [("Backstage plugins", "tool", False), ("Go", "hard_skill", True), ("Helm charts", "tool", False)]),
    ("lever", "Robinhood", "rh-7710", "Senior Platform Engineer, Payments & Risk", "Remote - US", "remote", 18, "rejected", 3.6,
     [("Kafka", "tool", True), ("Terraform", "tool", True), ("Go", "hard_skill", False)]),
    ("linkedin", "HashiCorp", "3991000001", "Principal Solutions Architect", "Remote", "remote", 19, "scored", 3.5,
     [("Terraform", "tool", True), ("Consul", "tool", False), ("Pre-sales", "domain", True)]),
    ("greenhouse", "Airbnb", "5550222", "Senior Staff Engineer, Cloud Infrastructure", "Remote - US", "remote", 20, "applied", 4.1,
     [("GCP", "tool", False), ("Terraform", "tool", True)]),
    ("manual", "Northbeam Labs", "nb-001", "Head of Platform", "Remote", "remote", 21, "found", None, []),
    ("ashby", "Linear", "lin-3021", "Senior Infrastructure Engineer", "Remote", "remote", 0, "found", None, []),
    ("greenhouse", "Stripe", "6544100", "Staff Engineer, AI Infrastructure", "Remote - US", "remote", 0, "scored", 4.0,
     [("LLMs", "hard_skill", True), ("GPU scheduling", "hard_skill", False), ("Go", "hard_skill", False)]),
]

MATCHED_POOL = [
    ("Kubernetes at scale", ["r1.b1", "s.kubernetes"], "strong"),
    ("AWS cloud architecture", ["r1.b1", "s.aws", "c1"], "strong"),
    ("Internal developer platform", ["r1.b2"], "strong"),
    ("CI/CD pipelines", ["r1.b4", "r2.b2"], "strong"),
    ("Python services", ["r1.b3", "s.python"], "partial"),
    ("LLM application experience", ["r1.b3", "s.llm"], "partial"),
    ("Leading engineering teams", ["sum.2"], "strong"),
    ("Regulated industry experience", ["sum.1", "r1.b4"], "partial"),
    ("Java backend APIs", ["r2.b1", "s.java"], "strong"),
    ("Containers and Docker", ["r2.b2", "s.docker"], "strong"),
]

SUMMARIES = {
    "apply": "Strong match on Kubernetes platform work and developer tooling. Main gaps are tools the team uses daily that you have not listed.",
    "maybe": "Good overlap on platform and cloud work. Several required tools are missing, so expect questions on them.",
    "skip": "The role leans on areas outside your experience. Worth a pass unless the company matters to you.",
}


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def status_path(final: str) -> list:
    pre = ["found"]
    if final == "found":
        return pre
    pre.append("scored")
    if final in ("scored",):
        return pre
    if final in ("skipped", "prepared", "needs_approval"):
        return pre + [final]
    if final in ("dismissed",):
        return pre + ["prepared", "dismissed"]
    if final == "closed":
        return pre + ["prepared", "closed"]
    pre += ["prepared", "applied"]
    if final == "applied":
        return pre
    pre.append("replied")
    if final == "replied":
        return pre
    return pre + [final]


def resume_html(company: str, title: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Resume for %s</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;line-height:1.5}</style>"
        "</head><body><h1>Jordan Rivera</h1><p>Platform Architect</p>"
        "<p><em>Demo placeholder resume tailored for %s at %s.</em></p>"
        "<h2>Experience</h2><h3>Lead Platform Architect, Northwind Health</h3><ul>"
        "<li>Led migration of 40 services from VMs to Kubernetes on AWS EKS, cutting infrastructure cost 30%%</li>"
        "<li>Designed an internal developer platform used by 220 engineers</li></ul></body></html>\n"
    ) % (company, title, company)


def make(dest: Path, today: str, force: bool = False) -> Path:
    dest = Path(dest).expanduser().resolve()
    if dest.exists() and any(dest.iterdir()):
        if not force:
            raise SystemExit("%s is not empty. Use --force to replace it." % dest)
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)
    now = datetime.strptime(today, "%Y-%m-%d").replace(hour=14, minute=5)

    # profile + marker
    shutil.copytree(str(HERE / "profile"), str(dest / "profile"))
    jslib.write_json(dest / jslib.MARKER, {"schema_version": 1, "created_at": iso(now - timedelta(days=24)),
                                           "plugin_version": jslib.PLUGIN_VERSION})
    (dest / "profile" / "resume-master.md").write_text(
        "# Jordan Rivera\n\nPlatform Architect. Demo master resume.\n", encoding="utf-8")
    jslib.write_json(dest / "profile" / "gap-notes.json", {
        "terraform": {"status": "learning", "note": "Doing the HashiCorp tutorials on weekends"},
        "security-clearance": {"status": "ignore", "note": "Not pursuing cleared roles"},
        "people-management": {"status": "ignore", "note": "Staying on the IC track"},
        "pci-dss": {"status": "done", "note": "Covered by Contoso Bank payments work"},
    })

    job_ids = []
    for idx, (source, company, sid, title, loc, remote, ago, status, score, missing) in enumerate(JOBS):
        found = now - timedelta(days=ago, hours=rng.randint(0, 6), minutes=rng.randint(0, 59))
        job = jslib.new_job(source, sid, company, title, location=loc, remote=remote)
        jid = job["id"]
        job_ids.append(jid)
        base_url = {
            "greenhouse": "https://boards.greenhouse.io/%s/jobs/%s",
            "lever": "https://jobs.lever.co/%s/%s",
            "ashby": "https://jobs.ashbyhq.com/%s/%s",
            "indeed": "https://www.indeed.com/viewjob?jk=%s%s",
            "dice": "https://www.dice.com/job-detail/%s-%s",
            "linkedin": "https://www.linkedin.com/jobs/view/%s%s",
            "manual": "https://example.com/careers/%s/%s",
        }[source]
        url = base_url % (jslib.slug(company) if source not in ("indeed", "linkedin") else "", sid)
        job.update({
            "url": url, "apply_url": url,
            "salary": "" if rng.random() < 0.4 else "$%dk - $%dk" % (rng.choice([175, 185, 195, 210]), rng.choice([230, 245, 260, 280])),
            "posted_at": (found - timedelta(days=rng.randint(0, 5))).strftime("%Y-%m-%d"),
            "found_at": iso(found),
        })
        # status history, spaced out after found
        hist = []
        path = status_path(status)
        span = (now - found) * 0.9
        step = span / max(1, len(path) - 1)
        for i, st in enumerate(path):
            t = found + step * i
            note = ""
            if st == "dismissed":
                note = "contract role" if "Contract" in title else "on-site hybrid 4 days, too far"
            if st == "closed":
                note = "posting removed"
            hist.append({"status": st, "at": iso(t), "note": note})
        job["status"] = status
        job["status_history"] = hist
        if status == "dismissed":
            job["dismissed_reason"] = hist[-1]["note"]
        applied = [h for h in hist if h["status"] == "applied"]
        if applied:
            job["applied_at"] = applied[0]["at"]

        d = jslib.job_dir(dest, jid)
        d.mkdir(parents=True, exist_ok=True)
        (d / "jd.md").write_text("# %s at %s\n\nDemo job description.\n" % (title, company), encoding="utf-8")

        if score is not None:
            rec = "apply" if score >= 4.0 else ("maybe" if score >= 3.4 else "skip")
            matched = rng.sample(MATCHED_POOL, rng.randint(3, 5))
            scored_at = hist[1]["at"]
            jslib.write_json(d / "score.json", {
                "schema_version": 1, "job_id": jid, "score": score, "recommendation": rec,
                "summary": SUMMARIES[rec],
                "matched": [{"requirement": r, "evidence": e, "strength": s} for r, e, s in matched],
                "missing": [{"item": m, "category": c, "required": rq} for m, c, rq in missing],
                "keywords": ["platform engineering", "kubernetes", "aws"],
                "deal_breakers_hit": ["contract"] if "Contract" in title else (["clearance required"] if "Clearance" in title else []),
                "scored_at": scored_at,
            })
            job["score"] = score
            job["recommendation"] = rec

        if "prepared" in [h["status"] for h in hist] or status == "needs_approval":
            prepared_at = [h["at"] for h in hist if h["status"] in ("prepared", "needs_approval")][0]
            major = status == "needs_approval" or idx in (10, 14)
            pending = status == "needs_approval"
            changes = [
                {"type": "reword", "target": "roles[0].bullets[0]",
                 "before": "Led migration of 40 services from VMs to Kubernetes on AWS EKS, cutting infrastructure cost 30%",
                 "after": "Led the move of 40 services to Kubernetes (AWS EKS), cutting infrastructure cost 30%",
                 "source_ids": ["r1.b1"]},
                {"type": "reorder", "target": "skills", "before": "Java, Docker, Kubernetes, AWS",
                 "after": "Kubernetes, AWS, Docker, Java", "source_ids": ["s.kubernetes", "s.aws", "s.docker", "s.java"]},
                {"type": "drop", "target": "roles[1].bullets[2]", "before": "Mentored 4 junior engineers", "after": "",
                 "source_ids": ["r2.b3"]},
            ]
            reasons = []
            if major:
                changes.append({"type": "headline_change", "target": "headline", "before": "Platform Architect",
                                "after": "Principal Platform Engineer", "source_ids": []})
                reasons.append("headline changed")
                if idx == 4:
                    changes.append({"type": "skill_promote", "target": "summary",
                                    "before": "14 years building cloud platforms and developer tooling for regulated industries",
                                    "after": "14 years building cloud and AI platforms, including LLM services, for regulated industries",
                                    "source_ids": ["sum.1", "r1.b3"]})
                    reasons.append("skill used lightly promoted to summary (LLM)")
            verify = {"passed": True, "issues": []}
            if idx == 0:
                verify = {"passed": False, "issues": [
                    {"severity": "block", "path": "roles[0].bullets[1]", "message": "number 45% not in sources"},
                    {"severity": "warn", "path": "summary", "message": "tool 'Terraform' not in fact bank"},
                ]}
                changes.append({"type": "reword", "target": "roles[0].bullets[1]",
                                "before": "Designed an internal developer platform used by 220 engineers, reducing new service setup from 2 weeks to 1 day",
                                "after": "Designed a developer platform used by 220 engineers, cutting setup time 45%",
                                "source_ids": ["r1.b2"]})
            approval = "pending" if pending else ("approved" if major else "auto")
            jslib.write_json(d / "changes.json", {
                "schema_version": 1, "job_id": jid,
                "classification": "major" if major else "minor",
                "reasons": reasons or ["rewording and reordering only"],
                "rewrite_ratio": 0.34 if major else round(0.08 + 0.02 * (idx % 5), 2),
                "changes": changes, "verify": verify, "approval": approval,
                "decided_at": None if approval in ("pending", "auto") else prepared_at,
            })
            job["approval"] = approval
            if idx % 4 != 3:
                (d / "resume.html").write_text(resume_html(company, title), encoding="utf-8")
            if idx % 3 == 0:
                (d / "answers.md").write_text(
                    "# Answers for %s\n\nWhy this role: demo answer.\n" % company, encoding="utf-8")

        jslib.save_job(dest, job)

    # memory
    mem = dest / "memory"
    mem.mkdir(exist_ok=True)
    sig_rows = []
    for i in range(18):
        ts = now - timedelta(days=20 - i, hours=rng.randint(0, 8))
        typ = ["dismiss", "apply", "edit", "reject_change", "approve_change", "frustration", "repeat", "outcome", "source_error"][i % 9]
        sig = {"ts": iso(ts), "type": typ, "skill": "tailor" if typ in ("edit", "reject_change", "frustration") else "dashboard",
               "job_id": job_ids[i % len(job_ids)], "detail": "demo %s signal" % typ}
        if typ == "frustration":
            sig["text"] = "I already told you, no 'spearheaded'"
        sig_rows.append(sig)
    for s in sig_rows:
        jslib.append_jsonl(mem / "signals.jsonl", s)

    def d_ago(n):
        return iso(now - timedelta(days=n))

    jslib.write_json(mem / "lessons.json", {"schema_version": 1, "lessons": [
        {"id": "L-001", "text": "Never use the word 'spearheaded'. You removed it 4 times.", "scope": "tailor",
         "kind": "auto", "status": "active", "created": d_ago(18), "last_applied": d_ago(1),
         "evidence": [sig_rows[2]["ts"], sig_rows[5]["ts"], sig_rows[11]["ts"], sig_rows[14]["ts"]], "source": "retro"},
        {"id": "L-002", "text": "Skip roles that say contract or contract-to-hire.", "scope": "scan",
         "kind": "approved", "status": "active", "created": d_ago(12), "last_applied": d_ago(2),
         "evidence": [sig_rows[0]["ts"], sig_rows[9]["ts"]], "source": "feedback"},
        {"id": "L-003", "text": "Keep the Contoso Bank payments bullet when the job mentions fintech.", "scope": "tailor",
         "kind": "auto", "status": "active", "created": d_ago(6), "last_applied": None,
         "evidence": [sig_rows[13]["ts"]], "source": "retro"},
        {"id": "L-004", "text": "Prefer 'Principal Platform Engineer' as the headline.", "scope": "tailor",
         "kind": "auto", "status": "retired", "created": d_ago(20), "last_applied": d_ago(15),
         "evidence": [sig_rows[1]["ts"]], "source": "retro"},
    ]})
    (mem / "lessons.md").write_text(
        "# Lessons\n\n- L-001 (tailor): Never use the word 'spearheaded'.\n"
        "- L-002 (scan): Skip roles that say contract or contract-to-hire.\n"
        "- L-003 (tailor): Keep the Contoso Bank payments bullet when the job mentions fintech.\n",
        encoding="utf-8")
    jslib.write_json(mem / "proposals.json", {"schema_version": 1, "proposals": [
        {"id": "P-001", "text": "Raise min_score to 4.0? You dismissed 6 of 7 jobs scored under 4.", "kind": "preference",
         "status": "pending", "created": d_ago(3), "patch": {"file": "profile/preferences.json", "set": {"min_score": 4.0}}},
        {"id": "P-002", "text": "Turn off Dice? It failed to sign in on 3 of the last 5 runs.", "kind": "source",
         "status": "pending", "created": d_ago(2), "patch": {"file": "profile/sources.json", "set": {"sources.dice.enabled": False}}},
        {"id": "P-003", "text": "Add 'developer tools' to industries you like.", "kind": "preference",
         "status": "accepted", "created": d_ago(14), "patch": {"file": "profile/preferences.json", "set": {}}},
    ]})

    # run log: daily for 21 days plus 3 weekly
    for n in range(21, -1, -1):
        ts = now - timedelta(days=n, hours=6)
        found_n = rng.randint(6, 18)
        new_n = rng.randint(0, min(5, found_n))
        scored = new_n
        prepared = rng.randint(0, min(2, scored))
        errs = []
        if n in (15, 9, 4):
            errs = ["dice: not signed in"]
        if n == 7:
            errs = ["linkedin: login wall, skipped", "greenhouse: airbnb board timed out"]
        jslib.append_jsonl(dest / "runs" / "run-log.jsonl", {
            "ts": iso(ts), "kind": "daily", "found": found_n, "new": new_n, "scored": scored,
            "prepared": prepared, "needs_approval": 1 if n in (1, 3) else 0, "errors": errs, "notes": ""})
        if n in (14, 7, 0):
            jslib.append_jsonl(dest / "runs" / "run-log.jsonl", {
                "ts": iso(ts + timedelta(hours=2)), "kind": "weekly", "found": 0, "new": 0, "scored": 0,
                "prepared": 0, "needs_approval": 0, "errors": [], "notes": "gaps nudge and retro"})

    # derived gaps ledger
    try:
        import gaps  # noqa: E402
        gaps.write_gaps(dest, gaps.build_gaps(dest, today=today))
    except ImportError:
        pass
    return dest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dir")
    ap.add_argument("--today", default=jslib.today())
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    dest = make(Path(args.dir), args.today, args.force)
    print("Demo home ready at %s (%d jobs)" % (dest, len(JOBS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
