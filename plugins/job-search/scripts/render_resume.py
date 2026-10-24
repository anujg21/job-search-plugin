#!/usr/bin/env python3
"""Render a resume to ATS-friendly HTML, Markdown and PDF (Chrome, else xhtml2pdf if installed).

Layout comes from profile/resume-style.json when present (see DEFAULT_STYLE).

Usage:
  render_resume.py <job_id> [--no-pdf] [--json] [--home PATH]   # jobs/<id>/resume.{html,md,pdf}
  render_resume.py --master [--no-pdf] [--json] [--home PATH]   # profile/resume-master.{html,pdf}

The master render never touches profile/resume-master.md (the user's original resume text).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402
import resume_lib as rl  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "resume.html"
MAC_CHROME = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
LINUX_CHROME = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]
TWO_PAGE_WORDS = 950  # rough word budget for two Letter pages at 10.5pt

# Layout only, never content. profile/resume-style.json overrides any key (onboarding writes
# it from the look of the user's own resume). Missing file means this plain default.
DEFAULT_STYLE = {
    "font": 'Arial, Helvetica, "Liberation Sans", sans-serif',
    "base_size_pt": 10.5,
    "text_color": "#111111",
    "accent_color": "#111111",
    "muted_color": "#333333",
    "page_size": "Letter",
    "margins_in": [0.5, 0.6],
    "header_align": "left",
    "name_size_pt": 18,
    "name_caps": False,
    "name_letter_spacing_pt": 0.2,
    "headline_bold": True,
    "contact_separator": " | ",
    "section_caps": True,
    "section_letter_spacing_pt": 0.8,
    "section_rule": True,
    "skills_layout": "list",
    "skill_groups": {},
    "role_format": "title_company",
    "date_style": "own_line",
    "section_titles": {},
    "role_separator": ", ",
}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fmt_date(d: str) -> str:
    d = (d or "").strip()
    if d.lower() in ("present", "current", "now"):
        return "Present"
    parts = d.split("-")
    if len(parts) >= 2 and parts[1].isdigit() and 1 <= int(parts[1]) <= 12:
        return "%s %s" % (MONTHS[int(parts[1]) - 1], parts[0])
    return d


def date_range(r: dict) -> str:
    a, b = fmt_date(r.get("start", "")), fmt_date(r.get("end", ""))
    return "%s - %s" % (a, b) if a and b else (a or b)


def find_chrome() -> Optional[str]:
    env = os.environ.get("JOBSEARCH_CHROME")
    if env:
        return env if (os.path.exists(env) or shutil.which(env)) else None
    for p in MAC_CHROME:
        if os.path.exists(p):
            return p
    for name in LINUX_CHROME:
        p = shutil.which(name)
        if p:
            return p
    return None


def load_style(home: Path) -> dict:
    style = dict(DEFAULT_STYLE)
    custom = jslib.read_json(home / "profile" / "resume-style.json", {}) or {}
    style.update({k: v for k, v in custom.items() if k in DEFAULT_STYLE})
    return style


def css(st: dict) -> str:
    m = st["margins_in"] if isinstance(st["margins_in"], list) else [st["margins_in"]] * 2
    caps = "uppercase" if st["section_caps"] else "none"
    rule = "border-bottom: 1px solid %s; padding-bottom: 1pt;" % st["muted_color"] if st["section_rule"] else ""
    return """
  @page { size: %(page)s; margin: %(mv)sin %(mh)sin; }
  * { box-sizing: border-box; }
  html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { margin: 0 auto; max-width: 7.5in; padding: 0.4in 0; font-family: %(font)s;
    font-size: %(base)spt; line-height: 1.3; color: %(text)s; background: #fff; }
  @media print { body { padding: 0; max-width: none; } }
  header { margin-bottom: 6pt; text-align: %(align)s; }
  h1 { font-size: %(name)spt; margin: 0; letter-spacing: %(nls)spt; color: %(accent)s;
    text-transform: %(ncaps)s; }
  .headline { font-weight: %(hw)s; margin: 2pt 0 2pt; }
  .contact { font-size: %(small)spt; color: %(muted)s; margin: 0; }
  .contact a { color: %(muted)s; text-decoration: none; }
  h2 { font-size: %(base)spt; text-transform: %(caps)s; letter-spacing: %(sls)spt;
    color: %(accent)s; margin: 9pt 0 3pt; %(rule)s }
  p { margin: 0 0 3pt; }
  .role { margin: 0 0 5pt; break-inside: avoid-page; page-break-inside: avoid; }
  .role-head { font-weight: bold; margin: 0; }
  .role-date { color: %(muted)s; font-weight: normal; white-space: nowrap; }
  .role-meta { color: %(muted)s; font-size: %(small)spt; margin: 0 0 2pt; }
  .skill-group { margin: 0 0 1pt; }
  ul { margin: 2pt 0 0 0; padding-left: 14pt; }
  li { margin: 0 0 1.5pt; }
  .item { margin: 0 0 3pt; }
""" % {"page": st["page_size"], "mv": m[0], "mh": m[1], "font": st["font"],
       "base": st["base_size_pt"], "small": round(st["base_size_pt"] * 0.9, 1),
       "text": st["text_color"], "accent": st["accent_color"], "muted": st["muted_color"],
       "align": st["header_align"], "name": st["name_size_pt"],
       "nls": st["name_letter_spacing_pt"], "ncaps": "uppercase" if st["name_caps"] else "none",
       "hw": "bold" if st["headline_bold"] else "normal", "caps": caps,
       "sls": st["section_letter_spacing_pt"], "rule": rule}


def short_url(u: str) -> str:
    """linkedin.com/in/x instead of https://www.linkedin.com/in/x/, as people write it."""
    u = re.sub(r"^https?://", "", u or "")
    return re.sub(r"^www\.", "", u).rstrip("/")


def group_skills(skills: List[str], groups: dict) -> List[tuple]:
    """Put the chosen skills under the user's own group labels, in the user's order."""
    seen, out = set(), []
    for label, members in groups.items():
        names = {str(x).lower() for x in members or []}
        hit = [s for s in skills if s.lower() in names and s not in seen]
        if hit:
            out.append((label, hit))
            seen.update(hit)
    rest = [s for s in skills if s not in seen]
    if rest:
        out.append(("Other" if out else "", rest))
    return out


def collect(fb: dict, resume: dict) -> dict:
    """Resolve ids into display data."""
    idx = jslib.fact_index(fb)
    person = fb.get("person", {}) or {}
    edu = []
    for x in resume.get("education", []) or []:
        e = idx.get(x if isinstance(x, str) else (x or {}).get("id"))
        if e:
            edu.append(", ".join(v for v in (e.get("degree"), e.get("school"), str(e.get("year") or "")) if v))
    certs = []
    for x in resume.get("certifications", []) or []:
        c = idx.get(x if isinstance(x, str) else (x or {}).get("id"))
        if c:
            certs.append(", ".join(v for v in (c.get("name"), str(c.get("year") or "")) if v))
    projects = []
    for p in resume.get("projects", []) or []:
        fp = idx.get(p.get("id")) or {}
        projects.append({"name": fp.get("name", ""), "text": p.get("text", "")})
    contact = [person.get(k) for k in ("location", "email", "phone") if person.get(k)]
    links = [(l.get("label") or l.get("url"), l.get("url")) for l in person.get("links", []) or [] if l.get("url")]
    return {
        "name": person.get("name", ""),
        "headline": resume.get("headline", ""),
        "contact": contact,
        "links": links,
        "summary": ((resume.get("summary") or {}).get("text") or "").strip(),
        "skills": [s.get("name", "") for s in resume.get("skills", []) or [] if s.get("name")],
        "roles": resume.get("roles", []) or [],
        "projects": projects,
        "education": edu,
        "certifications": certs,
    }


def to_html(d: dict, st: Optional[dict] = None) -> str:
    st = st or DEFAULT_STYLE
    e = html.escape
    titles = {"summary": "Summary", "skills": "Skills", "experience": "Experience",
              "projects": "Projects", "education": "Education", "certifications": "Certifications"}
    titles.update(st.get("section_titles") or {})
    if st["section_caps"]:  # done here, not in CSS, so the no-Chrome PDF renderer matches
        titles = {k: v.upper() for k, v in titles.items()}
    name = d["name"].upper() if st["name_caps"] else d["name"]
    out: List[str] = ["<header>", "<h1>%s</h1>" % e(name)]
    if d["headline"]:
        out.append('<p class="headline">%s</p>' % e(d["headline"]))
    bits = [e(c) for c in d["contact"]]
    bits += ['<a href="%s">%s</a>' % (e(u, quote=True), e(short_url(u))) for _, u in d["links"]]
    if bits:
        out.append('<p class="contact">%s</p>' % e(st["contact_separator"]).join(bits))
    out.append("</header>")
    if d["summary"]:
        out += ["<section>", "<h2>%s</h2>" % e(titles["summary"]), "<p>%s</p>" % e(d["summary"]), "</section>"]
    if d["skills"]:
        out += ["<section>", "<h2>%s</h2>" % e(titles["skills"])]
        if st["skills_layout"] == "grouped" and st.get("skill_groups"):
            for label, names in group_skills(d["skills"], st["skill_groups"]):
                lead = "<strong>%s:</strong> " % e(label) if label else ""
                out.append('<p class="skill-group">%s%s</p>' % (lead, e(", ".join(names))))
        else:
            out.append("<p>%s</p>" % e(", ".join(d["skills"])))
        out.append("</section>")
    if d["roles"]:
        out += ["<section>", "<h2>%s</h2>" % e(titles["experience"])]
        for r in d["roles"]:
            out.append('<div class="role">')
            title, company, loc = r.get("title", ""), r.get("company", ""), r.get("location", "")
            if st["role_format"] == "company_title":
                head = e(company) + e(st["role_separator"]) + e(title) + (", " + e(loc) if loc else "")
                meta = date_range(r)
            else:
                head = "%s, %s" % (e(title), e(company))
                meta = " | ".join(x for x in (date_range(r), loc) if x)
            if st["date_style"] == "inline_muted" and meta:
                out.append('<p class="role-head">%s&nbsp;&nbsp;&nbsp;<span class="role-date">%s</span></p>'
                           % (head, e(meta)))
            else:
                out.append('<p class="role-head">%s</p>' % head)
                if meta:
                    out.append('<p class="role-meta">%s</p>' % e(meta))
            bullets = [b.get("text", "") for b in r.get("bullets", []) or [] if b.get("text")]
            if bullets:
                out.append("<ul>" + "".join("<li>%s</li>" % e(b) for b in bullets) + "</ul>")
            out.append("</div>")
        out.append("</section>")
    if d["projects"]:
        out += ["<section>", "<h2>%s</h2>" % e(titles["projects"])]
        for p in d["projects"]:
            label = "<strong>%s</strong>: " % e(p["name"]) if p["name"] else ""
            out.append('<p class="item">%s%s</p>' % (label, e(p["text"])))
        out.append("</section>")
    if d["education"]:
        out += ["<section>", "<h2>%s</h2>" % e(titles["education"])] + ['<p class="item">%s</p>' % e(x) for x in d["education"]] + ["</section>"]
    if d["certifications"]:
        out += ["<section>", "<h2>%s</h2>" % e(titles["certifications"])] + ['<p class="item">%s</p>' % e(x) for x in d["certifications"]] + ["</section>"]
    body = "\n".join(out)
    tpl = TEMPLATE.read_text(encoding="utf-8")
    title = "%s Resume" % d["name"] if d["name"] else "Resume"
    return tpl.replace("{{TITLE}}", e(title)).replace("{{CSS}}", css(st)).replace("{{BODY}}", body)


def to_markdown(d: dict) -> str:
    out = ["# %s" % d["name"]]
    if d["headline"]:
        out.append("**%s**" % d["headline"])
    contact = list(d["contact"]) + [u for _, u in d["links"]]
    if contact:
        out.append(" | ".join(contact))
    if d["summary"]:
        out += ["", "## Summary", "", d["summary"]]
    if d["skills"]:
        out += ["", "## Skills", "", ", ".join(d["skills"])]
    if d["roles"]:
        out += ["", "## Experience"]
        for r in d["roles"]:
            out += ["", "### %s, %s" % (r.get("title", ""), r.get("company", ""))]
            meta = " | ".join(x for x in (date_range(r), r.get("location", "")) if x)
            if meta:
                out.append(meta)
            out.append("")
            out += ["- %s" % b.get("text", "") for b in r.get("bullets", []) or [] if b.get("text")]
    if d["projects"]:
        out += ["", "## Projects", ""]
        out += ["- %s%s" % ("**%s**: " % p["name"] if p["name"] else "", p["text"]) for p in d["projects"]]
    if d["education"]:
        out += ["", "## Education", ""] + ["- %s" % x for x in d["education"]]
    if d["certifications"]:
        out += ["", "## Certifications", ""] + ["- %s" % x for x in d["certifications"]]
    return "\n".join(out) + "\n"


def print_pdf(chrome: str, html_path: Path, pdf_path: Path) -> Optional[str]:
    """Returns None on success, else an error string."""
    with tempfile.TemporaryDirectory() as prof:
        cmd = [chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf-no-header",
               "--no-first-run", "--no-default-browser-check", "--disable-extensions",
               "--user-data-dir=%s" % prof, "--print-to-pdf=%s" % pdf_path, html_path.resolve().as_uri()]
        try:
            if pdf_path.exists():
                pdf_path.unlink()
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired) as ex:
            return "chrome failed: %s" % ex
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        return "chrome ran but wrote no PDF"
    return None


def pdf_without_chrome(html_path: Path, pdf_path: Path) -> Optional[str]:
    """Pure Python fallback for places without Chrome (cloud runs). Needs the optional
    xhtml2pdf package: pip install xhtml2pdf. Returns None on success, else a reason."""
    try:
        from xhtml2pdf import pisa  # type: ignore
    except ImportError:
        return "no Chrome and no xhtml2pdf; run: pip install xhtml2pdf, or open the HTML and print to PDF"
    try:
        with open(pdf_path, "wb") as f:
            res = pisa.CreatePDF(html_path.read_text(encoding="utf-8"), dest=f)
    except Exception as ex:  # a broken page should not stop the run
        return "xhtml2pdf failed: %s" % ex
    if res.err or not pdf_path.exists() or pdf_path.stat().st_size == 0:
        return "xhtml2pdf wrote no PDF"
    return None


def render(home: Path, job_id: Optional[str], master: bool, pdf: bool) -> dict:
    fb = jslib.load_fact_bank(home)
    if master:
        resume = rl.build_master(fb)
        base = jslib.profile_path(home, "resume-master")
        md_path = None  # never overwrite the user's resume-master.md
    else:
        d = jslib.job_dir(home, job_id)
        resume = jslib.read_json(d / "resume.json")
        if resume is None:
            raise SystemExit("No resume.json for %s. Run /job-search:tailor first." % job_id)
        base = d / "resume"
        md_path = base.with_suffix(".md")
    data = collect(fb, resume)
    html_path = base.with_suffix(".html")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(to_html(data, load_style(home)), encoding="utf-8")
    md_text = to_markdown(data)
    if md_path:
        md_path.write_text(md_text, encoding="utf-8")
    n_words = len(md_text.split())
    result = {"html": str(html_path), "md": str(md_path) if md_path else None, "pdf": None,
              "pdf_note": "", "words": n_words, "warnings": []}
    if n_words > TWO_PAGE_WORDS:
        result["warnings"].append("about %d words; likely more than 2 pages. Trim low-relevance bullets." % n_words)
    if pdf:
        chrome = find_chrome()
        pdf_path = base.with_suffix(".pdf")
        err = print_pdf(chrome, html_path, pdf_path) if chrome else pdf_without_chrome(html_path, pdf_path)
        if err:
            result["pdf_note"] = err
        else:
            result["pdf"] = str(pdf_path)
    else:
        result["pdf_note"] = "PDF skipped (--no-pdf)"
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("job_id", nargs="?")
    ap.add_argument("--master", action="store_true")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--home")
    a = ap.parse_args(argv)
    if not a.master and not a.job_id:
        ap.error("give a job_id or --master")
    home = jslib.require_home(a.home)
    res = render(home, a.job_id, a.master, not a.no_pdf)
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        print("wrote %s" % res["html"])
        if res["md"]:
            print("wrote %s" % res["md"])
        print("wrote %s" % res["pdf"] if res["pdf"] else res["pdf_note"])
        for w in res["warnings"]:
            print("warning: " + w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
