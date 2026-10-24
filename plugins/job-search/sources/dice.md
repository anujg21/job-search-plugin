# Dice

Dice runs a public server for its Claude connector (`https://mcp.dice.com/mcp`, no sign-in).
`scan.py` calls it directly, like the Greenhouse, Lever and Ashby APIs, so Dice needs no
Chrome and no Dice account.

Run when `sources.dice.enabled` is true and `sources.dice.queries` has at least one query.
`has_access` does not matter for Dice.

## How scan.py does it

For each query `{"q": ..., "l": ...}` it calls the server's `search_jobs` tool with
`keyword=q`, `posted_date=SEVEN` and `sort=datePosted`. When `l` is "Remote" (or empty) it
asks for `workplace_types=["Remote"]`, otherwise it passes `location=l`. Postings that pass
the prefilter and are not tracked yet get one `get_job_details` call each for the full
description and skills list, up to `max_per_run` (default 20). The job id is the posting's
`guid`, and the URL is `https://www.dice.com/job-detail/<guid>`.

## When scan.py cannot reach Dice

In a claude.ai cloud session the domain allowlist may block `mcp.dice.com`. The scan JSON
then has `"dice": "blocked"` and a `browser_next` item for Dice. Do this instead:

1. Look for the Dice connector's tools: ToolSearch with `dice search_jobs`. The plugin bundles
   the connector, and the user may also have added it under Customize, Connectors. Tool names
   look like `mcp__plugin_job-search_dice__search_jobs` or end in `search_jobs` under a Dice
   server.
2. Record what you found: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" connector dice ok`
   (or `missing` when there is no tool or the call fails). If found, call `search_jobs` once
   per query with the same arguments as above. For each
   result not already in `<home>/jobs` (a folder starting `dice-` and ending `-<guid>`), call
   `get_job_details` with `job_id` set to its `guid`. Stop at `max_per_run`.
3. Write the postings as one JSON list to a temp file in the shape from `sources/README.md`:
   `source: "dice"`, `source_job_id: <guid>`, `company: companyName`, `title`,
   `location: jobLocation.displayName`, `remote` from `workplaceTypes`, `employment:
   employmentType`, `salary`, `posted_at: postedDate`, `url` and `apply_url`: the job-detail
   URL without its `?utm_...` part, `description`: the details text.
4. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/add_job.py" --home "<home>" --file "$TMP" --json`
   and add its counts to the scan totals.
5. No connector tools either: skip Dice and note `dice: blocked, allow mcp.dice.com`.

Read only. Never apply, save a job, or use "easy apply".
