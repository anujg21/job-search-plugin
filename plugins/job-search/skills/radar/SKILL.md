---
name: radar
description: Career Trend Radar. Research-driven career positioning from the user's resume and preferences. Researches current job titles, live job descriptions and hiring trends from authoritative sources, then forecasts how JDs and titles will shift over 1 to 3 years and which emerging roles fit best. Inside the job-search plugin it reads the fact bank, uses the jobs already collected as a free JD sample, saves a structured radar the rest of the plugin uses (target title proposals, rising-skill flags on the gaps list, resume wording hints, a dashboard tab), and can run unattended on a monthly cadence. Use when the user runs /job-search:radar, asks what roles to target, which titles fit them, what skills are trending, how their field is changing, what to focus on next, or how to future-proof their career, even if they don't say "research" or "trends".
---

# Career Trend Radar

Turn a resume and preferences into an evidence-backed view of (a) where the market is now for this person and (b) where it is heading. Every market claim needs a source the reader can check. Forecasts are labeled as forecasts with the signals behind them.

This skill works in two modes:
- **Plugin mode**: a job-search data folder exists (`jobctl.py home` finds one). Inputs come from the data folder, results are saved there, and the rest of the plugin uses them.
- **Standalone mode**: no data folder. Run the original flow below and deliver the report only.

## Before you start
1. Find the data folder: run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" home`.
   If no home exists, use standalone mode (do not send the user to onboarding just for this).
   `${CLAUDE_PLUGIN_ROOT}` is this plugin's folder. If it is empty or shows up unexpanded
   (some Claude apps do not set it), use the folder two levels above this SKILL.md instead:
   the skill's base directory ends in `skills/<name>`, and the plugin folder holds `scripts/`.
2. In plugin mode, read `<home>/memory/lessons.md` if it exists. Follow every active lesson whose
   scope is `all` or `radar`. Lessons never override the truthfulness rules or the approval gate.

`RADAR` below means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/radar.py"`.

## Reuse a recent radar first (plugin mode)

The research takes 5 to 10 minutes and a lot of usage, and the market does not change from
one day to the next. Never run it again just because a new chat started. Check first:
`RADAR status --json`.

- **No radar yet** (`exists` false): go on to Inputs and run it.
- **A radar exists:**
  - **Interactive** (the user is in the chat): show one line, "Your career radar is from
    <as_of> (<age_days> days ago): <verdict>". Then ask with two options:
    "Use this radar (recommended)" and "Run it again (5 to 10 minutes)". If `due` is true,
    say it is older than the user's refresh setting (`every_days`) and recommend running it
    again instead. If the user picks "Use this radar", answer from `radar/latest.json` and the
    report it names. Do not research.
  - **The user asked for a fresh one** ("rerun the radar", "refresh it", "it's outdated"):
    run it without asking.
  - **Unattended** (called from `/job-search:run` or a schedule): run only when `due` is true.
- **`started_today_unfinished` is true**: a run started today and did not save. Do not start
  another one on your own. Interactive: tell the user and ask before trying again.
  Unattended: skip it and report `radar: last run did not finish, skipped`.

Right before you start researching, run `RADAR mark-start`. `RADAR save` records when it
finished. Together they keep the "last run" date that the checks above use.

## Inputs (confirm before researching)

Research is expensive and every finding is judged against the resume and preferences, so lock both down first.

**Plugin mode.** The resume is `profile/fact-bank.json` (source of truth) plus `profile/resume-master.md`. Preferences are `profile/preferences.json`. Show a five-line summary (current title, years, core skills, target titles, location and remote, IC vs manager) and ask the user to confirm or correct it. Ask only for what the files don't say: roles or work they enjoy or want to avoid, IC vs manager, time horizon. If the run is unattended (called from `/job-search:run` or a schedule), do not ask: use the files and list them under Assumptions.

**Standalone mode.**
1. **Resume.** Attached file (PDF/DOCX/text), pasted text, or LinkedIn export. Read it fully.
2. **Preferences ("likings"):**
   - Roles or work they enjoy / want more of
   - Roles or work they want to avoid
   - Location, remote/hybrid, willingness to relocate
   - Seniority target (IC vs manager, step up vs lateral)
   - Industries and target companies in/out of scope
   - Time horizon (next move vs 2-3 year plan)

**Gathering them (standalone):**
- **Nothing found** in the conversation, attachments, memory, or past chats: ask the user to attach the resume and share preferences. Wait for the answer.
- **Found in memory or past chats:** show a short summary of what you found and ask the user to confirm or correct it. Ask whether they want to attach the current resume, since memory may be stale. Wait for the answer.
- **Partial:** confirm what you have and ask only for what's missing.

Use one short message with an AskUserQuestion-style multiple-choice form when available. Only if the session is unattended proceed on found or inferred inputs, and list them under Assumptions in the report.

## Workflow

### 1. Build the candidate profile
Extract from the resume, staying strictly to what it says:
- Current/most recent title, years of experience, seniority signals (scope, team size, budget, org reach)
- Core skill clusters (group related tools: e.g. "AWS: Bedrock, Lambda, EKS")
- Domains/industries
- Distinctive differentiators (rare combos, founder experience, regulated-industry depth, publications)
- Credentials

Never invent skills or inflate scope. If something is ambiguous, flag it. In plugin mode, note the fact bank ids behind each cluster; you need them in step 6.

### 2. Map current titles
Search for the titles this profile maps to today. Cast wide: the same work often carries 3-6 different titles across companies (e.g. "Platform Architect", "Principal Platform Engineer", "Staff Infrastructure Engineer", "AI Platform Lead"). For each candidate title, note how common it is and what level it implies.

### 3. Pull live job descriptions
**Plugin mode: start with what the plugin already collected.** Run `RADAR local-tally --json`. It counts skills across every scored job in the data folder (matched and missing, required vs preferred) with posting dates. Use it as your first sample. Then top up with web research only for titles the local sample doesn't cover, so the total reaches 10-20 postings per top title.

Collect 10-20 current postings for the top 3-5 titles. Prefer primary sources:
- Company career pages and ATS boards (Greenhouse `boards.greenhouse.io`, Lever `jobs.lever.co`, Ashby `jobs.ashbyhq.com`, Workday)
- LinkedIn Jobs, Indeed, Wellfound, Dice (as discovery; follow through to the company posting when possible)

Mix company types: big tech, Fortune 500 in the person's industry, growth-stage startups. Note posting dates; discard anything older than ~90 days. When a posting is found through an aggregator, open the original ATS link to confirm it's live and dated; mark unconfirmed ones in the report.

Tally across postings:
- Required vs preferred skills, with frequency counts ("Kubernetes: 14/18")
- Recurring responsibilities and scope language
- New or unusual requirements that appear in only a few postings (these are often leading indicators)
- Comp ranges where disclosed (pay-transparency states publish them)

### 4. Research macro trends
Use the trusted-source list in `references/sources.md` (read it now: `${CLAUDE_PLUGIN_ROOT}/skills/radar/references/sources.md`). Run separate searches per source/question rather than one combined query. Look for:
- Fastest-growing and declining roles in the person's field
- Skill demand shifts (what's rising, what's becoming table stakes)
- Regulation, technology, or org-design changes reshaping the work
- Hiring volume and comp direction

Fetch the actual report/page when a snippet is thin. Record publication date for every source; older than 18 months gets flagged.

### 5. Forecast
Read `${CLAUDE_PLUGIN_ROOT}/skills/radar/references/forecasting.md` before writing this section. Produce:
- **Emerging titles** likely to fit this person in 1-3 years, each with the signals supporting it, earliest evidence seen, and a confidence level (high/medium/low)
- **JD changes**: how requirements for their current target titles are likely to shift (skills moving from "preferred" to "required", new responsibilities, skills fading)
- **Titles at risk** of shrinking, merging, or being automated

Separate evidence from extrapolation clearly. A forecast with no cited signal doesn't go in.

### 6. Gap and fit analysis
Compare the profile to both the current market (step 3) and the forecast (step 5):
- **Strong matches**: where they already meet most requirements
- **Close gaps**: 1-2 skills away, with the fastest credible way to close each (project, certification, open-source work, internal role change)
- **Strategic bets**: forecast roles worth positioning toward now
- **Resume wording**: terms the market uses for things they already do but describe differently. Only suggest relabeling real experience. In plugin mode each suggestion must name the fact bank ids it relabels; a suggestion without ids is dropped.

## Output

Deliver a report the person will keep. The full report runs long. Most readers decide from the first screen, so the top must stand alone: someone who reads only "Your action plan" knows what to do this week.

**Where it goes.**
- Plugin mode: write the report to `<home>/radar/radar-<YYYY-MM-DD>.md`, then save the structured radar (next section). The dashboard's Career radar tab links to the report.
- Standalone: use the environment's document artifact type if one exists; otherwise a markdown file (or an HTML page when visuals can't be embedded otherwise).

### Visuals
Show shapes as pictures where the format supports charts or diagrams:
- **Fit vs. growth 2x2** of candidate titles (x = your fit, y = market momentum). Put it in the action plan.
- **Skill demand chart**: bar chart of skill frequency across collected JDs, with the person's level marked (have / partial / gap).
- **Forecast timeline**: emerging titles and JD shifts placed on a 0-12 / 12-24 / 24-36 month line with confidence.
- **Pay range chart** by title or company tier when comp data exists (point at midpoint, whisker for range).

Each visual gets one sentence underneath saying what to take from it. No visual repeats a table's numbers. If the format can't render visuals (a markdown file), use compact tables instead; the dashboard draws the 2x2 and skill chart from the structured radar.

### Structure

```
# Career Trend Radar: [Name], [Month Year]

## Your action plan  (first screen, scannable)
- One-line verdict: best-fit title now + top emerging bet
- Top 3 actions this month, each a checkbox with a concrete next step
  (e.g. "Apply: [posting link]", "Build: eval harness in repo X")
- Top 3 roles to apply to now, with links
- Biggest gap and the fastest fix
- Fit vs. growth 2x2 visual

## At a glance
3-5 bullets max: market direction, pay range for best-fit titles, one forecast.

## Assumptions
Inputs used and whether the user confirmed them.

## Your profile
Skill clusters, differentiators, seniority read.

## Titles to target now
Table: Title | Fit (H/M/L) | Why | Typical comp (if found) | Example postings

## What live JDs are asking for
Skill demand chart (or table) + notable new requirements.

## Market trends shaping your field
Bullet findings, each cited.

## Forecast: next 1-3 years
Forecast timeline visual, then:
### Emerging titles  (signals, confidence)
### How JDs will change
### Titles losing ground

## Gaps and moves
Strong matches / close gaps / strategic bets, each with concrete next step.

## Resume language to adopt

## Sources
Every source with title, publisher, date, URL.
```

Keep prose tight: short sentences, bullets for parallel items, bold the key term in each bullet. No em dashes. If a `humanizer` skill is available, run the final prose through it.

## Save the structured radar (plugin mode)

Write this JSON to a temp file and run `RADAR save --file <tmp> --report radar/radar-<YYYY-MM-DD>.md`. The script checks it (fact ids exist, every forecast has a cited signal, enums are valid) and prints what it dropped. Fix and resave if it refuses.

```json
{
  "as_of": "YYYY-MM-DD",
  "verdict": "Best fit now: ML Platform Engineer. Top bet: AI Infrastructure Engineer.",
  "actions": [{"text": "Apply: Staff ML Platform Engineer at X", "url": "https://..."}],
  "titles_now": [{"title": "ML Platform Engineer", "fit": "high|medium|low", "momentum": "high|medium|low",
                  "why": "...", "comp": "$190k-$240k", "postings": ["https://..."]}],
  "skill_demand": [{"skill": "Kubernetes", "count": 14, "sample": 18, "required": 11, "you": "have|partial|gap"}],
  "rising_skills": [{"skill": "LLM evaluation", "confidence": "high|medium|low",
                     "signals": [{"text": "...", "url": "https://..."}]}],
  "emerging_titles": [{"title": "AI Infrastructure Engineer", "confidence": "medium", "horizon_months": 24,
                       "fit": "high|medium|low", "signals": [{"text": "...", "url": "https://..."}],
                       "fit_note": "...", "watch_for": "..."}],
  "jd_shifts": [{"change": "Terraform moves from preferred to required", "confidence": "medium",
                 "horizon_months": 12, "signals": [{"text": "...", "url": "https://..."}]}],
  "titles_at_risk": [{"title": "Release Engineer", "why": "...", "signals": [{"text": "...", "url": "https://..."}]}],
  "resume_language": [{"market_term": "internal developer platform", "your_term": "developer platform",
                       "fact_ids": ["r1.b2"]}],
  "assumptions": ["Preferences taken from preferences.json, not confirmed (unattended run)"],
  "sources": [{"title": "...", "publisher": "...", "date": "2026-09", "url": "https://..."}]
}
```

Then run `RADAR propose`. It turns the radar into proposals the user accepts or declines on the dashboard: high-fit titles missing from `target_titles`, and high-fit emerging titles worth watching. It never edits preferences directly. Then rebuild the dashboard: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_dashboard.py"`.

How the rest of the plugin uses the radar:
- `gaps.py` marks gaps that appear in `rising_skills` as rising and ranks them a little higher.
- The tailor skill may use a `resume_language` market term only in a bullet that cites one of that entry's `fact_ids`. The verifier still checks every line.
- `/job-search:run weekly` reruns the radar when it is older than `preferences.radar_every_days` (default 30, 0 turns it off).

In the chat reply after delivering, repeat only the verdict and the top 3 actions, then give the report path (or link).

## Quality bar
- Cite every market claim. No "studies show".
- Date everything. The market moves fast; the report states its as-of date.
- Count, don't vibe: skill demand claims come from tallies or published data.
- Honest fit ratings. A low-fit title the person likes still gets rated low, with what would change that.
- No fabricated postings, comp numbers, or statistics. If data wasn't found, say so.
- The radar never adds anything to the fact bank or the resume. It only suggests wording for experience the fact bank already proves.

## Learning from this session
If the user corrects you, repeats an instruction they gave before, or sounds frustrated
("again", "I already told you", all caps, undoing the same change twice), log it:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal <repeat|frustration|edit> --skill radar --detail "<what went wrong>" --text "<their words>"`
Then fix the problem in this session. The weekly retro turns repeated signals into lessons.
