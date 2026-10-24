"""Helpers shared by the tailoring scripts (verify, classify, render, approve, detect_edits).

Standard library only, Python 3.9+. See docs/DATA_MODEL.md for resume.json / changes.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402

# ---------- hashing ----------


def canonical_hash(obj) -> str:
    data = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def file_hash(path: Path) -> Optional[str]:
    obj = jslib.read_json(path)
    if obj is None:
        return None
    return canonical_hash(obj)


# ---------- baseline (master) resume ----------


def master_summary_text(fb: dict) -> str:
    parts = []
    for s in fb.get("summary_facts", []) or []:
        t = (s.get("text") or "").strip()
        if t:
            parts.append(t if t.endswith((".", "!", "?")) else t + ".")
    return " ".join(parts)


def build_master(fb: dict, job_id: str = "") -> dict:
    """The untailored resume: every role and bullet in fact-bank order, first headline."""
    roles = []
    for r in fb.get("roles", []) or []:
        roles.append({
            "role_id": r["id"],
            "company": r.get("company", ""),
            "title": r.get("title", ""),
            "start": r.get("start", ""),
            "end": r.get("end", ""),
            "location": r.get("location", ""),
            "bullets": [{"text": b.get("text", ""), "source_ids": [b["id"]]}
                        for b in r.get("bullets", []) or []],
        })
    headlines = fb.get("headlines") or []
    headline = headlines[0] if headlines else (roles[0]["title"] if roles else "")
    return {
        "schema_version": jslib.SCHEMA_VERSION,
        "job_id": job_id,
        "headline": headline,
        "summary": {"text": master_summary_text(fb),
                    "source_ids": [s["id"] for s in fb.get("summary_facts", []) or []]},
        "roles": roles,
        "skills": [{"name": s.get("name", ""), "source_ids": [s["id"]]} for s in fb.get("skills", []) or []],
        "education": [e["id"] for e in fb.get("education", []) or []],
        "certifications": [c["id"] for c in fb.get("certifications", []) or []],
        "projects": [{"id": p["id"], "text": p.get("text", ""), "source_ids": [p["id"]]}
                     for p in fb.get("projects", []) or []],
    }


def bullet_owner(fb: dict) -> dict:
    """bullet id -> role id."""
    out = {}
    for r in fb.get("roles", []) or []:
        for b in r.get("bullets", []) or []:
            out[b["id"]] = r["id"]
    return out


def iter_lines(resume: dict):
    """Yield (path, text, source_ids, role_id) for every text line that must cite sources."""
    s = resume.get("summary") or {}
    if (s.get("text") or "").strip():
        yield "summary", s.get("text", ""), list(s.get("source_ids") or []), None
    for i, r in enumerate(resume.get("roles", []) or []):
        for j, b in enumerate(r.get("bullets", []) or []):
            yield "roles[%d].bullets[%d]" % (i, j), b.get("text", ""), list(b.get("source_ids") or []), r.get("role_id")
    for i, p in enumerate(resume.get("projects", []) or []):
        yield "projects[%d]" % i, p.get("text", ""), list(p.get("source_ids") or ([p["id"]] if p.get("id") else [])), None


def resume_text(resume: dict) -> str:
    """Flatten a resume into plain text (used for rewrite ratio and word counts)."""
    out = [resume.get("headline", "")]
    out.append((resume.get("summary") or {}).get("text", ""))
    for r in resume.get("roles", []) or []:
        out.append("%s %s" % (r.get("title", ""), r.get("company", "")))
        for b in r.get("bullets", []) or []:
            out.append(b.get("text", ""))
    out.append(", ".join(s.get("name", "") for s in resume.get("skills", []) or []))
    for p in resume.get("projects", []) or []:
        out.append(p.get("text", ""))
    return "\n".join(x for x in out if x)


def words(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+(?:[.'][a-z0-9]+)*|[%$]", (text or "").lower())


# ---------- numbers ----------

_SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mm": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}
_UNITS = ("hour", "day", "week", "month", "quarter", "year", "minute", "second", "sprint")
_WORD_NUMS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100, "dozen": 12,
}

_NUM_RE = re.compile(
    r"(?<![\w./])(?P<money>\$\s?)?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?P<plus>\+)?"
    r"(?:\s?(?P<suffix>%|percent\b|per\s?cent\b|[kKmMbB]\b|mm\b|x\b|million\b|billion\b|thousand\b))?(?P<plus2>\+)?"
)
_WORD_RE = re.compile(
    r"\b(?P<word>%s)\b(?=[\s-]+(?P<after>percent|per cent|million|billion|thousand|(?:%s)s?)\b)"
    % ("|".join(_WORD_NUMS), "|".join(_UNITS)),
    re.I,
)
_UNIT_RE = re.compile(r"^[\s-]*(%s)s?\b" % "|".join(_UNITS), re.I)
_IGNORE_RE = re.compile(r"24\s*/\s*7|365\s*/\s*24", re.I)
# "over 200", "more than 40": the claim is a lower bound, true only if a source number is bigger.
_LOWER_RE = re.compile(r"\b(?:over|more than|upwards of|in excess of|at least|north of|exceeding|greater than)\s*$", re.I)
_RATE_RE = re.compile(
    r"^[^.;,()\d]{0,40}?(?:\b(?:per|a|an|each|every)\s+(?P<per>hour|day|week|month|quarter|year)\b"
    r"|\b(?P<adv>hourly|daily|weekly|monthly|quarterly|yearly|annually)\b)", re.I)
_RATE_ADV = {"hourly": "hour", "daily": "day", "weekly": "week", "monthly": "month",
             "quarterly": "quarter", "yearly": "year", "annually": "year"}
_FRACTION_RE = re.compile(
    r"\b(?:(?P<numer>a|one|two|three|four)[\s-]+)?(?P<den>thirds?|quarters?|half|fifths?)\b", re.I)
_FRACTION_DEN = {"third": 3, "quarter": 4, "half": 2, "fifth": 5}
_NUMER = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4}
_FRACTION_CONTEXT = re.compile(r"\b(?:by|cut|cutting|reduc\w*|lower\w*|nearly|almost|over|roughly|about|in|"
                               r"saving|saved|improv\w*|increas\w*|decreas\w*)\s+$", re.I)
_MULT_WORDS = {"doubled": ("mult", 2), "doubling": ("mult", 2), "tripled": ("mult", 3), "tripling": ("mult", 3),
               "quadrupled": ("mult", 4), "quadrupling": ("mult", 4), "twofold": ("mult", 2),
               "two-fold": ("mult", 2), "threefold": ("mult", 3), "three-fold": ("mult", 3),
               "tenfold": ("mult", 10), "ten-fold": ("mult", 10), "halved": ("pct", 50), "halving": ("pct", 50)}
_MULT_RE = re.compile(r"\b(%s)\b" % "|".join(re.escape(k) for k in _MULT_WORDS), re.I)
_DECADE_RE = re.compile(r"\b(?P<n>a|one|two|three|four|\d+)\s+decades?\b", re.I)
_ZERO_RE = re.compile(r"\bzero\b", re.I)
# Magnitude words that stand in for a number. The fact bank always has the exact number.
VAGUE_QUANTITY_RE = re.compile(
    r"\b(?:tens of thousands|hundreds of thousands|dozens|a dozen|hundreds|thousands|millions|billions|"
    r"scores of|countless|myriad|innumerable)\b", re.I)


def _unit_after(text: str, pos: int) -> Optional[str]:
    m = _UNIT_RE.match(text[pos:pos + 20])
    return m.group(1).lower() if m else None


def _rate_after(text: str, pos: int) -> Optional[str]:
    m = _RATE_RE.match(text[pos:pos + 60])
    if not m:
        return None
    return (m.group("per") or _RATE_ADV[m.group("adv").lower()]).lower()


def _lower_before(text: str, pos: int) -> bool:
    return bool(_LOWER_RE.search(text[max(0, pos - 20):pos]))


def extract_numbers(text: str) -> List[dict]:
    """Find numbers, percentages, money and durations. Returns dicts with raw/value/kind/unit.

    kind is 'pct', 'money', 'mult' or 'plain'. unit is a time unit for durations, else None.
    rate is the time unit of "per month" / "daily" after the number, else None.
    lower is True for "40+", "over 40", "more than 40" (a lower bound).
    approx is True for fractions ("a third"), compared with a small tolerance.
    Numbers glued to letters (S3, EC2, k8s, OAuth2) are ignored. Also understands fractions
    ("a third", "in half"), multiplier words ("doubled", "halved"), decades and "zero".
    """
    text = _IGNORE_RE.sub(" ", text or "")
    out = []

    def add(raw, value, kind, unit, start, end, plus=False):
        lower = plus or _lower_before(text, start)
        out.append({"raw": raw.strip(), "value": round(value, 6), "kind": kind, "unit": unit,
                    "rate": _rate_after(text, end), "lower": lower, "approx": False})
        return out[-1]

    for m in _NUM_RE.finditer(text):
        end = m.end()
        if not m.group("suffix") and not m.group("plus") and end < len(text) and text[end].isalpha():
            continue  # 2FA, 3D, 10GB stays a token; only bare numbers count
        value = float(m.group("num").replace(",", ""))
        suffix = (m.group("suffix") or "").lower().replace(" ", "")
        kind = "plain"
        if suffix in ("%", "percent"):
            kind = "pct"
        elif suffix == "x":
            kind = "mult"
        elif suffix in _SCALE:
            value *= _SCALE[suffix]
        if m.group("money"):
            kind = "money"
        unit = _unit_after(text, end) if kind == "plain" else None
        add(m.group(0), value, kind, unit, m.start(), end, bool(m.group("plus") or m.group("plus2")))
    for m in _WORD_RE.finditer(text):
        value = float(_WORD_NUMS[m.group("word").lower()])
        after = m.group("after").lower()
        kind, unit = "plain", None
        if after.startswith("per"):
            kind = "pct"
        elif after in _SCALE:
            value *= _SCALE[after]
        else:
            unit = after.rstrip("s") if after.rstrip("s") in _UNITS else after
        add(m.group(0), value, kind, unit, m.start(), m.end())
    for m in _FRACTION_RE.finditer(text):
        den_word = m.group("den").lower().rstrip("s")
        before = text[max(0, m.start() - 25):m.start()]
        after = text[m.end():m.end() + 4].lower()
        if den_word == "quarter" and not (after.startswith(" of") or re.search(r"\bby\s+$", before, re.I)):
            continue  # "in a quarter" is a time span
        if den_word == "half" and re.search(r"\b(first|second|1st|2nd)\s+$", before, re.I):
            continue
        if not (after.startswith(" of") or _FRACTION_CONTEXT.search(before)):
            continue
        numer = _NUMER.get((m.group("numer") or "a").lower(), 1)
        n = add(m.group(0), 100.0 * numer / _FRACTION_DEN[den_word], "pct", None, m.start(), m.end())
        n["approx"] = True
    for m in _MULT_RE.finditer(text):
        kind, value = _MULT_WORDS[m.group(1).lower()]
        add(m.group(0), value, kind, None, m.start(), m.end())
    for m in _DECADE_RE.finditer(text):
        n = m.group("n").lower()
        value = float(n) if n.isdigit() else float(_NUMER[n])
        add(m.group(0), value * 10, "plain", "year", m.start(), m.end())
    for m in _ZERO_RE.finditer(text):
        add(m.group(0), 0.0, "plain", None, m.start(), m.end())
    return out


def _same_kind(n: dict, p: dict) -> bool:
    if n["kind"] in ("pct", "money", "mult") and p["kind"] != n["kind"]:
        return False
    if n["unit"] and p["unit"] != n["unit"]:
        return False
    if n.get("rate") and p.get("rate") and n["rate"] != p["rate"]:
        return False
    return True


def number_supported(n: dict, pool: List[dict]) -> bool:
    """Exact match on value, kind, duration unit and rate. A lower bound ("200+", "over 200")
    needs a source number above it (at most twice as big), or the same bound in the source."""
    for p in pool:
        if not _same_kind(n, p):
            continue
        if n.get("lower"):
            # "over 200" from 220 is fine; "over 40" is not backed by an unrelated 2021.
            if n["value"] < p["value"] <= 2 * n["value"] or (p.get("lower") and p["value"] == n["value"]):
                return True
            continue
        if p.get("lower"):
            continue
        tol = 1.0 if n.get("approx") or p.get("approx") else 0.0
        if abs(p["value"] - n["value"]) <= tol:
            return True
    return False


_RANGE_RE = re.compile(r"(?<![\w.$])(\d+)\s*(?:to|-|–|through)\s*(\d+)(?![\w.%])")


def number_ranges(text: str) -> List[tuple]:
    """(low, high) pairs written as "6 to 12" or "6-12" (plain numbers, no unit between)."""
    out = []
    for m in _RANGE_RE.finditer(text or ""):
        lo, hi = float(m.group(1)), float(m.group(2))
        if lo < hi and hi < 1900:
            out.append((lo, hi))
    return out


def vague_quantities(text: str) -> List[str]:
    return [m.group(0) for m in VAGUE_QUANTITY_RE.finditer(text or "")]


# ---------- verbs: scope ladder ----------

# Ownership ladder. A tailored line may not use a verb stronger than the strongest verb in
# the facts it cites. A fact with no ladder verb counts as level 3 (did the work).
VERB_LADDER = [
    # contributed < helped in spirit, but they are interchangeable on a resume: one tier.
    (1, ["contributed", "contributes", "contributing", "assisted", "assists", "assisting",
         "participated", "participates", "participating", "supported", "helped", "helps", "helping"]),
    (3, ["built", "designed", "developed", "created", "implemented", "introduced", "wrote", "shipped",
         "delivered", "launched", "established", "architected", "engineered", "migrated", "automated",
         "authored", "rebuilt", "set up"]),
    (4, ["led", "lead", "leads", "leading", "managed", "manages", "managing", "directed", "directs",
         "directing", "drove", "spearheaded", "spearheading", "oversaw", "oversees", "overseeing",
         "supervised", "supervising", "orchestrated"]),
    (5, ["owned", "owns", "owning"]),
    (6, ["headed", "heads"]),
]
LADDER_NAMES = {1: "contributed/helped", 3: "built", 4: "led", 5: "owned", 6: "headed"}
DEFAULT_VERB_LEVEL = 3
_VERB_LEVEL = {w: lvl for lvl, ws in VERB_LADDER for w in ws}
_VERB_RE = re.compile(r"(?<![A-Za-z-])(%s)(?![A-Za-z-])" % "|".join(
    sorted((re.escape(w) for w in _VERB_LEVEL), key=len, reverse=True)), re.I)
# "managed Kubernetes", "to a managed service": adjective, not a scope claim.
_ADJ_BEFORE = re.compile(r"\b(?:to|on|onto|a|an|the|fully|into|in|with|self|as)[\s-]+$", re.I)


def ladder_verbs(text: str) -> List[tuple]:
    """[(level, word)] for ownership-ladder verbs in text."""
    out = []
    for m in _VERB_RE.finditer(text or ""):
        w = m.group(1).lower()
        if w.startswith("manag") and _ADJ_BEFORE.search(text[max(0, m.start() - 12):m.start()]):
            continue
        out.append((_VERB_LEVEL[w], m.group(1)))
    return out


def verb_level(text: str, default: Optional[int] = None) -> Optional[int]:
    v = ladder_verbs(text)
    return max(l for l, _ in v) if v else default


# ---------- tech terms ----------

# Common tools and technologies. Matching is case-insensitive on word boundaries.
BUILTIN_TECH = [
    "terraform", "pulumi", "ansible", "chef", "puppet", "saltstack", "cloudformation", "crossplane",
    "kubernetes", "k8s", "docker", "podman", "helm", "kustomize", "argo cd", "argocd", "flux", "istio",
    "linkerd", "envoy", "consul", "vault", "nomad", "openshift", "rancher", "eks", "gke", "aks", "ecs",
    "fargate", "lambda", "aws", "gcp", "google cloud", "azure", "openstack", "cloudflare",
    "jenkins", "github actions", "gitlab", "gitlab ci", "circleci", "travis ci", "buildkite", "spinnaker",
    "tekton", "bazel", "gradle", "maven",
    "prometheus", "grafana", "datadog", "new relic", "splunk", "elk", "elasticsearch", "opensearch",
    "kibana", "logstash", "opentelemetry", "jaeger", "pagerduty", "honeycomb", "sentry",
    "kafka", "rabbitmq", "pulsar", "kinesis", "sqs", "sns", "nats", "redis", "memcached",
    "postgresql", "postgres", "mysql", "mariadb", "mongodb", "cassandra", "dynamodb", "cockroachdb",
    "snowflake", "bigquery", "redshift", "databricks", "spark", "hadoop", "airflow", "dbt", "flink",
    "python", "java", "javascript", "typescript", "golang", "rust", "scala", "kotlin", "ruby", "php",
    "c++", "c#", ".net", "node.js", "nodejs", "react", "angular", "vue", "django", "flask", "fastapi",
    "spring boot", "rails", "graphql", "grpc", "rest", "bash", "powershell", "perl", "haskell", "elixir",
    "erlang", "swift", "go",
    "pytorch", "tensorflow", "langchain", "llamaindex", "openai", "bedrock", "aws bedrock", "sagemaker",
    "vertex ai", "hugging face", "mlflow", "kubeflow", "ray", "vector database", "pinecone", "rag",
    "backstage", "linux", "windows server", "nginx", "haproxy", "sre", "soc 2", "soc2", "fedramp",
    "pci", "pci dss", "hipaa", "iso 27001", "okta", "oauth", "saml", "keycloak",
    "cka", "ckad", "cks", "cissp", "pmp", "certified kubernetes administrator", "aws certified",
    "scrum master", "csm", "togaf", "itil", "ccna", "ccnp", "comptia", "security+",
    "cdk", "aws cdk", "argo", "argo workflows", "argo rollouts", "fluxcd", "tf", "amazon web services",
    "azure devops", "bitbucket", "jira", "confluence", "new relic", "dynatrace", "victoriametrics",
    "loki", "tempo", "thanos", "cilium", "calico", "karpenter", "packer", "serverless", "cloud run",
    "app engine", "cloud functions", "step functions", "eventbridge", "aurora", "rds", "s3", "ec2",
]

# Words that are also ordinary English. Matched only when written capitalized mid-sentence.
AMBIGUOUS = {"go", "rust", "swift", "chef", "puppet", "spring", "ray", "flux", "vault", "consul",
             "envoy", "rest", "lambda", "react", "rails", "nomad", "ruby", "spark", "flask", "helm",
             "tempo", "loki", "calico", "packer", "serverless", "aurora", "argo"}
# Short acronyms that collide with words or other uses; matched only when written in capitals.
UPPER_ONLY = {"tf", "csm", "rds"}
# Fact-bank tags that are not technologies. Never checked.
GENERIC = {"apis", "api", "mentoring", "leadership", "communication", "platform engineering",
           "management", "architecture", "design", "testing", "agile", "scrum", "c", "r"}

ALIASES = {
    "k8s": ["kubernetes"], "kubernetes": ["k8s"], "golang": ["go"], "go": ["golang"],
    "postgres": ["postgresql"], "postgresql": ["postgres"], "gcp": ["google cloud"],
    "google cloud": ["gcp"], "nodejs": ["node.js"], "node.js": ["nodejs"], "argocd": ["argo cd"],
    "argo cd": ["argocd"], "soc2": ["soc 2"], "soc 2": ["soc2"], "bedrock": ["aws bedrock"],
    "aws bedrock": ["bedrock"], "eks": ["aws eks", "amazon eks"], "llm": ["llms", "large language model"],
    "tf": ["terraform"], "amazon web services": ["aws"], "aws": ["amazon web services"], "fluxcd": ["flux"],
    "cka": ["certified kubernetes administrator"], "certified kubernetes administrator": ["cka"],
}

TECH_MISSING_CATEGORIES = {"hard_skill", "tool", "cert"}


def _norm_term(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip().lower())


def _term_pattern(term: str, case_sensitive: bool = False):
    esc = re.escape(term)
    flags = 0 if case_sensitive else re.I
    return re.compile(r"(?<![A-Za-z0-9])" + esc + r"(?![A-Za-z0-9+#])", flags)


def term_in_text(term: str, text: str) -> bool:
    t = _norm_term(term)
    if t in UPPER_ONLY:
        return bool(_term_pattern(t.upper(), case_sensitive=True).search(text or ""))
    if t in AMBIGUOUS:
        cap = t[:1].upper() + t[1:]
        for m in _term_pattern(cap, case_sensitive=True).finditer(text or ""):
            before = (text or "")[:m.start()].rstrip()
            if before and before[-1] not in ".!?:;":
                return True
        return False
    return bool(_term_pattern(t).search(text or ""))


def term_supported(term: str, blob: str) -> bool:
    t = _norm_term(term)
    for cand in [t] + ALIASES.get(t, []):
        if _term_pattern(cand).search(blob):
            return True
    return False


def build_term_list(fb: dict, score: Optional[dict]) -> List[str]:
    """Known tech terms to police in resume text."""
    terms = set(_norm_term(t) for t in BUILTIN_TECH)
    for s in fb.get("skills", []) or []:
        terms.add(_norm_term(s.get("name", "")))
    for r in fb.get("roles", []) or []:
        for b in r.get("bullets", []) or []:
            for t in b.get("skills", []) or []:
                terms.add(_norm_term(t))
    for p in fb.get("projects", []) or []:
        for t in p.get("skills", []) or []:
            terms.add(_norm_term(t))
    if score:
        builtin = set(_norm_term(t) for t in BUILTIN_TECH)
        for k in score.get("keywords", []) or []:
            if _norm_term(k) in builtin:
                terms.add(_norm_term(k))
        for m in score.get("missing", []) or []:
            if m.get("category") in TECH_MISSING_CATEGORIES and len((m.get("item") or "").split()) <= 4:
                terms.add(_norm_term(m.get("item", "")))
    return sorted(t for t in terms if t and t not in GENERIC and len(t) > 1)


def source_blob(ids: Iterable[str], idx: dict) -> str:
    """Lowercased text of cited facts plus their skill tags and names."""
    parts = []
    for i in ids:
        f = idx.get(i)
        if not f:
            continue
        for key in ("text", "name", "title", "company", "degree", "school"):
            if f.get(key):
                parts.append(str(f[key]))
        parts.extend(f.get("skills", []) or [])
        parts.extend(f.get("title_aliases", []) or [])
    return " | ".join(parts).lower()


def load_job_bundle(home: Path, job_id: str):
    d = jslib.job_dir(home, job_id)
    return {
        "dir": d,
        "job": jslib.load_job(home, job_id),
        "resume": jslib.read_json(d / "resume.json"),
        "score": jslib.read_json(d / "score.json"),
        "changes": jslib.read_json(d / "changes.json"),
    }


def empty_changes(job_id: str) -> dict:
    return {
        "schema_version": jslib.SCHEMA_VERSION,
        "job_id": job_id,
        "classification": None,
        "reasons": [],
        "rewrite_ratio": None,
        "changes": [],
        "verify": None,
        "approval": None,
        "decided_at": None,
    }
