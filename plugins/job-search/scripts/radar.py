#!/usr/bin/env python3
"""Career Trend Radar helpers: local JD tally, validate/save the structured radar, proposals.

Usage:
  radar.py local-tally [--json] [--days 90]
  radar.py save --file radar.json [--report radar/radar-YYYY-MM-DD.md] [--json]
  radar.py propose [--json]
  radar.py status [--json]          # age of the latest radar and whether it is due
  radar.py latest                   # print radar/latest.json

See docs/DATA_MODEL.md (radar/) and skills/radar/SKILL.md.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402
import memory  # noqa: E402

LEVELS = ("high", "medium", "low")
YOU = ("have", "partial", "gap")
DEFAULT_EVERY_DAYS = 30


def radar_dir(home: Path) -> Path:
    return Path(home) / "radar"


def load_latest(home: Path) -> Optional[dict]:
    return jslib.read_json(radar_dir(home) / "latest.json")


# ---------- local tally ----------

def local_tally(home: Path, days: int = 90, today: Optional[str] = None) -> dict:
    """Count skills across scored jobs already in the data folder: a free JD sample."""
    today = today or jslib.today()
    cutoff = datetime.strptime(today, "%Y-%m-%d")
    skills = {}
    titles = {}
    sample = 0
    for job in jslib.iter_jobs(home):
        score = jslib.read_json(jslib.job_dir(home, job["id"]) / "score.json")
        if not score:
            continue
        seen = (job.get("posted_at") or job.get("found_at") or "")[:10]
        if seen:
            try:
                if (cutoff - datetime.strptime(seen, "%Y-%m-%d")).days > days:
                    continue
            except ValueError:
                pass
        sample += 1
        t = (job.get("title") or "").strip()
        if t:
            titles[t] = titles.get(t, 0) + 1
        per_job = {}
        for m in score.get("matched") or []:
            name = str(m.get("requirement") or "").strip()
            if name:
                per_job.setdefault(jslib.norm_key(name), {"name": name, "you": "have" if m.get("strength") == "strong" else "partial", "required": True})
        for m in score.get("missing") or []:
            if isinstance(m, str):
                m = {"item": m}
            name = str(m.get("item") or "").strip()
            if name:
                cur = per_job.setdefault(jslib.norm_key(name), {"name": name, "you": "gap", "required": False})
                cur["required"] = cur["required"] or bool(m.get("required"))
        for k in score.get("keywords") or []:
            per_job.setdefault(jslib.norm_key(k), {"name": k, "you": None, "required": False})
        for key, v in per_job.items():
            s = skills.setdefault(key, {"skill": v["name"], "count": 0, "required": 0, "you": v["you"], "last_seen": seen})
            s["count"] += 1
            s["required"] += 1 if v["required"] else 0
            if v["you"] and (s["you"] is None or YOU.index(v["you"]) < YOU.index(s["you"])):
                s["you"] = v["you"]
            if seen and seen > (s.get("last_seen") or ""):
                s["last_seen"] = seen
    fb = jslib.load_fact_bank(home)
    known = {jslib.norm_key(s.get("name", "")) for s in fb.get("skills") or []}
    for r in fb.get("roles") or []:
        for b in r.get("bullets") or []:
            known |= {jslib.norm_key(x) for x in b.get("skills") or []}
    for key, s in skills.items():
        if s["you"] is None:
            s["you"] = "have" if key in known else "unknown"
    rows = sorted(skills.values(), key=lambda r: (-r["count"], r["skill"].lower()))
    for r in rows:
        r["sample"] = sample
    return {
        "as_of": today, "window_days": days, "sample": sample,
        "titles": sorted(({"title": k, "count": v} for k, v in titles.items()), key=lambda r: -r["count"]),
        "skill_demand": rows,
    }


# ---------- validate / save ----------

def _signals_ok(item: dict) -> bool:
    sigs = item.get("signals") or []
    return any(isinstance(s, dict) and str(s.get("url") or "").startswith(("http://", "https://")) for s in sigs)


def validate(radar: dict, fact_bank: dict) -> (dict, List[str]):
    """Return a cleaned radar and a list of human notes about what was dropped or fixed."""
    notes = []
    ids = set(jslib.fact_index(fact_bank))
    out = dict(radar)
    out["schema_version"] = jslib.SCHEMA_VERSION
    out.setdefault("as_of", jslib.today())
    if not str(out.get("verdict") or "").strip():
        raise SystemExit("Radar needs a one-line verdict.")

    def level(v, field, where):
        v = str(v or "").lower()
        if v in ("h", "m", "l"):
            v = {"h": "high", "m": "medium", "l": "low"}[v]
        if v not in LEVELS:
            notes.append("%s: %s %r is not high/medium/low, set to low" % (where, field, v))
            return "low"
        return v

    titles = []
    for t in out.get("titles_now") or []:
        if not t.get("title"):
            continue
        t = dict(t)
        t["fit"] = level(t.get("fit"), "fit", t["title"])
        t["momentum"] = level(t.get("momentum"), "momentum", t["title"])
        titles.append(t)
    out["titles_now"] = titles

    for key in ("emerging_titles", "jd_shifts", "titles_at_risk", "rising_skills"):
        kept = []
        for item in out.get(key) or []:
            label = item.get("title") or item.get("change") or item.get("skill") or "?"
            if not _signals_ok(item):
                notes.append("%s: dropped %r, no cited signal with a URL" % (key, label))
                continue
            item = dict(item)
            if "confidence" in item or key != "titles_at_risk":
                item["confidence"] = level(item.get("confidence"), "confidence", label)
            if "fit" in item:
                item["fit"] = level(item.get("fit"), "fit", label)
            kept.append(item)
        out[key] = kept

    demand = []
    for d in out.get("skill_demand") or []:
        if not d.get("skill"):
            continue
        d = dict(d)
        if d.get("you") not in YOU:
            d["you"] = "gap"
        demand.append(d)
    out["skill_demand"] = demand

    lang = []
    for r in out.get("resume_language") or []:
        fids = [f for f in (r.get("fact_ids") or []) if f in ids]
        if not fids or not r.get("market_term"):
            notes.append("resume_language: dropped %r, it must relabel real fact bank ids" % r.get("market_term"))
            continue
        lang.append({"market_term": r["market_term"], "your_term": r.get("your_term", ""), "fact_ids": fids})
    out["resume_language"] = lang

    out["sources"] = [s for s in (out.get("sources") or []) if str(s.get("url") or "").startswith(("http://", "https://"))]
    return out, notes


def save(home: Path, radar: dict, report: Optional[str] = None) -> (Path, List[str]):
    cleaned, notes = validate(radar, jslib.load_fact_bank(home))
    if report:
        cleaned["report"] = report
    cleaned["saved_at"] = jslib.now_iso()
    d = radar_dir(home)
    path = d / ("radar-%s.json" % cleaned["as_of"][:10])
    jslib.write_json(path, cleaned)
    jslib.write_json(d / "latest.json", cleaned)
    return path, notes


# ---------- proposals ----------

def _already_decided(home: Path, text: str) -> bool:
    for p in memory.load_proposals(home).get("proposals", []):
        if memory.norm_text(p.get("text", "")) == memory.norm_text(text):
            return True
    return False


def propose(home: Path) -> List[dict]:
    radar = load_latest(home)
    if not radar:
        raise SystemExit("No radar saved yet. Run /job-search:radar first.")
    prefs = jslib.load_preferences(home)
    have = {jslib.norm_key(t) for t in prefs.get("target_titles") or []}
    made = []
    candidates = [(t["title"], "fits you well today (%s market momentum)" % t.get("momentum", "?"))
                  for t in radar.get("titles_now") or [] if t.get("fit") == "high"]
    candidates += [(t["title"], "is an emerging title that fits you (%s confidence, about %s months out)"
                    % (t.get("confidence", "?"), t.get("horizon_months", "?")))
                   for t in radar.get("emerging_titles") or []
                   if t.get("fit") == "high" and t.get("confidence") in ("high", "medium")]
    seen = set()
    for title, why in candidates:
        key = jslib.norm_key(title)
        if key in have or key in seen:
            continue
        seen.add(key)
        text = "Add \"%s\" to your target titles? The career radar says it %s." % (title, why)
        if _already_decided(home, text):
            continue
        prop, created = memory.add_proposal(
            home, text, "preference",
            patch={"file": "profile/preferences.json", "append": {"target_titles": [title]}},
            evidence=["radar:%s" % radar.get("as_of", "")])
        if created:
            made.append(prop)
    return made + propose_boards(home, radar)


_BOARD_RES = [
    ("greenhouse", re.compile(r"https?://(?:job-boards|boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_app\?for=)?([A-Za-z0-9_-]+)")),
    ("lever", re.compile(r"https?://jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9_.-]+)")),
    ("ashby", re.compile(r"https?://jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)")),
]


def board_tokens(radar: dict) -> List[tuple]:
    """(source, token) pairs for ATS boards linked anywhere in the radar."""
    urls = []

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str) and x.startswith("http"):
            urls.append(x)
    walk(radar)
    found = []
    for u in urls:
        for source, rx in _BOARD_RES:
            m = rx.match(u)
            if m and (source, m.group(1).lower()) not in found:
                found.append((source, m.group(1).lower()))
    return found


def _configured_tokens(sources: dict, source: str) -> set:
    out = set()
    for c in ((sources.get("sources") or {}).get(source) or {}).get("companies") or []:
        tok = c.get("token") if isinstance(c, dict) else c
        if tok:
            out.add(str(tok).lower())
    return out


MAX_BOARD_PROPOSALS = 3


def propose_boards(home: Path, radar: dict) -> List[dict]:
    """Suggest a few new ATS boards, action-plan links first (walk order follows the radar)."""
    sources = jslib.load_sources(home)
    made = []
    for source, token in board_tokens({"actions": radar.get("actions"), "titles_now": radar.get("titles_now"), "rest": radar}):
        if len(made) >= MAX_BOARD_PROPOSALS:
            break
        if token in _configured_tokens(sources, source):
            continue
        text = "Add the %s job board \"%s\" to your daily scan? The career radar found roles that fit you there." % (source.capitalize(), token)
        if _already_decided(home, text):
            continue
        patch = {"file": "profile/sources.json", "append": {"sources.%s.companies" % source: [token]}}
        if not ((sources.get("sources") or {}).get(source) or {}).get("enabled"):
            patch["set"] = {"sources.%s.enabled" % source: True}
        prop, created = memory.add_proposal(home, text, "source", patch=patch,
                                            evidence=["radar:%s" % radar.get("as_of", "")])
        if created:
            made.append(prop)
    return made


# ---------- status ----------

def status(home: Path, today: Optional[str] = None) -> dict:
    prefs = jslib.load_preferences(home)
    every = prefs.get("radar_every_days", DEFAULT_EVERY_DAYS)
    radar = load_latest(home)
    if not radar:
        return {"exists": False, "age_days": None, "every_days": every, "due": bool(every)}
    today_d = datetime.strptime(today or jslib.today(), "%Y-%m-%d")
    age = (today_d - datetime.strptime(radar.get("as_of", jslib.today())[:10], "%Y-%m-%d")).days
    return {"exists": True, "as_of": radar.get("as_of"), "age_days": age, "every_days": every,
            "due": bool(every) and age >= every, "report": radar.get("report")}


# ---------- cli ----------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Career Trend Radar helpers")
    ap.add_argument("--home")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("local-tally")
    p.add_argument("--json", action="store_true")
    p.add_argument("--days", type=int, default=90)
    p = sub.add_parser("save")
    p.add_argument("--file", required=True)
    p.add_argument("--report")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("propose")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("status")
    p.add_argument("--json", action="store_true")
    sub.add_parser("latest")
    args = ap.parse_args(argv)
    home = jslib.require_home(args.home)

    if args.cmd == "local-tally":
        t = local_tally(home, args.days)
        if args.json:
            print(json.dumps(t, indent=2))
        else:
            print("%d scored jobs in the last %d days." % (t["sample"], t["window_days"]))
            for r in t["skill_demand"][:20]:
                print("  %-32s %3d/%d  required %d  you: %s" % (r["skill"][:32], r["count"], r["sample"], r["required"], r["you"]))
        return 0
    if args.cmd == "save":
        radar = jslib.read_json(Path(args.file))
        if not isinstance(radar, dict):
            raise SystemExit("Could not read radar JSON from %s" % args.file)
        path, notes = save(home, radar, args.report)
        if args.json:
            print(json.dumps({"path": str(path), "notes": notes}, indent=2))
        else:
            print("Saved %s" % path)
            for n in notes:
                print("  note: %s" % n)
        return 0
    if args.cmd == "propose":
        made = propose(home)
        if args.json:
            print(json.dumps(made, indent=2))
        else:
            print("%d new proposal(s)." % len(made))
            for p in made:
                print("  %s %s" % (p["id"], p["text"]))
        return 0
    if args.cmd == "status":
        s = status(home)
        if args.json:
            print(json.dumps(s, indent=2))
        elif not s["exists"]:
            print("No radar yet. Due: %s" % ("yes" if s["due"] else "no (radar_every_days is 0)"))
        else:
            print("Latest radar %s, %d days old. Refresh every %s days. Due: %s"
                  % (s["as_of"], s["age_days"], s["every_days"], "yes" if s["due"] else "no"))
        return 0
    if args.cmd == "latest":
        r = load_latest(home)
        print(json.dumps(r, indent=2) if r else "No radar saved yet.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
