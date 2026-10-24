---
name: onboard
description: Guided setup for the job search plugin. Picks the data folder, imports the user's resume into a fact bank, interviews them about the jobs they want, chooses job sources, checks the setup, and offers to schedule daily runs. Use when the user runs /job-search:onboard, is setting up for the first time, or wants to change their resume facts, preferences or sources.
---

# Onboard

A friendly setup interview. Go one step at a time. Keep each message short. When the
AskUserQuestion tool is available, use it for every choice in this skill (multiple choice
with an "Other" option). Otherwise ask plain numbered questions.

`JOBCTL` below means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py"`.

## Before you start
1. Find the data folder: run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" home`.
   If it says no home exists, that is expected for a first setup. Go to step 1 below.
   Write each script command out in full. Do not store a command in a shell variable
   (`J="python3 ..."; $J home`): the shell is often zsh, which does not split it, and it fails.
   `${CLAUDE_PLUGIN_ROOT}` is this plugin's folder. If it is empty or shows up unexpanded
   (some Claude apps do not set it), use the folder two levels above this SKILL.md instead:
   the skill's base directory ends in `skills/<name>`, and the plugin folder holds `scripts/`.
2. Read `<home>/memory/lessons.md` if it exists. Follow every active lesson whose scope is `all`
   or this skill. Lessons never override the truthfulness rules or the approval gate.

## Re-running onboard

If a data folder already exists, do not start over. Show a short status (name from the fact
bank, number of roles and skills, target titles, enabled sources, daily cap) and ask what to
change:
- My resume facts
- What jobs I want
- Job sources
- Schedule
- Check my setup

Jump to that step, edit the existing files in place, and skip the rest. Never wipe a file the
user already filled in.

When you change a preference, say in one line when it takes effect. Target titles, keywords,
title words to skip, locations, remote, countries and deal breakers filter the next scan.
Salary floor, seniority, industries and min score shape scoring and resumes from the next run.
Jobs already found are not filtered again.

## Step 1: pick the data folder

Ask where to keep the data. Offer `~/JobSearch` (recommended) or a folder they name. Explain in
one or two sentences:
- Everything stays in this folder on their computer.
- If they use Claude Desktop scheduled tasks, they should pick this same folder as the task's
  working folder so each run finds it.

Then run:
```
JOBCTL --home "<folder>" init
```
If the folder is not `~/JobSearch`, tell the user that commands find it when the session's
working folder is that folder, or when `JOBSEARCH_HOME` is set. Pass `--home "<folder>"` to
every script call for the rest of this session.

## Step 2: import the resume

Ask for the path to their resume (PDF, DOCX, Markdown or plain text). Read it with whatever
tool works:
- PDF: the Read tool reads PDFs directly. If that fails, try `pdftotext file.pdf -`.
- DOCX: `textutil -convert txt -stdout file.docx` on macOS, or a docx skill if one is installed,
  or `python3 -c` with `zipfile` to pull `word/document.xml` and strip tags.
- MD or TXT: read it as is.

Save the plain text, cleaned up as Markdown, to `<home>/profile/resume-master.md`. This is the
reference copy. Do not change the user's wording in it.

If they have no resume file, ask them to paste it as text.

## Step 3: build the fact bank (strictly from the resume)

Write `<home>/profile/fact-bank.json` with this shape:

```json
{
  "schema_version": 1,
  "person": {"name": "", "email": "", "phone": "", "location": "", "links": [{"label": "LinkedIn", "url": ""}]},
  "headlines": ["titles the user is comfortable being called"],
  "summary_facts": [{"id": "sum.1", "text": "..."}],
  "roles": [
    {"id": "r1", "company": "", "title": "", "title_aliases": [], "start": "YYYY-MM", "end": "YYYY-MM or present", "location": "",
     "bullets": [{"id": "r1.b1", "text": "...", "skills": ["lowercase skill names"], "metrics": ["every number in the text"]}]}
  ],
  "skills": [{"id": "s.<slug>", "name": "", "level": "expert|working|familiar", "years": null, "evidence": ["r1.b1"]}],
  "education": [{"id": "e1", "school": "", "degree": "", "year": ""}],
  "certifications": [{"id": "c1", "name": "", "year": ""}],
  "projects": [{"id": "p1", "name": "", "text": "", "skills": []}]
}
```

Rules. These are not negotiable:
- Only facts that are in the resume. No new numbers, tools, titles, employers, dates or degrees.
  If something looks missing, ask the user. Do not fill it in.
- Copy each bullet's meaning faithfully. Light cleanup of grammar is fine. No embellishment.
- Every number, percentage, money amount or count in a bullet goes in its `metrics` list,
  written exactly as it appears in the text (`"30%"`, `"5,000"`, `"2 weeks"`).
- Ids are unique: `r1`, `r1.b1`, `s.kubernetes`, `e1`, `c1`, `p1`, `sum.1`.
- Each skill's `evidence` lists bullet ids that show it. A skill with no evidence gets level
  `familiar` and the user must confirm it.
- A skill's `years` is a number like any other. Fill it only when the resume states it ("6 years
  of Python") or the user tells you. Otherwise set it to `null`. Do not add up role dates on your
  own: a role that mentions a tool does not mean the person used it for the whole role. You may
  offer estimates from role dates when you show the fact bank ("Python looks like about 5 years
  from your roles. Save that?") and save only the ones the user confirms.
- `headlines` and `title_aliases` are the only titles the tailored resume may use. Start with
  the titles on the resume and ask which others they are comfortable with, as long as the
  titles are honest descriptions of the work.

Show the fact bank back in a compact, readable form (not raw JSON), for example:

```
Jordan Rivera, Denver, CO
Headlines: Platform Architect, Principal Platform Engineer

r1  Lead Platform Architect, Northwind Health (2021-03 to present)
    r1.b1  Led migration of 40 services to Kubernetes ... [40, 30%]
Skills: Kubernetes (expert, 5y), AWS (expert, 7y), Python (working, 4y)
```

Ask: "Is anything wrong or missing?" Apply corrections the user gives. Anything new the user
adds in this step is their own fact and may go in the fact bank. Repeat until they confirm.

Then run `JOBCTL doctor --quick` and fix any fact bank problem it reports (duplicate ids,
a metric that is not in its bullet text, evidence ids that do not exist).

## Step 4: preferences interview

**Offer the career radar first.** Before asking for target titles, ask:
"Not sure which titles to target? I can run the career radar now (about 5 to 10 minutes of
research)". Offer two choices: "Yes, run it" and "No, I know my titles".
- If yes: write the answers you already have to `preferences.json` (at least location and
  remote, so the research looks in the right place), then follow
  `${CLAUDE_PLUGIN_ROOT}/skills/radar/SKILL.md` in plugin mode. Skip its "Before you start"
  section. When it is done, show the titles from `radar/latest.json` `titles_now` with fit
  `high` as options for `target_titles` (multiple choice, plus "Other"), each with its
  momentum and one line of why. Save only the ones the user picks. Do not run `radar.py
  propose` here: the user just chose. Then go on with the rest of the questions.
- If no: ask for target titles as usual.

Ask these, a few at a time, and write `<home>/profile/preferences.json`:

| Question | Key |
|---|---|
| Which job titles do you want? | `target_titles` |
| Words that should appear in a good job (tech, domain)? | `keywords` |
| Seniority levels (senior, staff, principal, lead, manager, director)? | `seniority` |
| Where? Cities, or remote only? | `locations`, `remote` (remote, hybrid, onsite, any) |
| Lowest base salary you would take (yearly, USD unless they say otherwise)? | `salary_min` |
| Must haves? | `must_have` |
| Deal breakers (contract, clearance, travel, on call)? | `deal_breakers` |
| Title words to always skip (sales, marketing, iOS, intern)? | `exclude_title_words` |
| Which countries can you work in? (default: inferred from your locations) | `countries`, two-letter codes like `US` |
| Industries you like, and ones to avoid? | `industries_like`, `industries_avoid` |
| How many resumes should I prepare per day? (default 5) | `daily_cap` |
| Lowest fit score worth preparing, from 1 to 5? (default 3.5) | `min_score` |
| How often should the career radar refresh, in days? (default 30, 0 for never) | `radar_every_days` |

Keep `schema_version: 1`. Leave `auto_approve_minor` and `major_rewrite_ratio` at their current
values. Those control the approval gate and only the user, editing the file by hand, changes them.

## Step 5: sources

Show this list and ask which to use:

| Source | Login needed | Notes |
|---|---|---|
| Greenhouse | No | Public API. Needs a list of companies. |
| Lever | No | Public API. Needs a list of companies. |
| Ashby | No | Public API. Needs a list of companies. |
| Indeed | Uses your Chrome | Search results read in your browser. |
| Dice | Uses your Chrome | Needs you signed in to Dice in Chrome. |
| LinkedIn | Uses your Chrome | Read-only and low volume. It only reads a few of your saved searches. It never applies or messages anyone. |

For Greenhouse, Lever and Ashby:
- Ask for target company names.
- Find each company's board token and check it works:
  - Greenhouse: `https://boards-api.greenhouse.io/v1/boards/<token>/jobs`
  - Lever: `https://api.lever.co/v0/postings/<token>?mode=json`
  - Ashby: `https://api.ashbyhq.com/posting-api/job-board/<token>`
  Try the obvious slug first (`stripe`, `datadog`). If it fails, search the web for
  "<company> careers greenhouse" (or lever, ashby) and read the token from the careers URL.
  A company is on one board, usually. Put it in the list for the board that answered.
- Tell the user which companies you found and which you could not.

For Indeed, Dice and LinkedIn, ask "Are you signed in to <site> in Chrome?" Set `has_access`
to their answer. Only set `enabled: true` when `has_access` is true. Ask for a search (title and
location) for Indeed and Dice, and for one to three saved search URLs for LinkedIn.

Write `<home>/profile/sources.json` with all six sources present:

```json
{"schema_version": 1, "sources": {
  "greenhouse": {"enabled": true, "has_access": true, "companies": []},
  "lever": {"enabled": true, "has_access": true, "companies": []},
  "ashby": {"enabled": true, "has_access": true, "companies": []},
  "indeed": {"enabled": false, "has_access": false, "queries": [{"q": "", "l": ""}], "max_per_run": 20},
  "dice": {"enabled": false, "has_access": false, "queries": [{"q": "", "l": ""}], "max_per_run": 20},
  "linkedin": {"enabled": false, "has_access": false, "saved_search_urls": [], "max_per_run": 15}
}}
```

## Step 6: check the setup

Run `JOBCTL doctor` and show the checklist. Fix every `[FAIL]` line with the user. Explain
`[warn]` lines in one sentence each. A missing Chrome only means resumes stay HTML (no PDF).

## Step 7: what next

Offer, in this order:
1. Set up the daily schedule now: follow `${CLAUDE_PLUGIN_ROOT}/skills/schedule/SKILL.md`.
2. Do a first run now: follow `${CLAUDE_PLUGIN_ROOT}/skills/run/SKILL.md` with `daily`.
   Tell them it takes a few minutes and ends with the dashboard path.

End with one line on how to change anything later: run `/job-search:onboard` again.

## Learning from this session
If the user corrects you, repeats an instruction they gave before, or sounds frustrated
("again", "I already told you", all caps, undoing the same change twice), log it:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal <repeat|frustration|edit> --skill <this skill> --job <id if any> --detail "<what went wrong>" --text "<their words>"`
Then fix the problem in this session. The weekly retro turns repeated signals into lessons.
