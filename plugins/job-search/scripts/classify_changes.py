#!/usr/bin/env python3
"""Compare a tailored resume.json to the master resume and apply the minor/major gate.

Usage: classify_changes.py <job_id> [--json] [--home PATH]

Writes jobs/<id>/changes.json (keeps an existing "verify" block if it matches the current
resume, otherwise re-runs verify), saves jobs/<id>/resume.generated.json for edit detection,
and sets the job status to `prepared` (auto-approved minor) or `needs_approval`.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402
import resume_lib as rl  # noqa: E402
import verify_resume  # noqa: E402

SECTIONS = ("summary", "skills", "education", "certifications", "projects")


def _norm(t: str) -> str:
    return " ".join((t or "").split())


def _has_section(resume: dict, key: str) -> bool:
    v = resume.get(key)
    if key == "summary":
        return bool(((v or {}).get("text") or "").strip())
    return bool(v)


def _is_sorted(seq) -> bool:
    return all(a <= b for a, b in zip(seq, seq[1:]))


def diff_resumes(fb: dict, base: dict, tail: dict) -> tuple:
    """Return (changes, before_text, after_text) where the texts pair kept content for the ratio."""
    changes = []
    idx = jslib.fact_index(fb)
    before_parts, after_parts = [], []

    # headline
    if _norm(tail.get("headline")) != _norm(base.get("headline")):
        changes.append({"type": "headline_change", "target": "headline",
                        "before": base.get("headline", ""), "after": tail.get("headline", ""), "source_ids": []})
    before_parts.append(base.get("headline", ""))
    after_parts.append(tail.get("headline", ""))

    # summary
    bs, ts = base.get("summary") or {}, tail.get("summary") or {}
    if _has_section(tail, "summary"):
        before_parts.append(bs.get("text", ""))
        after_parts.append(ts.get("text", ""))
        if _norm(ts.get("text")) != _norm(bs.get("text")):
            changes.append({"type": "summary_change", "target": "summary", "before": bs.get("text", ""),
                            "after": ts.get("text", ""), "source_ids": list(ts.get("source_ids") or [])})

    # skill promotion into the summary
    sum_after, sum_before = ts.get("text", "") or "", bs.get("text", "") or ""
    sum_ids = set(ts.get("source_ids") or [])
    for s in fb.get("skills", []) or []:
        name = s.get("name", "")
        cands = [c for c in (name, s["id"].split(".", 1)[-1]) if c and len(c) > 1]
        in_text = any(rl.term_in_text(c, sum_after) and not rl.term_in_text(c, sum_before) for c in cands)
        if in_text or (s["id"] in sum_ids and s["id"] not in set(bs.get("source_ids") or [])):
            changes.append({"type": "skill_promote", "target": "summary", "before": "", "after": name,
                            "source_ids": [s["id"]], "level": s.get("level", "")})

    # sections added / removed
    for key in SECTIONS:
        hb, ht = _has_section(base, key), _has_section(tail, key)
        if hb and not ht:
            changes.append({"type": "remove_section", "target": key, "before": key, "after": "", "source_ids": []})
        elif ht and not hb:
            changes.append({"type": "add_section", "target": key, "before": "", "after": key, "source_ids": []})

    # roles
    base_roles = {r["role_id"]: (i, r) for i, r in enumerate(base.get("roles", []) or [])}
    tail_role_ids = [r.get("role_id") for r in tail.get("roles", []) or []]
    for rid, (i, r) in base_roles.items():
        if rid not in tail_role_ids:
            changes.append({"type": "remove_section", "target": "roles[%s]" % rid,
                            "before": "%s, %s" % (r.get("title"), r.get("company")), "after": "",
                            "source_ids": [rid]})
    order = [base_roles[x][0] for x in tail_role_ids if x in base_roles]
    if not _is_sorted(order):
        changes.append({"type": "reorder", "target": "roles", "before": ", ".join(base_roles), "after": ", ".join(x for x in tail_role_ids if x), "source_ids": []})

    for ti, tr in enumerate(tail.get("roles", []) or []):
        rid = tr.get("role_id")
        if rid not in base_roles:
            changes.append({"type": "add_section", "target": "roles[%d]" % ti, "before": "",
                            "after": "%s, %s" % (tr.get("title"), tr.get("company")), "source_ids": [rid] if rid else []})
            for b in tr.get("bullets", []) or []:
                after_parts.append(b.get("text", ""))
            continue
        br = base_roles[rid][1]
        if _norm(tr.get("title")) != _norm(br.get("title")):
            changes.append({"type": "title_change", "target": "roles[%d].title" % ti, "before": br.get("title", ""),
                            "after": tr.get("title", ""), "source_ids": [rid]})
        base_bullets = br.get("bullets", []) or []
        pos = {b["source_ids"][0]: k for k, b in enumerate(base_bullets)}
        text_of = {b["source_ids"][0]: b.get("text", "") for b in base_bullets}
        used, order = set(), []
        for bj, b in enumerate(tr.get("bullets", []) or []):
            ids = list(b.get("source_ids") or [])
            bids = [x for x in ids if x in pos]
            used.update(bids)
            if bids:
                order.append(min(pos[x] for x in bids))
            before = " ".join(text_of[x] for x in bids)
            before_parts.append(before)
            after_parts.append(b.get("text", ""))
            if _norm(before) != _norm(b.get("text")):
                ch = {"type": "reword", "target": "roles[%d].bullets[%d]" % (ti, bj), "before": before,
                      "after": b.get("text", ""), "source_ids": ids}
                if len(bids) > 1:
                    ch["note"] = "merged %d bullets" % len(bids)
                changes.append(ch)
        if not _is_sorted(order):
            changes.append({"type": "reorder", "target": "roles[%d].bullets" % ti, "before": "", "after": "",
                            "source_ids": [base_bullets[k]["source_ids"][0] for k in order]})
        for b in base_bullets:
            sid = b["source_ids"][0]
            if sid not in used:
                changes.append({"type": "drop", "target": "roles[%d].bullets" % ti, "before": b.get("text", ""),
                                "after": "", "source_ids": [sid]})

    # skills: drops and reorder
    if _has_section(tail, "skills"):
        bpos = {}
        for k, s in enumerate(base.get("skills", []) or []):
            for x in s.get("source_ids") or []:
                bpos[x] = k
        tpos, kept = [], set()
        for s in tail.get("skills", []) or []:
            ks = [bpos[x] for x in s.get("source_ids") or [] if x in bpos]
            if ks:
                tpos.append(min(ks))
                kept.update(x for x in s.get("source_ids") or [])
        if not _is_sorted(tpos):
            changes.append({"type": "reorder", "target": "skills", "before": "", "after": "", "source_ids": []})
        for s in base.get("skills", []) or []:
            if not any(x in kept for x in s.get("source_ids") or []):
                changes.append({"type": "drop", "target": "skills", "before": s.get("name", ""), "after": "",
                                "source_ids": list(s.get("source_ids") or [])})

    # projects
    base_proj = {p["id"]: p for p in base.get("projects", []) or []}
    for pi, p in enumerate(tail.get("projects", []) or []):
        bp = base_proj.get(p.get("id"))
        before = bp.get("text", "") if bp else ""
        before_parts.append(before)
        after_parts.append(p.get("text", ""))
        if bp and _norm(before) != _norm(p.get("text")):
            changes.append({"type": "reword", "target": "projects[%d]" % pi, "before": before,
                            "after": p.get("text", ""), "source_ids": list(p.get("source_ids") or [p.get("id")])})
    return changes, "\n".join(before_parts), "\n".join(after_parts)


def rewrite_ratio(before: str, after: str) -> float:
    """Share of kept text that was rewritten (word level). Dropping or reordering is not rewriting."""
    a, b = rl.words(before), rl.words(after)
    if not a and not b:
        return 0.0
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return round(1.0 - sm.ratio(), 3)


def classify(fb: dict, prefs: dict, base: dict, tail: dict, verify: dict) -> dict:
    changes, before, after = diff_resumes(fb, base, tail)
    ratio = rewrite_ratio(before, after)
    limit = float(prefs.get("major_rewrite_ratio", 0.30) or 0.30)
    reasons = []
    types = {c["type"] for c in changes}
    if "headline_change" in types:
        reasons.append("headline changed")
    if "title_change" in types:
        reasons.append("job title changed")
    if "add_section" in types:
        reasons.append("section added: " + ", ".join(c["target"] for c in changes if c["type"] == "add_section"))
    if "remove_section" in types:
        reasons.append("section removed: " + ", ".join(c["target"] for c in changes if c["type"] == "remove_section"))
    for c in changes:
        if c["type"] == "skill_promote" and c.get("level") == "familiar":
            reasons.append("lightly used skill %r promoted to summary" % c["after"])
    if ratio > limit:
        reasons.append("rewrote %d%% of the text (limit %d%%)" % (round(ratio * 100), round(limit * 100)))
    if not verify.get("passed"):
        reasons.append("verify failed")
    return {"classification": "major" if reasons else "minor", "reasons": reasons,
            "rewrite_ratio": ratio, "changes": changes}


def classify_job(home: Path, job_id: str) -> dict:
    b = rl.load_job_bundle(home, job_id)
    if b["job"] is None:
        raise SystemExit("Unknown job id: %s" % job_id)
    if b["resume"] is None:
        raise SystemExit("No resume.json for %s. Run /job-search:tailor first." % job_id)
    fb = jslib.load_fact_bank(home)
    prefs = jslib.load_preferences(home)
    resume = b["resume"]
    rhash = rl.canonical_hash(resume)

    existing = b["changes"] or rl.empty_changes(job_id)
    verify = existing.get("verify")
    if not verify or verify.get("resume_hash") not in (None, rhash) or "passed" not in verify:
        verify = verify_resume.verify_resume(fb, resume, b["score"])

    result = classify(fb, prefs, rl.build_master(fb, job_id), resume, verify)
    verify_failed = not verify.get("passed")
    if verify_failed:
        approval, status, note = "pending", "needs_approval", "verify failed"
    elif result["classification"] == "minor" and prefs.get("auto_approve_minor", True):
        approval, status, note = "auto", "prepared", "minor changes auto-approved"
    else:
        approval, status = "pending", "needs_approval"
        note = "; ".join(result["reasons"]) or "minor changes; auto-approve is off"

    out = dict(existing)
    out.update({
        "schema_version": jslib.SCHEMA_VERSION,
        "job_id": job_id,
        "classification": result["classification"],
        "reasons": result["reasons"],
        "rewrite_ratio": result["rewrite_ratio"],
        "changes": result["changes"],
        "verify": verify,
        "approval": approval,
        "decided_at": jslib.now_iso() if approval == "auto" else None,
        "classified_at": jslib.now_iso(),
        "generated_hash": rhash,
        "edits_logged_hash": None,
    })
    jslib.write_json(b["dir"] / "changes.json", out)
    shutil.copyfile(str(b["dir"] / "resume.json"), str(b["dir"] / "resume.generated.json"))
    jslib.update_job(home, job_id, approval=approval)
    jslib.set_status(home, job_id, status, note=note)
    out["status"] = status
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("job_id")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--home")
    a = ap.parse_args(argv)
    home = jslib.require_home(a.home)
    out = classify_job(home, a.job_id)
    if a.json:
        print(json.dumps(out, indent=2))
    else:
        counts = {}
        for c in out["changes"]:
            counts[c["type"]] = counts.get(c["type"], 0) + 1
        print("%s: %s change set, rewrite %d%%, verify %s, approval %s, status %s" % (
            a.job_id, out["classification"], round(out["rewrite_ratio"] * 100),
            "passed" if out["verify"].get("passed") else "FAILED", out["approval"], out["status"]))
        if counts:
            print("  changes: " + ", ".join("%s x%d" % kv for kv in sorted(counts.items())))
        for r in out["reasons"]:
            print("  needs approval: " + r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
