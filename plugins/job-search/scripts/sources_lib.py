"""Shared helpers for job sources: HTML to text, cheap prefilter, ingest, HTTP fetch.

Used by scan.py (API sources) and add_job.py (browser / pasted sources).
Standard library only, Python 3.9+.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402

USER_AGENT = "job-search-plugin/%s (+https://github.com/; personal job search)" % jslib.PLUGIN_VERSION
TIMEOUT = 20

# ---------- HTTP ----------


class FetchError(Exception):
    pass


def fetch_json(url: str, timeout: int = TIMEOUT) -> Any:
    """GET a URL and parse JSON. Raises FetchError with a short readable message."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        try:
            raw = resp.read()
        finally:
            close = getattr(resp, "close", None)
            if close:
                close()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise FetchError("HTTP 404 (board not found, check the company token)")
        raise FetchError("HTTP %s" % e.code)
    except urllib.error.URLError as e:
        raise FetchError("network error: %s" % getattr(e, "reason", e))
    except (TimeoutError, OSError) as e:  # socket.timeout is an OSError subclass
        raise FetchError("network error: %s" % e)
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        return json.loads(raw)
    except ValueError:
        raise FetchError("response was not valid JSON")


# ---------- HTML to text ----------

_BLOCK = {"p", "div", "section", "article", "header", "footer", "table", "tr", "blockquote", "pre"}
_HEADINGS = {"h1": "## ", "h2": "## ", "h3": "### ", "h4": "#### ", "h5": "#### ", "h6": "#### "}


class _TextBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: List[str] = []
        self.lists: List[Dict[str, Any]] = []
        self.skip = 0
        self.bold = 0
        self.in_heading = False

    def _nl(self, n: int = 1) -> None:
        text = "".join(self.out)
        have = len(text) - len(text.rstrip("\n"))
        if not text.strip():
            return
        if have < n:
            self.out.append("\n" * (n - have))

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style", "head", "title"):
            self.skip += 1
        elif tag in _HEADINGS:
            self._nl(2)
            self.out.append(_HEADINGS[tag])
            self.in_heading = True
        elif tag in ("ul", "ol"):
            self._nl(1 if self.lists else 2)
            self.lists.append({"ordered": tag == "ol", "n": 0})
        elif tag == "li":
            self._nl(1)
            depth = max(len(self.lists) - 1, 0)
            if self.lists and self.lists[-1]["ordered"]:
                self.lists[-1]["n"] += 1
                bullet = "%d. " % self.lists[-1]["n"]
            else:
                bullet = "- "
            self.out.append("  " * depth + bullet)
        elif tag == "br":
            self.out.append("\n")
        elif tag in _BLOCK:
            self._nl(2)
        elif tag in ("strong", "b") and not self.in_heading:
            self.bold += 1
            if self.bold == 1:
                self.out.append("**")
        elif tag in ("td", "th"):
            self.out.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "head", "title"):
            self.skip = max(self.skip - 1, 0)
        elif tag in _HEADINGS:
            self.in_heading = False
            self._nl(2)
        elif tag in ("ul", "ol"):
            if self.lists:
                self.lists.pop()
            self._nl(1 if self.lists else 2)
        elif tag in _BLOCK:
            self._nl(2)
        elif tag in ("strong", "b") and not self.in_heading:
            if self.bold == 1:
                if self.out and self.out[-1].endswith(" "):
                    self.out[-1] = self.out[-1].rstrip(" ")
                    self.out.append("** ")
                else:
                    self.out.append("**")
            self.bold = max(self.bold - 1, 0)

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        data = re.sub(r"\s+", " ", data.replace("\xa0", " "))
        if not data.strip():
            text = "".join(self.out)
            if text and not text.endswith((" ", "\n")):
                self.out.append(" ")
            return
        text = "".join(self.out)
        if text.endswith("\n") or text.endswith("- ") or not text:
            data = data.lstrip()
        self.out.append(data)


def looks_like_html(text: str) -> bool:
    return bool(re.search(r"</?(p|div|br|li|ul|ol|h[1-6]|span|strong|b|em|a)\b[^>]*>", text or "", re.I))


def html_to_text(raw: str) -> str:
    """Convert job-board HTML to readable markdown-ish text.

    Handles Greenhouse's double-escaped HTML (`&lt;p&gt;`), keeps headings and bullets,
    and unescapes entities.
    """
    if not raw:
        return ""
    s = raw
    # Greenhouse returns HTML escaped once more than needed.
    if "&lt;" in s and "<" not in s.replace("&lt;", ""):
        s = html.unescape(s)
    elif re.search(r"&lt;/?(p|div|li|ul|h[1-6]|strong|br)\b", s):
        s = html.unescape(s)
    if not looks_like_html(s):
        return _tidy(html.unescape(s))
    p = _TextBuilder()
    p.feed(s)
    p.close()
    return _tidy("".join(p.out))


def _tidy(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\xa0", " ")
    lines = [ln.rstrip() for ln in text.split("\n")]
    out: List[str] = []
    for ln in lines:
        # drop empty bold markers and bullet-only lines
        ln = re.sub(r"\*\*\s*\*\*", "", ln)
        if re.fullmatch(r"\s*(-|\d+\.)\s*", ln):
            continue
        if not ln.strip():
            if out and out[-1] == "":
                continue
            out.append("")
        else:
            out.append(ln)
    return "\n".join(out).strip() + "\n"


# ---------- text helpers ----------

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.]*")
_STOP = {"and", "or", "of", "the", "a", "an", "for", "to", "in", "at", "with", "&", "-", "i", "ii", "iii", "iv"}
ROLE_NOUNS = {
    "engineer", "architect", "developer", "manager", "director", "scientist", "designer",
    "analyst", "consultant", "specialist", "administrator", "lead", "head", "sre", "devops",
    "researcher", "programmer", "owner", "officer", "vp", "president", "strategist",
    "technologist", "fellow", "advocate", "writer", "recruiter", "coordinator", "executive",
}


# Level words say how senior a job is, not what it is. "Senior" alone must not make
# "Senior Network Engineer" look like a match for "Senior Data Engineer".
LEVEL_WORDS = {
    "senior", "sr", "staff", "principal", "junior", "jr", "mid", "associate", "distinguished",
    "entry", "level", "intermediate", "experienced",
}


def _stem(tok: str) -> str:
    tok = tok.strip(".")
    if len(tok) > 3 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


# Spelled-out and short forms of the same title words, so "ML Platform Engineer" matches
# "Machine Learning Platform Engineer". Applied to both job titles and the user's targets.
_SYNONYMS = [
    (re.compile(r"\bmachine[- ]learning\b"), "ml"),
    (re.compile(r"\bartificial[- ]intelligence\b"), "ai"),
    (re.compile(r"\bsite[- ]reliability(?: engineering| engineer)?\b"), "sre"),
    (re.compile(r"\bdev[- ]ops\b"), "devops"),
    (re.compile(r"\bsr\.?(?=\s)"), "senior"),
    (re.compile(r"\bjr\.?(?=\s)"), "junior"),
    (re.compile(r"\bswe\b"), "software engineer"),
]


def _normalize(text: str) -> str:
    low = (text or "").lower()
    for rx, rep in _SYNONYMS:
        low = rx.sub(rep, low)
    return low


def tokens(text: str) -> List[str]:
    return [_stem(t) for t in _TOKEN_RE.findall(_normalize(text)) if t not in _STOP]


def _phrase_in(phrase: str, text: str) -> bool:
    phrase = phrase.strip().lower()
    if not phrase:
        return False
    pat = r"(?<![a-z0-9])" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"s?(?![a-z0-9])"
    return re.search(pat, (text or "").lower()) is not None


# Single-word deal breakers ("contract") are only counted in the description when they sit
# next to an employment word. "Own contract renewals" should not drop a sales job.
_EMPLOYMENT_WORDS = {
    "role", "position", "basis", "job", "employment", "assignment", "opportunity", "hire",
    "w2", "w-2", "c2c", "corp", "1099", "duration", "month", "months", "term", "engagement",
    "only", "contractor", "contractors", "temporary", "temp", "length", "extension", "rate",
    "hourly", "type",
}


def _single_word_in_context(word: str, text: str, window: int = 3) -> bool:
    words = re.findall(r"[a-z0-9][a-z0-9-]*", (text or "").lower())
    w = word.lower()
    for i, t in enumerate(words):
        parts = t.split("-")
        if t == w or t == w + "s" or w in parts:
            if len(parts) > 1 and w in parts:
                # "contract-to-hire", "12-month-contract"
                if any(p in _EMPLOYMENT_WORDS for p in parts if p != w):
                    return True
            near = words[max(0, i - window): i] + words[i + 1: i + 1 + window]
            for n in near:
                if n in _EMPLOYMENT_WORDS or any(p in _EMPLOYMENT_WORDS for p in n.split("-")):
                    return True
    return False


# ---------- remote / location ----------

def infer_remote(*texts: str, description: str = "") -> str:
    """Return remote|hybrid|onsite|unknown from location/title/workplace text, then description."""
    joined = " ".join(t for t in texts if t).lower()
    if re.search(r"\bhybrid\b", joined):
        return "hybrid"
    if re.search(r"\b(remote|anywhere|work from home|wfh|distributed)\b", joined):
        return "remote"
    if re.search(r"\b(on-?site|in[- ]office|in office)\b", joined):
        return "onsite"
    d = (description or "").lower()
    if d:
        if re.search(r"\b(fully remote|100% remote|remote[- ]first|remote position|remote role|"
                     r"work remotely|this role is remote|this is a remote|remote[- ]eligible|"
                     r"eligible (for|to work) remote(ly)?|open to remote|remote[- ]friendly|"
                     r"performed remotely)\b", d):
            return "remote"
        if re.search(r"\bhybrid (role|position|schedule|work)\b|\bthis role is hybrid\b", d):
            return "hybrid"
        if re.search(r"\b(this role is (on-?site|in[- ]office)|fully on-?site|100% on-?site)\b", d):
            return "onsite"
    return "unknown"


def _pref_place_keys(locations: List[str]) -> List[str]:
    keys = []
    for loc in locations or []:
        low = loc.lower()
        if "remote" in low or "anywhere" in low:
            continue
        city = low.split(",")[0].strip()
        if city:
            keys.append(city)
    return keys


def location_ok(job_location: str, job_remote: str, prefs: dict) -> Tuple[bool, str]:
    want = (prefs.get("remote") or "any").lower()
    places = _pref_place_keys(prefs.get("locations") or [])
    loc = (job_location or "").lower()
    in_place = any(p in loc for p in places) if loc else False
    if want == "any":
        return True, ""
    if job_remote == "remote":
        return True, ""
    if job_remote == "unknown":
        # Greenhouse rarely says whether a role is remote. A named city outside the user's
        # places is far more often onsite, so skip it rather than spend scoring time on it.
        # For a remote-only user with no cities, every named city is outside their places.
        # A bare country ("United States", "USA") is vague, not a city.
        vague = any(w in loc for w in ("remote", "anywhere", "multiple", "various", "flexible")) \
            or _country_only(loc)
        if loc and not in_place and not vague and (places or want == "remote"):
            return False, "location: unclear remote status in %s" % job_location
        return True, ""
    if in_place:
        return True, ""
    if not loc and job_remote != "onsite":
        return True, ""
    if want == "remote":
        return False, "location: %s role in %s" % (job_remote, job_location or "unknown place")
    if want == "hybrid":
        if job_remote == "hybrid" and not places:
            return True, ""
        return False, "location: %s role in %s" % (job_remote, job_location or "unknown place")
    if want == "onsite":
        if not places:
            return True, ""
        return False, "location: %s not in preferred locations" % (job_location or "unknown place")
    return True, ""


# ---------- country ----------

_US_STATES = {
    "alabama": "al", "alaska": "ak", "arizona": "az", "arkansas": "ar", "california": "ca",
    "colorado": "co", "connecticut": "ct", "delaware": "de", "florida": "fl", "georgia": "ga",
    "hawaii": "hi", "idaho": "id", "illinois": "il", "indiana": "in", "iowa": "ia", "kansas": "ks",
    "kentucky": "ky", "louisiana": "la", "maine": "me", "maryland": "md", "massachusetts": "ma",
    "michigan": "mi", "minnesota": "mn", "mississippi": "ms", "missouri": "mo", "montana": "mt",
    "nebraska": "ne", "nevada": "nv", "new hampshire": "nh", "new jersey": "nj", "new mexico": "nm",
    "new york": "ny", "north carolina": "nc", "north dakota": "nd", "ohio": "oh", "oklahoma": "ok",
    "oregon": "or", "pennsylvania": "pa", "rhode island": "ri", "south carolina": "sc",
    "south dakota": "sd", "tennessee": "tn", "texas": "tx", "utah": "ut", "vermont": "vt",
    "virginia": "va", "washington": "wa", "west virginia": "wv", "wisconsin": "wi", "wyoming": "wy",
    "district of columbia": "dc",
}

# Country names and big tech-hiring cities, mapped to a country code. Not exhaustive: a job whose
# place we can't name stays "unknown country" and is kept.
_COUNTRY_WORDS = {
    "US": ["united states", "usa", "u.s.", "us-remote", "remote us", "us remote", "americas",
           "san francisco", "new york", "seattle", "chicago", "boston", "austin", "denver", "atlanta",
           "los angeles", "miami", "tampa", "washington dc", "palo alto", "mountain view", "sunnyvale"],
    "CA": ["canada", "toronto", "vancouver", "montreal", "ottawa", "calgary", "waterloo"],
    "GB": ["united kingdom", "uk", "england", "scotland", "london", "manchester", "edinburgh"],
    "IE": ["ireland", "dublin"],
    "FR": ["france", "paris", "nantes", "lyon"],
    "DE": ["germany", "berlin", "munich", "hamburg", "frankfurt"],
    "NL": ["netherlands", "amsterdam"],
    "ES": ["spain", "madrid", "barcelona"],
    "PT": ["portugal", "lisbon", "porto"],
    "SE": ["sweden", "stockholm"],
    "CH": ["switzerland", "zurich", "geneva"],
    "PL": ["poland", "warsaw", "krakow"],
    "IL": ["israel", "tel aviv"],
    "IN": ["india", "bengaluru", "bangalore", "hyderabad", "pune", "chennai", "gurgaon", "noida", "mumbai"],
    "SG": ["singapore"],
    "JP": ["japan", "tokyo"],
    "AU": ["australia", "sydney", "melbourne"],
    "BR": ["brazil", "sao paulo", "são paulo"],
    "MX": ["mexico"],
    "EU": ["emea", "europe", "eu remote", "remote eu"],
    "RS": ["serbia", "belgrade", "novi sad"],
    "DK": ["denmark", "copenhagen", "aarhus"],
    "NO": ["norway", "oslo"],
    "FI": ["finland", "helsinki"],
    "BE": ["belgium", "brussels"],
    "AT": ["austria", "vienna"],
    "IT": ["italy", "milan", "rome"],
    "CZ": ["czech republic", "czechia", "prague", "brno"],
    "RO": ["romania", "bucharest", "cluj"],
    "UA": ["ukraine", "kyiv", "kiev", "lviv"],
    "GR": ["greece", "athens"],
    "HU": ["hungary", "budapest"],
    "BG": ["bulgaria", "sofia"],
    "HR": ["croatia", "zagreb"],
    "EE": ["estonia", "tallinn"],
    "LT": ["lithuania", "vilnius"],
    "LV": ["latvia", "riga"],
    "TR": ["turkey", "turkiye", "istanbul"],
    "AE": ["united arab emirates", "uae", "dubai", "abu dhabi"],
    "AR": ["argentina", "buenos aires"],
    "CO": ["colombia", "bogota", "medellin"],
    "CL": ["chile", "santiago"],
    "CR": ["costa rica", "san jose, costa rica"],
    "UY": ["uruguay", "montevideo"],
    "PE": ["peru", "lima"],
    "PH": ["philippines", "manila"],
    "VN": ["vietnam", "ho chi minh", "hanoi"],
    "KR": ["south korea", "korea", "seoul"],
    "CN": ["china", "beijing", "shanghai", "shenzhen"],
    "TW": ["taiwan", "taipei"],
    "HK": ["hong kong"],
    "NZ": ["new zealand", "auckland", "wellington"],
    "ZA": ["south africa", "cape town", "johannesburg"],
    "NG": ["nigeria", "lagos"],
    "KE": ["kenya", "nairobi"],
    "EG": ["egypt", "cairo"],
}


_COUNTRY_ONLY = {
    "us", "u.s.", "usa", "u.s.a.", "united states", "united states of america", "america",
    "americas", "north america", "canada", "united kingdom", "uk", "europe", "emea", "latam",
}


def _country_only(loc: str) -> bool:
    """True when every part of a location is just a country or region name."""
    parts = [re.sub(r"[^a-z. ]+", " ", p).strip() for p in re.split(r"[;|/]", (loc or "").lower())]
    parts = [" ".join(p.split()) for p in parts if p.strip()]
    return bool(parts) and all(p in _COUNTRY_ONLY for p in parts)


def countries_in(text: str) -> set:
    """Country codes named in a location string. Empty set means we could not tell."""
    low = " " + (text or "").lower() + " "
    found = set()
    for code, words in _COUNTRY_WORDS.items():
        for w in words:
            if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low):
                found.add(code)
                break
    if re.search(r",\s*(" + "|".join(_US_STATES.values()) + r")\b", low) or \
            any(re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", low) for n in _US_STATES):
        found.add("US")
    if "US" in found and "new mexico" in low and "mexico" not in low.replace("new mexico", ""):
        found.discard("MX")
    return found


def user_countries(prefs: dict) -> set:
    """preferences.countries if set, otherwise inferred from preferences.locations."""
    explicit = {c.upper() for c in (prefs.get("countries") or []) if c}
    if explicit:
        return explicit
    found = set()
    for loc in prefs.get("locations") or []:
        found |= countries_in(loc)
    return found


def country_ok(item: dict, prefs: dict) -> Tuple[bool, str]:
    mine = user_countries(prefs)
    if not mine or (prefs.get("remote") or "").lower() == "any" and not prefs.get("countries"):
        return True, ""
    text = "%s; %s" % (item.get("location") or "", item.get("offices") or "")
    theirs = countries_in(text)
    if not theirs or theirs & mine:
        return True, ""
    return False, "location: outside %s (%s)" % ("/".join(sorted(mine)), item.get("location") or "")


# ---------- prefilter ----------

def title_ok(title: str, prefs: dict) -> Tuple[bool, str]:
    targets = prefs.get("target_titles") or []
    keywords = prefs.get("keywords") or []
    if not targets and not keywords:
        return True, ""
    ttoks = set(tokens(title))
    if not ttoks:
        return False, "title: empty"
    for word in prefs.get("exclude_title_words") or []:
        if word and _phrase_in(word, title.lower()):
            return False, "title: excluded word '%s'" % word
    for t in targets:
        need = set(tokens(t))
        if need and need <= ttoks:
            return True, ""
    role_nouns = set()
    for t in targets:
        role_nouns |= {x for x in tokens(t) if x in ROLE_NOUNS}
    title_low = title.lower()
    for kw in keywords:
        ktoks = tokens(kw)
        if not ktoks:
            continue
        hit = set(ktoks) <= ttoks or _phrase_in(kw, title_low)
        if hit and (not role_nouns or role_nouns & ttoks):
            return True, ""
    # Partial target match: share a role noun and at least one other target token that is
    # not a level word.
    for t in targets:
        need = set(tokens(t))
        nouns = need & ROLE_NOUNS
        rest = need - ROLE_NOUNS - LEVEL_WORDS
        if nouns and nouns <= ttoks and rest and rest & ttoks:
            return True, ""
    return False, "title: no match for target titles or keywords"


def title_rank(title: str, prefs: dict) -> float:
    """How closely a title matches the user's targets. Higher is better. Used to pick which
    found jobs to score first, so a big backlog is worked best-first instead of newest-first."""
    ttoks = set(tokens(title))
    if not ttoks:
        return 0.0
    title_low = (title or "").lower()
    best = 0.0
    for t in prefs.get("target_titles") or []:
        core_words = [w for w in t.lower().split() if _stem(w.strip(",.")) not in LEVEL_WORDS]
        core = set(tokens(" ".join(core_words)))
        if not core:
            continue
        if _phrase_in(" ".join(core_words), title_low):
            best = max(best, 3.0)  # "Data Engineer" inside "Senior Staff Data Engineer, Payments"
        elif core <= ttoks:
            best = max(best, 2.0)  # same words, other order
        else:
            best = max(best, 1.5 * len(core & ttoks) / len(core))
    hits = sum(1 for kw in prefs.get("keywords") or [] if kw and _phrase_in(kw, title_low))
    return round(best + 0.5 * hits, 3)


def deal_breaker_hit(prefs: dict, title: str, description: str, employment: str = "") -> Optional[str]:
    head = "%s %s" % (title or "", employment or "")
    for phrase in prefs.get("deal_breakers") or []:
        phrase = (phrase or "").strip()
        if not phrase:
            continue
        if _phrase_in(phrase, head):
            return phrase
        if len(phrase.split()) > 1:
            if _phrase_in(phrase, description):
                return phrase
        elif _single_word_in_context(phrase, description):
            return phrase
    return None


def prefilter(item: dict, prefs: dict) -> Tuple[bool, str]:
    """Cheap filter before any LLM work. item keys: title, location, remote, description, employment."""
    ok, why = title_ok(item.get("title", ""), prefs)
    if not ok:
        return False, why
    ok, why = location_ok(item.get("location", ""), item.get("remote", "unknown"), prefs)
    if not ok:
        return False, why
    ok, why = country_ok(item, prefs)
    if not ok:
        return False, why
    hit = deal_breaker_hit(prefs, item.get("title", ""), item.get("description", ""), item.get("employment", ""))
    if hit:
        return False, "deal breaker: %s" % hit
    return True, ""


def reason_bucket(reason: str) -> str:
    return reason.split(":", 1)[0].strip().replace(" ", "_") if reason else ""


# ---------- misc normalizers ----------

def salary_from_text(text: str) -> str:
    """Find a '$150,000 - $200,000' style range in description text."""
    if not text:
        return ""
    m = re.search(
        r"(\$\s?\d{1,3}(?:,\d{3})+(?:\.\d+)?|\$\s?\d{2,3}(?:\.\d+)?\s?[kK])\s*(?:-|–|—|to)\s*"
        r"(?:USD\s*)?(\$?\s?\d{1,3}(?:,\d{3})+(?:\.\d+)?|\$?\s?\d{2,3}(?:\.\d+)?\s?[kK])",
        text,
    )
    if m:
        return "%s - %s" % (m.group(1).replace(" ", ""), m.group(2).replace(" ", ""))
    return ""


def norm_date(value: Any) -> Optional[str]:
    """ISO string, epoch ms/s, or 'N days ago' -> YYYY-MM-DD. None if unknown."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e11:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    s = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    if re.fullmatch(r"\d{10,13}", s):
        return norm_date(int(s))
    low = s.lower()
    now = datetime.now(timezone.utc)
    if low in ("today", "just now", "just posted") or re.search(r"\b(hour|minute)s?\s+ago\b", low):
        return now.strftime("%Y-%m-%d")
    if low == "yesterday":
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    m = re.search(r"(\d+)\+?\s*(day|week|month)s?\s+ago", low)
    if m:
        n = int(m.group(1))
        days = n * {"day": 1, "week": 7, "month": 30}[m.group(2)]
        return (now - timedelta(days=days)).strftime("%Y-%m-%d")
    return None


def stable_id_from(*parts: str) -> str:
    key = "|".join((p or "").strip().lower() for p in parts)
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def jd_markdown(job: dict, text: str) -> str:
    head = ["# %s" % job.get("title", ""), ""]
    meta = [
        ("Company", job.get("company")), ("Location", job.get("location")),
        ("Remote", job.get("remote")), ("Salary", job.get("salary")),
        ("Posted", job.get("posted_at")), ("Source", job.get("source")),
        ("URL", job.get("url")),
    ]
    for k, v in meta:
        if v:
            head.append("%s: %s  " % (k, v))
    head.append("")
    return "\n".join(head) + "\n" + (text or "").strip() + "\n"


# ---------- ingest ----------

def new_result() -> dict:
    return {"fetched": 0, "matched": 0, "new": 0, "known": 0, "new_ids": [], "errors": [],
            "filtered": {}}


def ingest(home: Path, items: List[dict], prefs: dict, result: dict, use_filter: bool = True,
           dry_run: bool = False, limit_per_company: Optional[int] = None) -> dict:
    """Prefilter and add normalized items. Each item has the job.json fields plus
    `description` (plain text) and optional `employment`."""
    per_company: Dict[str, int] = {}
    for it in items:
        result["fetched"] += 1
        if use_filter:
            ok, why = prefilter(it, prefs)
            if not ok:
                b = reason_bucket(why)
                result["filtered"][b] = result["filtered"].get(b, 0) + 1
                continue
        result["matched"] += 1
        job = jslib.new_job(
            it["source"], it["source_job_id"], it["company"], it["title"],
            location=it.get("location") or "", remote=it.get("remote") or "unknown",
            url=it.get("url") or "", apply_url=it.get("apply_url") or it.get("url") or "",
            salary=it.get("salary") or "", posted_at=it.get("posted_at"),
        )
        if jslib.load_job(home, job["id"]) is not None:
            result["known"] += 1
            continue
        ckey = jslib.slug(it["company"])
        if limit_per_company is not None and per_company.get(ckey, 0) >= limit_per_company:
            result["filtered"]["company_limit"] = result["filtered"].get("company_limit", 0) + 1
            continue
        per_company[ckey] = per_company.get(ckey, 0) + 1
        if dry_run:
            result["new"] += 1
            result["new_ids"].append(job["id"])
            continue
        if jslib.add_job(home, job, jd_markdown(job, it.get("description", ""))):
            result["new"] += 1
            result["new_ids"].append(job["id"])
        else:
            result["known"] += 1
    return result


def print_summary(result: dict, label: str = "scan") -> None:
    print("%s: fetched %d, matched %d, new %d, already known %d"
          % (label, result["fetched"], result["matched"], result["new"], result["known"]))
    if result.get("filtered"):
        parts = ", ".join("%s %d" % (k, v) for k, v in sorted(result["filtered"].items()))
        print("filtered out: %s" % parts)
    for jid in result.get("new_ids", [])[:50]:
        print("  new: %s" % jid)
    if len(result.get("new_ids", [])) > 50:
        print("  ... and %d more" % (len(result["new_ids"]) - 50))
    for e in result.get("errors", []):
        print("  error: %s" % e)
