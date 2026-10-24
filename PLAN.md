# Job Search Plugin: Plan v1

Status: plan only, no code yet. Date: 2026-10-24.

## 1. Recommendation in one paragraph

Build a **Claude plugin in a GitHub repo** and do not build a web app yet. The plugin holds skills (search, score, tailor, track gaps, build dashboard) and runs from a Claude Desktop **Scheduled** task. All data stays in a local folder as JSON and Markdown. Each run regenerates a static HTML dashboard that the user opens locally. We write our own plugin and borrow proven ideas from the open source projects below (all MIT) instead of trialing them first. Section 2a maps each borrowed idea to the skill that uses it.

## 2. Existing solutions

### Open source

| Project | What it covers | Gaps vs. your goals |
|---|---|---|
| [career-ops](https://github.com/career-ops-hq/career-ops) (MIT, ~77k stars) | Scores jobs 1-5 against CV, tailors CV and cover letter, Greenhouse/Lever/Ashby APIs + 100+ company feeds, "reformulate, never fabricate" prompt plus a code check that blocks facts not in your sources, terminal tracker, you press Submit. Runs in Claude Code and Codex. | No LinkedIn/Indeed/Dice. Gap tracking is rejection-pattern based, not a ranked skills ledger. Dashboard is terminal-first. |
| [ai-job-search](https://github.com/MadsLorentzen/ai-job-search) (MIT) | `/rank`, `/apply`, keywords your profile lacks are shown as gaps instead of added, `/upskill` gap heatmap and learning plan, `/html-report` offline dashboard. | Sources are mostly Danish portals + LinkedIn public. No scheduler. |
| [JobPilot](https://github.com/suxrobgm/jobpilot) (MIT) | Claude Code plugin, LinkedIn/Indeed via real browser, auto-fills and submits, web dashboard, Gmail reply matching. | Full auto-submit. No truthfulness guard described. Riskiest with LinkedIn ToS. |
| [Job-Agent-Public](https://github.com/MikaIsmayilov/Job-Agent-Public) | Daily find and rank, tailors top 5 per day. `/onboard` flow. | Small project, good reference for the onboarding and daily queue. |
| [ResumeSkills](https://github.com/Paramchoudhary/ResumeSkills) | Skill pack incl. a truthful `resume-tailor`. | Skills only, no pipeline. |
| [JobSpy](https://pypi.org/project/python-jobspy/) | Python scraper: LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google. | LinkedIn rate-limits fast. Scraping is against LinkedIn ToS. |

### Paid (verify current pricing yourself; review sites disagree)

| Product | How it meets your needs | What to borrow |
|---|---|---|
| Jobright.ai | Job feed with match score and "why you match" breakdown, AI agent. | Per-job match explanation split into matched / partial / missing. |
| Simplify | Free autofill extension for Workday, Greenhouse, Lever. You review and submit. | Treat "apply" as "prefill a form the user submits." Saved answers to common screening questions. |
| Teal | Tracker + resume versions per job + keyword match grid. | One master resume, many per-job versions, each linked to the job record. |
| Jobscan | ATS match-rate report with hard skills, soft skills, title match. | Categorized gap report (hard skill / tool / cert / domain / seniority). |
| Huntr | Kanban tracker, Chrome job clipper. | Pipeline stages: Found, Prepared, Needs approval, Applied, Replied, Rejected, Interview. |
| LoopCV, JobCopilot, LazyApply | True background auto-apply with criteria and daily caps. | Daily caps and source allowlists. Avoid the spray model; reviewers call it low quality. |

None of them combine a truthful-by-construction resume with a long-term ranked skills-gap ledger. That is the part worth building.

### 2a. What we borrow, and where it goes

Read each project's relevant files while writing the matching skill. Credit them in the README.

| Idea | From | Our skill |
|---|---|---|
| `/onboard` interview that builds the profile and preferences | Job-Agent-Public | `onboard` |
| Source toggles with "I have access" confirmation | JobPilot setup | `onboard` |
| Greenhouse / Lever / Ashby API adapters and company list format | career-ops provider modules | `scan` |
| Liveness check so dead postings are skipped | career-ops `--verify` | `scan` |
| Indeed / LinkedIn search fields and rate-limit habits | JobSpy | `scan` (Indeed adapter) |
| Reading boards in the user's real logged-in browser | JobPilot | `scan` (Dice, LinkedIn adapters) |
| 1-5 fit score with a written evaluation | career-ops | `score` |
| Matched / partial / missing breakdown | Jobright | `score` |
| Gap categories (hard skill, tool, cert, domain, seniority) | Jobscan | `score`, `gaps` |
| "Reformulate, never fabricate" prompt + check that blocks unknown facts | career-ops | `tailor` |
| Unsupported keywords become gaps, not resume lines | ai-job-search | `tailor` |
| Reviewer critique pass on the draft | ai-job-search `/apply` | `tailor` |
| Trim to 2 pages by relevance | ai-job-search | `tailor` |
| Truthful `resume-tailor` prompt wording | ResumeSkills | `tailor` |
| One master resume, versions per job | Teal | data layout |
| Gap heatmap + learning plan with time estimates | ai-job-search `/upskill` | `gaps` |
| Offline HTML report built from tracker files | ai-job-search `/html-report` | `dashboard` |
| Pipeline stages | Huntr | `dashboard` |
| Daily caps and pick top N per day | Job-Agent-Public, LoopCV | `run` |
| Plugin packaging for Claude Code + Codex from one repo | JobPilot | repo layout |

## 3. Why a plugin and not a web app (for now)

- Users run it on their own Claude subscription. No API keys, no hosting, no auth.
- Scheduled tasks in Claude Desktop (Cowork) can use installed plugins, skills and connectors ([help article](https://support.claude.com/en/articles/13854387-schedule-recurring-tasks-in-cowork)). Available on all paid plans.
- Distribution is a GitHub repo that doubles as a plugin marketplace (`/plugin marketplace add owner/repo`).
- ChatGPT: the closest equivalent is Codex, which reads the same skill files (career-ops and JobPilot already ship for both). Keep skills as plain Markdown so one repo serves both. ChatGPT desktop "Tasks" cannot drive local files, so treat it as phase 2.

**Open risk to verify first:** Anthropic's docs conflict on whether scheduled tasks run on your machine (needs app open, can use local files and Chrome) or remotely (runs while asleep, may not see local files or your logged-in browser). This decides where data lives. Spike this before anything else.

## 4. Architecture (v1)

```
job-search-plugin/                 # GitHub repo = plugin marketplace
  .claude-plugin/marketplace.json
  plugins/job-search/
    .claude-plugin/plugin.json
    skills/
      onboard/        # pick sources, import resume, set preferences
      scan/           # fetch jobs from enabled sources
      score/          # fit score + matched/missing breakdown
      tailor/         # truthful rewrite + change classification
      gaps/           # update skills-gap ledger, rank, nudge
      dashboard/      # regenerate dashboard.html
      run/            # orchestrates scan > score > tailor > gaps > dashboard
      feedback/       # capture a correction, complaint or like/dislike
      retro/          # weekly: turn signals into lessons, propose changes
    sources/          # one Markdown file per source adapter
    templates/        # resume HTML/CSS template, dashboard template

~/JobSearch/                        # user data, outside the plugin cache
  profile/
    fact-bank.json     # source of truth: roles, dates, bullets, skills, each with an id
    resume-master.md
    preferences.json   # titles, locations, salary floor, must-haves, deal-breakers
    sources.json       # enabled sources + "I have access" confirmations
  jobs/<job-id>/
    jd.md  score.json  resume.md  resume.pdf  changes.json  status.json
  gaps.json            # running ledger across all JDs
  memory/
    signals.jsonl      # raw events: edits, rejections, repeated asks, complaints
    lessons.md         # active rules every skill reads before it runs
    proposals.md       # suggested changes waiting for the user's yes/no
  dashboard.html
```

Plain files because they are easy to read, diff and back up with git, and Claude edits them with no extra tooling. The dashboard is one static HTML file with the data inlined, opened in a browser (or served with `python3 -m http.server` for a local URL).

### Sources (onboarding page lists these as toggles)

| Source | Method | Notes |
|---|---|---|
| Greenhouse | Public Job Board API per company | Clean, ToS-safe. Needs a company list. |
| Lever, Ashby | Public posting APIs | Same pattern, cheap to add. |
| Indeed | Web search + page read, or JobSpy | Moderate reliability. |
| Dice | Claude in Chrome using your logged-in session | No public API. |
| LinkedIn | Claude in Chrome, low volume, read-only | ToS forbids scraping and bots. Keep it to reading a few saved searches. Never auto-submit. |

Adding a source = adding one Markdown adapter file. No code change.

### Truthful tailoring (the core rule)

1. Every bullet in a tailored resume must cite a `fact-bank` id. The tailor skill may reword, reorder, merge and drop. It may not add a fact, metric, tool, title or date that has no id.
2. A verify step diffs the tailored resume against the fact bank and rejects any number, tool name or title that is not in it (career-ops does this in code; v1 can do it with a second LLM pass plus a simple keyword check).
3. JD keywords the user lacks go to `gaps.json`, never into the resume.

### Minor vs. major change gate

| Minor: auto-approve | Major: needs your approval |
|---|---|
| Reword a bullet using JD vocabulary | Add or remove a whole role or section |
| Reorder bullets or skills | Change job title or headline |
| Drop low-relevance bullets | Promote a skill used only lightly to the summary |
| Swap summary emphasis | Rewrite more than ~30% of the text |

`changes.json` stores each change with type, before, after and fact id. The dashboard shows it per job.

### Apply step

v1 does not submit. It prepares: tailored PDF, cover note, prefilled answers to common questions, and a direct apply link. The dashboard shows an "Open and apply" button and a "Mark applied" toggle. Phase 2 can add Claude in Chrome form fill for Greenhouse and Lever only, with you clicking Submit.

### Skills-gap ledger and nudges

For each scored JD, record missing items with category (hard skill, tool, cert, domain, seniority) and weight (required vs. nice-to-have). `gaps.json` keeps counts across all JDs and over time. Ranking = frequency x required-weight x fit with your preferences. The dashboard shows the top 10, a trend line, and one concrete suggestion per top gap (a course, a small project, or a bullet you could truthfully add once done). A weekly scheduled run produces the nudge.

### Dashboard views

1. Pipeline table: company, role, source, date found, score, status, applied date, link.
2. Job detail: score breakdown, matched / missing, resume diff, approval state.
3. Approval queue: major changes waiting on you.
4. Skills gaps: ranked list and trend.
5. Run log: when each scheduled run happened and what it did.

### Schedules

- Daily: `run` (scan, score, tailor top N, rebuild dashboard). N is set in preferences, e.g. 5.
- Weekly: `gaps` summary and nudge, then `retro`.

### Memory: getting better the more you use it

The goal: the user should never have to correct the same thing twice.

**1. Capture signals.** Every skill appends to `memory/signals.jsonl` when one of these happens:

| Signal | Example | Detected how |
|---|---|---|
| Edit after tailoring | You change "led" back to "contributed to" | Diff between our resume and the one you saved |
| Rejected change | You decline a major change in the approval queue | Approval state |
| Job dismissed | You mark a job "not interested: too junior" | Dashboard status + reason |
| Applied vs. skipped | You apply to fintech roles, skip agency roles | Status over time |
| Repeated instruction | You say "no contract roles" for the third time | `feedback` compares the ask to past signals |
| Frustration | "again", "I already told you", all caps, undoing the same edit twice | `feedback` flags the tone and links it to what caused it |
| Outcome | Rejected, interview, offer (logged by you; Gmail later) | Status |

**2. Turn signals into lessons.** A pattern seen 2+ times, or once with frustration, becomes a candidate lesson in plain English, e.g. "Never use 'spearheaded'. User removed it 4 times." The weekly `retro` groups signals and writes the candidates.

**3. Apply small lessons on their own, ask about big ones.** Same minor/major rule as the resume:
- Auto: word choices, tone, skipping a company type, adjusting score weights a little.
- Ask (goes to `proposals.md` and the dashboard): changing preferences, dropping a source, editing the fact bank, changing the daily cap.

**4. Every skill reads `lessons.md` first.** Lessons are short, dated and say where they came from, so you can see why the plugin behaves the way it does. You can edit or delete any lesson from the dashboard's "What I've learned" view.

**5. Hard limits.** No lesson can override the truthfulness rules or the approval gate. Lessons that go unused for 60 days, or that you reverse, get retired.

**6. Improving the plugin itself.** When `retro` sees a problem that is about the plugin and not your taste (a source adapter that keeps failing, a score you keep overriding), it writes a short anonymized note to `proposals.md` marked "for the maintainer." With your OK it becomes a GitHub issue, so fixes reach all 2-3 users. Borrowed from ai-job-search, which posts triage upstream to an issue.

**Capturing feedback from a static dashboard.** v1 keeps the dashboard static. Its "Not interested", "Reject change" and "This is wrong" buttons copy a ready-made prompt (e.g. `/job-search:feedback acme-123 dismiss: too junior`) for you to paste into Claude. If that gets annoying, it is the first reason to add a tiny local server.

## 5. Path to a product later

Keep these boundaries now so the move to a hosted app is a port, not a rewrite:
- Skills are the business logic. Later they become prompts called by a server through the Claude or OpenAI API with the user's own key.
- The file layout maps one-to-one to tables (profile, jobs, changes, gaps). Add a `schema_version` field from day one.
- Source adapters stay one-file-per-source so a hosted worker can run the same list.
- Later stack, when there are paying users: a small web app plus a job queue plus Postgres, BYO-key stored encrypted, and an MCP server so users can still drive it from Claude or ChatGPT. Not before.

## 6. Out of scope for v1

Gmail reply tracking (phase 2; JobPilot's approach is a reference), auto-submit, multi-user hosting, ChatGPT desktop.

## 7. Build order

1. Spike (an hour, not a trial): create a throwaway Scheduled task that writes a file to `~/JobSearch` and opens a Chrome tab. This confirms where tasks run before we lock the data location.
2. Repo skeleton: marketplace.json, plugin.json, empty skills, data folder layout, `schema_version`.
3. `onboard` + fact bank.
4. `scan` with the Greenhouse adapter, then `score`.
5. `tailor` + verify + change gate.
6. `dashboard`.
7. `gaps` ledger and weekly nudge.
8. Memory: signal capture in every skill, `feedback`, `lessons.md` read at start, then `retro`.
9. Indeed, Dice, LinkedIn adapters.
10. `run` orchestrator + daily and weekly schedules. Hand the repo to the 2-3 users.
11. Career Trend Radar (`radar` skill, `radar.py`): monthly market research saved to `radar/`.
    Wired into gaps (rising flags), the dashboard (Career radar tab), the weekly run, onboarding
    (title ideas), tailoring (wording hints tied to fact ids) and proposals.
