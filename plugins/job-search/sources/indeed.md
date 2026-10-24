# Indeed (browser)

Indeed has no public API. Claude reads search results in the user's own Chrome through
Claude in Chrome (`mcp__claude-in-chrome__*` tools), then hands the jobs to `add_job.py`.

Run this only when `sources.indeed.enabled` and `sources.indeed.has_access` are both true.

## Rules

- Read only. Never click Apply, "Apply now", "Apply on company site", Save, or any button that
  sends something. Only navigate to URLs and read pages.
- Slow pace: wait 3 to 6 seconds between pages. Open postings one at a time.
- Stop after `max_per_run` postings (default 20) across all queries.
- If you see a sign-in wall, a CAPTCHA, "verify you are human", or an "unusual activity" page,
  stop Indeed for this run. Do not try to solve it. Record:
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal source_error --skill scan --detail "indeed: <what you saw>"`
  and move on. Never wait for the user during a scheduled run.

## Steps

1. Load the Chrome tools in one ToolSearch call:
   `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__find,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_close_mcp`
   If they do not exist or no browser is connected, use the fallback at the end.
2. Call `tabs_context_mcp`, then open a new tab with `tabs_create_mcp`. Work only in that tab.
3. List the ids you already have so you can skip them: `ls "<home>/jobs" | grep '^indeed-'`.
4. For each query `{"q": ..., "l": ...}` in `sources.indeed.queries`, open:
   `https://www.indeed.com/jobs?q=<q>&l=<l>&fromage=7&sort=date`
   URL-encode both values (spaces become `+`). `fromage=7` keeps the last 7 days.
   For the next page add `&start=10`, then `&start=20`. Read at most 2 pages per query.
5. Read the result cards with `get_page_text` (or `find` "job result cards" if the text is
   unclear). For each card note title, company, location, salary snippet and the job key.
   The job key is the `jk` value in the card link (`/viewjob?jk=<jk>` or `/rc/clk?jk=<jk>`).
   Skip a card if a folder in `<home>/jobs` starts with `indeed-` and ends with `-<jk>`
   (lower case). Skip sponsored cards that have no `jk`.
6. Open each remaining posting at `https://www.indeed.com/viewjob?jk=<jk>` and read the full
   page with `get_page_text`. Take:
   - title, company, location (as shown)
   - remote: "remote", "hybrid", "onsite" when the page says so, otherwise leave it out
   - employment: the job type line (Full-time, Contract, Part-time, Temporary)
   - salary: the pay line if shown, as written
   - posted_at: the "Posted N days ago" text or a date
   - description: the full "Full job description" section, as plain text with its bullets
   - url: `https://www.indeed.com/viewjob?jk=<jk>`; apply_url: the same URL (do not click the
     apply button to discover the company link)
   - source: `indeed`, source_job_id: `<jk>`
7. Write all postings as one JSON list to a temp file, for example
   `TMP=$(mktemp -t jobsearch-indeed).json`, using the shape in `sources/README.md`.
8. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/add_job.py" --home "<home>" --file "$TMP" --json`, keep the
   counts for the scan summary, then delete the temp file.
9. Close your tab with `tabs_close_mcp`.

## Fallback without Chrome

Use WebSearch for public postings, for example
`"<q>" <l> site:indeed.com/viewjob` and `"<q>" (site:boards.greenhouse.io OR site:jobs.lever.co OR site:jobs.ashbyhq.com)`.
Fetch each result with WebFetch. If a page will not load or shows a block page, skip it.
Use `source: "indeed"` and the `jk` from the URL for Indeed pages. For ATS pages use the ATS
name as the source and the posting id from the URL as `source_job_id`. Stay under
`max_per_run` and ingest with `add_job.py` as above. If the user would benefit, mention in
the summary that companies found this way could be added to the Greenhouse, Lever or Ashby
lists so `scan.py` picks them up directly.
