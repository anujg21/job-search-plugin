#!/usr/bin/env python3
"""Find resumes the user edited after tailoring and log one `edit` signal per change.

Usage: detect_edits.py [--json] [--no-render] [--no-pdf] [--home PATH]

For each job whose changes.json has generated_hash: if resume.json now hashes differently,
diff it against jobs/<id>/resume.generated.json and log edits. The logged hash is stored in
changes.json["edits_logged_hash"] so the same edit is never logged twice.

An edited resume.json is also rendered again (resume.html, resume.md and, with Chrome,
resume.pdf), so the files the user attaches match their edit. --no-render skips that.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402
import resume_lib as rl  # noqa: E402


def _short(t: str, n: int = 160) -> str:
    t = " ".join((t or "").split())
    return t if len(t) <= n else t[: n - 3] + "..."


def diff_edits(old: dict, new: dict) -> list:
    """Return [{target, before, after, source_ids}] for every user change."""
    out = []
    if (old.get("headline") or "") != (new.get("headline") or ""):
        out.append({"target": "headline", "before": old.get("headline", ""), "after": new.get("headline", ""), "source_ids": []})
    os_, ns = (old.get("summary") or {}).get("text", ""), (new.get("summary") or {}).get("text", "")
    if " ".join(os_.split()) != " ".join(ns.split()):
        out.append({"target": "summary", "before": os_, "after": ns, "source_ids": list((new.get("summary") or {}).get("source_ids") or [])})

    def bullets(res):
        m = {}
        for i, r in enumerate(res.get("roles", []) or []):
            for j, b in enumerate(r.get("bullets", []) or []):
                key = (r.get("role_id"), tuple(sorted(b.get("source_ids") or [])))
                m[key] = ("roles[%d].bullets[%d]" % (i, j), b.get("text", ""))
        return m

    ob, nb = bullets(old), bullets(new)
    for key, (path, text) in ob.items():
        if key not in nb:
            out.append({"target": path, "before": text, "after": "", "source_ids": list(key[1])})
        elif " ".join(text.split()) != " ".join(nb[key][1].split()):
            out.append({"target": nb[key][0], "before": text, "after": nb[key][1], "source_ids": list(key[1])})
    for key, (path, text) in nb.items():
        if key not in ob:
            out.append({"target": path, "before": "", "after": text, "source_ids": list(key[1])})

    oroles = {r.get("role_id"): r for r in old.get("roles", []) or []}
    for i, r in enumerate(new.get("roles", []) or []):
        o = oroles.get(r.get("role_id"))
        if o and (o.get("title") or "") != (r.get("title") or ""):
            out.append({"target": "roles[%d].title" % i, "before": o.get("title", ""), "after": r.get("title", ""), "source_ids": [r.get("role_id")]})
    osk = [s.get("name") for s in old.get("skills", []) or []]
    nsk = [s.get("name") for s in new.get("skills", []) or []]
    if osk != nsk:
        out.append({"target": "skills", "before": ", ".join(osk), "after": ", ".join(nsk), "source_ids": []})
    return out


def _rerender(home: Path, job_id: str, pdf: bool) -> str:
    try:
        import render_resume  # noqa: WPS433 (local module)
        out = render_resume.render(home, job_id, False, pdf)
        return out.get("pdf") or out.get("html") or ""
    except (SystemExit, Exception) as ex:  # never lose the logged edits over a render problem
        return "render failed: %s" % ex


def detect(home: Path, render: bool = False, pdf: bool = False) -> list:
    results = []
    for job in jslib.iter_jobs(home):
        d = jslib.job_dir(home, job["id"])
        changes = jslib.read_json(d / "changes.json")
        if not changes or not changes.get("generated_hash"):
            continue
        cur = rl.file_hash(d / "resume.json")
        if cur is None or cur == changes["generated_hash"] or cur == changes.get("edits_logged_hash"):
            continue
        old = jslib.read_json(d / "resume.generated.json")
        new = jslib.read_json(d / "resume.json")
        if old is None:
            continue
        edits = diff_edits(old, new)
        for e in edits:
            if e["before"] and e["after"]:
                kind = "changed"
            elif e["after"]:
                kind = "added"
            else:
                kind = "removed"
            detail = '%s %s%s: "%s" -> "%s"' % (
                e["target"], kind, " (%s)" % ", ".join(e["source_ids"]) if e["source_ids"] else "",
                _short(e["before"]), _short(e["after"]))
            jslib.add_signal(home, "edit", skill="tailor", job_id=job["id"], detail=detail,
                             text=e["after"] or None)
        changes["edits_logged_hash"] = cur
        changes["edits_logged_at"] = jslib.now_iso()
        jslib.write_json(d / "changes.json", changes)
        res = {"job_id": job["id"], "edits": edits}
        if render and edits:
            res["rendered"] = _rerender(home, job["id"], pdf)
        results.append(res)
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-render", action="store_true", help="do not re-render edited resumes")
    ap.add_argument("--no-pdf", action="store_true", help="re-render HTML and Markdown only")
    ap.add_argument("--home")
    a = ap.parse_args(argv)
    home = jslib.require_home(a.home)
    res = detect(home, render=not a.no_render, pdf=not a.no_pdf)
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        if not res:
            print("no new resume edits")
        for r in res:
            print("%s: logged %d edit(s)%s" % (r["job_id"], len(r["edits"]),
                                               "; re-rendered %s" % r["rendered"] if r.get("rendered") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
