#!/usr/bin/env python3
"""Check a job's answers.md (cover note and screening answers) against the fact bank.

Usage: check_answers.py <job_id> [--json] [--home PATH]

The cover note is free text, so verify_resume.py does not see it. This check catches the
two slips that matter most there:
- a number that is not in the fact bank or preferences ("cut costs 40%", "12 years");
- em or en dashes, which the plugin's writing rules forbid.
Exit 1 when there are issues. It never edits the file.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402
import resume_lib as rl  # noqa: E402

DASHES = {"\u2014": "em dash", "\u2013": "en dash"}


def number_pool(fb: dict, prefs: dict) -> list:
    pool = []

    def add(text) -> None:
        if text not in (None, ""):
            pool.extend(rl.extract_numbers(str(text)))

    for s in fb.get("summary_facts", []) or []:
        add(s.get("text"))
    for r in fb.get("roles", []) or []:
        add(r.get("title"))
        for k in ("start", "end"):
            add(str(r.get(k) or "")[:4])
        for b in r.get("bullets", []) or []:
            add(b.get("text"))
            for m in b.get("metrics", []) or []:
                add(m)
    for s in fb.get("skills", []) or []:
        if s.get("years") not in (None, ""):
            add("%s years" % s["years"])
            add(s["years"])
    for key in ("education", "certifications"):
        for x in fb.get(key, []) or []:
            add(x.get("year"))
            add(x.get("name") or x.get("degree"))
    for p in fb.get("projects", []) or []:
        add(p.get("text"))
    sal = prefs.get("salary_min")
    if isinstance(sal, (int, float)) and sal:
        add("$%s" % format(int(sal), ","))
        add(int(sal))
    return pool


def check_text(text: str, fb: dict, prefs: dict) -> list:
    issues = []
    pool = number_pool(fb, prefs)
    for i, line in enumerate(text.splitlines(), 1):
        for ch, name in DASHES.items():
            if ch in line:
                issues.append({"line": i, "message": "%s in %r; use a comma, period or the word 'to'" % (name, line.strip()[:80])})
        # The heading is "# Company: Job title"; titles can carry numbers ("Engineer II").
        if line.startswith("#") or "[fill in]" in line and not re.search(r"\d", line.replace("[fill in]", "")):
            continue
        for n in rl.extract_numbers(line):
            if not rl.number_supported(n, pool):
                issues.append({"line": i, "message": "number %r is not in your fact bank or preferences: %r" % (
                    n["raw"], line.strip()[:120])})
    return issues


def check_job(home: Path, job_id: str) -> dict:
    path = jslib.job_dir(home, job_id) / "answers.md"
    if not path.exists():
        raise SystemExit("No answers.md for %s. Run /job-search:tailor first." % job_id)
    issues = check_text(path.read_text(encoding="utf-8"), jslib.load_fact_bank(home), jslib.load_preferences(home))
    return {"job_id": job_id, "passed": not issues, "issues": issues}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("job_id")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--home")
    a = ap.parse_args(argv)
    home = jslib.require_home(a.home)
    res = check_job(home, a.job_id)
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print("answers %s: %s (%d issue%s)" % (a.job_id, "PASSED" if res["passed"] else "FAILED",
                                               len(res["issues"]), "" if len(res["issues"]) == 1 else "s"))
        for x in res["issues"]:
            print("  line %d: %s" % (x["line"], x["message"]))
    return 0 if res["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
