#!/usr/bin/env python3
"""Approve or reject the tailored resume changes for one job.

Usage: approve.py <job_id> approve|reject [--reason TEXT] [--json] [--home PATH]

approve -> changes.json approval "approved", status `prepared`.
reject  -> approval "rejected", status `scored` so the job can be tailored again.
A resume that failed verify cannot be approved: fix it and re-run verify first.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402


class ApproveError(ValueError):
    pass


def decide(home: Path, job_id: str, action: str, reason: str = "") -> dict:
    if action not in ("approve", "reject"):
        raise ApproveError("action must be approve or reject")
    job = jslib.load_job(home, job_id)
    if job is None:
        raise ApproveError("unknown job id %s" % job_id)
    path = jslib.job_dir(home, job_id) / "changes.json"
    changes = jslib.read_json(path)
    if not changes:
        raise ApproveError("no changes.json for %s; run /job-search:tailor first" % job_id)
    verify = changes.get("verify") or {}
    if action == "approve" and verify and not verify.get("passed", True):
        raise ApproveError("verify failed for %s; fix the block issues and re-run verify_resume.py "
                           "before approving (the approval gate cannot override truthfulness)" % job_id)

    ts = jslib.now_iso()
    changes["approval"] = "approved" if action == "approve" else "rejected"
    changes["decided_at"] = ts
    if reason:
        changes["decision_reason"] = reason
    jslib.write_json(path, changes)
    jslib.update_job(home, job_id, approval=changes["approval"])

    types = sorted({c.get("type", "") for c in changes.get("changes", []) or []})
    detail = "types: %s; reasons: %s" % (", ".join(types) or "none", "; ".join(changes.get("reasons") or []) or "none")
    if action == "approve":
        jslib.set_status(home, job_id, "prepared", note="changes approved" + (": " + reason if reason else ""))
        jslib.add_signal(home, "approve_change", skill="approve", job_id=job_id, detail=detail, text=reason or None)
        status = "prepared"
    else:
        jslib.set_status(home, job_id, "scored",
                         note="changes rejected%s; re-tailor" % (": " + reason if reason else ""))
        jslib.add_signal(home, "reject_change", skill="approve", job_id=job_id, detail=detail, text=reason or None)
        status = "scored"
    return {"job_id": job_id, "approval": changes["approval"], "status": status, "decided_at": ts}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("job_id")
    ap.add_argument("action", choices=["approve", "reject"])
    ap.add_argument("--reason", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--home")
    a = ap.parse_args(argv)
    home = jslib.require_home(a.home)
    try:
        res = decide(home, a.job_id, a.action, a.reason)
    except ApproveError as ex:
        if a.json:
            print(json.dumps({"ok": False, "error": str(ex)}))
        else:
            print("approve: error: %s" % ex, file=sys.stderr)
        return 1
    if a.json:
        res["ok"] = True
        print(json.dumps(res, indent=2))
    else:
        print("%s: %s, status %s" % (res["job_id"], res["approval"], res["status"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
