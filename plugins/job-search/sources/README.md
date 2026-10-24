# Job sources

Each file in this folder tells Claude how to get jobs from one place. The scan skill
(`/job-search:scan`) reads `profile/sources.json`, and for every enabled source it either
runs `scripts/scan.py` (API sources) or follows the matching guide here (browser sources).

| Source | File | How jobs come in |
|---|---|---|
| Greenhouse | `greenhouse.md` | `scan.py`, public Job Board API |
| Lever | `lever.md` | `scan.py`, public Postings API |
| Ashby | `ashby.md` | `scan.py`, public Job Board API |
| Indeed | `indeed.md` | Claude in Chrome reads search results, then `add_job.py` |
| Dice | `dice.md` | Claude in Chrome reads search results, then `add_job.py` |
| LinkedIn | `linkedin.md` | Claude in Chrome reads a few saved searches, then `add_job.py` |

`check-access.md` checks, in the user's Chrome, whether Indeed, Dice and LinkedIn can be read
(signed in, no block page). Onboarding uses it instead of asking the user.

## Adding a new source

1. Add `<name>.md` to this folder. Copy the closest existing guide and change the parts
   that differ: where to search, how to read a result, which fields map to which job fields.
2. Add an entry for it under `sources` in `profile/sources.json`, with `enabled` and
   `has_access`. Browser sources also need `queries` (or saved search URLs) and `max_per_run`.
3. That is enough for a browser source. Claude follows the guide, writes a JSON list of jobs
   to a temp file and runs `add_job.py`, which applies the same prefilter and dedupe as the
   API scan.
4. Optional, for a site with a public JSON API: add a parser to `scripts/scan.py`
   (a URL template plus a `parse_<name>(payload, token, name)` function registered in
   `PARSERS` and `API_SOURCES`), and a recorded sample under `tests/fixtures/api/` with a
   test in `tests/test_sources.py`.

## The job object `add_job.py` accepts

```json
[
  {
    "source": "indeed",
    "source_job_id": "a1b2c3",
    "company": "Acme",
    "title": "Senior Platform Engineer",
    "location": "Remote, US",
    "remote": "remote",
    "employment": "Full-time",
    "url": "https://...",
    "apply_url": "https://...",
    "salary": "$180,000 - $210,000",
    "posted_at": "2026-10-20",
    "description": "Full job description, plain text or HTML"
  }
]
```

Only `company`, `title` and `source` are required. Leave a field out rather than guessing.
If `source_job_id` is missing, `add_job.py` derives a stable id from the URL, so always
include the URL. `posted_at` may be a date or text like "3 days ago".

## Rules for every source

- Read only. Never click Apply, Easy Apply, Submit, Save, Follow or Message.
- Never type into a site except its search box, and never change account settings.
- Go slowly: one page at a time, a short pause between postings.
- On a login wall, CAPTCHA, "unusual activity" page or anything that asks the user to act,
  stop that source, record a `source_error` signal and move on to the next source.
- Respect `max_per_run`.
