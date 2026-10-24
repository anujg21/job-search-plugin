# LinkedIn (browser, low volume)

LinkedIn's terms forbid automated scraping and bots. This guide keeps volume low and reads
only what the user would see by opening their own saved searches. Claude uses the user's
logged-in Chrome through Claude in Chrome (`mcp__claude-in-chrome__*` tools) and hands the
jobs to `add_job.py`.

Run this only when `sources.linkedin.enabled` and `sources.linkedin.has_access` are both true.

## Rules

- Read only. Never click Apply, Easy Apply, Save, Follow, Connect, Message, or any button that
  sends something. Never fill in a form. Only navigate to URLs and read pages.
- Low volume: at most `max_per_run` postings (default 15) per run, at most 3 searches,
  and only the first page of each search.
- Slow pace: wait 5 to 10 seconds between postings.
- If LinkedIn shows a sign-in page, an "authwall", a security check or CAPTCHA, or the URL
  contains `/checkpoint/` or `/authwall`, stop LinkedIn for this run at once. Do not try to
  get past it. Record:
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal source_error --skill scan --detail "linkedin: <what you saw>"`
  and move on. Never wait for the user during a scheduled run.

## Steps

1. Load the Chrome tools in one ToolSearch call:
   `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__find,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_close_mcp`
   If they do not exist or no browser is connected, use the fallback at the end.
2. Call `tabs_context_mcp`, then open a new tab with `tabs_create_mcp`. Work only in that tab.
3. List the ids you already have: `ls "<home>/jobs" | grep '^linkedin-'`.
4. Pick the searches:
   - Use `sources.linkedin.saved_search_urls` first (up to 3).
   - If that list is empty, build up to 2 URLs from `sources.linkedin.queries` if present,
     otherwise from the first two `target_titles` in `profile/preferences.json`:
     `https://www.linkedin.com/jobs/search/?keywords=<q>&location=<l>&f_TPR=r604800&sortBy=DD`
     Add `&f_WT=2` for remote only (`f_WT=1` onsite, `f_WT=3` hybrid; join with `%2C`).
     Use "United States" as `<l>` when the preference is remote in the US.
     `f_TPR=r604800` limits results to the last 7 days.
5. Open each search and read the result list with `get_page_text`. For each card note title,
   company, location and the job id. The id is the number in `/jobs/view/<id>/` or in the
   `currentJobId=<id>` URL parameter. Skip ids already in `<home>/jobs` (a folder starting
   with `linkedin-` and ending with `-<id>`). Skip cards marked "Promoted" when they do not
   match the target titles.
6. Open each remaining job at `https://www.linkedin.com/jobs/view/<id>/` and read it with
   `get_page_text`. If the description is cut off behind a "See more" or "Show more" control,
   you may click that one control; it only expands text. Take:
   - title, company, location (as shown)
   - remote: from the workplace label (Remote, Hybrid, On-site)
   - employment: the job type (Full-time, Contract, ...)
   - salary: the pay line if shown
   - posted_at: "N days ago" text or a date
   - description: the full "About the job" text, keeping bullets
   - url and apply_url: `https://www.linkedin.com/jobs/view/<id>/`
   - source: `linkedin`, source_job_id: `<id>`
7. Write all postings as one JSON list to a temp file (`TMP=$(mktemp -t jobsearch-linkedin).json`)
   using the shape in `sources/README.md`.
8. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/add_job.py" --home "<home>" --file "$TMP" --json`, keep the
   counts for the scan summary, then delete the temp file.
9. Close your tab with `tabs_close_mcp`.

## Fallback without Chrome

Do not fetch LinkedIn pages without the user's browser. Instead use WebSearch for the same
titles on public ATS boards, for example
`"<title>" remote (site:boards.greenhouse.io OR site:jobs.lever.co OR site:jobs.ashbyhq.com)`,
WebFetch each result, and ingest them with `add_job.py` using the ATS name as `source` and the
posting id from the URL as `source_job_id`. Stay under `max_per_run`.
