# Dice (browser)

Dice has no public API. Claude reads search results in the user's own Chrome through
Claude in Chrome (`mcp__claude-in-chrome__*` tools), then hands the jobs to `add_job.py`.

Run this only when `sources.dice.enabled` and `sources.dice.has_access` are both true.

## Rules

- Read only. Never click Apply, Easy Apply, Save, or anything that sends a message or form.
  Only navigate to URLs and read pages.
- Slow pace: wait 3 to 6 seconds between pages. Open postings one at a time.
- Stop after `max_per_run` postings (default 20) across all queries.
- On a sign-in wall, CAPTCHA, or "access denied" page, stop Dice for this run without trying
  to get past it. Record:
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal source_error --skill scan --detail "dice: <what you saw>"`
  and move on. Never wait for the user during a scheduled run.

## Steps

1. Load the Chrome tools in one ToolSearch call:
   `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__find,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_close_mcp`
   If they do not exist or no browser is connected, use the fallback at the end.
2. Call `tabs_context_mcp`, then open a new tab with `tabs_create_mcp`. Work only in that tab.
3. List the ids you already have: `ls "<home>/jobs" | grep '^dice-'`.
4. For each query `{"q": ..., "l": ...}` in `sources.dice.queries`, open:
   - normal location: `https://www.dice.com/jobs?q=<q>&location=<l>&filters.postedDate=SEVEN&page=1&pageSize=20`
   - when `l` is "Remote": `https://www.dice.com/jobs?q=<q>&filters.workplaceTypes=Remote&filters.postedDate=SEVEN&page=1&pageSize=20`
   URL-encode values. Use `page=2` for a second page. Read at most 2 pages per query.
5. Read the result cards with `get_page_text` (or `find` "job search result cards"). For each
   card note title, company, location, employment type and the job link. Links look like
   `https://www.dice.com/job-detail/<id>`; the `<id>` (a UUID) is the source_job_id.
   Skip a card if a folder in `<home>/jobs` starts with `dice-` and ends with `-<id>`.
6. Open each remaining `https://www.dice.com/job-detail/<id>` and read it with `get_page_text`. Take:
   - title, company, location
   - remote: from the workplace label (Remote, Hybrid, On-Site) if shown
   - employment: the employment type (Full-time, Contract, Contract to Hire, Third Party).
     The prefilter uses it for deal breakers such as "contract".
   - salary: the pay line as written, if any
   - posted_at: the posted date or "Posted N days ago"
   - description: the full job description as plain text, keeping bullets
   - url and apply_url: the job-detail URL
   - source: `dice`, source_job_id: `<id>`
7. Write all postings as one JSON list to a temp file (`TMP=$(mktemp -t jobsearch-dice).json`)
   using the shape in `sources/README.md`.
8. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/add_job.py" --home "<home>" --file "$TMP" --json`, keep the
   counts for the scan summary, then delete the temp file.
9. Close your tab with `tabs_close_mcp`.

## Fallback without Chrome

Use WebSearch, for example `"<q>" <l> site:dice.com/job-detail`, then WebFetch each result.
Skip pages that do not load or need a login. Use `source: "dice"` and the id from the URL.
Stay under `max_per_run` and ingest with `add_job.py` as above.
