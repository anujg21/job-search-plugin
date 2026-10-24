"""Shared helpers for job-search plugin scripts. Standard library only, Python 3.9+.

See docs/DATA_MODEL.md for every file layout referenced here.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

SCHEMA_VERSION = 1
PLUGIN_VERSION = "0.1.0"
MARKER = "jobsearch.json"

STATUSES = [
    "found", "scored", "skipped", "prepared", "needs_approval",
    "applied", "replied", "interview", "rejected", "offer",
    "dismissed", "closed",
]

SIGNAL_TYPES = {
    "edit", "reject_change", "approve_change", "dismiss", "apply", "repeat",
    "frustration", "outcome", "override_score", "source_error", "note",
}


# ---------- time ----------

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def iso_week(date_str: str) -> str:
    """'2026-10-24' or full ISO timestamp -> '2026-W43'."""
    d = datetime.strptime(date_str[:10], "%Y-%m-%d")
    y, w, _ = d.isocalendar()
    return "%d-W%02d" % (y, w)


# ---------- home ----------

def resolve_home(arg: Optional[str] = None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    env = os.environ.get("JOBSEARCH_HOME")
    if env:
        return Path(env).expanduser().resolve()
    cwd = Path.cwd()
    if (cwd / MARKER).exists():
        return cwd.resolve()
    return (Path.home() / "JobSearch").resolve()


def require_home(arg: Optional[str] = None) -> Path:
    home = resolve_home(arg)
    if not (home / MARKER).exists():
        raise SystemExit(
            "No job-search home at %s. Run /job-search:onboard first "
            "(or scripts/jobctl.py init --home <path>)." % home
        )
    return home


# ---------- json io ----------

def read_json(path: Path, default: Any = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    """Atomic write so a crashed run never leaves half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def append_jsonl(path: Path, obj: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


# ---------- text ----------

def slug(text: str, max_len: int = 40) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].strip("-") or "x"


def norm_key(item: str) -> str:
    """Normalize a skill/gap name to a stable key: 'Terraform (IaC)' -> 'terraform-iac'."""
    s = str(item).lower().strip()
    s = s.replace("+", "plus").replace("#", "sharp").replace(".js", "js")
    return slug(s, 60)


def posting_key(job: dict) -> Optional[tuple]:
    """(company, title) with case and punctuation ignored. Boards often post one role once per
    city; jobs with the same key are the same role for scoring and gap counting."""
    company = slug(job.get("company") or "", 60)
    title = slug(job.get("title") or "", 120)
    if company == "x" or title == "x":
        return None
    return (company, title)


def make_job_id(source: str, company: str, source_job_id: str) -> str:
    jid = "%s-%s-%s" % (slug(source, 12), slug(company, 30), slug(source_job_id, 40))
    return jid[:80].strip("-")


# ---------- profile ----------

def profile_path(home: Path, name: str) -> Path:
    return Path(home) / "profile" / name


def load_fact_bank(home: Path) -> dict:
    return read_json(profile_path(home, "fact-bank.json"), {}) or {}


def load_preferences(home: Path) -> dict:
    return read_json(profile_path(home, "preferences.json"), {}) or {}


def load_sources(home: Path) -> dict:
    return read_json(profile_path(home, "sources.json"), {"sources": {}}) or {"sources": {}}


def fact_index(fact_bank: dict) -> dict:
    """Map every fact id -> the object that owns it (bullet, role, skill, ...)."""
    idx = {}
    for s in fact_bank.get("summary_facts", []) or []:
        idx[s["id"]] = s
    for r in fact_bank.get("roles", []) or []:
        idx[r["id"]] = r
        for b in r.get("bullets", []) or []:
            idx[b["id"]] = b
    for key in ("skills", "education", "certifications", "projects"):
        for x in fact_bank.get(key, []) or []:
            if "id" in x:
                idx[x["id"]] = x
    return idx


# ---------- jobs ----------

def jobs_dir(home: Path) -> Path:
    return Path(home) / "jobs"


def job_dir(home: Path, job_id: str) -> Path:
    return jobs_dir(home) / job_id


def load_job(home: Path, job_id: str) -> Optional[dict]:
    return read_json(job_dir(home, job_id) / "job.json")


def iter_jobs(home: Path) -> Iterator[dict]:
    d = jobs_dir(home)
    if not d.exists():
        return
    for p in sorted(d.iterdir()):
        j = read_json(p / "job.json") if p.is_dir() else None
        if j:
            yield j


def save_job(home: Path, job: dict) -> None:
    write_json(job_dir(home, job["id"]) / "job.json", job)


def new_job(source: str, source_job_id: str, company: str, title: str, **fields: Any) -> dict:
    ts = now_iso()
    job = {
        "schema_version": SCHEMA_VERSION,
        "id": make_job_id(source, company, source_job_id),
        "source": source,
        "source_job_id": str(source_job_id),
        "company": company,
        "title": title,
        "location": "",
        "remote": "unknown",
        "url": "",
        "apply_url": "",
        "salary": "",
        "posted_at": None,
        "found_at": ts,
        "status": "found",
        "status_history": [{"status": "found", "at": ts, "note": ""}],
        "score": None,
        "recommendation": None,
        "approval": None,
        "dismissed_reason": None,
        "applied_at": None,
    }
    for k, v in fields.items():
        if k in job and v is not None:
            job[k] = v
    return job


def add_job(home: Path, job: dict, jd_text: str = "") -> bool:
    """Create the job folder if new. Returns True if the job was new."""
    d = job_dir(home, job["id"])
    if (d / "job.json").exists():
        return False
    save_job(home, job)
    if jd_text:
        (d / "jd.md").write_text(jd_text, encoding="utf-8")
    return True


def update_job(home: Path, job_id: str, **fields: Any) -> dict:
    job = load_job(home, job_id)
    if job is None:
        raise SystemExit("Unknown job id: %s" % job_id)
    job.update(fields)
    save_job(home, job)
    return job


def set_status(home: Path, job_id: str, status: str, note: str = "") -> dict:
    if status not in STATUSES:
        raise SystemExit("Unknown status %r. Valid: %s" % (status, ", ".join(STATUSES)))
    job = load_job(home, job_id)
    if job is None:
        raise SystemExit("Unknown job id: %s" % job_id)
    ts = now_iso()
    job["status"] = status
    job.setdefault("status_history", []).append({"status": status, "at": ts, "note": note})
    if status == "applied" and not job.get("applied_at"):
        job["applied_at"] = ts
    if status == "dismissed" and note:
        job["dismissed_reason"] = note
    save_job(home, job)
    return job


# ---------- memory ----------

def add_signal(home: Path, type: str, **fields: Any) -> dict:
    if type not in SIGNAL_TYPES:
        raise SystemExit("Unknown signal type %r. Valid: %s" % (type, ", ".join(sorted(SIGNAL_TYPES))))
    sig = {"id": "S-" + uuid.uuid4().hex[:12], "ts": now_iso(), "type": type}
    sig.update({k: v for k, v in fields.items() if v is not None})
    append_jsonl(Path(home) / "memory" / "signals.jsonl", sig)
    return sig


def log_run(home: Path, **fields: Any) -> dict:
    entry = {"ts": now_iso()}
    entry.update(fields)
    append_jsonl(Path(home) / "runs" / "run-log.jsonl", entry)
    return entry
