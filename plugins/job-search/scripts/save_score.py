#!/usr/bin/env python3
"""Validate and save a score.json for one job.

Usage: save_score.py <job_id> [--file score.json | --file - ] [--json] [--home PATH]
Reads stdin when --file is missing or "-".

Drops evidence ids that are not in the fact bank (with a warning), clamps the score to 1-5,
fills the recommendation from preferences.min_score when missing, writes jobs/<id>/score.json,
copies score/recommendation into job.json and sets status `scored` (or `skipped`).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402

RECOMMENDATIONS = ("apply", "maybe", "skip")
CATEGORIES = ("hard_skill", "tool", "cert", "domain", "seniority", "soft_skill", "other")
STRENGTHS = ("strong", "partial")
# Re-scoring a job further along the pipeline must not move it backwards.
RESCORABLE = {None, "found", "scored", "skipped"}


class ScoreError(ValueError):
    pass


def _str_list(v, field: str) -> list:
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ScoreError("%s must be a list of strings" % field)
    return [x.strip() for x in v if x.strip()]


def recommend(score: float, min_score: float) -> str:
    if score >= min_score:
        return "apply"
    if score >= min_score - 0.5:
        return "maybe"
    return "skip"


def validate(raw: dict, job_id: str, fb: dict, prefs: dict) -> tuple:
    """Return (clean score dict, warnings). Raises ScoreError for unusable input."""
    if not isinstance(raw, dict):
        raise ScoreError("score.json must be a JSON object")
    warnings = []
    idx = jslib.fact_index(fb)

    if raw.get("job_id") and raw["job_id"] != job_id:
        raise ScoreError("job_id %r does not match %r" % (raw["job_id"], job_id))
    try:
        score = float(raw.get("score"))
    except (TypeError, ValueError):
        raise ScoreError("score must be a number from 1 to 5")
    if score != score:  # NaN
        raise ScoreError("score must be a number from 1 to 5")
    clamped = round(min(5.0, max(1.0, score)), 1)
    if clamped != round(score, 1):
        warnings.append("score %s clamped to %s" % (score, clamped))

    matched = []
    for i, m in enumerate(raw.get("matched") or []):
        if not isinstance(m, dict) or not str(m.get("requirement", "")).strip():
            raise ScoreError("matched[%d] needs a requirement" % i)
        ev = _str_list(m.get("evidence"), "matched[%d].evidence" % i)
        bad = [x for x in ev if x not in idx]
        for x in bad:
            warnings.append("matched[%d]: dropped unknown evidence id %r" % (i, x))
        ev = [x for x in ev if x in idx]
        if not ev:
            warnings.append("matched[%d] %r dropped: no valid evidence ids" % (i, m["requirement"]))
            continue
        strength = m.get("strength") if m.get("strength") in STRENGTHS else "partial"
        matched.append({"requirement": str(m["requirement"]).strip(), "evidence": ev, "strength": strength})

    missing = []
    for i, m in enumerate(raw.get("missing") or []):
        if isinstance(m, str):
            m = {"item": m}
        if not isinstance(m, dict) or not str(m.get("item", "")).strip():
            raise ScoreError("missing[%d] needs an item" % i)
        cat = m.get("category")
        if cat not in CATEGORIES:
            warnings.append("missing[%d]: category %r set to 'other'" % (i, cat))
            cat = "other"
        missing.append({"item": str(m["item"]).strip(), "category": cat, "required": bool(m.get("required", False))})

    keywords = _str_list(raw.get("keywords"), "keywords")
    deal = _str_list(raw.get("deal_breakers_hit"), "deal_breakers_hit")

    rec = raw.get("recommendation")
    if rec is not None and rec not in RECOMMENDATIONS:
        raise ScoreError("recommendation must be one of %s" % ", ".join(RECOMMENDATIONS))
    if rec is None:
        rec = recommend(clamped, float(prefs.get("min_score", 3.5) or 3.5))
    if deal and rec != "skip":
        warnings.append("deal breaker hit (%s); recommendation set to skip" % ", ".join(deal))
        rec = "skip"

    clean = {
        "schema_version": jslib.SCHEMA_VERSION,
        "job_id": job_id,
        "score": clamped,
        "recommendation": rec,
        "summary": str(raw.get("summary") or "").strip(),
        "matched": matched,
        "missing": missing,
        "keywords": keywords,
        "deal_breakers_hit": deal,
        "scored_at": jslib.now_iso(),
    }
    return clean, warnings


def save(home: Path, job_id: str, raw: dict) -> dict:
    job = jslib.load_job(home, job_id)
    if job is None:
        raise ScoreError("unknown job id %s" % job_id)
    clean, warnings = validate(raw, job_id, jslib.load_fact_bank(home), jslib.load_preferences(home))
    jslib.write_json(jslib.job_dir(home, job_id) / "score.json", clean)
    jslib.update_job(home, job_id, score=clean["score"], recommendation=clean["recommendation"])
    status = job.get("status")
    if status in RESCORABLE:
        skip = clean["recommendation"] == "skip" or bool(clean["deal_breakers_hit"])
        status = "skipped" if skip else "scored"
        note = "score %.1f, %s" % (clean["score"], clean["recommendation"])
        if clean["deal_breakers_hit"]:
            note += "; deal breaker: " + ", ".join(clean["deal_breakers_hit"])
        jslib.set_status(home, job_id, status, note=note)
    else:
        warnings.append("status %r kept; job is past scoring" % status)
    return {"job_id": job_id, "score": clean["score"], "recommendation": clean["recommendation"],
            "status": status, "matched": len(clean["matched"]), "missing": len(clean["missing"]),
            "warnings": warnings}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("job_id")
    ap.add_argument("--file", default="-")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--home")
    a = ap.parse_args(argv)
    home = jslib.require_home(a.home)
    try:
        text = sys.stdin.read() if a.file == "-" else Path(a.file).read_text(encoding="utf-8")
        raw = json.loads(text)
        res = save(home, a.job_id, raw)
    except (ScoreError, json.JSONDecodeError, OSError) as ex:
        if a.json:
            print(json.dumps({"ok": False, "error": str(ex)}))
        else:
            print("save_score: error: %s" % ex, file=sys.stderr)
        return 1
    if a.json:
        res["ok"] = True
        print(json.dumps(res, indent=2))
    else:
        print("%s: score %.1f, %s, status %s (%d matched, %d missing)" % (
            res["job_id"], res["score"], res["recommendation"], res["status"], res["matched"], res["missing"]))
        for w in res["warnings"]:
            print("  warning: " + w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
