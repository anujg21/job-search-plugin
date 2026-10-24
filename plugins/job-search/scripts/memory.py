#!/usr/bin/env python3
"""Lessons, proposals and signal analysis for the job-search plugin.

Commands:
  memory.py lessons [--json]
  memory.py lesson-add --text T --scope S [--kind auto|approved] [--evidence id,...] [--source retro|feedback|user]
  memory.py lesson-retire <id> [--reason R]
  memory.py lesson-touch <id>
  memory.py render
  memory.py proposal-add --text T --kind K [--patch JSON] [--evidence id,...]
  memory.py proposal-decide <id> accept|decline
  memory.py proposals [--json] [--status S]
  memory.py candidates [--json] [--since DAYS]
  memory.py retire-stale [--days 60]

Every command accepts --home PATH. Schemas: docs/DATA_MODEL.md (memory section).
Lessons and proposals can never weaken the truthfulness rules or the approval gate.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import platform
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402


def _sig_key(sig: dict) -> str:
    """Signals carry a unique id; older ones only have a timestamp."""
    return sig.get("id") or sig.get("ts")


SCOPES = ("all", "scan", "score", "tailor", "apply", "gaps", "dashboard", "feedback", "retro", "run")
LESSON_KINDS = ("auto", "approved")
LESSON_SOURCES = ("retro", "feedback", "user")
PROPOSAL_KINDS = ("preference", "source", "fact_bank", "cap", "maintainer")
PATCHABLE_FILES = ("profile/preferences.json", "profile/sources.json")
# Keys that hold the approval gate. No lesson or proposal may change them.
PROTECTED_KEYS = ("auto_approve_minor", "major_rewrite_ratio")
SIMILAR_TEXT = 0.75
SIMILAR_LESSON = 0.85

# ---------- guardrail ----------

NEGATION = re.compile(r"\b(never|don'?t|do not|does not|doesn'?t|not|no|avoid|stop|refuse|without)\b")

# (regex, negatable, reason). Negatable patterns are fine when a negation word comes
# before them in the same clause ("Never invent metrics" is a good lesson).
WEAKENING_PATTERNS: List[Tuple[str, bool, str]] = [
    (r"\badd(ing)? (any |new |extra |more |missing |unlisted |jd |the )*(skills?|tools?|metrics?|numbers?|titles?|certifications?|certs?|degrees?|employers?|roles?)\b",
     True, "adds facts that are not in the fact bank"),
    (r"\b(invent|fabricat|make up|making up|made up|embellish|exaggerat|inflat|pad the resume|stretch the truth)\w*",
     True, "invents or inflates facts"),
    (r"\b(claim|list|mention)\w* (skills?|tools?|experience) (i|they|the user|you) (don'?t|do not|doesn'?t|does not|lack)",
     False, "claims skills the user does not have"),
    (r"\b(skip|skipping|disable|bypass|turn off|ignore|drop)\w* (the )?(verif\w*|verify step|truth\w*|fact[- ]?bank check|fact check\w*)",
     True, "skips the verify step"),
    (r"\bignore (the )?(fact[- ]?bank|truth\w*|approval\w*|approval gate)\b",
     True, "ignores the truth rules or approval"),
    (r"\bauto[- ]?approv\w* (all|every|major|big|large|headline|title|everything)\b",
     True, "auto-approves major changes"),
    (r"\b(skip|skipping|bypass|disable|remove|turn off)\w* (the )?approval",
     True, "removes the approval gate"),
    (r"\b(don'?t|do not|no need to|stop|never) (ask|asking|wait|waiting|check|checking)( for| me for| with me for)? (my |the user'?s? |user )?(approval|permission|ok|sign[- ]?off|confirmation)",
     False, "stops asking for approval"),
    (r"\bno (more )?(approval|approvals|sign[- ]?off)\b", False, "removes the approval gate"),
    (r"\bwithout (my |the user'?s? )?(approval|asking|permission|verif\w*|checking)", True,
     "acts without approval or verification"),
    (r"\b(auto[- ]?submit|submit\w* (the )?applications?|apply automatically|automatically apply)\b",
     True, "submits applications for the user"),
    (r"\b(round|bump|boost|increase|raise|tweak|adjust|change|alter|nudge|update)\w* (up )?(the |my |all |any |our |user'?s? |resume |key )*(metrics?|numbers?|figures?|percentages?|stats?|statistics?|dates?|team sizes?)\b",
     True, "changes numbers or dates from the fact bank"),
    (r"\bround\w* (\w+ ){0,3}up\b", True, "changes numbers or dates from the fact bank"),
    (r"\b(upgrade|promote|bump|inflate|raise)\w* (the |my |all |user'?s? |job |role )*(titles?|seniority)\b",
     True, "inflates titles or seniority"),
]


def weakening_reason(text: str) -> Optional[str]:
    """Return why a lesson/proposal text weakens a hard rule, or None if it is fine."""
    low = " " + (text or "").lower().replace("\u2019", "'") + " "
    for pattern, negatable, reason in WEAKENING_PATTERNS:
        for m in re.finditer(pattern, low):
            if negatable:
                clause_start = max(low.rfind(sep, 0, m.start()) for sep in (".", ";", "!", "?", "\n", " but "))
                prefix = low[clause_start + 1:m.start()]
                if NEGATION.search(prefix):
                    continue
            return reason
    return None


# ---------- io ----------

def lessons_path(home: Path) -> Path:
    return Path(home) / "memory" / "lessons.json"


def proposals_path(home: Path) -> Path:
    return Path(home) / "memory" / "proposals.json"


def load_lessons(home: Path) -> dict:
    data = jslib.read_json(lessons_path(home), None)
    if not isinstance(data, dict):
        data = {"schema_version": jslib.SCHEMA_VERSION, "lessons": []}
    data.setdefault("lessons", [])
    return data


def save_lessons(home: Path, data: dict) -> None:
    jslib.write_json(lessons_path(home), data)
    render_lessons(home)


def load_proposals(home: Path) -> dict:
    data = jslib.read_json(proposals_path(home), None)
    if not isinstance(data, dict):
        data = {"schema_version": jslib.SCHEMA_VERSION, "proposals": []}
    data.setdefault("proposals", [])
    return data


def save_proposals(home: Path, data: dict) -> None:
    jslib.write_json(proposals_path(home), data)


def next_id(items: List[dict], prefix: str) -> str:
    n = 0
    for it in items:
        m = re.match(r"^%s-(\d+)$" % prefix, str(it.get("id", "")))
        if m:
            n = max(n, int(m.group(1)))
    return "%s-%03d" % (prefix, n + 1)


def _find(items: List[dict], item_id: str) -> dict:
    for it in items:
        if it.get("id") == item_id:
            return it
    raise SystemExit("No item with id %s." % item_id)


def _split_evidence(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(ts[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def norm_text(text: str) -> str:
    t = (text or "").lower().replace("\u2019", "").replace("'", "")
    t = re.sub(r"[^a-z0-9% ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ---------- lessons ----------

LESSONS_HEADER = """# Lessons

These are rules the plugin learned from your feedback. Every skill reads this file first.

How they apply:
1. The truthfulness rules and the approval gate always win. No lesson can add facts, skip the verify step, or skip your approval on major changes.
2. A lesson scoped to a skill beats a lesson scoped to `all` when they disagree.
3. A newer lesson beats an older one on the same topic.
4. Your direct instruction in the current session beats any lesson.

To remove a lesson: `/job-search:feedback lesson <id> retire`.
"""


def render_lessons(home: Path) -> Path:
    data = load_lessons(home)
    active = [l for l in data["lessons"] if l.get("status") == "active"]
    lines = [LESSONS_HEADER.rstrip(), ""]
    if not active:
        lines += ["No active lessons yet.", ""]
    else:
        order = list(SCOPES) + sorted({l.get("scope", "all") for l in active} - set(SCOPES))
        for scope in order:
            group = [l for l in active if l.get("scope", "all") == scope]
            if not group:
                continue
            lines.append("## Scope: %s" % scope)
            lines.append("")
            for l in group:
                n = len(l.get("evidence") or [])
                lines.append("- [%s] %s (since %s, from %d signal%s)" % (
                    l["id"], l["text"], (l.get("created") or "")[:10], n, "" if n == 1 else "s"))
            lines.append("")
    path = Path(home) / "memory" / "lessons.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def add_lesson(home: Path, text: str, scope: str, kind: str = "auto",
               evidence: Optional[List[str]] = None, source: str = "feedback") -> Tuple[dict, bool]:
    """Returns (lesson, created). Merges evidence into a near-identical active lesson."""
    text = (text or "").strip()
    if not text:
        raise SystemExit("Lesson text is empty.")
    if scope not in SCOPES:
        raise SystemExit("Unknown scope %r. Valid: %s" % (scope, ", ".join(SCOPES)))
    if kind not in LESSON_KINDS:
        raise SystemExit("Unknown kind %r. Valid: %s" % (kind, ", ".join(LESSON_KINDS)))
    if source not in LESSON_SOURCES:
        raise SystemExit("Unknown source %r. Valid: %s" % (source, ", ".join(LESSON_SOURCES)))
    reason = weakening_reason(text)
    if reason:
        raise GuardrailError(
            "Refused: this lesson %s. Lessons can never relax the truthfulness rules "
            "or the approval gate." % reason)
    evidence = list(evidence or [])
    data = load_lessons(home)
    for l in data["lessons"]:
        if l.get("status") == "active" and l.get("scope") == scope and \
                difflib.SequenceMatcher(None, norm_text(l["text"]), norm_text(text)).ratio() >= SIMILAR_LESSON:
            ev = l.setdefault("evidence", [])
            for e in evidence:
                if e not in ev:
                    ev.append(e)
            save_lessons(home, data)
            return l, False
    lesson = {
        "id": next_id(data["lessons"], "L"),
        "text": text,
        "scope": scope,
        "kind": kind,
        "status": "active",
        "created": jslib.now_iso(),
        "last_applied": None,
        "evidence": evidence,
        "source": source,
    }
    data["lessons"].append(lesson)
    save_lessons(home, data)
    return lesson, True


def retire_lesson(home: Path, lesson_id: str, reason: str = "") -> dict:
    data = load_lessons(home)
    l = _find(data["lessons"], lesson_id)
    l["status"] = "retired"
    l["retired_at"] = jslib.now_iso()
    l["retired_reason"] = reason or ""
    save_lessons(home, data)
    return l


def touch_lesson(home: Path, lesson_id: str) -> dict:
    data = load_lessons(home)
    l = _find(data["lessons"], lesson_id)
    l["last_applied"] = jslib.now_iso()
    save_lessons(home, data)
    return l


def retire_stale(home: Path, days: int = 60, now: Optional[datetime] = None) -> List[dict]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    data = load_lessons(home)
    retired = []
    for l in data["lessons"]:
        if l.get("status") != "active":
            continue
        ref = _parse_ts(l.get("last_applied")) or _parse_ts(l.get("created"))
        if ref is not None and ref < cutoff:
            l["status"] = "retired"
            l["retired_at"] = jslib.now_iso()
            l["retired_reason"] = "not used for %d days" % days
            retired.append(l)
    if retired:
        save_lessons(home, data)
    else:
        render_lessons(home)
    return retired


class GuardrailError(SystemExit):
    pass


# ---------- proposals ----------

def _validate_patch(patch: dict) -> None:
    if not isinstance(patch, dict):
        raise SystemExit("--patch must be a JSON object.")
    f = patch.get("file")
    if not f:
        raise SystemExit("--patch needs a \"file\" key.")
    for op in ("set", "append"):
        if op in patch and not isinstance(patch[op], dict):
            raise SystemExit("patch.%s must be an object." % op)
        for key in (patch.get(op) or {}):
            if key.split(".")[-1] in PROTECTED_KEYS or key.split(".")[0] in PROTECTED_KEYS:
                raise GuardrailError(
                    "Refused: %s controls the approval gate. Proposals cannot change it." % key)


def add_proposal(home: Path, text: str, kind: str, patch: Optional[dict] = None,
                 evidence: Optional[List[str]] = None) -> Tuple[dict, bool]:
    text = (text or "").strip()
    if not text:
        raise SystemExit("Proposal text is empty.")
    if kind not in PROPOSAL_KINDS:
        raise SystemExit("Unknown kind %r. Valid: %s" % (kind, ", ".join(PROPOSAL_KINDS)))
    reason = weakening_reason(text)
    if reason:
        raise GuardrailError(
            "Refused: this proposal %s. The truthfulness rules and approval gate cannot change." % reason)
    if patch is not None:
        _validate_patch(patch)
    data = load_proposals(home)
    for p in data["proposals"]:
        if p.get("status") == "pending" and norm_text(p.get("text", "")) == norm_text(text):
            return p, False
    prop = {
        "id": next_id(data["proposals"], "P"),
        "text": text,
        "kind": kind,
        "status": "pending",
        "created": jslib.now_iso(),
        "patch": patch,
    }
    if evidence:
        prop["evidence"] = list(evidence)
    data["proposals"].append(prop)
    save_proposals(home, data)
    return prop, True


def _set_path(obj: dict, dotted: str, value) -> None:
    parts = dotted.split(".")
    cur = obj
    for p in parts[:-1]:
        if not isinstance(cur.get(p), dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def _get_path(obj: dict, dotted: str):
    cur = obj
    for p in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def apply_patch(home: Path, patch: dict) -> List[str]:
    """Apply a shallow set/append patch. Keys may be dotted (sources.dice.enabled)."""
    _validate_patch(patch)
    f = patch["file"]
    if f not in PATCHABLE_FILES:
        raise SystemExit("Only %s can be patched automatically, not %s." % (" and ".join(PATCHABLE_FILES), f))
    path = Path(home) / f
    data = jslib.read_json(path, {}) or {}
    changed = []
    for key, value in (patch.get("set") or {}).items():
        if key == "schema_version":
            continue
        _set_path(data, key, value)
        changed.append("%s = %s" % (key, json.dumps(value)))
    for key, value in (patch.get("append") or {}).items():
        cur = _get_path(data, key)
        if cur is None:
            cur = []
        if not isinstance(cur, list):
            raise SystemExit("Cannot append to %s: it is not a list." % key)
        values = value if isinstance(value, list) else [value]
        added = [v for v in values if v not in cur]
        _set_path(data, key, cur + added)
        if added:
            changed.append("%s += %s" % (key, json.dumps(added)))
    data["schema_version"] = data.get("schema_version", jslib.SCHEMA_VERSION)
    jslib.write_json(path, data)
    return changed


def sensitive_terms(home: Path) -> List[str]:
    fb = jslib.load_fact_bank(home)
    terms = []
    person = fb.get("person") or {}
    name = person.get("name") or ""
    if name:
        terms.append(name)
        terms += [p for p in re.split(r"\s+", name) if len(p) > 2]
    for k in ("email", "phone", "location"):
        if person.get(k):
            terms.append(person[k])
    for link in person.get("links") or []:
        if link.get("url"):
            terms.append(link["url"])
    for r in fb.get("roles") or []:
        if r.get("company"):
            terms.append(r["company"])
        if r.get("location"):
            terms.append(r["location"])
    for e in fb.get("education") or []:
        if e.get("school"):
            terms.append(e["school"])
    # longest first so "Northwind Health" is replaced before "Northwind"
    return sorted({t for t in terms if t and len(t) > 2}, key=len, reverse=True)


def anonymize(text: str, home: Path) -> str:
    out = text or ""
    for term in sensitive_terms(home):
        out = re.sub(re.escape(term), "[redacted]", out, flags=re.IGNORECASE)
    out = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", out)
    out = re.sub(r"\+?\d[\d\s().-]{7,}\d", "[phone]", out)
    out = re.sub(r"(/Users/|/home/|C:\\\\Users\\\\)[^/\\\s]+", r"\1[user]", out)
    home_str = str(Path(home))
    out = out.replace(home_str, "<home>")
    return out


def write_maintainer_issue(home: Path, prop: dict) -> Path:
    signals = jslib.read_jsonl(Path(home) / "memory" / "signals.jsonl")
    ev = set(prop.get("evidence") or [])
    related = [s for s in signals if _sig_key(s) in ev]
    body = [
        "## Problem",
        "",
        anonymize(prop.get("text", ""), home),
        "",
        "## Evidence",
        "",
    ]
    if related:
        for s in related[:10]:
            body.append("- %s %s (%s): %s" % (
                s.get("ts", "")[:10], s.get("type"), s.get("skill") or "-",
                anonymize(s.get("detail") or "", home)))
    else:
        body.append("- Seen by the weekly retro. No raw signals attached.")
    body += [
        "",
        "## Environment",
        "",
        "- job-search plugin %s" % jslib.PLUGIN_VERSION,
        "- Python %s on %s" % (platform.python_version(), platform.system()),
        "",
        "This issue was drafted by the job-search plugin and anonymized. Names, emails, "
        "phone numbers and company names from the user's profile were removed.",
        "",
    ]
    title = anonymize(prop.get("text", ""), home).split("\n")[0][:80]
    content = "# %s\n\n%s" % (title, "\n".join(body))
    path = Path(home) / "memory" / ("maintainer-issue-%s.md" % prop["id"])
    path.write_text(content, encoding="utf-8")
    return path


def decide_proposal(home: Path, prop_id: str, decision: str) -> Tuple[dict, List[str]]:
    """Returns (proposal, messages)."""
    if decision not in ("accept", "decline"):
        raise SystemExit("Decision must be accept or decline.")
    data = load_proposals(home)
    prop = _find(data["proposals"], prop_id)
    if prop.get("status") != "pending":
        raise SystemExit("%s was already %s." % (prop_id, prop.get("status")))
    msgs: List[str] = []
    prop["decided_at"] = jslib.now_iso()
    if decision == "decline":
        prop["status"] = "declined"
        msgs.append("Declined %s. It will not be proposed again." % prop_id)
        save_proposals(home, data)
        return prop, msgs

    prop["status"] = "accepted"
    patch = prop.get("patch") or None
    kind = prop.get("kind")
    if kind == "fact_bank" or (patch and patch.get("file") == "profile/fact-bank.json"):
        prop["applied"] = False
        msgs.append("Accepted %s. Fact bank changes are never applied automatically." % prop_id)
        msgs.append("To make this change, run /job-search:onboard, say \"edit my fact bank\", "
                    "and confirm the exact wording: %s" % prop.get("text"))
    elif kind == "maintainer":
        path = write_maintainer_issue(home, prop)
        prop["applied"] = True
        prop["issue_file"] = str(path.relative_to(home))
        msgs.append("Accepted %s. Draft GitHub issue written to %s." % (prop_id, path))
        msgs.append("Read it, then open a new issue on the plugin's GitHub repo and paste it in.")
    elif patch:
        changed = apply_patch(home, patch)
        prop["applied"] = True
        msgs.append("Accepted %s. Updated %s: %s" % (
            prop_id, patch.get("file"), "; ".join(changed) or "no change needed"))
    else:
        prop["applied"] = False
        msgs.append("Accepted %s. It has no automatic patch, so make the change by hand "
                    "or with /job-search:onboard." % prop_id)
    save_proposals(home, data)
    return prop, msgs


# ---------- candidates ----------

STAT_ONLY_TYPES = {"apply", "outcome", "approve_change"}


def _covered_ts(home: Path) -> Tuple[set, Dict[str, List[str]]]:
    covered: set = set()
    by_ts: Dict[str, List[str]] = defaultdict(list)
    for l in load_lessons(home)["lessons"]:
        if l.get("status") == "active":
            for ts in l.get("evidence") or []:
                covered.add(ts)
                by_ts[ts].append(l["id"])
    for p in load_proposals(home)["proposals"]:
        for ts in p.get("evidence") or []:
            covered.add(ts)
            by_ts[ts].append(p["id"])
    return covered, by_ts


def _group_summary(kind: str, sigs: List[dict], key: dict) -> dict:
    texts = []
    for s in sigs:
        t = s.get("text") or ""
        if t and t not in texts:
            texts.append(t)
    types = Counter(s.get("type") for s in sigs)
    frustrated = any(s.get("type") == "frustration" for s in sigs)
    main_type = key.get("type") or types.most_common(1)[0][0]
    skill = key.get("skill") if "skill" in key else Counter(s.get("skill") for s in sigs).most_common(1)[0][0]
    if main_type == "source_error":
        hint = "maintainer proposal (a source keeps failing)"
    elif main_type == "override_score":
        hint = "auto lesson to nudge score weighting; maintainer proposal if it keeps happening"
    elif main_type == "dismiss":
        hint = "auto lesson (skip pattern) or a preference proposal (deal breaker)"
    elif main_type == "reject_change":
        hint = "auto lesson on tailoring style"
    else:
        hint = "auto lesson if it is about wording, tone or filters; otherwise a proposal"
    return {
        "group_by": kind,
        "type": main_type,
        "types": dict(types),
        "skill": skill,
        "detail": key.get("detail") or (sigs[0].get("detail") or ""),
        "count": len(sigs),
        "frustration": frustrated,
        "signal_ts": [_sig_key(s) for s in sigs],
        "job_ids": sorted({s["job_id"] for s in sigs if s.get("job_id")}),
        "texts": texts[:5],
        "first": min(s.get("ts", "") for s in sigs),
        "last": max(s.get("ts", "") for s in sigs),
        "hint": hint,
    }


def _qualifies(sigs: List[dict]) -> bool:
    return len(sigs) >= 2 or any(s.get("type") == "frustration" for s in sigs)


def analyze(home: Path, since_days: Optional[int] = None, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    all_signals = jslib.read_jsonl(Path(home) / "memory" / "signals.jsonl")
    signals = all_signals
    if since_days is not None:
        cutoff = now - timedelta(days=since_days)
        signals = [s for s in signals if (_parse_ts(s.get("ts")) or now) >= cutoff]
    covered, _ = _covered_ts(home)

    # 1. group by (type, skill, normalized detail)
    detail_groups: Dict[Tuple[str, str, str], List[dict]] = defaultdict(list)
    for s in signals:
        if s.get("type") in STAT_ONLY_TYPES:
            continue
        d = norm_text(s.get("detail") or "")
        if not d:
            continue
        detail_groups[(s.get("type") or "", s.get("skill") or "", d)].append(s)

    groups: List[dict] = []
    excluded = 0
    for (typ, skill, d), sigs in detail_groups.items():
        fresh = [s for s in sigs if _sig_key(s) not in covered]
        if not _qualifies(sigs):
            continue
        if not fresh or not _qualifies(fresh) or len(fresh) < len(sigs) and len(fresh) < 2:
            excluded += 1
            continue
        groups.append(_group_summary("detail", fresh, {"type": typ, "skill": skill, "detail": d}))

    # 2. cluster the user's own words by similarity
    with_text = [s for s in signals if norm_text(s.get("text") or "") and s.get("type") not in STAT_ONLY_TYPES]
    clusters: List[List[dict]] = []
    reps: List[str] = []
    for s in with_text:
        t = norm_text(s["text"])
        placed = False
        for i, rep in enumerate(reps):
            if difflib.SequenceMatcher(None, rep, t).ratio() > SIMILAR_TEXT:
                clusters[i].append(s)
                placed = True
                break
        if not placed:
            clusters.append([s])
            reps.append(t)
    detail_sets = [set(g["signal_ts"]) for g in groups]
    for sigs in clusters:
        if not _qualifies(sigs):
            continue
        fresh = [s for s in sigs if _sig_key(s) not in covered]
        if not fresh or not _qualifies(fresh) or len(fresh) < len(sigs) and len(fresh) < 2:
            excluded += 1
            continue
        ts_set = {_sig_key(s) for s in fresh}
        if any(ts_set <= ds for ds in detail_sets):
            continue
        groups.append(_group_summary("text", fresh, {}))

    groups.sort(key=lambda g: (not g["frustration"], -g["count"], g["last"]))
    for i, g in enumerate(groups, 1):
        g["id"] = "G%d" % i

    return {
        "schema_version": jslib.SCHEMA_VERSION,
        "generated_at": jslib.now_iso(),
        "signals_considered": len(signals),
        "groups": groups,
        "groups_excluded_as_covered": excluded,
        "stats": derived_stats(home, signals),
        "rules": [
            "Never write a lesson or proposal that adds facts, skips verify, or skips approval.",
            "Auto lessons: wording, tone, skip patterns, small score weighting nudges.",
            "Proposals: preferences, sources, daily cap, fact bank, maintainer issues.",
            "Pass the group's signal_ts as --evidence so the group is not proposed again.",
        ],
    }


def _job_score(home: Path, job_id: Optional[str], sig: dict) -> Optional[float]:
    if isinstance(sig.get("score"), (int, float)):
        return float(sig["score"])
    if not job_id:
        return None
    job = jslib.load_job(home, job_id)
    if job and isinstance(job.get("score"), (int, float)):
        return float(job["score"])
    return None


def _change_types(sig: dict) -> List[str]:
    """Change types from a signal: approve.py writes 'types: a, b; reasons: ...'."""
    if sig.get("change_type"):
        return [sig["change_type"]]
    d = (sig.get("detail") or "").strip()
    m = re.match(r"^types:\s*([^;]*)", d, flags=re.IGNORECASE)
    if m:
        types = [t.strip() for t in m.group(1).split(",") if t.strip() and t.strip() != "none"]
        return types or ["unknown"]
    first = re.split(r"[\s:;,]+", d, maxsplit=1)[0] if d else ""
    return [first or "unknown"]


def derived_stats(home: Path, signals: List[dict]) -> dict:
    prefs = jslib.load_preferences(home)
    min_score = prefs.get("min_score", 3.5)
    if not isinstance(min_score, (int, float)):
        min_score = 3.5

    dismiss = [s for s in signals if s.get("type") == "dismiss"]
    reasons = Counter(norm_text(s.get("detail") or s.get("text") or "") or "(no reason)" for s in dismiss)

    dismissed_scores = []
    for s in dismiss:
        sc = _job_score(home, s.get("job_id"), s)
        if sc is not None:
            dismissed_scores.append(sc)
    applied_scores = []
    for s in signals:
        if s.get("type") == "apply":
            sc = _job_score(home, s.get("job_id"), s)
            if sc is not None:
                applied_scores.append(sc)

    buckets = Counter()
    for sc in dismissed_scores:
        b = "%.1f-%.1f" % (int(sc * 2) / 2.0, int(sc * 2) / 2.0 + 0.5)
        buckets[b] += 1

    suggestion = None
    total = len(dismissed_scores)
    if total >= 3:
        x = (int(min_score * 2) + 1) / 2.0
        while x <= 4.5:
            under = sum(1 for sc in dismissed_scores if sc < x)
            applied_under = sum(1 for sc in applied_scores if sc < x)
            if under >= 3 and under / float(total) >= 0.6 and applied_under <= 0.2 * under:
                suggestion = {
                    "key": "min_score", "current": min_score, "suggested": x,
                    "dismissed_under": under, "dismissed_total": total, "applied_under": applied_under,
                    "text": "Raise min_score to %.1f? You dismissed %d of %d jobs that scored under %.1f." % (
                        x, under, total, x),
                    "patch": {"file": "profile/preferences.json", "set": {"min_score": x}},
                }
                break
            x += 0.5

    change = defaultdict(lambda: {"approved": 0, "rejected": 0})
    for s in signals:
        if s.get("type") in ("approve_change", "reject_change"):
            for ct in _change_types(s):
                change[ct]["approved" if s["type"] == "approve_change" else "rejected"] += 1
    change_rates = {}
    for ct, c in change.items():
        n = c["approved"] + c["rejected"]
        change_rates[ct] = dict(c, reject_rate=round(c["rejected"] / float(n), 2) if n else 0.0)

    src_err = defaultdict(list)
    for s in signals:
        if s.get("type") == "source_error":
            src = s.get("source") or s.get("skill") or ""
            d = s.get("detail") or ""
            if (not src or src == "scan") and ":" in d:
                src = d.split(":", 1)[0].strip()
            src_err[src or "unknown"].append(d)
    repeated_sources = [
        {"source": k, "count": len(v), "samples": list(dict.fromkeys(v))[:3],
         "hint": "maintainer proposal" if len(v) >= 3 else "watch"}
        for k, v in sorted(src_err.items(), key=lambda kv: -len(kv[1])) if len(v) >= 2
    ]

    overrides = [s for s in signals if s.get("type") == "override_score"]
    return {
        "dismiss_reasons": dict(reasons.most_common()),
        "dismissed_vs_score": {
            "current_min_score": min_score,
            "dismissed_scores": sorted(dismissed_scores),
            "buckets": dict(sorted(buckets.items())),
            "applied_scores": sorted(applied_scores),
            "suggestion": suggestion,
        },
        "change_decisions": change_rates,
        "repeated_source_errors": repeated_sources,
        "override_score_count": len(overrides),
        "override_score_jobs": sorted({s["job_id"] for s in overrides if s.get("job_id")}),
        "frustration_count": sum(1 for s in signals if s.get("type") == "frustration"),
        "repeat_count": sum(1 for s in signals if s.get("type") == "repeat"),
    }


# ---------- cli ----------

def _print_or_json(args, obj, human: str) -> None:
    if getattr(args, "json", False):
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    else:
        print(human)


def cmd_lessons(args) -> int:
    home = jslib.require_home(args.home)
    data = load_lessons(home)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    active = [l for l in data["lessons"] if l.get("status") == "active"]
    if not active:
        print("No active lessons.")
    for l in active:
        print("[%s] (%s, %s) %s" % (l["id"], l.get("scope"), l.get("kind"), l["text"]))
    return 0


def cmd_lesson_add(args) -> int:
    home = jslib.require_home(args.home)
    try:
        lesson, created = add_lesson(home, args.text, args.scope, args.kind,
                                     _split_evidence(args.evidence), args.source)
    except GuardrailError as e:
        print(str(e.code))
        return 2
    if created:
        print("Added %s (%s): %s" % (lesson["id"], lesson["scope"], lesson["text"]))
    else:
        print("Already learned as %s. Added the new evidence to it." % lesson["id"])
    return 0


def cmd_lesson_retire(args) -> int:
    home = jslib.require_home(args.home)
    l = retire_lesson(home, args.id, args.reason or "")
    print("Retired %s: %s" % (l["id"], l["text"]))
    return 0


def cmd_lesson_touch(args) -> int:
    home = jslib.require_home(args.home)
    l = touch_lesson(home, args.id)
    print("%s last applied %s." % (l["id"], l["last_applied"]))
    return 0


def cmd_render(args) -> int:
    home = jslib.require_home(args.home)
    print("Wrote %s" % render_lessons(home))
    return 0


def cmd_proposal_add(args) -> int:
    home = jslib.require_home(args.home)
    patch = None
    if args.patch:
        try:
            patch = json.loads(args.patch)
        except json.JSONDecodeError as e:
            raise SystemExit("--patch is not valid JSON: %s" % e)
    try:
        prop, created = add_proposal(home, args.text, args.kind, patch, _split_evidence(args.evidence))
    except GuardrailError as e:
        print(str(e.code))
        return 2
    print(("Added %s: %s" if created else "Already pending as %s: %s") % (prop["id"], prop["text"]))
    return 0


def cmd_proposal_decide(args) -> int:
    home = jslib.require_home(args.home)
    _, msgs = decide_proposal(home, args.id, args.decision)
    print("\n".join(msgs))
    return 0


def cmd_proposals(args) -> int:
    home = jslib.require_home(args.home)
    data = load_proposals(home)
    items = [p for p in data["proposals"] if not args.status or p.get("status") == args.status]
    if args.json:
        print(json.dumps(items, indent=2, ensure_ascii=False))
        return 0
    if not items:
        print("No proposals.")
    for p in items:
        print("[%s] %s (%s): %s" % (p["id"], p.get("status"), p.get("kind"), p["text"]))
    return 0


def cmd_candidates(args) -> int:
    home = jslib.require_home(args.home)
    res = analyze(home, args.since)
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0
    print("%d signals, %d candidate patterns (%d already covered)." % (
        res["signals_considered"], len(res["groups"]), res["groups_excluded_as_covered"]))
    for g in res["groups"]:
        print("- %s %s/%s x%d%s: %s" % (g["id"], g["type"], g["skill"] or "-", g["count"],
                                         " FRUSTRATED" if g["frustration"] else "",
                                         g["detail"] or (g["texts"][0] if g["texts"] else "")))
    sug = res["stats"]["dismissed_vs_score"]["suggestion"]
    if sug:
        print("Suggestion: %s" % sug["text"])
    for r in res["stats"]["repeated_source_errors"]:
        print("Source %s failed %d times." % (r["source"], r["count"]))
    return 0


def cmd_retire_stale(args) -> int:
    home = jslib.require_home(args.home)
    retired = retire_stale(home, args.days)
    if retired:
        for l in retired:
            print("Retired %s (unused %d days): %s" % (l["id"], args.days, l["text"]))
    else:
        print("No stale lessons.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="memory.py", description="Lessons, proposals and signal analysis.")
    p.add_argument("--home", default=None)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--home", default=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="cmd")
    sub.required = True

    s = sub.add_parser("lessons", parents=[common])
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_lessons)

    s = sub.add_parser("lesson-add", parents=[common])
    s.add_argument("--text", required=True)
    s.add_argument("--scope", required=True, choices=SCOPES)
    s.add_argument("--kind", default="auto", choices=LESSON_KINDS)
    s.add_argument("--evidence", default="")
    s.add_argument("--source", default="feedback", choices=LESSON_SOURCES)
    s.set_defaults(fn=cmd_lesson_add)

    s = sub.add_parser("lesson-retire", parents=[common])
    s.add_argument("id")
    s.add_argument("--reason", default="")
    s.set_defaults(fn=cmd_lesson_retire)

    s = sub.add_parser("lesson-touch", parents=[common])
    s.add_argument("id")
    s.set_defaults(fn=cmd_lesson_touch)

    sub.add_parser("render", parents=[common]).set_defaults(fn=cmd_render)

    s = sub.add_parser("proposal-add", parents=[common])
    s.add_argument("--text", required=True)
    s.add_argument("--kind", required=True, choices=PROPOSAL_KINDS)
    s.add_argument("--patch", default=None, help='e.g. {"file":"profile/preferences.json","set":{"min_score":4.0}}')
    s.add_argument("--evidence", default="")
    s.set_defaults(fn=cmd_proposal_add)

    s = sub.add_parser("proposal-decide", parents=[common])
    s.add_argument("id")
    s.add_argument("decision", choices=("accept", "decline"))
    s.set_defaults(fn=cmd_proposal_decide)

    s = sub.add_parser("proposals", parents=[common])
    s.add_argument("--json", action="store_true")
    s.add_argument("--status", default=None)
    s.set_defaults(fn=cmd_proposals)

    s = sub.add_parser("candidates", parents=[common])
    s.add_argument("--json", action="store_true")
    s.add_argument("--since", type=int, default=None, help="only signals from the last N days")
    s.set_defaults(fn=cmd_candidates)

    s = sub.add_parser("retire-stale", parents=[common])
    s.add_argument("--days", type=int, default=60)
    s.set_defaults(fn=cmd_retire_stale)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
