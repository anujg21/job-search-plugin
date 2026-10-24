#!/usr/bin/env python3
"""Home setup and small job/memory commands for the job-search plugin.

Commands (see docs/CONVENTIONS.md):
  jobctl.py home
  jobctl.py init [--from-fixtures DIR]
  jobctl.py list [--status S] [--rank] [--limit N] [--json]
  jobctl.py status <job_id> <status> [--note TEXT]
  jobctl.py signal <type> [--skill S] [--job ID] [--detail D] [--text T]
  jobctl.py gapnote <gap_key> <learning|ignore|done> [--note TEXT]
  jobctl.py runlog --kind daily|weekly|manual [--found N] [--new N] [--scored N]
                   [--prepared N] [--needs-approval N] [--errors TEXT ...] [--notes TEXT]
  jobctl.py doctor [--quick] [--json]

Every command accepts --home PATH (before or after the command name).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402

API_SOURCES = ("greenhouse", "lever", "ashby")
BROWSER_SOURCES = ("indeed", "linkedin")
GAP_NOTE_STATUSES = ("learning", "ignore", "done")
CONNECTORS = ("dice", "indeed")
CONNECT_HOWTO = ("connect it once: in Claude Desktop or claude.ai open Customize, Plugins, Job search, "
                 "Connectors, then click Connect next to %s%s. In Claude Code run /mcp and pick %s")
RUN_KINDS = ("daily", "weekly", "manual")


# ---------- templates ----------

def template_preferences() -> dict:
    return {
        "schema_version": jslib.SCHEMA_VERSION,
        "target_titles": [],
        "keywords": [],
        "seniority": [],
        "locations": [],
        "remote": "any",
        "salary_min": 0,
        "must_have": [],
        "deal_breakers": [],
        "exclude_title_words": [],
        "countries": [],
        "industries_like": [],
        "industries_avoid": [],
        "daily_cap": 5,
        "min_score": 3.5,
        "radar_every_days": 30,
        "auto_approve_minor": True,
        "major_rewrite_ratio": 0.30,
    }


def template_sources() -> dict:
    return {
        "schema_version": jslib.SCHEMA_VERSION,
        "sources": {
            "greenhouse": {"enabled": True, "has_access": True, "companies": []},
            "lever": {"enabled": True, "has_access": True, "companies": []},
            "ashby": {"enabled": True, "has_access": True, "companies": []},
            "indeed": {"enabled": False, "has_access": False, "queries": [], "max_per_run": 20},
            "dice": {"enabled": False, "has_access": True, "queries": [], "max_per_run": 20},
            "linkedin": {"enabled": False, "has_access": False, "saved_search_urls": [], "max_per_run": 15},
        },
    }


def template_fact_bank() -> dict:
    return {
        "schema_version": jslib.SCHEMA_VERSION,
        "person": {"name": "", "email": "", "phone": "", "location": "", "links": []},
        "headlines": [],
        "summary_facts": [],
        "roles": [],
        "skills": [],
        "education": [],
        "certifications": [],
        "projects": [],
    }


README_TXT = """Job search data folder
======================

This folder holds everything the job-search plugin knows about you and your search.
It stays on your computer. Nothing here is uploaded by the plugin.

jobsearch.json     Marker file. Tells the plugin this is the data folder.
profile/           Your facts and settings.
  fact-bank.json     Everything your resume is allowed to say. Each fact has an id.
  resume-master.md   Your original resume text, kept for reference.
  preferences.json   Titles, locations, salary floor, deal breakers, daily cap, min score.
  sources.json       Which job boards to search and the companies to watch.
  gap-notes.json     Your notes on skill gaps (learning, ignore, done).
jobs/<job id>/     One folder per job: description, score, tailored resume, answers.
gaps.json          Skill gaps across all jobs. Rebuilt on every run.
memory/            What the plugin learned from your feedback.
  signals.jsonl      Raw events (edits, dismissals, repeated requests).
  lessons.json       Lessons the plugin follows. lessons.md is the readable copy.
  proposals.json     Suggested changes waiting for your yes or no.
runs/              Run log and weekly retro notes.
dashboard.html     Open this in your browser to see everything.

To change a setting, run /job-search:onboard again or edit the JSON files.
To back up, copy this folder. If you keep it in git, consider ignoring jobs/*/resume.pdf.
"""


# ---------- helpers ----------

def _write_if_missing(path: Path, data, created: List[str]) -> None:
    if path.exists():
        return
    if isinstance(data, (dict, list)):
        jslib.write_json(path, data)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
    created.append(str(path))


def _render_lessons(home: Path) -> None:
    """Render lessons.md via memory.py so both scripts share one format."""
    try:
        import memory  # noqa: WPS433 (local module)
        memory.render_lessons(home)
    except Exception as e:  # pragma: no cover - never block init on rendering
        md = home / "memory" / "lessons.md"
        if not md.exists():
            md.write_text("# Lessons\n\nNo lessons yet.\n", encoding="utf-8")
        print("note: could not render lessons.md (%s)" % e, file=sys.stderr)


def init_home(home: Path, from_fixtures: Optional[str] = None) -> List[str]:
    created: List[str] = []
    home.mkdir(parents=True, exist_ok=True)
    for sub in ("profile", "jobs", "memory", "runs"):
        (home / sub).mkdir(exist_ok=True)

    if from_fixtures:
        src = Path(from_fixtures).expanduser()
        if not src.is_dir():
            raise SystemExit("Fixtures folder not found: %s" % src)
        for p in sorted(src.iterdir()):
            if p.is_file() and p.suffix in (".json", ".md", ".txt"):
                dest = home / "profile" / p.name
                if not dest.exists():
                    shutil.copyfile(str(p), str(dest))
                    created.append(str(dest))

    _write_if_missing(home / jslib.MARKER, {
        "schema_version": jslib.SCHEMA_VERSION,
        "created_at": jslib.now_iso(),
        "plugin_version": jslib.PLUGIN_VERSION,
    }, created)
    prof = home / "profile"
    _write_if_missing(prof / "preferences.json", template_preferences(), created)
    _write_if_missing(prof / "sources.json", template_sources(), created)
    _write_if_missing(prof / "fact-bank.json", template_fact_bank(), created)
    _write_if_missing(prof / "gap-notes.json", {}, created)
    mem = home / "memory"
    _write_if_missing(mem / "signals.jsonl", "", created)
    _write_if_missing(mem / "lessons.json", {"schema_version": jslib.SCHEMA_VERSION, "lessons": []}, created)
    _write_if_missing(mem / "proposals.json", {"schema_version": jslib.SCHEMA_VERSION, "proposals": []}, created)
    if not (mem / "lessons.md").exists():
        _render_lessons(home)
        created.append(str(mem / "lessons.md"))
    _write_if_missing(home / "README.txt", README_TXT, created)
    return created


# ---------- doctor ----------

def _collect_ids(fb: dict) -> List[str]:
    ids: List[str] = []
    for x in fb.get("summary_facts", []) or []:
        ids.append(x.get("id"))
    for r in fb.get("roles", []) or []:
        ids.append(r.get("id"))
        for b in r.get("bullets", []) or []:
            ids.append(b.get("id"))
    for key in ("skills", "education", "certifications", "projects"):
        for x in fb.get(key, []) or []:
            ids.append(x.get("id"))
    return ids


def check_fact_bank(fb: dict) -> List[str]:
    """Return a list of problems (empty list = sane)."""
    problems: List[str] = []
    ids = _collect_ids(fb)
    missing_ids = [i for i in ids if not i]
    if missing_ids:
        problems.append("%d entries have no id" % len(missing_ids))
    seen, dups = set(), set()
    for i in ids:
        if not i:
            continue
        if i in seen:
            dups.add(i)
        seen.add(i)
    if dups:
        problems.append("duplicate ids: %s" % ", ".join(sorted(dups)))
    for r in fb.get("roles", []) or []:
        for b in r.get("bullets", []) or []:
            text = (b.get("text") or "").lower()
            for m in b.get("metrics", []) or []:
                if str(m).lower() not in text:
                    problems.append("%s: metric %r is not in the bullet text" % (b.get("id"), m))
    for s in fb.get("skills", []) or []:
        for ev in s.get("evidence", []) or []:
            if ev not in seen:
                problems.append("%s: evidence id %r does not exist" % (s.get("id"), ev))
    return problems


def _find_chrome() -> Optional[str]:
    env = os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        return env
    mac = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for p in mac:
        if Path(p).exists():
            return p
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    win = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for p in win:
        if Path(p).exists():
            return p
    return None


def run_doctor(home: Path, quick: bool = False) -> List[dict]:
    checks: List[dict] = []

    def add(name: str, status: str, detail: str = "") -> None:
        checks.append({"check": name, "status": status, "detail": detail})

    ok_py = sys.version_info >= (3, 9)
    add("Python 3.9 or newer", "pass" if ok_py else "fail", platform.python_version())

    if not (home / jslib.MARKER).exists():
        add("Data folder exists", "fail", "%s has no %s. Run /job-search:onboard." % (home, jslib.MARKER))
        return checks
    add("Data folder exists", "pass", str(home))

    loaded = {}
    for name in ("fact-bank.json", "preferences.json", "sources.json"):
        path = home / "profile" / name
        if not path.exists():
            add("profile/%s" % name, "fail", "missing")
            continue
        try:
            data = jslib.read_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            add("profile/%s" % name, "fail", "not valid JSON: %s" % e)
            continue
        if not isinstance(data, dict) or data.get("schema_version") != jslib.SCHEMA_VERSION:
            add("profile/%s" % name, "fail", "schema_version must be %d" % jslib.SCHEMA_VERSION)
            continue
        loaded[name] = data
        add("profile/%s" % name, "pass", "valid")

    gn = home / "profile" / "gap-notes.json"
    if gn.exists():
        try:
            jslib.read_json(gn)
            add("profile/gap-notes.json", "pass", "valid")
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            add("profile/gap-notes.json", "fail", "not valid JSON: %s" % e)

    if (home / "profile" / "resume-master.md").exists():
        add("profile/resume-master.md", "pass", "present")
    else:
        add("profile/resume-master.md", "warn", "missing. Import your resume with /job-search:onboard.")

    fb = loaded.get("fact-bank.json")
    if fb is not None:
        problems = check_fact_bank(fb)
        if not (fb.get("roles") or []):
            problems.insert(0, "no roles yet. Import your resume with /job-search:onboard")
        if problems:
            add("Fact bank sanity", "fail", "; ".join(problems[:8]) + (" ..." if len(problems) > 8 else ""))
        else:
            n_b = sum(len(r.get("bullets", []) or []) for r in fb.get("roles", []))
            add("Fact bank sanity", "pass", "%d roles, %d bullets, %d skills" % (
                len(fb.get("roles", [])), n_b, len(fb.get("skills", []) or [])))
        if not (fb.get("headlines") or []):
            add("Fact bank headlines", "warn", "no headlines. The resume will reuse your role titles.")

    src = loaded.get("sources.json")
    if src is not None:
        sources = src.get("sources", {}) or {}
        enabled = [k for k, v in sources.items() if v.get("enabled")]
        if enabled:
            add("At least one source enabled", "pass", ", ".join(enabled))
        else:
            add("At least one source enabled", "fail", "turn on a source in /job-search:onboard")
        usable = [k for k in enabled
                  if (sources[k].get("companies") if k in API_SOURCES
                      else bool(sources[k].get("queries")) if k == "dice"
                      else (k == "indeed" or sources[k].get("has_access")))]
        if enabled and not usable:
            add("A source that can find jobs", "fail",
                "no companies listed and Dice, Indeed, LinkedIn are off; add companies or turn on "
                "Dice or Indeed with /job-search:onboard (Job sources)")
        for k in enabled:
            v = sources[k]
            if k in API_SOURCES and not v.get("companies"):
                add("Source %s" % k, "warn", "enabled but no companies listed")
            if k in CONNECTORS and v.get("connector") is not True:
                add("Connector %s" % k, "warn", ("not confirmed; " if v.get("connector") is None
                                                 else "not connected; ") + CONNECT_HOWTO % (
                    k.title(), " and sign in to Indeed" if k == "indeed" else "", k))
            if k == "dice" and not v.get("queries"):
                add("Source dice", "warn", "enabled but no searches; run /job-search:onboard (Job sources)")
            if k == "indeed" and not v.get("has_access"):
                add("Source indeed", "warn", "uses the Indeed connector if connected, else web search")
            elif k in BROWSER_SOURCES and not v.get("has_access"):
                add("Source %s" % k, "warn", "enabled but Chrome access not confirmed (see sources/check-access.md)")

    for name in ("lessons.json", "proposals.json"):
        path = home / "memory" / name
        try:
            jslib.read_json(path)
            add("memory/%s" % name, "pass" if path.exists() else "warn",
                "valid" if path.exists() else "missing (run jobctl.py init)")
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            add("memory/%s" % name, "fail", "not valid JSON: %s" % e)

    if not quick:
        chrome = _find_chrome()
        if chrome:
            add("Chrome for PDF export", "pass", chrome)
        else:
            add("Chrome for PDF export", "warn", "not found. Resumes will be HTML only. Set CHROME_PATH if it is installed.")
    return checks


# ---------- commands ----------

def cmd_home(args) -> int:
    home = jslib.resolve_home(args.home)
    if (home / jslib.MARKER).exists():
        print(home)
        return 0
    print("No job-search home exists at %s. Run /job-search:onboard first." % home)
    return 1


def cmd_init(args) -> int:
    home = jslib.resolve_home(args.home)
    created = init_home(home, args.from_fixtures)
    if created:
        print("Data folder ready at %s (%d new files)." % (home, len(created)))
    else:
        print("Data folder already set up at %s. Nothing changed." % home)
    return 0


def cmd_list(args) -> int:
    home = jslib.require_home(args.home)
    jobs = [j for j in jslib.iter_jobs(home) if not args.status or j.get("status") == args.status]
    jobs.sort(key=lambda j: (-(j.get("score") or 0), j.get("found_at") or ""))
    if getattr(args, "rank", False):
        import sources_lib  # noqa: WPS433 (local module)
        prefs = jslib.load_preferences(home)
        for j in jobs:
            j["title_rank"] = sources_lib.title_rank(j.get("title", ""), prefs)
        # Best title match first, then newest.
        jobs.sort(key=lambda j: j.get("found_at") or "", reverse=True)
        jobs.sort(key=lambda j: j["title_rank"], reverse=True)
        # The same role posted in several cities: score it once. Copies of a role that is
        # already scored, or that appears higher in this list, go to the end.
        seen = {}
        for j in jslib.iter_jobs(home):
            if j.get("status") != "found":
                seen.setdefault(jslib.posting_key(j), j["id"])
        firsts, dups = [], []
        for j in jobs:
            key = jslib.posting_key(j)
            if key and key in seen:
                j["duplicate_of"] = seen[key]
                dups.append(j)
            else:
                if key:
                    seen[key] = j["id"]
                firsts.append(j)
        jobs = firsts + dups
    if getattr(args, "limit", None):
        jobs = jobs[: args.limit]
    if args.json:
        print(json.dumps(jobs, indent=2, ensure_ascii=False))
        return 0
    if not jobs:
        print("No jobs%s." % (" with status %s" % args.status if args.status else ""))
        return 0
    for j in jobs:
        score = j.get("score")
        print("%-50s %-15s %-4s %s | %s" % (
            j.get("id"), j.get("status"), "%.1f" % score if isinstance(score, (int, float)) else "-",
            j.get("company"), j.get("title")))
    print("%d jobs." % len(jobs))
    return 0


def cmd_status(args) -> int:
    home = jslib.require_home(args.home)
    job = jslib.set_status(home, args.job_id, args.status, args.note or "")
    print("%s is now %s." % (job["id"], job["status"]))
    return 0


def cmd_signal(args) -> int:
    home = jslib.require_home(args.home)
    sig = jslib.add_signal(home, args.type, skill=args.skill, job_id=args.job,
                           detail=args.detail, text=args.text)
    print(json.dumps(sig, ensure_ascii=False))
    return 0


def cmd_gapnote(args) -> int:
    home = jslib.require_home(args.home)
    path = home / "profile" / "gap-notes.json"
    notes = jslib.read_json(path, {}) or {}
    key = jslib.norm_key(args.gap_key)
    notes[key] = {"status": args.status, "note": args.note or ""}
    jslib.write_json(path, notes)
    print("Gap %s marked %s." % (key, args.status))
    return 0


def cmd_runlog(args) -> int:
    home = jslib.require_home(args.home)
    entry = jslib.log_run(
        home, kind=args.kind, found=args.found, new=args.new, scored=args.scored,
        prepared=args.prepared, needs_approval=args.needs_approval,
        errors=[e for e in (args.errors or []) if e], notes=args.notes or "")
    print(json.dumps(entry, ensure_ascii=False))
    return 0


def cmd_connector(args) -> int:
    """Record whether a connector worked, so doctor can tell the user how to connect it."""
    home = jslib.require_home(args.home)
    path = home / "profile" / "sources.json"
    cfg = jslib.read_json(path, {}) or {}
    src = cfg.setdefault("sources", {}).setdefault(args.name, {})
    src["connector"] = args.state == "ok"
    src["connector_checked"] = jslib.now_iso()
    jslib.write_json(path, cfg)
    print("%s connector: %s" % (args.name, "connected" if src["connector"] else "not connected"))
    return 0


def cmd_doctor(args) -> int:
    home = jslib.resolve_home(args.home)
    checks = run_doctor(home, quick=args.quick)
    failed = [c for c in checks if c["status"] == "fail"]
    if args.json:
        print(json.dumps({"home": str(home), "ok": not failed, "checks": checks}, indent=2))
    else:
        marks = {"pass": "[ok]  ", "warn": "[warn]", "fail": "[FAIL]"}
        print("Checking %s" % home)
        for c in checks:
            print("%s %s%s" % (marks[c["status"]], c["check"], (": " + c["detail"]) if c["detail"] else ""))
        if failed:
            print("%d problem(s) to fix." % len(failed))
        else:
            print("All required checks passed.")
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jobctl.py", description="Job search home and job commands.")
    p.add_argument("--home", default=None, help="data folder (default: resolved by jslib)")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--home", default=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="cmd")
    sub.required = True

    sub.add_parser("home", parents=[common], help="print the data folder").set_defaults(fn=cmd_home)

    s = sub.add_parser("init", parents=[common], help="create the data folder")
    s.add_argument("--from-fixtures", default=None, help="copy profile files from this folder")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("list", parents=[common], help="list jobs")
    s.add_argument("--status", default=None)
    s.add_argument("--json", action="store_true")
    s.add_argument("--rank", action="store_true",
                   help="best match to your target titles first (use with --status found)")
    s.add_argument("--limit", type=int, default=None, help="show at most N jobs")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("status", parents=[common], help="set a job status")
    s.add_argument("job_id")
    s.add_argument("status", choices=jslib.STATUSES)
    s.add_argument("--note", default="")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("signal", parents=[common], help="log a memory signal")
    s.add_argument("type", choices=sorted(jslib.SIGNAL_TYPES))
    s.add_argument("--skill", default=None)
    s.add_argument("--job", default=None)
    s.add_argument("--detail", default=None)
    s.add_argument("--text", default=None)
    s.set_defaults(fn=cmd_signal)

    s = sub.add_parser("gapnote", parents=[common], help="flag a skill gap")
    s.add_argument("gap_key")
    s.add_argument("status", choices=GAP_NOTE_STATUSES)
    s.add_argument("--note", default="")
    s.set_defaults(fn=cmd_gapnote)

    s = sub.add_parser("runlog", parents=[common], help="append a run-log entry")
    s.add_argument("--kind", choices=RUN_KINDS, default="manual")
    for name in ("found", "new", "scored", "prepared", "needs-approval"):
        s.add_argument("--" + name, type=int, default=0)
    s.add_argument("--errors", action="append", default=[],
                   help="one problem per flag; repeat the flag for more")
    s.add_argument("--notes", default="")
    s.set_defaults(fn=cmd_runlog)

    s = sub.add_parser("connector", parents=[common], help="record whether a connector worked")
    s.add_argument("name", choices=CONNECTORS)
    s.add_argument("state", choices=("ok", "missing"))
    s.set_defaults(fn=cmd_connector)

    s = sub.add_parser("doctor", parents=[common], help="check the setup")
    s.add_argument("--quick", action="store_true", help="skip the Chrome check")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_doctor)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
