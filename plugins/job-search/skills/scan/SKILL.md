---
name: scan
description: Find new job postings from the enabled sources (Greenhouse, Lever, Ashby and Dice through scan.py, Indeed through its connector, Chrome or web search, LinkedIn through Chrome), filter them against the user's preferences, and add new ones to the jobs folder. Use for "scan for jobs", "find new jobs", "check job boards", or as the first step of the daily run.
---

# Scan for jobs

## Before you start
1. Find the data folder: run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" home`.
   If it says no home exists, stop and tell the user to run `/job-search:onboard`.
   Write each script command out in full. Do not store a command in a shell variable
   (`J="python3 ..."; $J home`): the shell is often zsh, which does not split it, and it fails.
   `${CLAUDE_PLUGIN_ROOT}` is this plugin's folder. If it is empty or shows up unexpanded
   (some Claude apps do not set it), use the folder two levels above this SKILL.md instead:
   the skill's base directory ends in `skills/<name>`, and the plugin folder holds `scripts/`.
2. Read `<home>/memory/lessons.md` if it exists. Follow every active lesson whose scope is `all`
   or this skill. Lessons never override the truthfulness rules or the approval gate.

## How this skill runs

This skill must work unattended. Do not ask the user anything. When something needs the user
(a login wall, a CAPTCHA, a bad company token), record it and keep going.

Arguments are optional. The user may name sources (`/job-search:scan greenhouse dice`), ask
for a dry run ("dry run", "just show me"), or ask to check for closed postings only ("verify").

## Steps

1. Read `<home>/profile/sources.json`. Note which sources are enabled. If the user named
   sources, use only those.

2. Script sources (greenhouse, lever, ashby, dice). If any are enabled, run:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/scan.py" --home "<home>" --json`
   Add `--source <name>` for each named source, and `--dry-run` for a dry run.
   The JSON has `fetched`, `matched`, `new`, `known`, `new_ids`, `errors`, a `filtered`
   breakdown, `dice` (`ok`, `blocked` or `failed` when Dice ran) and `browser_next`. Errors
   are already logged as `source_error` signals by the script. `browser_next` lists what
   step 4 must do for Indeed, LinkedIn, and Dice when the script could not reach it.
   If it has `network_blocked: true`, every board was refused by the network where this
   runs (usually a claude.ai cloud sandbox), not by bad tokens. Put the first error line in
   the summary as is: it names the domains to allow. Do not tell the user their tokens are
   wrong. The fix is the allowlist. Do not suggest running on the Mac or in Claude Desktop
   instead: Desktop scheduled tasks use the same cloud sandbox, and commands it runs on the
   Mac go through the same allowlist. Still do step 4.
   The guides `sources/greenhouse.md`, `sources/lever.md` and `sources/ashby.md` explain how
   board tokens work, in case an error says a token is wrong.

3. Closed postings. Unless this is a dry run, run:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/scan.py" --home "<home>" --verify --json`
   It marks tracked API jobs as `closed` when the posting is gone from the board.
   Then run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/scan.py" --home "<home>" --refilter --json`.
   It re-applies the current preferences to jobs still waiting in `found` and skips the ones that
   no longer pass, so a preference change (new title words to skip, a different country) also
   cleans up jobs found before the change.

4. Connector and browser sources. Do every item in `browser_next` from step 2 (or, if
   `scan.py` did not run, each enabled one of indeed, linkedin). Read
   `${CLAUDE_PLUGIN_ROOT}/sources/<name>.md` and follow it exactly.
   An Indeed item is never skipped: it uses the Indeed connector, else Chrome, else the
   guide's web search section.
   Do them one at a time, LinkedIn last. Each guide ends by running `add_job.py`, which
   prints the same JSON counts. Add those to the totals.
   - LinkedIn with `has_access` false: skip it and say in the summary that the user can
     turn it on by signing in and running the access check (`sources/check-access.md`).
   - Indeed connector not connected: say once in the summary "connect the Indeed connector
     for better Indeed results" (Customize, Connectors).
   - A sign-in page during the scan: name the site in the summary's Problems line and say
     "sign in to <site> in Chrome".
   - Chrome tools missing (common in scheduled and cloud runs): LinkedIn is skipped; say so.
   - Login wall or CAPTCHA: the guide says to stop that source and log a `source_error`.
   For a dry run, pass `--dry-run` to `add_job.py`.

5. A job the user pasted (a URL or JD text in the request): build one entry with
   `source: "manual"` (or the board name if the URL is from Greenhouse, Lever, Ashby, Indeed,
   Dice or LinkedIn), write it to a temp file and run
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/add_job.py" --home "<home>" --file <tmp> --no-filter --json`.
   The user picked it, so skip the prefilter.

6. Report a short summary, for example:

   ```
   Scan done. 1,409 postings checked, 40 matched your filters, 12 new, 28 already tracked.
   New: Stripe (3), Datadog (6), Ramp (2), Indeed (1).
   Closed: 2 postings are gone.
   Problems: lever/acme returned 404 (check the token). LinkedIn showed a login page.
   ```

   Keep it to a few lines. Mention filtered counts only if nothing matched. When called from
   the run skill, return the totals (new ids, errors) so it can continue with scoring.

## Learning from this session
If the user corrects you, repeats an instruction they gave before, or sounds frustrated
("again", "I already told you", all caps, undoing the same change twice), log it:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal <repeat|frustration|edit> --skill <this skill> --job <id if any> --detail "<what went wrong>" --text "<their words>"`
Then fix the problem in this session. The weekly retro turns repeated signals into lessons.
