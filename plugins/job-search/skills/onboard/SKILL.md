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

## When the scripts cannot run here

A claude.ai session in the browser runs in a cloud sandbox. The data folder may be on the
user's Mac (reached through a connected computer), the plugin scripts may not run there yet,
and the sandbox may block the job board APIs and have no Chrome. When `jobctl.py home`
fails or a script cannot run:
- Keep going with what you can read and write. Never stop setup for this.
- At the end, list in one short block what you could not do (board checks, Chrome sign-in
  check, `doctor`) and give the fix: open Claude Desktop, start a Cowork task in the data
  folder, and run `/job-search:onboard`, then pick "Check my setup". The first scheduled run
  also reports bad boards.
- Do not leave a site enabled that you could not check, except Indeed, which works through
  web search.

## Re-running onboard

If a data folder already exists, do not start over. Show a short status (name from the fact
bank, number of roles and skills, target titles, enabled sources, daily cap) and ask what to
change:
- My resume facts
- Resume look (match the PDF to my own resume: "Keep the resume's look" in step 2, then
  re-render prepared resumes with `render_resume.py <job_id>` for each)
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

### Keep the resume's look

Tailored resumes and their PDFs should look like the user's own resume, so they can apply
with them directly.
1. Copy the original file into the data folder as `<home>/profile/original-resume.<ext>`.
2. Read its look and write `<home>/profile/resume-style.json`. Only layout, never content.
   Every key is optional; leave out what you cannot tell. Keys (defaults in
   `scripts/render_resume.py`, `DEFAULT_STYLE`):
   - `font` (a CSS font stack, for example `Calibri, Carlito, Arial, sans-serif`),
     `base_size_pt`, `name_size_pt`, `text_color`, `accent_color`, `muted_color` (hex)
   - `page_size` (`Letter` or `A4`), `margins_in` (`[top/bottom, sides]`)
   - `header_align` (`left` or `center`), `name_caps`, `name_letter_spacing_pt`,
     `headline_bold`, `contact_separator`
   - `section_caps`, `section_letter_spacing_pt`, `section_rule` (a line under headings),
     `section_titles` (for example `{"skills": "Technical Skills"}`)
   - `role_format`: `company_title` ("Company, Title, Location") or `title_company`;
     `role_separator` between company and title, copied from the original;
     `date_style`: `inline_muted` (dates after the role line) or `own_line`
   - `skills_layout`: `grouped` or `list`; `skill_groups`: the original's group labels, each
     with the fact bank skill names under it (`{"Cloud & Platform": ["AWS", "Kubernetes"]}`)
   How to read it: a DOCX keeps fonts in `word/document.xml` (`w:rFonts`), sizes in
   half points (`w:sz`), colors (`w:color`) and margins in twentieths of a point
   (`w:pgMar`). For a PDF, read the page and judge the look. Ask the user nothing about it.
3. Render the master resume to check:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_resume.py" --master` and tell the user
   where the PDF is, so they can compare it with their original.

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
- `headlines` and `title_aliases` are the only titles the tailored resume may use. Fill them
  with the titles on the resume. Do not ask the user for other titles here: step 4 runs the
  career radar first and offers the titles it finds, which can then become headlines.

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

**Titles come from the career radar.** Do not ask "which titles do you want?" first. Most
people do not know the market's names for their work, so research the titles before asking.

1. Ask only where they want to work: locations and remote (remote, hybrid, onsite, any).
   Write them to `preferences.json` so the research looks in the right place.
2. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/radar.py" status --json`.
   - A radar already exists: use it. Say "Using your career radar from <as_of>." Do not run
     it again unless the user asks, or `due` is true and the user agrees.
   - No radar yet: say in one line that you are researching titles that fit their resume
     (5 to 10 minutes) and that they can say "skip" to name titles themselves. Then follow
     `${CLAUDE_PLUGIN_ROOT}/skills/radar/SKILL.md` in plugin mode. Skip its "Before you start"
     section and its input confirmation: the user just confirmed the fact bank, so use the
     files and the answers from this interview.
   - The research fails or the user says skip: ask for target titles directly and go on.
3. Show the titles from `radar/latest.json` `titles_now` with fit `high` or `medium` as
   multiple choice (multi-select), each with its fit, momentum and one line of why. Save the
   ones the user picks to `target_titles`.
4. Then ask once: "Any other titles you want me to search for?" Free text, and "No" is a
   fine answer.
5. Ask once whether the picked titles may also appear as the headline on their tailored
   resumes. Add a title to `headlines` only if the user says it honestly describes work they
   have done. Never add one on your own.

Do not run `radar.py propose` here: the user just chose.

Ask these, a few at a time, and write `<home>/profile/preferences.json`:

| Question | Key |
|---|---|
| (from the radar step above) | `target_titles` |
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

Nothing in this step blocks setup. If the user skips a question, use the default and go on.
Ask everything in one short message with the options below, not one source at a time.

| Source | Login needed | Notes |
|---|---|---|
| Greenhouse | No | Public API. Watches the companies you name. |
| Lever | No | Public API. Watches the companies you name. |
| Ashby | No | Public API. Watches the companies you name. |
| Dice | No | Dice's public connector. Searches your titles. On by default. |
| Indeed | One-time Indeed sign-in to connect it | The Indeed connector; falls back to your Chrome or web search. |
| LinkedIn | Yes, in Chrome | No connector exists. Read-only in your Chrome, low volume. Never applies or messages anyone. |

**Companies are optional.** Ask "Any companies you would like me to watch? (optional, you can
skip)". Then:
- Add the job boards the radar found: run
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/radar.py" boards --json` and offer them as a
  multi-select ("The radar found jobs that fit you on these boards"). This gives the user
  companies without having to name any. Show each by its company name, not the token
  (tokens can be numbers, like `8451` for 84.51°). Greenhouse gives the name at
  `https://boards-api.greenhouse.io/v1/boards/<token>`; for Lever and Ashby use the company
  name from the radar posting.
- For each company the user names, find its board token and check it works:
  - Greenhouse: `https://boards-api.greenhouse.io/v1/boards/<token>/jobs`
  - Lever: `https://api.lever.co/v0/postings/<token>?mode=json`
  - Ashby: `https://api.ashbyhq.com/posting-api/job-board/<token>`
  Try the obvious slug first (`stripe`, `datadog`). If it fails, search the web for
  "<company> careers greenhouse" (or lever, ashby) and read the token from the careers URL.
  Put the company in the list for the board that answered. Tell the user which you found
  and which you could not, and move on.
- No companies at all is fine. Dice, Indeed and LinkedIn still search by title, and the
  weekly radar suggests boards later. Turn Dice and Indeed on by default (neither needs
  Chrome). Never finish setup with nothing that can find jobs.

**Searches are built for the user.** Do not ask for search terms or saved search URLs. For
Indeed and Dice, make one query per target title (up to 3) with the first location, or
`Remote` for remote-only. For LinkedIn, build up to 3 search URLs:
`https://www.linkedin.com/jobs/search/?keywords=<title>&location=<location>&f_TPR=r604800`
(URL-encoded; add `&f_WT=2` for remote only). The user can paste their own saved searches
later.

**Connect Dice and Indeed.** These are connectors bundled with the plugin, and only the user
can connect them. Always show the user the numbered steps from "Connectors first" in
`sources/check-access.md` (Customize, Plugins, Job search, Connectors, Connect), then check
them as that guide says, including setting each one to **Always allow**. Say why in one
line: they make scheduled runs find Dice and Indeed jobs without Chrome, and a scheduled run
cannot stop to approve a connector.

**Other connectors (optional).** Say in one line that the plugin ships Dice and Indeed, and
that any other job connector they connect can be added (`sources/other-connectors.md`). If
they name one, add it to `extra_connectors` in sources.json. Never block setup on this.

**Check access yourself.** Do not ask "are you signed in?". Follow
`${CLAUDE_PLUGIN_ROOT}/sources/check-access.md`. It checks the Indeed connector (and helps
the user connect it), checks LinkedIn in the user's Chrome, and sets `enabled` and
`has_access`. Dice needs no check. If Chrome is not connected it says how to connect it, and
setup goes on.

Write `<home>/profile/sources.json` with all six sources present:

```json
{"schema_version": 1, "sources": {
  "greenhouse": {"enabled": true, "has_access": true, "companies": []},
  "lever": {"enabled": true, "has_access": true, "companies": []},
  "ashby": {"enabled": true, "has_access": true, "companies": []},
  "indeed": {"enabled": true, "has_access": false, "queries": [{"q": "", "l": ""}], "max_per_run": 20},
  "dice": {"enabled": true, "has_access": true, "queries": [{"q": "", "l": ""}], "max_per_run": 20},
  "linkedin": {"enabled": false, "has_access": false, "saved_search_urls": [], "max_per_run": 15}
}}
```

## Step 6: check the setup

Run `JOBCTL doctor` and show the checklist. Fix every `[FAIL]` line with the user. Explain
`[warn]` lines in one sentence each. A "Connector dice" or "Connector indeed" warning means
the connector is not connected yet: show its steps again, as the warning says. A missing Chrome only means resumes stay HTML (no PDF).

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
