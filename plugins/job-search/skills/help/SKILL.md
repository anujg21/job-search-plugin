---
name: help
description: Guide for the job-search plugin. Explains what the plugin does, how to set it up, what each command and dashboard tab is for, where files live, and what to do next given the user's current setup. Use when the user runs /job-search:help, asks how the plugin works, what a command or dashboard button does, where something is, why something happened (a job was skipped, a resume needs approval, a source found nothing), what to do next, or seems unsure or confused about the job search plugin ("what now?", "I don't get it", "how do I...", "where do I see...").
---

# Help

Answer the user's question about this plugin in plain words. Short answers: two to six
lines, then the one command or click that helps. Do not paste this whole guide. If they
asked nothing specific ("help", "what now?", "I'm lost"), give the "Where you are" answer
below.

## Before you start
1. Find the data folder: run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" home`.
   No home is fine here: the user has not set up yet.
   Write each script command out in full. Do not store a command in a shell variable
   (`J="python3 ..."; $J home`): the shell is often zsh, which does not split it, and it fails.
   `${CLAUDE_PLUGIN_ROOT}` is this plugin's folder. If it is empty or shows up unexpanded
   (some Claude apps do not set it), use the folder two levels above this SKILL.md instead:
   the skill's base directory ends in `skills/<name>`, and the plugin folder holds `scripts/`.
2. Read `<home>/memory/lessons.md` if it exists. Follow every active lesson whose scope is `all`
   or this skill.

## Where you are (look before answering)

Check the real state instead of guessing. Run only what the question needs:
- `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" doctor --quick`: setup problems.
- `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" list --rank`: jobs and their status.
- `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/radar.py" status`: radar age.
- The last lines of `<home>/runs/run-log.jsonl`: whether scheduled runs happen.

Then suggest the one next step that fits:

| State | Next step |
|---|---|
| No data folder | `/job-search:onboard` (about 15 minutes) |
| Doctor warns "Connector dice" or "Connector indeed" | Customize, Plugins, Job search, Connectors, Connect |
| Set up, never run | `/job-search:run daily`, then `/job-search:schedule` |
| No run in the last 2 days | The schedule is not running. See "Scheduled runs" below |
| Resumes waiting for approval | Open the dashboard, Approvals tab, or `/job-search:approve` |
| Prepared jobs not applied to | `/job-search:apply <job_id>` for the best one |
| All quiet | Open the dashboard. Log any replies. Look at the top skill gap |

## What the plugin does

Each day it finds jobs on the boards the user picked, skips ones that do not match their
preferences, scores the rest from 1 to 5 against their fact bank, and prepares a tailored
resume, cover note and screening answers for the best few. On Sundays it also nudges them on
their top skill gaps, turns their feedback into lessons, and refreshes the career radar about
once a month. It never submits an application. The user clicks Submit.

## Ideas people ask about

- **Fact bank** (`profile/fact-bank.json`): the user's resume as a list of facts, each with an
  id. Tailored resumes can only use these facts. Change it with `/job-search:onboard`.
- **Truth check:** every tailored resume line must trace to a fact. A line that adds a skill,
  number, title or date the fact bank lacks blocks the resume. Missing skills go to the
  skills gap list instead.
- **Approval:** small resume changes are approved on their own. Big ones (a lot rewritten, or
  a different headline) wait on the Approvals tab. A resume that failed the truth check shows
  Re-tailor instead of Approve.
- **Fit score:** 1 to 5. Jobs below the user's minimum (default 3.5) get no resume.
- **Daily cap:** how many resumes it prepares per day (default 5).
- **Skills gaps:** skills target jobs ask for that the fact bank lacks, ranked by how often
  they come up. Marked "rising" when the radar says demand is growing.
- **Career radar:** research on titles that fit the user, rising skills and where the field
  is heading. It runs once during setup and then about every 30 days on the weekly run. It
  does not run again in a new chat; `/job-search:radar` shows the saved one and asks before
  researching again.
- **Lessons and suggestions:** the plugin learns from edits, dismissals and complaints. Small
  lessons apply on their own. Bigger changes wait as suggestions on the "What I've learned"
  tab. Nothing it learns can loosen the truth check or the approval step.

## Commands

| Command | Use it to |
|---|---|
| `/job-search:onboard` | Set up, or change resume facts, preferences or sources |
| `/job-search:schedule` | Get the values for the daily and weekly scheduled tasks |
| `/job-search:run daily` | Do a full run now |
| `/job-search:run weekly` | Daily run plus nudge, retro and radar when due |
| `/job-search:scan` | Only fetch new jobs |
| `/job-search:score` | Only score jobs |
| `/job-search:tailor <job_id>` | Tailor a resume for one job |
| `/job-search:approve` | Review resumes waiting for approval |
| `/job-search:apply <job_id>` | Get the resume, answers and link, and fill the form |
| `/job-search:gaps` | See top skill gaps and what to do |
| `/job-search:radar` | See the career radar, or refresh it |
| `/job-search:dashboard` | Rebuild and open the dashboard |
| `/job-search:feedback <text>` | Report a problem, or paste a dashboard command |
| `/job-search:retro` | Turn recent feedback into lessons now |
| `/job-search:help` | This guide |

Job ids look like `greenhouse-stripe-1234567`. They are on the dashboard and in
`jobctl.py list`.

## The dashboard

`<home>/dashboard.html`, opened in a browser. It is rebuilt on every run. Buttons copy a
short command; the user pastes it into Claude. The page never changes data by itself.

| Tab | Shows |
|---|---|
| Pipeline | Funnel from found to interview, and every job. Click a job for its details |
| Approvals | Resumes with big changes waiting for a yes or no |
| Skills gaps | Missing skills ranked, with a weekly trend |
| Career radar | Best titles, actions, forecast, rising skills, the full report |
| What I've learned | Suggestions to accept or decline, and active lessons |
| Runs | Whether scheduled runs happen and what failed |

## Job sources

- **Greenhouse, Lever, Ashby:** public company job boards. They need a list of companies, which
  is optional; the radar suggests some.
- **Dice:** Dice's public connector server, searched by `scan.py` with the user's titles. No
  account or Chrome needed.
- **Connecting Dice and Indeed:** Customize, Plugins, Job search, Connectors tab, Connect
  next to each (Indeed asks for an Indeed sign-in). Then set each connector's tools to
  **Always allow** under Customize, Connectors, or scheduled runs leave them out. In Claude
  Code, `/mcp`. `doctor` warns until they work.
- **More connectors:** the plugin ships Dice and Indeed only. Any other job connector the
  user connects (and sets to Always allow) can be added with "add <name> as a job source";
  see `sources/other-connectors.md`.
- **Resume look and PDF:** tailored resumes copy the look of the user's own resume
  (`profile/resume-style.json`, set up in onboarding, "Resume look"). PDFs come from Chrome,
  or from `xhtml2pdf` in cloud runs. `/job-search:apply` makes one if it is missing.
- **Indeed:** the Indeed connector, bundled with the plugin.
  Without it, Indeed is read in Chrome or found through web search.
- **LinkedIn:** no job search connector exists. Read only, low volume, in the user's own
  Chrome through the Claude in Chrome extension while they are signed in. Scheduled cloud
  runs have no Chrome, so they skip it.
- The plugin checks access itself (`sources/check-access.md`).
- **Cloud runs** (scheduled tasks, claude.ai): the domain allowlist must include
  `boards-api.greenhouse.io`, `api.lever.co`, `api.ashbyhq.com` and `mcp.dice.com`
  (Settings, Capabilities). Connectors are not affected by it.
- "A source found nothing": check the Runs tab for the error. For LinkedIn, sign in in
  Chrome and keep Chrome open at run time.

## Scheduled runs

Claude Desktop, Scheduled (left sidebar), New task. Two tasks: `/job-search:run daily` every day
and `/job-search:run weekly` on Sundays, each with the data folder as its folder. The computer
must be awake with Claude Desktop open at that time. `/job-search:schedule` prints the exact
values.

## Files

```
<home>/
  profile/        fact bank, original resume, preferences, sources
  jobs/<id>/      job post, score, tailored resume (HTML and PDF), cover note, answers
  gaps.json       skill gaps
  memory/         feedback, lessons, suggestions
  radar/          career radar reports
  runs/           run log, weekly nudges, retros
  dashboard.html
```

Everything stays on the user's computer.

## When you cannot answer

If the question is about something this plugin does not do (email tracking, auto-submit,
other job sites), say so plainly and give the closest thing it does. If it looks like a bug,
log it and offer `/job-search:feedback`:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal frustration --skill help --detail "<what confused them>" --text "<their words>"`

## Learning from this session
If the user corrects you, repeats an instruction they gave before, or sounds frustrated
("again", "I already told you", all caps, undoing the same change twice), log it:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal <repeat|frustration|edit> --skill help --detail "<what went wrong>" --text "<their words>"`
Then fix the problem in this session. The weekly retro turns repeated signals into lessons.
