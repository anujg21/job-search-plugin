#!/usr/bin/env python3
"""Add jobs that Claude extracted from a browser source (indeed, dice, linkedin) or a pasted JD.

Usage:
  add_job.py [--home H] [--file jobs.json | < jobs.json] [--no-filter] [--dry-run] [--json]

Input is a JSON list (or a single object) of:
  {source, source_job_id, company, title, location, url, apply_url, salary, posted_at, description}
Optional: remote (remote|hybrid|onsite|unknown), employment (e.g. "Contract", "Full-time").
`description` may be plain text or HTML. If `source_job_id` is missing a stable id is derived
from the url (or company + title when there is no url).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402
import sources_lib as sl  # noqa: E402

KNOWN_SOURCES = {"greenhouse", "lever", "ashby", "indeed", "dice", "linkedin", "manual"}
REMOTE_VALUES = {"remote", "hybrid", "onsite", "unknown"}


def normalize(raw: dict) -> dict:
    """Validate and normalize one input object. Raises ValueError with a short reason."""
    if not isinstance(raw, dict):
        raise ValueError("entry is not an object")
    title = str(raw.get("title") or "").strip()
    company = str(raw.get("company") or "").strip()
    if not title or not company:
        raise ValueError("missing title or company")
    source = str(raw.get("source") or "manual").strip().lower()
    if source not in KNOWN_SOURCES:
        source = jslib.slug(source, 12)
    url = str(raw.get("url") or "").strip()
    sid = str(raw.get("source_job_id") or "").strip()
    if not sid:
        sid = sl.stable_id_from(url) if url else sl.stable_id_from(company, title)
    desc_raw = str(raw.get("description") or "")
    desc = sl.html_to_text(desc_raw) if sl.looks_like_html(desc_raw) else sl._tidy(desc_raw) if desc_raw else ""
    location = str(raw.get("location") or "").strip()
    remote = str(raw.get("remote") or "").strip().lower()
    if remote in ("on-site", "on site", "in office"):
        remote = "onsite"
    if remote not in REMOTE_VALUES or remote == "unknown":
        remote = sl.infer_remote(location, title, description=desc)
    salary = str(raw.get("salary") or "").strip() or sl.salary_from_text(desc)
    return {
        "source": source,
        "source_job_id": sid,
        "company": company,
        "title": title,
        "location": location,
        "remote": remote,
        "url": url,
        "apply_url": str(raw.get("apply_url") or "").strip() or url,
        "salary": salary,
        "posted_at": sl.norm_date(raw.get("posted_at")),
        "description": desc,
        "employment": str(raw.get("employment") or "").strip(),
    }


def run_add(home, data, use_filter: bool = True, dry_run: bool = False) -> dict:
    if isinstance(data, dict):
        data = data.get("jobs") if isinstance(data.get("jobs"), list) else [data]
    result = sl.new_result()
    items: List[dict] = []
    for i, raw in enumerate(data or []):
        try:
            items.append(normalize(raw))
        except ValueError as e:
            result["fetched"] += 1
            label = (raw.get("url") or raw.get("title") or "#%d" % i) if isinstance(raw, dict) else "#%d" % i
            result["errors"].append("entry %s: %s" % (label, e))
    prefs = jslib.load_preferences(home)
    sl.ingest(home, items, prefs, result, use_filter=use_filter, dry_run=dry_run)
    return result


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--home")
    ap.add_argument("--file", help="JSON file; reads stdin when omitted")
    ap.add_argument("--no-filter", action="store_true", help="skip the title/location/deal-breaker prefilter")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    home = jslib.require_home(args.home)
    try:
        if args.file:
            with open(args.file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.load(sys.stdin)
    except (OSError, ValueError) as e:
        print("add_job: could not read input JSON: %s" % e, file=sys.stderr)
        return 2
    res = run_add(home, data, use_filter=not args.no_filter, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        sl.print_summary(res, "add_job" + (" (dry run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
