#!/usr/bin/env python3
"""Rebuild the skills-gap ledger (gaps.json) from every jobs/*/score.json.

Usage:
  gaps.py [--home H] [--json] [--top N] [--nudge]

Full rebuild every time, so running it twice gives the same result.
See docs/DATA_MODEL.md "gaps.json (derived)".
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402

ALIAS_FILE = Path(os.path.dirname(os.path.abspath(__file__))) / "gap_aliases.json"

RECENT_DAYS = 14
STALE_DAYS = 90
PREF_BOOST = 1.2
# Gaps the career radar (radar/latest.json) marks as rising get a small extra push.
RISING_BOOST = {"high": 1.15, "medium": 1.08, "low": 1.08}

# Words in titles/keywords too generic to say a gap "relates" to the user's goals.
GENERIC_TOKENS = {
    "senior", "staff", "principal", "lead", "engineer", "engineering", "architect",
    "manager", "developer", "and", "the", "of", "for", "with", "in", "to", "a", "an",
    "sr", "jr", "head", "director", "experience", "remote",
}


# ---------- helpers ----------

# Things a job asks for that nobody can learn: keep them out of the skills ledger.
_LOGISTICS_RE = re.compile(
    r"authori[sz]ation|\bvisa\b|sponsorship|citizen|clearance|relocat|\bon-?site\b|in[- ]office|"
    r"\btravel\b|located in|based in|time ?zone|right to work|work permit|residen", re.I)


def is_logistics(item: str) -> bool:
    return bool(_LOGISTICS_RE.search(item or ""))


def load_aliases(path: Optional[Path] = None) -> dict:
    data = jslib.read_json(path or ALIAS_FILE, {}) or {}
    raw = data.get("aliases", {}) or {}
    return {jslib.norm_key(k): jslib.norm_key(v) for k, v in raw.items()}


def canonical_key(item: str, aliases: dict) -> str:
    key = jslib.norm_key(item)
    seen = set()
    while key in aliases and key not in seen:  # follow short chains, never loop
        seen.add(key)
        key = aliases[key]
    return key


def _parse_date(value) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    m = re.match(r"^\d{4}-\d{2}-\d{2}", value)
    return m.group(0) if m else None


def _days_between(a: str, b: str) -> int:
    da = datetime.strptime(a, "%Y-%m-%d")
    db = datetime.strptime(b, "%Y-%m-%d")
    return (db - da).days


def recency_factor(last_seen: Optional[str], today: str) -> float:
    """1.0 if seen in the last 14 days, linear decay to 0.5 at 90 days and beyond."""
    if not last_seen:
        return 0.5
    age = max(0, _days_between(last_seen, today))
    if age <= RECENT_DAYS:
        return 1.0
    if age >= STALE_DAYS:
        return 0.5
    frac = (age - RECENT_DAYS) / float(STALE_DAYS - RECENT_DAYS)
    return round(1.0 - 0.5 * frac, 4)


def _tokens(text: str) -> set:
    return {t for t in jslib.norm_key(text).split("-") if t and t not in GENERIC_TOKENS}


def preference_terms(prefs: dict) -> list:
    terms = []
    for field in ("keywords", "target_titles"):
        for t in prefs.get(field, []) or []:
            if isinstance(t, str) and t.strip():
                terms.append(t)
    return terms


def relates_to_preferences(key: str, name: str, terms: list) -> bool:
    """True when the gap shares a meaningful word with a keyword or target title."""
    gap_tokens = _tokens(key) | _tokens(name)
    if not gap_tokens:
        return False
    for term in terms:
        tkey = jslib.norm_key(term)
        if tkey and (tkey == key or (len(tkey) >= 4 and tkey in key) or (len(key) >= 4 and key in tkey)):
            return True
        if gap_tokens & _tokens(term):
            return True
    return False


# ---------- career radar ----------

_SPLIT_RE = re.compile(r"\s*(?:/|,|\bor\b|\band\b|\(|\))\s*", re.I)


def radar_keys(name: str, aliases: dict) -> list:
    """Canonical keys a radar skill name stands for: the whole name plus each part of
    'Terraform / IaC' or 'GitOps (ArgoCD)'."""
    keys = []
    for i, part in enumerate([name] + _SPLIT_RE.split(name or "")):
        part = (part or "").strip()
        if not part:
            continue
        k = canonical_key(part, aliases)
        if i and len(k) < 2:  # "A/B testing" must not yield a key "a"
            continue
        if k and k != "x" and k not in keys:
            keys.append(k)
    return keys


def load_radar(home: Path) -> Optional[dict]:
    try:
        data = jslib.read_json(Path(home) / "radar" / "latest.json")
    except (ValueError, OSError):
        return None
    return data if isinstance(data, dict) else None


def radar_rising(radar: Optional[dict], aliases: dict) -> dict:
    """key -> {"confidence", "why", "skill", "url"} for every rising skill or radar gap."""
    out = {}
    if not radar:
        return out
    for r in radar.get("rising_skills") or []:
        if not isinstance(r, dict) or not r.get("skill"):
            continue
        conf = r.get("confidence") if r.get("confidence") in RISING_BOOST else "low"
        url = next((s.get("url") for s in r.get("signals") or [] if isinstance(s, dict) and s.get("url")), None)
        info = {"confidence": conf, "why": "rising in the career radar", "skill": r["skill"], "url": url}
        for k in radar_keys(r["skill"], aliases):
            cur = out.get(k)
            if not cur or list(RISING_BOOST).index(conf) < list(RISING_BOOST).index(cur["confidence"]):
                out[k] = info
    for d in radar.get("skill_demand") or []:
        if not isinstance(d, dict) or d.get("you") != "gap" or not d.get("skill"):
            continue
        why = "a gap in %s of %s radar postings" % (d.get("count", "?"), d.get("sample", "?"))
        for k in radar_keys(d["skill"], aliases):
            out.setdefault(k, {"confidence": "medium", "why": why, "skill": d["skill"], "url": None})
    return out


def fact_bank_keys(home: Path, aliases: dict) -> set:
    fb = jslib.load_fact_bank(home)
    keys = set()
    for s in fb.get("skills") or []:
        if isinstance(s, dict) and s.get("name"):
            keys.add(canonical_key(s["name"], aliases))
    for r in fb.get("roles") or []:
        for b in r.get("bullets") or []:
            keys |= {canonical_key(x, aliases) for x in b.get("skills") or []}
    for p in fb.get("projects") or []:
        if isinstance(p, dict):
            keys |= {canonical_key(x, aliases) for x in p.get("skills") or []}
    return keys


def _mentioned(key: str, keys: set) -> bool:
    """Exact key, or a whole-word part of a longer key ("observability" in
    "observability-platforms"). Used before claiming a skill is absent, so it errs on present."""
    if key in keys:
        return True
    if len(key) < 4:
        return False
    k = "-" + key + "-"
    return any(k in "-" + x + "-" for x in keys)


def radar_only(radar: Optional[dict], ledger_keys: set, have: set, aliases: dict) -> list:
    """Rising radar skills that none of the user's scored jobs asked for and the fact bank lacks."""
    out = []
    for r in (radar or {}).get("rising_skills") or []:
        if not isinstance(r, dict) or not r.get("skill"):
            continue
        keys = radar_keys(r["skill"], aliases)
        if any(_mentioned(k, ledger_keys) or _mentioned(k, have) for k in keys):
            continue
        url = next((s.get("url") for s in r.get("signals") or [] if isinstance(s, dict) and s.get("url")), None)
        out.append({"key": keys[0] if keys else jslib.norm_key(r["skill"]), "skill": r["skill"],
                    "confidence": r.get("confidence") or "low", "url": url})
    return out


# ---------- build ----------

def build_gaps(home: Path, today: Optional[str] = None, aliases: Optional[dict] = None) -> dict:
    home = Path(home)
    today = today or jslib.today()
    aliases = load_aliases() if aliases is None else aliases
    prefs = jslib.load_preferences(home)
    terms = preference_terms(prefs)
    radar = load_radar(home)
    rising = radar_rising(radar, aliases)
    notes_raw = jslib.read_json(jslib.profile_path(home, "gap-notes.json"), {}) or {}
    notes = {}
    for k, v in notes_raw.items():
        if k == "schema_version" or not isinstance(v, dict):
            continue
        notes[canonical_key(k, aliases)] = v

    total = 0
    acc = {}  # key -> working dict
    seen_postings = set()  # (company, title): the same role posted in several cities counts once
    jobs_root = jslib.jobs_dir(home)
    dirs = sorted(p for p in jobs_root.iterdir() if p.is_dir()) if jobs_root.exists() else []
    for d in dirs:
        score = jslib.read_json(d / "score.json")
        if not isinstance(score, dict):
            continue
        posting = jslib.posting_key(jslib.read_json(d / "job.json") or {})
        if posting:
            if posting in seen_postings:
                continue
            seen_postings.add(posting)
        total += 1
        job_id = score.get("job_id") or d.name
        seen_date = _parse_date(score.get("scored_at"))
        if not seen_date:
            job = jslib.read_json(d / "job.json") or {}
            seen_date = _parse_date(job.get("found_at"))
        if not seen_date:
            seen_date = datetime.fromtimestamp((d / "score.json").stat().st_mtime, timezone.utc).strftime("%Y-%m-%d")

        per_job = {}  # key -> {"required": bool, "names": [...], "cats": [...]}
        for m in score.get("missing", []) or []:
            if isinstance(m, str):
                m = {"item": m}
            if not isinstance(m, dict):
                continue
            item = str(m.get("item") or "").strip()
            if is_logistics(item):
                continue
            if not item:
                continue
            key = canonical_key(item, aliases)
            slot = per_job.setdefault(key, {"required": False, "names": [], "cats": []})
            slot["required"] = slot["required"] or bool(m.get("required"))
            slot["names"].append(item)
            if m.get("category"):
                slot["cats"].append(str(m["category"]))

        for key, slot in per_job.items():
            a = acc.setdefault(key, {
                "names": Counter(), "cats": Counter(), "job_ids": [], "required": 0,
                "first": None, "last": None, "weekly": Counter(),
            })
            a["names"].update(slot["names"])
            a["cats"].update(slot["cats"])
            a["job_ids"].append(job_id)
            if slot["required"]:
                a["required"] += 1
            a["first"] = seen_date if not a["first"] or seen_date < a["first"] else a["first"]
            a["last"] = seen_date if not a["last"] or seen_date > a["last"] else a["last"]
            a["weekly"][jslib.iso_week(seen_date)] += 1

    items = {}
    ranking = []
    for key in sorted(acc):
        a = acc[key]
        # most common display form; ties go to the alphabetically first for stability
        name = sorted(a["names"].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        cat = sorted(a["cats"].items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if a["cats"] else "other"
        count = len(a["job_ids"])
        note = notes.get(key) or {}
        related = relates_to_preferences(key, name, terms)
        rise = rising.get(key)
        items[key] = {
            "name": name,
            "category": cat,
            "count": count,
            "required_count": a["required"],
            "first_seen": a["first"],
            "last_seen": a["last"],
            "job_ids": sorted(a["job_ids"]),
            "weekly": dict(sorted(a["weekly"].items())),
            "aliases": sorted(a["names"].keys()),
            "related": related,
            "note_status": note.get("status"),
        }
        if rise:
            items[key].update({"rising": True, "rising_confidence": rise["confidence"], "rising_why": rise["why"]})
        if note.get("status") in ("ignore", "done"):
            continue
        share = count / float(total) if total else 0.0
        req_ratio = a["required"] / float(count) if count else 0.0
        rec = recency_factor(a["last"], today)
        score = share * (0.5 + 0.5 * req_ratio) * rec * (PREF_BOOST if related else 1.0)
        if rise:
            score *= RISING_BOOST[rise["confidence"]]
        ranking.append({
            "key": key,
            "score": round(score, 4),
            "share": round(share, 4),
            "required_ratio": round(req_ratio, 4),
            "recency": rec,
            "related": related,
            "rising": bool(rise),
        })
    ranking.sort(key=lambda r: (-r["score"], -items[r["key"]]["count"], r["key"]))

    return {
        "schema_version": jslib.SCHEMA_VERSION,
        "updated_at": jslib.now_iso(),
        "total_jds": total,
        "items": items,
        "ranking": ranking,
        "radar_as_of": (radar or {}).get("as_of"),
        "radar_only_rising": radar_only(radar, set(items), fact_bank_keys(home, aliases), aliases),
    }


def write_gaps(home: Path, data: dict) -> Path:
    path = Path(home) / "gaps.json"
    jslib.write_json(path, data)
    return path


# ---------- output ----------

def format_table(data: dict, top: int) -> str:
    rows = data["ranking"][:top]
    total = data["total_jds"]
    lines = ["Skills gaps from %d scored job descriptions." % total]
    if not rows:
        lines.append("No gaps yet. Score some jobs first (/job-search:run).")
        return "\n".join(lines)
    lines.append("%-3s %-28s %-11s %6s %6s %8s %6s" % ("#", "Gap", "Category", "Jobs", "Share", "Required", "Score"))
    for i, r in enumerate(rows, 1):
        it = data["items"][r["key"]]
        name = it["name"] + (" *" if r["related"] else "") + (" ^" if r.get("rising") else "")
        lines.append("%-3d %-28s %-11s %6d %5.0f%% %7.0f%% %6.2f" % (
            i, name[:28], it["category"][:11], it["count"], r["share"] * 100,
            r["required_ratio"] * 100, r["score"]))
    lines.append("* relates to your target titles or keywords")
    if any(r.get("rising") for r in rows):
        lines.append("^ rising in your career radar")
    extra = data.get("radar_only_rising") or []
    if extra:
        lines.append("Trending but not in your jobs yet: %s" % ", ".join(e["skill"] for e in extra))
    skipped = [k for k, it in data["items"].items() if it.get("note_status") in ("ignore", "done")]
    if skipped:
        lines.append("Not ranked (you marked ignore or done): %s" % ", ".join(sorted(skipped)))
    return "\n".join(lines)


def format_nudge(data: dict, n: int = 3) -> str:
    rows = data["ranking"][:n]
    total = data["total_jds"]
    if not rows:
        return "No skills gaps to report yet. Once a few jobs are scored, this nudge lists the top 3."
    out = ["Top %d skills gaps this week (from %d job descriptions):" % (len(rows), total), ""]
    for i, r in enumerate(rows, 1):
        it = data["items"][r["key"]]
        req = it["required_count"]
        out.append("%d. %s (%s)" % (i, it["name"], it["category"]))
        out.append("   Why it matters: in %d of %d jobs (%.0f%%), required in %d of those." % (
            it["count"], total, r["share"] * 100, req))
        if r["related"]:
            out.append("   It ties in with your target titles or keywords.")
        if it.get("rising"):
            out.append("   Your career radar marks it as rising (%s confidence)." % it.get("rising_confidence"))
        out.append("   Next step: [suggestion: one free course, doc, or weekend project for %s]" % it["name"])
        out.append("   Track it: /job-search:feedback gap %s learning" % r["key"])
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Rebuild the skills-gap ledger from all score.json files.")
    ap.add_argument("--home")
    ap.add_argument("--json", action="store_true", help="print gaps.json content")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--nudge", action="store_true", help="print a short nudge for the top 3 gaps")
    ap.add_argument("--today", help=argparse.SUPPRESS)  # for tests: YYYY-MM-DD
    args = ap.parse_args(argv)

    home = jslib.require_home(args.home)
    data = build_gaps(home, today=args.today)
    write_gaps(home, data)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif args.nudge:
        print(format_nudge(data, 3), end="")
    else:
        print(format_table(data, args.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
