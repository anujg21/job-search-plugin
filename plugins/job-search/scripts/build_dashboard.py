#!/usr/bin/env python3
"""Build <home>/dashboard.html: one self-contained static page with the data inlined.

Usage:
  build_dashboard.py [--home H] [--out PATH] [--json]

The page makes no network requests. Data goes into a
<script type="application/json"> tag; the JS in templates/dashboard.html renders it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402

PLUGIN_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
TEMPLATE = PLUGIN_ROOT / "templates" / "dashboard.html"
PLACEHOLDER = "__DASHBOARD_DATA_JSON__"
RUN_LOG_LIMIT = 50
TREND_WEEKS = 8
MAX_DIFF_CHARS = 2000
DEFAULT_MIN_SCORE = 3.5
DEFAULT_MAJOR_RATIO = 0.30


def _num(value, default):
    """A number from preferences, or the default when it is missing or not numeric."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return value


def _clip(value, n=MAX_DIFF_CHARS):
    if isinstance(value, str) and len(value) > n:
        return value[:n] + "..."
    return value


def _safe_read(path: Path, default=None):
    """Read JSON but never crash the whole dashboard on one bad file."""
    try:
        return jslib.read_json(path, default)
    except (ValueError, OSError):
        return default


def summarize_changes(ch: dict) -> dict:
    if not isinstance(ch, dict):
        return None
    changes = []
    for c in ch.get("changes", []) or []:
        if not isinstance(c, dict):
            continue
        changes.append({
            "type": c.get("type"), "target": c.get("target"),
            "before": _clip(c.get("before")), "after": _clip(c.get("after")),
            "source_ids": c.get("source_ids") or [],
        })
    verify = ch.get("verify") or {}
    return {
        "classification": ch.get("classification"),
        "reasons": ch.get("reasons") or [],
        "rewrite_ratio": ch.get("rewrite_ratio"),
        "approval": ch.get("approval"),
        "decided_at": ch.get("decided_at"),
        "verify": {"passed": verify.get("passed"), "issues": verify.get("issues") or []},
        "changes": changes,
    }


def summarize_score(sc: dict) -> dict:
    if not isinstance(sc, dict):
        return None
    return {
        "score": sc.get("score"),
        "recommendation": sc.get("recommendation"),
        "summary": sc.get("summary"),
        "matched": sc.get("matched") or [],
        "missing": sc.get("missing") or [],
        "deal_breakers_hit": sc.get("deal_breakers_hit") or [],
        "scored_at": sc.get("scored_at"),
    }


RADAR_REPORT_RE = re.compile(r"^radar/radar-\d{4}-\d{2}-\d{2}\.md$")
RADAR_DEFAULT_EVERY = 30
RADAR_REPORT_MAX = 300000


def summarize_radar(home: Path, base: str, today: str) -> dict:
    """radar/latest.json plus its age and a link to the report. None when there is no radar."""
    radar = _safe_read(home / "radar" / "latest.json")
    if not isinstance(radar, dict):
        return None
    out = dict(radar)
    prefs = jslib.load_preferences(home)
    every = prefs.get("radar_every_days", RADAR_DEFAULT_EVERY)
    out["every_days"] = every
    age = None
    try:
        age = (datetime.strptime(today, "%Y-%m-%d") - datetime.strptime(str(radar.get("as_of"))[:10], "%Y-%m-%d")).days
    except ValueError:
        pass
    out["age_days"] = age
    out["stale"] = bool(every) and age is not None and age >= every
    report = radar.get("report")
    out["report_href"] = None
    out["report_md"] = None
    if isinstance(report, str) and RADAR_REPORT_RE.match(report) and (home / report).is_file():
        out["report_href"] = base + report
        try:
            # Inlined so the dashboard can show the report in its own theme (rendered as text nodes).
            out["report_md"] = (home / report).read_text(encoding="utf-8")[:RADAR_REPORT_MAX]
        except (OSError, UnicodeDecodeError):
            pass
    return out


def week_labels(today: str, n: int = TREND_WEEKS) -> list:
    d = datetime.strptime(today, "%Y-%m-%d")
    out = []
    for i in range(n - 1, -1, -1):
        out.append(jslib.iso_week((d - timedelta(weeks=i)).strftime("%Y-%m-%d")))
    return out


def gather(home: Path, out_path: Path) -> dict:
    home = Path(home)
    rel = os.path.relpath(str(home), str(out_path.parent)).replace(os.sep, "/")
    base = "" if rel == "." else rel.rstrip("/") + "/"

    jobs = []
    jroot = jslib.jobs_dir(home)
    dirs = sorted(p for p in jroot.iterdir() if p.is_dir()) if jroot.exists() else []
    for d in dirs:
        job = _safe_read(d / "job.json")
        if not isinstance(job, dict):
            continue
        jid = job.get("id") or d.name
        files = {}
        for key, name in (("resume_html", "resume.html"), ("resume_pdf", "resume.pdf"), ("answers_md", "answers.md")):
            if (d / name).exists():
                files[key] = "%sjobs/%s/%s" % (base, d.name, name)
        score = summarize_score(_safe_read(d / "score.json"))
        changes = summarize_changes(_safe_read(d / "changes.json"))
        jobs.append({
            "id": jid,
            "source": job.get("source"),
            "company": job.get("company"),
            "title": job.get("title"),
            "location": job.get("location"),
            "remote": job.get("remote"),
            "url": job.get("url"),
            "apply_url": job.get("apply_url"),
            "salary": job.get("salary"),
            "posted_at": job.get("posted_at"),
            "found_at": job.get("found_at"),
            "status": job.get("status"),
            "status_history": job.get("status_history") or [],
            "score": job.get("score") if job.get("score") is not None else (score or {}).get("score"),
            "recommendation": job.get("recommendation") or (score or {}).get("recommendation"),
            "approval": (changes or {}).get("approval") or job.get("approval"),
            "dismissed_reason": job.get("dismissed_reason"),
            "applied_at": job.get("applied_at"),
            "files": files,
            "score_detail": score,
            "changes": changes,
        })

    signals = jslib.read_jsonl(home / "memory" / "signals.jsonl")
    sig_counts = Counter(s.get("type", "unknown") for s in signals if isinstance(s, dict))
    runs = jslib.read_jsonl(home / "runs" / "run-log.jsonl")
    runs = sorted((r for r in runs if isinstance(r, dict)), key=lambda r: r.get("ts") or "")[-RUN_LOG_LIMIT:]
    runs.reverse()

    gaps = _safe_read(home / "gaps.json", None)
    if not isinstance(gaps, dict):
        try:  # no ledger yet: compute it in memory so the gaps view is never stale-empty
            import gaps as gaps_mod
            gaps = gaps_mod.build_gaps(home)
        except Exception:  # noqa: BLE001 - the dashboard must still build
            gaps = None
    notes = _safe_read(jslib.profile_path(home, "gap-notes.json"), {}) or {}
    notes = {k: v for k, v in notes.items() if isinstance(v, dict)}
    lessons = (_safe_read(home / "memory" / "lessons.json", {}) or {}).get("lessons", []) or []
    proposals = (_safe_read(home / "memory" / "proposals.json", {}) or {}).get("proposals", []) or []

    today = jslib.today()
    found_weekly = Counter()
    for j in jobs:
        try:
            found_weekly[jslib.iso_week(str(j.get("found_at") or ""))] += 1
        except ValueError:
            pass
    prefs = jslib.load_preferences(home)
    try:
        radar = summarize_radar(home, base, today)
    except Exception:  # noqa: BLE001 - the dashboard must still build
        radar = None
    return {
        "schema_version": jslib.SCHEMA_VERSION,
        "generated_at": jslib.now_iso(),
        "today": today,
        "home": str(home),
        "weeks": week_labels(today),
        "found_weekly": dict(sorted(found_weekly.items())),
        "prefs": {
            "min_score": _num(prefs.get("min_score"), DEFAULT_MIN_SCORE),
            "major_rewrite_ratio": _num(prefs.get("major_rewrite_ratio"), DEFAULT_MAJOR_RATIO),
        },
        "jobs": jobs,
        "gaps": gaps,
        "gap_notes": notes,
        "lessons": lessons,
        "proposals": proposals,
        "radar": radar,
        "runs": runs,
        "signal_counts": dict(sorted(sig_counts.items())),
    }


def to_script_json(data: dict) -> str:
    """JSON safe to place inside <script type="application/json">.

    Escaping <, > and & means "</script" or "<!--" in the data can never close the tag.
    U+2028/2029 are escaped too so the text stays valid if someone copies it into JS.
    """
    s = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return (s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
             .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def render(data: dict, template_path: Path = TEMPLATE) -> str:
    tpl = Path(template_path).read_text(encoding="utf-8")
    if PLACEHOLDER not in tpl:
        raise SystemExit("Dashboard template is missing the %s placeholder" % PLACEHOLDER)
    return tpl.replace(PLACEHOLDER, to_script_json(data), 1)


def build(home: Path, out: Path = None) -> Path:
    home = Path(home)
    out = Path(out).expanduser().resolve() if out else home / "dashboard.html"
    data = gather(home, out)
    html = render(data)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name("." + out.name + ".tmp")
    tmp.write_text(html, encoding="utf-8")
    os.replace(str(tmp), str(out))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the static dashboard.html for the job-search home.")
    ap.add_argument("--home")
    ap.add_argument("--out", help="output path (default <home>/dashboard.html)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    home = jslib.require_home(args.home)
    out = build(home, Path(args.out) if args.out else None)
    njobs = sum(1 for _ in jslib.iter_jobs(home))
    if args.json:
        print(json.dumps({"path": str(out), "jobs": njobs}))
    else:
        print("Dashboard written to %s (%d jobs)." % (out, njobs))
        print("Open it: file://%s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
