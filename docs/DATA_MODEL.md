# Data model (contract)

Every script and skill must follow this file. All files are UTF-8 JSON unless noted.
Every top-level JSON object carries `"schema_version": 1`. Timestamps are ISO 8601 UTC
(`2026-10-24T15:04:05Z`), dates are `YYYY-MM-DD`.

Python scripts use the standard library only and must run on Python 3.9
(`from __future__ import annotations`, no `match`, no PEP 604 unions at runtime).
Shared helpers live in `plugins/job-search/scripts/jslib.py`. Use them; do not re-implement
home resolution, JSON IO, job ids, or signal logging.

## Home folder

Resolved by `jslib.resolve_home(arg)` in this order:
1. `--home` CLI argument
2. `$JOBSEARCH_HOME`
3. current working directory, if it contains `jobsearch.json`
4. `~/JobSearch`

```
<home>/
  jobsearch.json             # marker: {"schema_version":1,"created_at":...,"plugin_version":"0.1.0"}
  profile/
    fact-bank.json           # source of truth for everything the resume may say
    resume-master.md         # the user's original resume text (reference only)
    preferences.json
    sources.json
    gap-notes.json           # user flags on gaps: {"<gap_key>": {"status":"learning|ignore|done","note":""}}
  jobs/<job_id>/
    job.json                 # metadata + status (see below)
    jd.md                    # full job description text
    score.json               # written by the score skill
    resume.json              # tailored resume, every line cites fact ids
    resume.generated.json    # copy of resume.json as generated, for edit detection
    resume.html  resume.md  resume.pdf  # rendered (pdf optional, needs Chrome)
    changes.json             # change list, minor/major classification, verify result, approval
    answers.md               # cover note + prefilled screening answers
  gaps.json                  # derived; rebuilt by scripts/gaps.py from all score.json
  memory/
    signals.jsonl            # one JSON object per line
    lessons.json             # source of truth for lessons
    lessons.md               # rendered from lessons.json; skills read this first
    proposals.json
  runs/run-log.jsonl
  dashboard.html             # rebuilt by scripts/build_dashboard.py
```

## profile/fact-bank.json

```json
{
  "schema_version": 1,
  "person": {"name": "", "email": "", "phone": "", "location": "", "links": [{"label": "LinkedIn", "url": ""}]},
  "headlines": ["Platform Architect", "Principal Engineer"],
  "summary_facts": [{"id": "sum.1", "text": "15 years building platforms ..."}],
  "roles": [
    {
      "id": "r1", "company": "Acme", "title": "Lead Platform Architect",
      "title_aliases": ["Platform Architect"],
      "start": "2021-03", "end": "present", "location": "Denver, CO",
      "bullets": [
        {"id": "r1.b1", "text": "Led migration of 40 services to Kubernetes, cutting infra cost 30%",
         "skills": ["kubernetes", "aws"], "metrics": ["40", "30%"]}
      ]
    }
  ],
  "skills": [{"id": "s.kubernetes", "name": "Kubernetes", "level": "expert|working|familiar", "years": 6, "evidence": ["r1.b1"]}],
  "education": [{"id": "e1", "school": "", "degree": "", "year": "2010"}],
  "certifications": [{"id": "c1", "name": "AWS Solutions Architect Professional", "year": "2023"}],
  "projects": [{"id": "p1", "name": "", "text": "", "skills": []}]
}
```

Rules: ids are unique across the file. `metrics` lists every number/percentage that appears in the
bullet text. A skill's `years` is `null` unless the resume or the user states it
(never computed from role dates without the user's yes). `headlines` and `title_aliases` are the only titles the resume may use.

## profile/preferences.json

```json
{
  "schema_version": 1,
  "target_titles": ["Platform Architect", "AI Architect"],
  "keywords": ["platform", "kubernetes", "ai"],
  "seniority": ["senior", "staff", "principal", "lead"],
  "locations": ["Remote - US", "Denver, CO"],
  "remote": "remote|hybrid|onsite|any",
  "salary_min": 180000,
  "must_have": [],
  "deal_breakers": ["contract", "clearance required"],
  "exclude_title_words": ["marketing", "sales", "ios"],
  "countries": ["US"],
  "industries_like": [],
  "industries_avoid": [],
  "daily_cap": 5,
  "min_score": 3.5,
  "auto_approve_minor": true,
  "major_rewrite_ratio": 0.30
}
```

`countries` is optional; when empty it is inferred from `locations` ("Denver, CO" means US).
Jobs whose location names only other countries are skipped before scoring.
`exclude_title_words` drops a job before scoring when its title contains any of the words.

## profile/sources.json

```json
{
  "schema_version": 1,
  "sources": {
    "greenhouse": {"enabled": true, "has_access": true, "companies": ["stripe", "airbnb"]},
    "lever":      {"enabled": false, "has_access": true, "companies": []},
    "ashby":      {"enabled": false, "has_access": true, "companies": []},
    "indeed":     {"enabled": false, "has_access": false, "queries": [{"q": "platform architect", "l": "Remote"}], "max_per_run": 20},
    "dice":       {"enabled": false, "has_access": false, "queries": [{"q": "platform architect", "l": "Remote"}], "max_per_run": 20},
    "linkedin":   {"enabled": false, "has_access": false, "saved_search_urls": [], "max_per_run": 15}
  }
}
```

`has_access` is the user's onboarding confirmation that they are signed in / have an account.
API sources (greenhouse, lever, ashby) need no login, so `has_access` is always true.

## jobs/<job_id>/job.json

`job_id = jslib.make_job_id(source, company, source_job_id)` →
lowercase `<source>-<company-slug>-<source_job_id-slug>`, max 80 chars.

```json
{
  "schema_version": 1,
  "id": "greenhouse-stripe-6543210",
  "source": "greenhouse|lever|ashby|indeed|dice|linkedin|manual",
  "source_job_id": "6543210",
  "company": "Stripe",
  "title": "Staff Platform Engineer",
  "location": "Remote - US",
  "remote": "remote|hybrid|onsite|unknown",
  "url": "https://...",
  "apply_url": "https://...",
  "salary": "",
  "posted_at": "2026-10-20",
  "found_at": "2026-10-24T15:04:05Z",
  "status": "found",
  "status_history": [{"status": "found", "at": "2026-10-24T15:04:05Z", "note": ""}],
  "score": null,
  "recommendation": null,
  "approval": null,
  "dismissed_reason": null,
  "applied_at": null
}
```

`score`, `recommendation`, `approval` are denormalized copies (from score.json / changes.json)
so the dashboard can list jobs without opening every file. Update them with `jslib.set_status`
/ `jslib.update_job`.

Status values, in pipeline order:
`found` → `scored` → (`skipped` | `prepared` | `needs_approval`) → `applied` → `replied` → (`interview` | `rejected` | `offer`).
Plus `dismissed` (user said not interested) and `closed` (posting gone).

## jobs/<job_id>/score.json

```json
{
  "schema_version": 1,
  "job_id": "...",
  "score": 4.2,
  "recommendation": "apply|maybe|skip",
  "summary": "Two sentences on fit.",
  "matched": [{"requirement": "Kubernetes at scale", "evidence": ["r1.b1", "s.kubernetes"], "strength": "strong|partial"}],
  "missing": [{"item": "Terraform", "category": "hard_skill|tool|cert|domain|seniority|soft_skill|other", "required": true}],
  "keywords": ["platform engineering", "kubernetes"],
  "deal_breakers_hit": [],
  "scored_at": "..."
}
```

Score scale 1.0 to 5.0. `evidence` ids must exist in the fact bank.

## jobs/<job_id>/resume.json (tailored)

```json
{
  "schema_version": 1,
  "job_id": "...",
  "headline": "Platform Architect",
  "summary": {"text": "...", "source_ids": ["sum.1", "r1.b1"]},
  "roles": [
    {"role_id": "r1", "company": "Acme", "title": "Lead Platform Architect", "start": "2021-03", "end": "present", "location": "Denver, CO",
     "bullets": [{"text": "...", "source_ids": ["r1.b1"]}]}
  ],
  "skills": [{"name": "Kubernetes", "source_ids": ["s.kubernetes"]}],
  "education": ["e1"],
  "certifications": ["c1"],
  "projects": [{"id": "p1", "text": "...", "source_ids": ["p1"]}]
}
```

## jobs/<job_id>/changes.json

```json
{
  "schema_version": 1,
  "job_id": "...",
  "classification": "minor|major",
  "reasons": ["headline changed"],
  "rewrite_ratio": 0.18,
  "changes": [
    {"type": "reword|reorder|drop|add_section|remove_section|title_change|headline_change|summary_change|skill_promote",
     "target": "roles[0].bullets[1]", "before": "...", "after": "...", "source_ids": ["r1.b2"]}
  ],
  "verify": {"passed": true, "issues": [{"severity": "block|warn", "path": "roles[0].bullets[1]", "message": "number 45% not in sources"}]},
  "approval": "auto|pending|approved|rejected",
  "decided_at": null
}
```

Also written: `generated_hash`, `edits_logged_hash`, `edits_logged_at`, `classified_at`,
`decision_reason`, `verify.checked_at`, `verify.resume_hash`; `skill_promote` changes may carry
`level`, `reword` changes may carry `note`.

## gaps.json (derived)

```json
{
  "schema_version": 1,
  "updated_at": "...",
  "total_jds": 42,
  "items": {
    "terraform": {"name": "Terraform", "category": "tool", "count": 17, "required_count": 12,
                  "first_seen": "2026-10-01", "last_seen": "2026-10-24",
                  "job_ids": ["..."], "weekly": {"2026-W43": 5}}
  },
  "ranking": [{"key": "terraform", "score": 0.83, "share": 0.40}]
}
```

Gap key = `jslib.norm_key(item)`. Ranking excludes keys flagged `ignore` or `done` in gap-notes.json.

Career radar fields (only when `radar/latest.json` exists): an item whose canonical key matches a
radar `rising_skills[].skill` (or one part of it, such as "Terraform" in "Terraform / IaC") or a
`skill_demand` entry with `you: "gap"` gets `"rising": true`, `"rising_confidence"` and
`"rising_why"`, and its ranking score is multiplied by 1.15 (high confidence) or 1.08 (medium or
low). Ranking rows carry `"rising"`. Top level adds `"radar_as_of"` and `"radar_only_rising"`:
`[{"key", "skill", "confidence", "url"}]`, rising radar skills that no scored job asked for and the
fact bank does not list. The ledger itself stays built from the user's own scored jobs.

## memory

`signals.jsonl`, one per line, appended with `jslib.add_signal(home, type, **fields)`:
```json
{"id": "S-1a2b3c4d5e6f", "ts": "...", "type": "edit|reject_change|approve_change|dismiss|apply|repeat|frustration|outcome|override_score|source_error|note",
 "skill": "tailor", "job_id": "...", "detail": "short machine-ish description", "text": "user's own words if any"}
```

`lessons.json`:
```json
{"schema_version": 1, "lessons": [
  {"id": "L-001", "text": "Never use the word 'spearheaded'.", "scope": "all|scan|score|tailor|apply|gaps|dashboard|feedback|retro|run",
   "kind": "auto|approved", "status": "active|retired", "created": "...", "last_applied": null,
   "evidence": ["<signal id>", "..."], "source": "retro|feedback|user"}
]}
```

`proposals.json`:
```json
{"schema_version": 1, "proposals": [
  {"id": "P-001", "text": "Raise min_score to 4.0? You dismissed 9 of 10 jobs under 4.", "kind": "preference|source|fact_bank|cap|maintainer",
   "status": "pending|accepted|declined", "created": "...", "patch": {"file": "profile/preferences.json", "set": {"min_score": 4.0}}}
]}
```

Optional fields: lessons `retired_at`, `retired_reason`; proposals `evidence`, `decided_at`,
`applied`, `issue_file`. Patches support `set` and `append`, with dotted keys such as
`sources.dice.enabled`. Patches to `auto_approve_minor` or `major_rewrite_ratio` are refused.

Other memory files: `memory/maintainer-issue-<id>.md` (anonymized GitHub issue draft written when a
maintainer proposal is accepted).

Truthfulness rules and the approval gate can never be changed by a lesson or proposal.

## runs/

- `runs/nudge-<YYYY-MM-DD>.md`: weekly skills-gap nudge (gaps skill)
- `runs/retro-<YYYY-MM-DD>.md`: weekly retro summary (retro skill)

## runs/run-log.jsonl

```json
{"ts": "...", "kind": "daily|weekly|manual", "found": 12, "new": 4, "scored": 4, "prepared": 2, "needs_approval": 1, "errors": ["dice: not signed in"], "notes": ""}
```

## radar/ (Career Trend Radar)

Written by the `radar` skill through `scripts/radar.py save`.

- `radar/radar-<YYYY-MM-DD>.md`: the full report for the user.
- `radar/radar-<YYYY-MM-DD>.json` and `radar/latest.json`: the structured radar.

```json
{
  "schema_version": 1, "as_of": "2026-10-24", "saved_at": "...", "report": "radar/radar-2026-10-24.md",
  "verdict": "Best fit now: X. Top bet: Y.",
  "actions": [{"text": "...", "url": "https://..."}],
  "titles_now": [{"title": "...", "fit": "high|medium|low", "momentum": "high|medium|low", "why": "", "comp": "", "postings": []}],
  "skill_demand": [{"skill": "Kubernetes", "count": 14, "sample": 18, "required": 11, "you": "have|partial|gap"}],
  "rising_skills": [{"skill": "...", "confidence": "high|medium|low", "signals": [{"text": "", "url": "https://..."}]}],
  "emerging_titles": [{"title": "...", "confidence": "...", "horizon_months": 24, "fit": "...", "signals": [], "fit_note": "", "watch_for": ""}],
  "jd_shifts": [{"change": "...", "confidence": "...", "horizon_months": 12, "signals": []}],
  "titles_at_risk": [{"title": "...", "why": "", "signals": []}],
  "resume_language": [{"market_term": "...", "your_term": "...", "fact_ids": ["r1.b2"]}],
  "assumptions": [], "sources": [{"title": "", "publisher": "", "date": "", "url": "https://..."}]
}
```

Rules enforced by `radar.py save`: every forecast item (`rising_skills`, `emerging_titles`,
`jd_shifts`, `titles_at_risk`) needs at least one signal with a URL or it is dropped;
`resume_language` entries must cite existing fact bank ids or they are dropped.

Preference: `radar_every_days` (default 30, 0 = never refresh automatically).
The dashboard shows the radar in its Career radar tab and links the report;
`serve_dashboard.py` serves `radar/radar-<YYYY-MM-DD>.md` and no other radar file.
`radar.py propose` creates `preference` proposals that append high-fit titles to `target_titles`.
