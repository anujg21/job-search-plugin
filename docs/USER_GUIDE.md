# User guide

How to use the plugin once it is installed and scheduled. For setup, see [INSTALL.md](INSTALL.md).

## A normal week

Every morning the daily run does this on its own:

1. Checks your job boards for new postings and skips the ones that do not match your titles,
   locations, countries or deal breakers.
2. Scores the best new matches from 1 to 5 against your fact bank.
3. Tailors your resume for the top few (your daily cap) and writes a short cover note and
   answers to common screening questions.
4. Updates your skills gap list and rebuilds the dashboard.

Small resume changes are approved on their own. Big ones wait for you. Nothing is ever
submitted for you.

On Sundays the weekly run also writes a skills nudge, reviews your feedback from the week, and
refreshes the Career Trend Radar about once a month.

Your part takes 10 to 15 minutes a few times a week: open the dashboard, approve or reject
what is waiting, apply to the jobs you like, and log replies when they come in.

## The dashboard

After every run Claude opens the dashboard for you: in your browser when it runs on your
computer, or as a file in the chat (click it) when it runs in the cloud. You can also open
`~/JobSearch/dashboard.html` in your browser yourself. Buttons on the page copy a short command.
Paste it into Claude (a Cowork task or a Claude Code session) and Claude does the rest. The
page itself never changes your data.

| Tab | What you see | What you do there |
|---|---|---|
| Start here | What the dashboard is, how many resumes are ready, and five steps for using it. It opens first until you pick another tab | Follow the links to the tab you need |
| Pipeline | A funnel from Found to Interviews, then every job with its score, status and resume badge | Click a funnel step to filter. Click a job for details. |
| Job detail (click a row) | Fit score against your minimum, matched and missing skills, what changed in the resume, status timeline | Mark applied, Not interested, Something's wrong, log a reply or interview, approve or reject resume changes |
| Approvals | Resumes with big changes waiting for you | Approve, reject with a reason, or re-tailor when a check failed |
| Skills gaps | The skills your target jobs ask for most that you do not have, with a weekly trend | Mark a gap as learning, ignore or done |
| Career radar | Best fit title now and top bet, this month's actions, titles by fit and demand, a 3 year forecast, rising skills, wording tips, the full report | Open the actions, accept new titles or job boards it suggests |
| What I've learned | Suggestions waiting for your answer and the lessons it follows | Accept or decline suggestions, retire a lesson |
| Runs | A chart of recent runs and a table of every run | Check that the schedule is running and what failed |

## Common tasks

### Approve or reject a resume change

Open Approvals, or the job's detail panel. **Approve** keeps the tailored resume as it is.
**Reject** asks what should change, then the plugin re-tailors it. If the truth check failed,
you see **Re-tailor** instead of Approve, because a resume with an unbacked line cannot be
approved.

### Apply to a job

Run `/job-search:apply <job_id>`. You get the tailored resume as a PDF in the look of your own
resume (fonts, colors, headings and skill groups come from the file you imported), plus HTML,
the cover note,
the screening answers and the application link. (The dashboard's **Open & apply** link only
opens the posting; the job detail panel links the resume and answers next to it.) With Claude in Chrome connected, it can fill in the form on Greenhouse, Lever and Ashby
pages for you. It never clicks Submit. After you submit, click **Mark applied** (or tell
Claude you submitted) so the pipeline stays accurate.

### Log a reply

When a company writes back, open the job and click **Replied**, **Interview**, **Rejected** or
**Offer**. Email tracking is not built yet, so this is manual for now.

### Tell it something is wrong

Click **Something's wrong** on a job, or just say it:
`/job-search:feedback stop using the word "leveraged"`. If you repeat a complaint, or sound
frustrated, it becomes a lesson right away. Lessons show up under What I've learned.

### Edit a tailored resume yourself

Edit `jobs/<job_id>/resume.json` in your data folder, or describe the change with
`/job-search:feedback`. The next run notices the edit, rebuilds that resume's HTML and PDF,
and learns from your wording.

### Fix or add to your fact bank

Run `/job-search:onboard` and say what to change, for example "add my Kafka work at Acme from
2023". The fact bank is the only source for tailored resumes, so a skill or result you leave
out can never appear in one.

### Change what jobs it looks for

Run `/job-search:onboard` and change titles, locations, countries, title words to skip, deal
breakers, the daily cap or the minimum score. Jobs still waiting to be scored are re-filtered
on the next run.

### Add companies to watch

Run `/job-search:onboard` and name the companies. It finds their Greenhouse, Lever or Ashby
board. The Career radar also suggests boards where it found jobs that fit you; accept them on
the What I've learned tab.

## Dashboard commands

Each dashboard button copies one of these. You can also type them yourself.

| Command | Does |
|---|---|
| `/job-search:feedback applied <job_id>` | Marks a job applied |
| `/job-search:feedback dismiss <job_id> <reason>` | Not interested, with a reason it learns from |
| `/job-search:feedback outcome <job_id> replied` | Logs a reply (also `interview`, `rejected`, `offer`) |
| `/job-search:feedback approve <job_id>` | Approves a resume change |
| `/job-search:feedback reject <job_id> <reason>` | Rejects a change and re-tailors |
| `/job-search:feedback wrong <job_id> <what>` | Reports a problem with a job, score or resume |
| `/job-search:feedback gap <gap> learning` | Marks a skill gap (also `ignore`, `done`) |
| `/job-search:feedback proposal <id> accept` | Answers a suggestion (also `decline`) |
| `/job-search:feedback lesson <id> retire` | Stops following a lesson |
| `/job-search:feedback radar` | Runs the Career radar now |

## All commands

| Command | What it does |
|---|---|
| `/job-search:onboard` | Setup, or change your fact bank, preferences and sources |
| `/job-search:schedule` | Set up the daily and weekly runs |
| `/job-search:run daily` | Scan, score, tailor the top few, update gaps and the dashboard |
| `/job-search:run weekly` | The daily run, plus the skills nudge, the retro and the monthly radar |
| `/job-search:scan` | Fetch new jobs from your sources |
| `/job-search:score` | Score jobs against your fact bank |
| `/job-search:tailor <job_id>` | Tailor your resume for one job |
| `/job-search:approve` | Review resume changes waiting for you |
| `/job-search:apply <job_id>` | Get everything ready to apply |
| `/job-search:gaps` | Your top skill gaps and what to do about each |
| `/job-search:radar` | Career Trend Radar |
| `/job-search:dashboard` | Rebuild the dashboard and open it |
| `/job-search:feedback <text>` | Tell it anything, or paste a dashboard command |
| `/job-search:retro` | Turn recent feedback into lessons and suggestions |
| `/job-search:help` | Ask how anything works, or what to do next |

## How resumes stay truthful

1. Onboarding turns your resume into a fact bank, and you confirm it.
2. Tailoring may reword, reorder, merge and drop facts, and use the job post's own words when
   a fact supports them. Every line cites the facts it comes from.
3. A check blocks any number, tool, title, employer, date, scope or industry claim it cannot
   trace to a cited fact.
4. A reviewer pass reads each line next to its facts for claims a script cannot catch.
5. Skills you lack go to the skills gap list, never into the resume.

## Skills gaps and the weekly nudge

Every scored job adds the skills it asks for that your fact bank lacks. The gap list ranks
them by how often they show up, how often they are required, how recent they are, and whether
the Career radar says they are rising. Each Sunday you get a nudge for the top three: why each
one matters and one concrete next step. When you learn a skill, add it to your fact bank with
`/job-search:onboard` so resumes can use it.

## Career Trend Radar

The radar researches live postings and hiring reports, then shows the titles that fit you now,
the one to bet on, skills that are rising, how job descriptions are likely to change over the
next three years, and wording the market uses for work you have already done. Every claim
links to a source. New titles and job boards it finds arrive as suggestions you accept or
decline. It never edits your resume or fact bank.

It runs once during setup and then about every 30 days on the weekly run (change this with
`radar_every_days`). `/job-search:radar` shows the saved radar and its date, and asks before
researching again, since the research takes 5 to 10 minutes and the market does not change
daily. Say "refresh the radar" when you want a new one.

## What it learns from you

It logs your edits, dismissed jobs, rejected changes, repeated instructions and frustration.
Small lessons (word choice, tone, kinds of jobs to skip) apply on their own. Bigger ones (your
preferences, sources, daily cap, fact bank) wait for your answer. No lesson can loosen the
truth rules or the approval step.

## Your data folder

```
~/JobSearch/
  profile/        fact bank, your original resume, preferences, sources
  jobs/<id>/      job description, score, tailored resume (HTML, PDF), cover note and answers
  gaps.json       skill gaps across all jobs
  memory/         feedback signals, lessons, suggestions
  radar/          Career radar reports
  runs/           run log, weekly nudges and retros
  dashboard.html  open in your browser
```

Everything stays on your computer. Back it up like any other folder, or keep it in a private
git repository.

## Time and usage

In testing, a daily run took about 2 minutes and a weekly run about 3. Measured at API prices
they cost about $1.10 and $1.40. On a Claude plan they count toward your normal usage limits
instead. The radar adds 5 to 10 minutes of research about once a month.

## Questions

For anything not covered here, type `/job-search:help` or ask in plain words. It checks your
setup and answers.


**Will it apply to jobs for me?** No. It prepares everything and can fill in forms, but you
click Submit.

**Can it add keywords to beat applicant tracking systems?** Only words your experience backs
up. Keywords you lack go to the skills gap list.

**Does my Mac need to be on?** For scheduled runs, yes, with Claude Desktop open at the
scheduled time. Your data lives on your Mac, so the runs happen there.

**Does it read my email?** Not yet. Log replies from the dashboard.

**Is LinkedIn safe to use?** It only reads a few of your saved searches, slowly, and never
applies or messages anyone. LinkedIn's terms forbid scraping, so leave it off if you prefer.
