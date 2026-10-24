#!/usr/bin/env python3
"""Scan public ATS job boards (Greenhouse, Lever, Ashby) for new jobs.

Usage:
  scan.py [--home H] [--source NAME ...] [--json] [--dry-run] [--limit-per-company N]
  scan.py --verify [--home H] [--source NAME ...] [--json] [--dry-run]

Companies in profile/sources.json can be plain board tokens ("stripe") or objects
{"token": "stripe", "name": "Stripe"} when the display name differs from the token.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Callable, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402
import sources_lib as sl  # noqa: E402

API_SOURCES = ("greenhouse", "lever", "ashby")
VERIFY_STATUSES = ("found", "scored", "prepared", "needs_approval")

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
GREENHOUSE_LIST_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
LEVER_URL = "https://api.lever.co/v0/postings/{token}?mode=json"
ASHBY_URL = "https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true"
# Dice's public MCP server (the same one behind its Claude connector). No sign-in.
DICE_MCP_URL = "https://mcp.dice.com/mcp"
REMOTE_WORDS = ("remote", "anywhere", "")


def _company_entry(entry) -> Tuple[str, str]:
    """Return (token, display name)."""
    if isinstance(entry, dict):
        token = str(entry.get("token") or entry.get("slug") or entry.get("name") or "").strip()
        name = str(entry.get("name") or "").strip()
    else:
        token, name = str(entry).strip(), ""
    if not name:
        name = re.sub(r"[-_]+", " ", token).title() if token else ""
    return token, name


# ---------- parsers: API payload -> normalized items ----------

def parse_greenhouse(payload: dict, token: str, name: str) -> List[dict]:
    out = []
    for j in (payload or {}).get("jobs", []) or []:
        title = (j.get("title") or "").strip()
        loc = ((j.get("location") or {}).get("name") or "").strip()
        desc = sl.html_to_text(j.get("content") or "")
        company = (j.get("company_name") or "").strip() or name
        offices = ", ".join(o.get("name", "") for o in (j.get("offices") or []) if o.get("name"))
        out.append({
            "source": "greenhouse",
            "source_job_id": str(j.get("id")),
            "company": company,
            "title": title,
            "location": loc,
            "remote": sl.infer_remote(loc, title, offices, description=desc),
            "offices": offices,
            "url": j.get("absolute_url") or "",
            "apply_url": j.get("absolute_url") or "",
            "salary": sl.salary_from_text(desc),
            "posted_at": sl.norm_date(j.get("first_published") or j.get("updated_at")),
            "description": desc,
            "employment": "",
        })
    return out


def parse_lever(payload: list, token: str, name: str) -> List[dict]:
    out = []
    for j in payload or []:
        cats = j.get("categories") or {}
        title = (j.get("text") or "").strip()
        locs = cats.get("allLocations") or ([cats["location"]] if cats.get("location") else [])
        loc = "; ".join(locs)
        parts = [j.get("description") or j.get("descriptionBody") or ""]
        for lst in j.get("lists") or []:
            parts.append("<h3>%s</h3><ul>%s</ul>" % (lst.get("text", ""), lst.get("content", "")))
        if j.get("additional"):
            parts.append(j["additional"])
        desc = sl.html_to_text("\n".join(parts))
        wt = (j.get("workplaceType") or "").lower()
        remote = {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite"}.get(wt) or \
            sl.infer_remote(loc, title, description=desc)
        salary = ""
        sr = j.get("salaryRange") or {}
        if sr.get("min") or sr.get("max"):
            salary = "%s %s - %s %s" % (sr.get("currency", ""), sr.get("min", ""), sr.get("max", ""),
                                        sr.get("interval", ""))
            salary = re.sub(r"\s+", " ", salary).strip()
        out.append({
            "source": "lever",
            "source_job_id": str(j.get("id")),
            "company": name,
            "title": title,
            "location": loc,
            "remote": remote,
            "url": j.get("hostedUrl") or "",
            "apply_url": j.get("applyUrl") or j.get("hostedUrl") or "",
            "salary": salary or sl.salary_from_text(desc),
            "posted_at": sl.norm_date(j.get("createdAt")),
            "description": desc,
            "employment": cats.get("commitment") or "",
        })
    return out


def _ashby_salary(comp: Optional[dict]) -> str:
    if not comp:
        return ""
    s = comp.get("scrapeableCompensationSalarySummary") or comp.get("compensationTierSummary") or ""
    return s.replace("–", "-").replace("•", "|").strip()


def parse_ashby(payload: dict, token: str, name: str) -> List[dict]:
    out = []
    for j in (payload or {}).get("jobs", []) or []:
        if j.get("isListed") is False:
            continue
        title = (j.get("title") or "").strip()
        locs = [j.get("location") or ""]
        for s in j.get("secondaryLocations") or []:
            if isinstance(s, dict) and s.get("location"):
                locs.append(s["location"])
        loc = "; ".join(x for x in locs if x)
        desc = sl.html_to_text(j.get("descriptionHtml") or "") or sl._tidy(j.get("descriptionPlain") or "")
        wt = (j.get("workplaceType") or "").lower()
        # workplaceType wins: Ashby boards often set isRemote on hybrid roles.
        if wt == "remote":
            remote = "remote"
        elif wt == "hybrid":
            remote = "hybrid"
        elif wt == "onsite":
            remote = "onsite"
        elif j.get("isRemote") is True:
            remote = "remote"
        else:
            remote = sl.infer_remote(loc, title, description=desc)
        out.append({
            "source": "ashby",
            "source_job_id": str(j.get("id")),
            "company": name,
            "title": title,
            "location": loc,
            "remote": remote,
            "url": j.get("jobUrl") or "",
            "apply_url": j.get("applyUrl") or j.get("jobUrl") or "",
            "salary": _ashby_salary(j.get("compensation")) or sl.salary_from_text(desc),
            "posted_at": sl.norm_date(j.get("publishedAt")),
            "description": desc,
            "employment": j.get("employmentType") or "",
        })
    return out


def _dice_remote(j: dict) -> str:
    types = [t.lower() for t in j.get("workplaceTypes") or []]
    if j.get("isRemote") or "remote" in types:
        return "remote"
    if "hybrid" in types:
        return "hybrid"
    if "on-site" in types or "onsite" in types:
        return "onsite"
    return "unknown"


def parse_dice(payload: dict) -> List[dict]:
    out = []
    for j in (payload or {}).get("data", []) or []:
        guid = str(j.get("guid") or "").strip()
        if not guid:
            continue
        url = re.sub(r"\?.*$", "", j.get("detailsPageUrl") or "") or \
            "https://www.dice.com/job-detail/%s" % guid
        loc = ((j.get("jobLocation") or {}).get("displayName") or "").strip()
        out.append({
            "source": "dice",
            "source_job_id": guid,
            "company": (j.get("companyName") or "").strip() or "Unknown",
            "title": (j.get("title") or "").strip(),
            "location": loc,
            "remote": _dice_remote(j),
            "url": url,
            "apply_url": url,
            "salary": "" if (j.get("salary") or "").lower() in ("", "depends on experience")
                      else j.get("salary"),
            "posted_at": sl.norm_date(j.get("postedDate")),
            "description": sl._tidy(j.get("summary") or ""),
            "employment": j.get("employmentType") or "",
        })
    return out


def _dice_args(query: dict) -> dict:
    args = {"keyword": query.get("q", ""), "posted_date": "SEVEN", "sort": "datePosted",
            "jobs_per_page": 20}
    loc = (query.get("l") or "").strip()
    if loc.lower() in REMOTE_WORDS:
        args["workplace_types"] = ["Remote"]
    else:
        args["location"] = loc
    return args


def fetch_dice(home, conf: dict, prefs: dict) -> List[dict]:
    """Search Dice for each saved query. Only postings that pass the prefilter and are not
    tracked yet get the full description (one extra call each), up to max_per_run."""
    cap = int(conf.get("max_per_run") or 20)
    seen, keep = set(), []
    for q in conf.get("queries") or []:
        if not q.get("q"):
            continue
        for it in parse_dice(sl.mcp_tool(DICE_MCP_URL, "search_jobs", _dice_args(q))):
            if it["source_job_id"] in seen:
                continue
            seen.add(it["source_job_id"])
            if not sl.prefilter(it, prefs)[0]:
                keep.append(it)  # ingest counts it as filtered
                continue
            job_id = jslib.make_job_id("dice", it["company"], it["source_job_id"])
            if jslib.load_job(home, job_id) is not None or cap <= 0:
                keep.append(it)
                continue
            try:
                d = sl.mcp_tool(DICE_MCP_URL, "get_job_details", {"job_id": it["source_job_id"]})
                text = sl.html_to_text(d.get("description") or "")
                skills = ", ".join(s.get("name", "") for s in d.get("skills") or [] if s.get("name"))
                if text:
                    it["description"] = text + ("\n\nSkills: " + skills if skills else "")
            except sl.FetchError:
                pass  # keep the summary; scoring still works on a shorter text
            cap -= 1
            keep.append(it)
    return keep


PARSERS: Dict[str, Tuple[str, Callable]] = {
    "greenhouse": (GREENHOUSE_URL, parse_greenhouse),
    "lever": (LEVER_URL, parse_lever),
    "ashby": (ASHBY_URL, parse_ashby),
}


def fetch_board(source: str, token: str, name: str) -> List[dict]:
    url_tmpl, parser = PARSERS[source]
    payload = sl.fetch_json(url_tmpl.format(token=token))
    return parser(payload, token, name)


def fetch_board_ids(source: str, token: str) -> set:
    """Light fetch used by --verify: just the set of posting ids on the board."""
    if source == "greenhouse":
        payload = sl.fetch_json(GREENHOUSE_LIST_URL.format(token=token))
        return {str(j.get("id")) for j in payload.get("jobs", []) or []}
    if source == "lever":
        payload = sl.fetch_json(LEVER_URL.format(token=token))
        return {str(j.get("id")) for j in payload or []}
    payload = sl.fetch_json(ASHBY_URL.format(token=token))
    return {str(j.get("id")) for j in payload.get("jobs", []) or [] if j.get("isListed") is not False}


def _record_error(home, result: dict, source: str, token: str, msg: str, dry_run: bool) -> None:
    detail = "%s/%s: %s" % (source, token, msg)
    result["errors"].append(detail)
    if not dry_run:
        jslib.add_signal(home, "source_error", skill="scan", detail=detail)


def selected_sources(cfg: dict, wanted: Optional[List[str]]) -> List[str]:
    srcs = cfg.get("sources", {}) or {}
    names = []
    for s in API_SOURCES:
        conf = srcs.get(s) or {}
        if wanted:
            if s in wanted:
                names.append(s)
        elif conf.get("enabled"):
            names.append(s)
    return names


# ---------- scan ----------

def browser_next(cfg: dict, dice_status: str = "") -> List[dict]:
    """What the agent still has to do after this script, per source. Indeed never needs a
    sign-in, so it always has a route. Dice is fetched here; it only shows up when that failed."""
    srcs = cfg.get("sources", {}) or {}
    out = []
    indeed = srcs.get("indeed") or {}
    if indeed.get("enabled"):
        out.append({"source": "indeed", "guide": "sources/indeed.md",
                    "do": "the Indeed connector's search_jobs tool if it is loaded, else Chrome if "
                          "connected, else the 'Fallback without Chrome' section (WebSearch). "
                          "Run it even when unattended"})
    dice = srcs.get("dice") or {}
    if dice.get("enabled") and dice_status in ("blocked", "failed"):
        out.append({"source": "dice", "guide": "sources/dice.md",
                    "do": "scan.py could not reach Dice; use the Dice connector's search_jobs "
                          "tool if it is loaded, else skip and note 'dice: %s'" % dice_status})
    linkedin = srcs.get("linkedin") or {}
    if linkedin.get("enabled"):
        out.append({"source": "linkedin", "guide": "sources/linkedin.md",
                    "do": ("Chrome if its tools are connected, else skip and note 'linkedin: no browser'"
                           if linkedin.get("has_access") else
                           "skip and note 'linkedin: not signed in, see sources/check-access.md'")})
    return out


def run_scan(home, wanted: Optional[List[str]] = None, dry_run: bool = False,
             limit_per_company: Optional[int] = None) -> dict:
    cfg = jslib.load_sources(home)
    prefs = jslib.load_preferences(home)
    result = sl.new_result()
    tried = blocked = 0
    for source in selected_sources(cfg, wanted):
        conf = (cfg.get("sources", {}) or {}).get(source) or {}
        for entry in conf.get("companies") or []:
            token, name = _company_entry(entry)
            if not token:
                continue
            tried += 1
            try:
                items = fetch_board(source, token, name)
            except sl.FetchError as e:
                blocked += 1 if e.blocked else 0
                _record_error(home, result, source, token, str(e), dry_run)
                continue
            except Exception as e:  # malformed payload, keep going
                _record_error(home, result, source, token, "parse error: %s" % e, dry_run)
                continue
            sl.ingest(home, items, prefs, result, use_filter=True, dry_run=dry_run,
                      limit_per_company=limit_per_company)
    dice = (cfg.get("sources", {}) or {}).get("dice") or {}
    if (("dice" in wanted) if wanted else dice.get("enabled")) and dice.get("queries"):
        tried += 1
        try:
            sl.ingest(home, fetch_dice(home, dice, prefs), prefs, result, use_filter=True,
                      dry_run=dry_run, limit_per_company=limit_per_company)
            result["dice"] = "ok"
        except sl.FetchError as e:
            blocked += 1 if e.blocked else 0
            result["dice"] = "blocked" if e.blocked else "failed"
            _record_error(home, result, "dice", "search", str(e), dry_run)
    if tried and blocked == tried:
        # every board refused the same way: the network, not the tokens
        result["network_blocked"] = True
        result["errors"].insert(0, "network blocked: " + sl.BLOCKED_HINT)
    if not wanted:
        result["browser_next"] = browser_next(cfg, result.get("dice", ""))
    if wanted:
        for w in wanted:
            if w not in API_SOURCES and w != "dice":
                result["errors"].append("%s: not an API source; follow sources/%s.md instead" % (w, w))
    return result


# ---------- verify ----------

def _token_from_url(source: str, url: str) -> Optional[str]:
    url = url or ""
    pats = {
        "lever": r"jobs\.lever\.co/([^/?#]+)",
        "ashby": r"jobs\.ashbyhq\.com/([^/?#]+)",
        "greenhouse": r"(?:job-boards|boards)(?:\.eu)?\.greenhouse\.io/([^/?#]+)",
    }
    m = re.search(pats[source], url)
    return m.group(1) if m else None


def run_verify(home, wanted: Optional[List[str]] = None, dry_run: bool = False) -> dict:
    cfg = jslib.load_sources(home)
    srcs = cfg.get("sources", {}) or {}
    sources = [s for s in API_SOURCES if not wanted or s in wanted]
    result = {"checked": 0, "closed": 0, "closed_ids": [], "unverified": 0, "errors": []}
    jobs = [j for j in jslib.iter_jobs(home)
            if j.get("source") in sources and j.get("status") in VERIFY_STATUSES]
    if not jobs:
        return result

    # board key -> token for configured companies
    boards: Dict[Tuple[str, str], str] = {}
    for s in sources:
        for entry in (srcs.get(s) or {}).get("companies") or []:
            token, name = _company_entry(entry)
            if token:
                boards[(s, jslib.slug(token))] = token
                boards[(s, jslib.slug(name))] = token

    cache: Dict[Tuple[str, str], Optional[set]] = {}
    for job in jobs:
        s = job["source"]
        token = _token_from_url(s, job.get("url", "")) or _token_from_url(s, job.get("apply_url", "")) \
            or boards.get((s, jslib.slug(job.get("company", ""))))
        if not token:
            result["unverified"] += 1
            continue
        key = (s, token)
        if key not in cache:
            try:
                cache[key] = fetch_board_ids(s, token)
            except sl.FetchError as e:
                cache[key] = None
                _record_error(home, result, s, token, "verify: %s" % e, dry_run)
            except Exception as e:
                cache[key] = None
                _record_error(home, result, s, token, "verify parse error: %s" % e, dry_run)
        ids = cache[key]
        if ids is None:
            result["unverified"] += 1
            continue
        result["checked"] += 1
        if str(job.get("source_job_id")) not in ids:
            result["closed"] += 1
            result["closed_ids"].append(job["id"])
            if not dry_run:
                jslib.set_status(home, job["id"], "closed", note="posting no longer on %s board" % s)
    return result


def run_refilter(home: Path, dry_run: bool = False) -> dict:
    """Preferences changed? Skip 'found' jobs that the current filter would no longer let in."""
    prefs = jslib.load_preferences(home)
    res = {"checked": 0, "skipped": []}
    for job in jslib.iter_jobs(home):
        if job.get("status") != "found":
            continue
        res["checked"] += 1
        jd = jslib.job_dir(home, job["id"]) / "jd.md"
        item = {"title": job.get("title", ""), "location": job.get("location", ""),
                "remote": job.get("remote", "unknown"),
                "description": jd.read_text(encoding="utf-8") if jd.exists() else ""}
        ok, why = sl.prefilter(item, prefs)
        if not ok:
            res["skipped"].append([job["id"], why])
            if not dry_run:
                jslib.set_status(home, job["id"], "skipped", note="filtered: %s" % why)
    return res


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--home")
    ap.add_argument("--source", action="append", nargs="+", help="limit to these sources")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="fetch and filter but write nothing")
    ap.add_argument("--limit-per-company", type=int, default=None)
    ap.add_argument("--verify", action="store_true", help="close tracked jobs whose posting is gone")
    ap.add_argument("--refilter", action="store_true",
                    help="re-apply current preferences to jobs still in 'found' and skip the ones that no longer pass")
    args = ap.parse_args(argv)
    home = jslib.require_home(args.home)
    wanted = [s.lower() for grp in (args.source or []) for s in grp] or None

    if args.refilter:
        res = run_refilter(home, dry_run=args.dry_run)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print("refilter: checked %d, skipped %d" % (res["checked"], len(res["skipped"])))
            for jid, why in res["skipped"]:
                print("  skipped: %s (%s)" % (jid, why))
        return 0

    if args.verify:
        res = run_verify(home, wanted, dry_run=args.dry_run)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print("verify: checked %d, closed %d, could not check %d"
                  % (res["checked"], res["closed"], res["unverified"]))
            for jid in res["closed_ids"]:
                print("  closed: %s" % jid)
            for e in res["errors"]:
                print("  error: %s" % e)
        return 0

    res = run_scan(home, wanted, dry_run=args.dry_run, limit_per_company=args.limit_per_company)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        sl.print_summary(res, "scan" + (" (dry run)" if args.dry_run else ""))
        for b in res.get("browser_next") or []:
            print("next: %s: %s (%s)" % (b["source"], b["do"], b["guide"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
