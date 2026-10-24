---
name: run
description: The scheduled job search run. Daily it scans enabled sources, scores new jobs, tailors resumes for the best few, updates skill gaps and rebuilds the dashboard. Weekly it also writes the skill gap nudge, runs the retro, and refreshes the career radar when it is due. Fully unattended, never asks questions, never submits applications. Use when the user or a scheduled task runs /job-search:run daily or /job-search:run weekly.
---

# Run

Argument: `daily` (default) or `weekly`. Anything else counts as `daily`.

## Strict unattended rules

This skill usually runs from a scheduled task with nobody watching.
- Never ask the user a question and never wait for input. Not even for a yes or no.
- Never submit an application, send a message, or click Apply on any site.
- When something needs the user (a major resume change, a login wall, a CAPTCHA, a source
  that is down), record it and move on: job status `needs_approval`, a `source_error` signal,
  or an entry in the run's error list.
- If one step fails, write down the error and continue with the next step. A run that
  finishes with errors is better than a run that stops.

`JOBCTL` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py"`.

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

## How to run another skill from here

The other skills are Markdown files in this plugin. To run one, read
`${CLAUDE_PLUGIN_ROOT}/skills/<name>/SKILL.md` and follow its steps in this same session, with
these rules on top:
- Skip its "Before you start" section, which you already did.
- It is running unattended. Wherever it says to ask the user, take the safe default
  (skip, leave pending, or record for later) instead.
- Read the scope-specific lessons in `lessons.md` for that skill too.

If `CLAUDE_PLUGIN_ROOT` is not set, find the plugin folder by searching for
`skills/run/SKILL.md` under `~/.claude/plugins`.

## Daily steps

Keep a running tally: `found`, `new`, `scored`, `prepared`, `needs_approval`, `errors`
(a list of short strings like `"dice: not signed in"`).

1. **Quick check.** `JOBCTL doctor --quick`. If a check fails, add it to `errors`. Stop only if
   the data folder or the fact bank is unusable. Otherwise continue. Then run
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/detect_edits.py"` so any resume edits the user made
   since the last run are logged as signals. It also re-renders each edited resume, so its
   HTML and PDF match the edit. When tailoring later in this run, reuse the user's own wording
   from those edits where the facts allow.
2. **Scan.** Follow `skills/scan/SKILL.md`. It runs `scan.py` and the browser sources. Then
   run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/scan.py" --verify` so dead postings are closed.
   Take `found` and `new` from its output. Each source error goes in `errors`.
3. **Score.** Pick the jobs: `JOBCTL list --status found --rank --limit <daily_cap * 3> --json`
   (best match to the target titles first, then newest). Score those by following
   `skills/score/SKILL.md`, which also skips copies of the same role (`duplicate_of`).
   The rest stay `found` for the next run.
   Count them in `scored`.
4. **Tailor.** From jobs scored this run (and older `scored` jobs not yet prepared), pick the
   top `preferences.daily_cap` by score with score at or above `preferences.min_score` and no
   deal breaker hit. Tailor each by following `skills/tailor/SKILL.md`. Minor changes end as
   `prepared`. Major changes end as `needs_approval` and wait for the user. Count both.
5. **Gaps.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gaps.py"`.
6. **Dashboard.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_dashboard.py"`.
   If you are working on a copy of the data folder (a cloud run that staged it from the
   user's computer), add `--home-label "<the user's real data folder path>"` so the page
   shows their path, then copy every changed file back to the real folder.
7. **Mark lessons used.** For each lesson that changed what you did in this run, run
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/memory.py" lesson-touch <id>`. Unused lessons
   retire after 60 days, so this keeps the useful ones.
8. **Log the run.**
   ```
   JOBCTL runlog --kind <daily|weekly> --found N --new N --scored N --prepared N --needs-approval N --errors "<error 1>" --errors "<error 2>"
   ```
   Then run `build_dashboard.py` once more so the run log shows this run.

## Weekly steps

Do all daily steps first (but log the run once, at the end, with `--kind weekly`). Then:
1. **Gap nudge.** Follow `skills/gaps/SKILL.md` for the weekly summary and suggestions.
2. **Retro.** Follow `skills/retro/SKILL.md`.
3. **Career radar, when due.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/radar.py" status --json`.
   - If `due` is false, skip this step. Note `radar: not due (<age_days> days old)`.
   - If `started_today_unfinished` is true, skip this step. Note
     `radar: last run did not finish, skipped`.
   - If `due` is true, follow `${CLAUDE_PLUGIN_ROOT}/skills/radar/SKILL.md` in unattended mode:
     do not ask to confirm inputs, take them from the data folder and list them under
     Assumptions. It saves the report and `radar/latest.json`. Then run
     `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/radar.py" propose` so new title and job board ideas
     wait for the user in "What I've learned". Then run `gaps.py` again so rising gaps are marked.
     Note `radar: refreshed` and the number of new proposals.
   - If the research fails part way (no web access, too few sources), keep the old radar, add
     `radar: <short reason>` to `errors` and go on.
   The radar never edits preferences, the fact bank or any resume.
4. Rebuild the dashboard and log the run. Put the radar note in `--notes`.

Daily runs never run the radar, even when it is due.

## Summary

End with exactly five lines (six on a weekly run), so it reads well in a notification:

```
New jobs: <new> (from <found> found)
Prepared: <prepared> resumes ready to apply
Needs your approval: <needs_approval>
Top skill gap: <name from gaps.json ranking[0], or "none yet">
Dashboard: <home>/dashboard.html
```

Weekly runs add one line after those five: `Career radar: refreshed, <n> new suggestions`,
`Career radar: not due (<age> days old)`, or `Career radar: failed, kept the <as_of> radar`.

If there were errors, add one more line: `Problems: <count>. See the run log on the dashboard.`

## Learning from this session
If the user corrects you, repeats an instruction they gave before, or sounds frustrated
("again", "I already told you", all caps, undoing the same change twice), log it:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal <repeat|frustration|edit> --skill <this skill> --job <id if any> --detail "<what went wrong>" --text "<their words>"`
Then fix the problem in this session. The weekly retro turns repeated signals into lessons.
