#!/usr/bin/env python3
"""Check a tailored resume.json against the fact bank.

Usage: verify_resume.py <job_id> [--json] [--home PATH]

Block issues (exit 1): unknown or missing source ids; numbers not in the cited facts
(including "a third", "doubled", "5K+", "over 220", "two decades", a rate change such as
per month -> per day, one end of a "6 to 12" range, and vague magnitudes like "dozens");
skill-year claims that differ from the fact bank; wrong company/dates/title; headline not
allowed; seniority titles the person never held; verbs stronger than the cited facts
("led" from "mentored"); scope words (company-wide, global) and industries not in the
cited facts; unbacked skills; tech terms not in the cited facts (the "stuffed JD keyword"
check); certifications claimed in text; lines that share almost no words with the facts
they cite.
Warn issues never block: unknown proper nouns (customers, companies, products), outcome
phrases ("resulting in"), "owned" from a built-level fact, low word overlap, posting
phrases, padding.
Results are written to jobs/<id>/changes.json["verify"].
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402
import resume_lib as rl  # noqa: E402

SENIORITY_WORDS = ["principal", "head of", "director", "vice president", "vp", "svp", "evp", "chief",
                   "distinguished", "cto", "cio", "engineering manager"]
# Ordinary words in lower case ("staff", "fellow engineers"); a title claim only when capitalized.
SENIORITY_CAPS = ["Staff", "Fellow"]
LENGTH_WARN_RATIO = 1.6

# Scope claims that need the cited facts to say the same thing.
SCOPE_RE = re.compile(
    r"\b(?:company[- ]?wide|org[- ]wide|organi[sz]ation[- ]wide|enterprise[- ]wide|firm[- ]wide|"
    r"department[- ]wide|globally|global|worldwide|world[- ]wide|industry[- ]wide|industry[- ]leading|"
    r"across (?:the|all|every) (?:company|organi[sz]ation|org|enterprise|business|engineering|teams?|"
    r"business units?|product lines?)|every team|all teams|all of engineering|"
    r"entire (?:company|organi[sz]ation|engineering|org))\b", re.I)
# Industry / domain claim -> stems that must appear in the cited facts or the role's company.
INDUSTRIES = {
    "fintech": ["fintech", "financial technology"], "financial services": ["financ", "bank"],
    "banking": ["bank"], "payments": ["payment"], "insurance": ["insur"], "insurtech": ["insurtech"],
    "healthcare": ["health"], "health care": ["health"], "healthtech": ["healthtech"],
    "medical": ["medic", "health"], "pharma": ["pharma"], "pharmaceutical": ["pharma"],
    "biotech": ["biotech"], "life sciences": ["life science"],
    "e-commerce": ["e-commerce", "ecommerce"], "ecommerce": ["e-commerce", "ecommerce"], "retail": ["retail"],
    "government": ["government", "public sector"], "public sector": ["public sector", "government"],
    "defense": ["defense", "defence"], "aerospace": ["aerospace"], "gaming": ["gaming", "game"],
    "adtech": ["adtech", "advertis"], "advertising": ["advertis"], "crypto": ["crypto", "blockchain"],
    "blockchain": ["blockchain", "crypto"], "web3": ["web3"], "telecom": ["telecom"],
    "automotive": ["automotive"], "logistics": ["logistic"], "edtech": ["edtech"], "proptech": ["proptech"],
    "energy": ["energy"], "fortune 500": ["fortune 500"], "fortune 100": ["fortune 100"],
}
INDUSTRY_RE = re.compile(r"\b(%s)\b" % "|".join(re.escape(k) for k in sorted(INDUSTRIES, key=len, reverse=True)), re.I)
OUTCOME_RE = re.compile(r"\b(?:resulting in|resulted in|which led to|leading to|driving|enabling|"
                        r"which (?:saved|reduced|improved|increased)|contributing to)\b", re.I)
CERT_RE = re.compile(r"\bcertifi(?:ed|cation|cate)s?\b", re.I)
YEARS_OF_RE = re.compile(
    r"(?P<n>\d+)(?P<plus>\+)?\s+years?\s+(?:of\s+(?:hands-on\s+)?(?:experience\s+(?:with|in|using)\s+)?|"
    r"with\s+|in\s+|using\s+|working with\s+)(?P<what>[A-Za-z][\w.+#/-]*(?:\s+[A-Za-z][\w.+#/-]*){0,2})", re.I)
STOP = set("""a an the and or of to in on for with by at from as into onto over under via per that which who
this these those its their our his her my your is are was were be been being has have had it they them
than then so such also more most new each every all any up out off about across within while using used
use uses whom whose not no""".split())
OVERLAP_WARN = 0.4      # below this share of words found in the cited facts: warn
OVERLAP_OTHER = 0.5     # ...and block when an uncited fact covers at least this much
# Capitalized tokens too generic to be a named entity.
COMMON_CAPS = {"api", "apis", "cli", "sdk", "ui", "ux", "vm", "vms", "ci", "cd", "iac", "sre", "llm", "llms",
               "ai", "ml", "it", "qa", "devops", "devsecops", "saas", "paas", "iaas", "slo", "slos", "sla",
               "slas", "oss", "us", "usa", "eu", "uk"}


def _issue(issues: list, severity: str, path: str, message: str) -> None:
    issues.append({"severity": severity, "path": path, "message": message})


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _number_pool(ids: List[str], idx: dict, fb: dict, role_id: Optional[str]) -> List[dict]:
    pool = []
    for i in ids:
        f = idx.get(i)
        if not f:
            continue
        pool.extend(rl.extract_numbers(f.get("text", "") or ""))
        for m in f.get("metrics", []) or []:
            pool.extend(rl.extract_numbers(str(m)))
        if f.get("years") not in (None, ""):
            pool.append({"raw": str(f["years"]), "value": round(float(f["years"]), 6), "kind": "plain", "unit": "year"})
        if f.get("year"):
            pool.extend(rl.extract_numbers(str(f["year"])))
    if role_id and role_id in idx:
        r = idx[role_id]
        for k in ("start", "end"):
            pool.extend(rl.extract_numbers(str(r.get(k, ""))[:4]))
    # metrics lists ("5,000") lose the rate the text gives ("5,000 tickets per month")
    rates = {(n["value"], n["kind"]): n["rate"] for n in pool if n.get("rate")}
    for n in pool:
        if not n.get("rate") and (n["value"], n["kind"]) in rates:
            n["rate"] = rates[(n["value"], n["kind"])]
    return pool


def _check_ranges(issues: list, path: str, text: str, known: List[str], idx: dict) -> None:
    """A fact that says "6 to 12" may not become "12" (or "6") on its own."""
    src_ranges, src_singles = [], []
    for x in known:
        t = idx[x].get("text", "") or ""
        rs = rl.number_ranges(t)
        src_ranges.extend(rs)
        in_range = {v for r in rs for v in r}
        src_singles.extend(n["value"] for n in rl.extract_numbers(t) if n["value"] not in in_range)
    if not src_ranges:
        return
    nums = rl.extract_numbers(text)
    vals = {n["value"] for n in nums}
    for lo, hi in src_ranges:
        for n in nums:
            v = n["value"]
            if v not in (lo, hi) or v in src_singles:
                continue
            if (lo if v == hi else hi) in vals:
                continue
            pos = text.find(n["raw"])
            before = text[:pos] if pos >= 0 else ""
            if v == hi and re.search(r"\bup to\s*$", before, re.I):
                continue
            if v == lo and (n.get("lower") or re.search(r"\b(?:at least|from)\s*$", before, re.I)):
                continue
            _issue(issues, "block", path, "uses %r from the range %g to %g; keep the whole range" % (n["raw"], lo, hi))


def _check_seniority(issues: list, path: str, text: str, title_blob: str) -> None:
    """title_blob: allowed titles plus the cited facts' own text."""
    for w in SENIORITY_WORDS:
        pat = re.compile(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", re.I)
        if pat.search(text) and not pat.search(title_blob):
            _issue(issues, "block", path, "claims seniority %r that is not in any title the fact bank allows" % w)
    for w in SENIORITY_CAPS:
        if re.search(r"(?<![A-Za-z])" + w + r"(?![A-Za-z])", text) and w.lower() not in title_blob:
            _issue(issues, "block", path, "claims seniority %r that is not in any title the fact bank allows" % w.lower())


def _check_verbs(issues: list, path: str, text: str, known: List[str], idx: dict, extra: str) -> None:
    """Block a verb higher on the ownership ladder than any cited fact supports."""
    used = rl.ladder_verbs(text)
    if not used:
        return
    src = max(rl.verb_level(idx[x].get("text") or "", rl.DEFAULT_VERB_LEVEL) for x in known)
    if extra:
        src = max(src, rl.verb_level(extra, 0))
    lvl, word = max(used, key=lambda v: v[0])
    if lvl <= src:
        return
    src_word = rl.LADDER_NAMES[src]
    if lvl == 5 and src >= rl.DEFAULT_VERB_LEVEL:
        # "Owned the design of X" from "Designed X" is a common, defensible rewording.
        _issue(issues, "warn", path, "%r is stronger than the cited facts (%s level); check the person owned this"
               % (word, src_word))
        return
    _issue(issues, "block", path, "verb %r claims more ownership than the cited facts (%s level at most: %s)"
           % (word, src_word, ", ".join(known)))


def _unknown_names(text: str, vocab_blob: str, term_set: set) -> List[str]:
    """Capitalized words (not starting a sentence) that never appear in the allowed text."""
    vocab = set(re.findall(r"[a-z0-9]+", vocab_blob.lower()))
    out, cur = [], []
    for sent in re.split(r"(?<=[.!?;:])\s+", text or ""):
        toks = re.findall(r"[A-Za-z][\w&.+#/'-]*", sent)
        for i, tok in enumerate(toks):
            tok = tok.rstrip(".'-")
            unknown = False
            if i > 0 and tok[:1].isupper() and len(tok) > 1:
                pieces = re.findall(r"[a-z0-9]+", tok.lower())
                unknown = (not all(p in vocab or p in COMMON_CAPS for p in pieces)
                           and tok.lower() not in term_set)
            if unknown:
                cur.append(tok)
            elif cur:
                out.append(" ".join(cur))
                cur = []
        if cur:
            out.append(" ".join(cur))
            cur = []
    return out


def _overlap(text: str, blob: str):
    """Share of content words in text whose 5-letter stem appears in the cited facts."""
    toks = [t for t in re.findall(r"[a-z][a-z0-9+#]*", (text or "").lower())
            if len(t) >= 3 and t not in STOP and not rl.ladder_verbs(t)]
    if not toks:
        return 1.0, 0
    have = {t[:5] for t in re.findall(r"[a-z][a-z0-9+#]*", blob.lower())}
    hit = sum(1 for t in toks if t[:5] in have)
    return hit / len(toks), len(toks)


def _better_fact(text: str, known: List[str], idx: dict, cov: float):
    """An uncited bullet/project/summary fact that matches the line much better, as (id, overlap)."""
    best = None
    for fid, f in idx.items():
        if fid in known or not f.get("text") or "bullets" in f:
            continue
        c, _ = _overlap(text, rl.source_blob([fid], idx))
        if c >= OVERLAP_OTHER and c >= cov + 0.3 and (best is None or c > best[1]):
            best = (fid, c)
    return best


def verify_resume(fb: dict, resume: dict, score: Optional[dict] = None) -> dict:
    idx = jslib.fact_index(fb)
    owner = rl.bullet_owner(fb)
    roles_by_id = {r["id"]: r for r in fb.get("roles", []) or []}
    terms = rl.build_term_list(fb, score)
    term_set = set(terms)
    jd_phrases = sorted({k.strip().lower() for k in (score or {}).get("keywords", []) or []
                         if k.strip() and k.strip().lower() not in term_set and k.strip().lower() not in rl.GENERIC})
    issues: list = []

    # Allowed titles
    allowed_titles = set(h.strip().lower() for h in fb.get("headlines", []) or [])
    for r in fb.get("roles", []) or []:
        allowed_titles.add((r.get("title") or "").strip().lower())
        for a in r.get("title_aliases", []) or []:
            allowed_titles.add(a.strip().lower())
    title_blob = " | ".join(sorted(allowed_titles))

    headline = (resume.get("headline") or "").strip()
    if headline and headline.lower() not in allowed_titles:
        _issue(issues, "block", "headline",
               "headline %r is not a fact-bank headline or role title/alias" % headline)

    # Roles
    for i, r in enumerate(resume.get("roles", []) or []):
        p = "roles[%d]" % i
        rid = r.get("role_id")
        fr = roles_by_id.get(rid)
        if not fr:
            _issue(issues, "block", p, "unknown role_id %r" % rid)
            continue
        for k in ("company", "start", "end"):
            if (r.get(k) or "") != (fr.get(k) or ""):
                _issue(issues, "block", "%s.%s" % (p, k),
                       "%s %r does not match fact bank %r" % (k, r.get(k), fr.get(k)))
        allowed = [fr.get("title", "")] + list(fr.get("title_aliases", []) or [])
        if (r.get("title") or "") not in allowed:
            _issue(issues, "block", p + ".title",
                   "title %r is not %s" % (r.get("title"), " or ".join(repr(a) for a in allowed)))
        if r.get("location") and fr.get("location") and r.get("location") != fr.get("location"):
            _issue(issues, "warn", p + ".location",
                   "location %r differs from fact bank %r" % (r.get("location"), fr.get("location")))

    role_company = {r["id"]: (r.get("company") or "") for r in fb.get("roles", []) or []}
    all_companies = " | ".join(role_company.values()).lower()
    skill_years = {}
    for sk in fb.get("skills", []) or []:
        if sk.get("years") not in (None, ""):
            skill_years[_norm(sk.get("name", ""))] = (sk.get("name", ""), float(sk["years"]))

    # Text lines: summary, bullets, projects
    for path, text, ids, role_id in rl.iter_lines(resume):
        if not ids:
            _issue(issues, "block", path, "no source_ids; every line must cite fact-bank ids")
            continue
        unknown = [x for x in ids if x not in idx]
        for x in unknown:
            _issue(issues, "block", path, "unknown source id %r" % x)
        known = [x for x in ids if x in idx]
        if role_id:
            for x in known:
                if x in owner and owner[x] != role_id:
                    _issue(issues, "block", path,
                           "cites %s which belongs to role %s, not %s" % (x, owner[x], role_id))
        if not known:
            continue
        cited = ", ".join(known)

        blob = rl.source_blob(known, idx)
        if path == "summary":
            blob += " | " + title_blob
        company_ctx = all_companies if path == "summary" else role_company.get(role_id or "", "").lower()
        ctx_blob = blob + " | " + company_ctx

        # Numbers
        pool = _number_pool(known, idx, fb, role_id)
        for n in rl.extract_numbers(text):
            if not rl.number_supported(n, pool):
                if n.get("lower"):
                    why = "claims more than the cited facts say"
                elif n.get("rate"):
                    why = "is not in the cited facts at that rate (per %s)" % n["rate"]
                else:
                    why = "is not in the cited facts"
                _issue(issues, "block", path, "number %r %s (%s); keep numbers exactly as the fact states them"
                       % (n["raw"], why, cited))
        for v in rl.vague_quantities(text):
            if v.lower() not in blob:
                _issue(issues, "block", path,
                       "vague quantity %r stands in for a number; use the exact number from %s" % (v, cited))
        _check_ranges(issues, path, text, known, idx)
        for m in YEARS_OF_RE.finditer(text):
            if m.group(0).lower() in blob:
                continue
            n = float(m.group("n"))
            what = m.group("what").rstrip(".,;:").split()
            for k in range(len(what), 0, -1):
                hit = skill_years.get(_norm(" ".join(what[:k])))
                if hit:
                    name, yrs = hit
                    ok = (n < yrs) if m.group("plus") else (n == yrs)
                    if not ok:
                        _issue(issues, "block", path, "claims %s years of %s; the fact bank says %g"
                               % (m.group("n") + (m.group("plus") or ""), name, yrs))
                    break

        # Tech terms, certifications, posting phrases
        for t in terms:
            if rl.term_in_text(t, text) and not rl.term_supported(t, blob):
                _issue(issues, "block", path,
                       "term %r is not in the cited facts (%s); put it in score.json missing, not the resume" % (t, cited))
        if CERT_RE.search(text) and not CERT_RE.search(blob):
            _issue(issues, "block", path, "mentions a certification but no cited fact is one (%s)" % cited)
        for k in jd_phrases:
            if rl.term_in_text(k, text) and not rl.term_supported(k, blob):
                _issue(issues, "warn", path,
                       "posting phrase %r is not in the cited facts; keep it only if the facts really say this" % k)

        # Scope, industry, seniority, verbs
        for m in SCOPE_RE.finditer(text):
            if m.group(0).lower() not in blob:
                _issue(issues, "block", path, "scope claim %r is not in the cited facts (%s)" % (m.group(0), cited))
        for m in INDUSTRY_RE.finditer(text):
            if not any(st in ctx_blob for st in INDUSTRIES[m.group(1).lower()]):
                _issue(issues, "block", path, "industry claim %r is not in the cited facts or the company name (%s)"
                       % (m.group(1), cited))
        _check_seniority(issues, path, text, title_blob + " | " + blob)
        _check_verbs(issues, path, text, known, idx, title_blob if path == "summary" else "")

        # Warnings: outcomes, names, overlap, padding
        for m in OUTCOME_RE.finditer(text):
            if m.group(0).lower() not in blob:
                _issue(issues, "warn", path,
                       "outcome phrase %r: check the cited facts state this result (%s)" % (m.group(0), cited))
        for nm in _unknown_names(text, ctx_blob + " | " + title_blob, term_set):
            _issue(issues, "warn", path, "name %r is not in the cited facts; make sure it is not an invented "
                   "company, customer, product or team (%s)" % (nm, cited))
        if path != "summary":
            cov, n_words = _overlap(text, blob)
            if n_words >= 5 and cov < OVERLAP_WARN:
                better = _better_fact(text, known, idx, cov)
                if better:
                    _issue(issues, "block", path, "line reads like %s (%d%% word overlap) but cites %s (%d%%); "
                           "cite the fact it describes or rewrite it" % (better[0], round(better[1] * 100), cited, round(cov * 100)))
                else:
                    _issue(issues, "warn", path, "low word overlap with the cited facts (%d%%, %s); check it describes them"
                           % (round(cov * 100), cited))

        src_len = sum(len((idx[x].get("text") or "")) for x in known)
        if path.startswith("roles") and src_len and len(text) > LENGTH_WARN_RATIO * src_len:
            _issue(issues, "warn", path, "bullet is %.1fx longer than its sources; check for padding" % (len(text) / src_len))

    # Skills section
    for i, s in enumerate(resume.get("skills", []) or []):
        p = "skills[%d]" % i
        name = (s.get("name") or "").strip()
        ids = list(s.get("source_ids") or [])
        if not ids:
            _issue(issues, "block", p, "skill %r has no source_ids" % name)
            continue
        for x in ids:
            if x not in idx:
                _issue(issues, "block", p, "unknown source id %r" % x)
        known = [x for x in ids if x in idx]
        if not known:
            continue
        names = [n for x in known for n in [idx[x].get("name", "")] + list(idx[x].get("skills", []) or []) if n]
        sblob = rl.source_blob(known, idx)

        def backs(part: str) -> bool:
            return (any(jslib.norm_key(n) == jslib.norm_key(part) for n in names)
                    or rl.term_supported(part, sblob))

        backed = backs(name)
        if not backed:
            # "Kubernetes (EKS)": every part must be backed on its own
            parts = [x.strip() for x in re.split(r"[(),;&]|\band\b", name) if x.strip()]
            backed = len(parts) > 1 and all(backs(pt) for pt in parts)
        if not backed:
            _issue(issues, "block", p, "skill %r is not backed by its sources (%s)" % (name, ", ".join(known)))

    # Education / certifications
    for key, want in (("education", "education"), ("certifications", "certifications")):
        valid = {x["id"] for x in fb.get(want, []) or []}
        for i, x in enumerate(resume.get(key, []) or []):
            xid = x if isinstance(x, str) else (x or {}).get("id")
            if xid not in valid:
                _issue(issues, "block", "%s[%d]" % (key, i), "unknown %s id %r" % (key, xid))

    # Projects must reference a real project
    proj_ids = {p["id"] for p in fb.get("projects", []) or []}
    for i, p in enumerate(resume.get("projects", []) or []):
        if p.get("id") and p["id"] not in proj_ids:
            _issue(issues, "block", "projects[%d]" % i, "unknown project id %r" % p["id"])

    blocks = [x for x in issues if x["severity"] == "block"]
    return {
        "passed": not blocks,
        "issues": issues,
        "checked_at": jslib.now_iso(),
        "resume_hash": rl.canonical_hash(resume),
    }


def verify_job(home: Path, job_id: str) -> dict:
    b = rl.load_job_bundle(home, job_id)
    if b["job"] is None:
        raise SystemExit("Unknown job id: %s" % job_id)
    if b["resume"] is None:
        raise SystemExit("No resume.json for %s. Run /job-search:tailor first." % job_id)
    fb = jslib.load_fact_bank(home)
    result = verify_resume(fb, b["resume"], b["score"])
    changes = b["changes"] or rl.empty_changes(job_id)
    changes["verify"] = result
    jslib.write_json(b["dir"] / "changes.json", changes)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("job_id")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--home")
    a = ap.parse_args(argv)
    home = jslib.require_home(a.home)
    result = verify_job(home, a.job_id)
    if a.json:
        print(json.dumps(result, indent=2))
    else:
        blocks = [x for x in result["issues"] if x["severity"] == "block"]
        warns = [x for x in result["issues"] if x["severity"] == "warn"]
        print("verify %s: %s (%d block, %d warn)" % (a.job_id, "PASSED" if result["passed"] else "FAILED", len(blocks), len(warns)))
        for x in result["issues"]:
            print("  [%s] %s: %s" % (x["severity"], x["path"], x["message"]))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
