# Changelog

## 0.3.0 (2026-10-24)

- Dice no longer needs Chrome or a Dice account. `scan.py` searches Dice through its public
  connector server (`mcp.dice.com`) with your titles, and fetches full descriptions only for
  jobs that pass your filters. When a cloud run blocks that domain, the run uses the Dice
  connector instead.
- The plugin bundles the Dice and Indeed connectors (`.mcp.json`). Indeed now tries its
  connector first (one Indeed sign-in), then Chrome, then web search. Connectors work in
  scheduled cloud runs, since the domain allowlist does not apply to them.
- LinkedIn has no job search connector and stays Chrome only. Scheduled cloud runs skip it.
- A cloud run with no Chrome prints the tailored resumes to PDF on your Mac.
- Onboarding turns Dice and Indeed on by default and checks the Indeed connector instead of
  asking. `jobctl.py doctor` counts Dice with searches as a source that can find jobs.
- The "network blocked" message lists `mcp.dice.com` too, and no longer suggests running in
  Claude Desktop.

## 0.2.6 (2026-10-24)

- Indeed's web search fallback runs two searches per query and includes Greenhouse's
  `job-boards.greenhouse.io` pages, and retries a query without the location when it finds
  nothing.
- A blocked cloud run no longer suggests running in Claude Desktop instead. Desktop
  scheduled tasks use the same cloud sandbox; the domain allowlist is the fix.

## 0.2.5 (2026-10-24)

- `scan.py` now returns `browser_next`, a list of what to do for Indeed, Dice and LinkedIn.
  The run follows it, so Indeed is searched through web search when there is no Chrome. A
  scheduled cloud run skipped Indeed before.
- A cloud run no longer suggests running the scan on your Mac to get around the blocked
  boards. Commands it runs on your Mac go through the same domain allowlist.
- SCHEDULING.md: corrected where scheduled tasks run and what the cloud sandbox can reach.

## 0.2.4 (2026-10-24)

- The dashboard shows your real data folder when a cloud run built it from a staged copy
  (`build_dashboard.py --home-label`). It showed a temporary sandbox path before.

## 0.2.3 (2026-10-24)

- Scan says when the network blocks every job board (a claude.ai cloud sandbox) and names
  the domains to allow, instead of a list of failed boards.
- Scheduled and cloud runs without Chrome still search Indeed through web search.
- SCHEDULING.md: scheduled tasks run in Claude's cloud sandbox and reach your folder through
  your Mac; how to allow the job board domains.

## 0.2.2 (2026-10-24)

- Onboarding keeps going in a claude.ai browser session, where scripts, job board APIs and
  Chrome may not be available. It lists what it could not check and how to finish in
  Claude Desktop.
- INSTALL.md: run onboarding in Claude Desktop, and restart Desktop when it lags behind an
  update.

## 0.2.1 (2026-10-24)

- Skill descriptions no longer contain angle brackets, which claude.ai rejects on sync.
- `jobctl.py doctor` fails when no source can find jobs (no companies listed and Indeed,
  Dice and LinkedIn off). Onboarding turns Indeed on in that case.
- Onboarding shows job boards the radar found by company name instead of board id.

## 0.2.0 (2026-10-24)

- New `/job-search:help` skill. It answers questions about the plugin and suggests the next
  step from your current setup. Claude also uses it when you seem unsure how something works.
- Onboarding runs the career radar before asking for job titles, then offers the titles it
  found and asks if you want others.
- The radar is not run again in a new chat. `/job-search:radar` shows the saved radar and its
  date and asks before researching again. `radar/state.json` records when a run started and
  finished, so a run that failed today is not retried on its own.
- Companies are optional in onboarding. It offers the job boards the radar found, and builds
  Indeed, Dice and LinkedIn searches from your titles and locations.
- Onboarding checks Indeed, Dice and LinkedIn access in your Chrome instead of asking whether
  you are signed in (`sources/check-access.md`). Without Chrome, Indeed falls back to web
  search.

## Earlier changes, published with 0.1.0

Career Trend Radar.

- New guides: docs/INSTALL.md (Claude Desktop, Claude Code and local installs), docs/USER_GUIDE.md (dashboard tour and everyday tasks), docs/PUBLISHING.md (releasing updates). The README is now a short landing page that links to them.
- Skills fall back to their own folder when `${CLAUDE_PLUGIN_ROOT}` is not set.
- Dashboard is more visual and less wordy: pipeline funnel with weekly trend, score meters, fit split bar with skill chips, rewrite bar and change chips, status timeline, run chart, and plain-language proposal and verify text.
- Career radar tab: best fit and top bet chips, action cards, fit grid, skill demand bars, a 3-year forecast timeline, and the full report collapsed below.
- The Career radar tab now shows the full radar report inside the dashboard, in the dashboard's theme, with a section list and collapsible sections. "At a glance" keeps the charts.

- New `/job-search:radar` skill. It researches live postings and hiring reports and shows
  which titles fit you now, which skills are rising, and how job descriptions are changing.
  Every claim links to a source. It never changes your resume or fact bank.
- The dashboard has a Career radar tab: the verdict, top actions, a fit and momentum chart of
  titles, skill demand bars, emerging titles, job description shifts, titles losing ground,
  resume wording hints, sources and a link to the full report.
- The gaps list marks gaps the radar sees rising and ranks them a little higher. A short list
  shows skills that are trending but not in your jobs yet.
- The weekly run refreshes the radar when it is older than `radar_every_days` (default 30).
  Daily runs never do. New target titles and job boards from it wait for your answer.
- `/job-search:feedback radar` runs the radar now.
- Tailoring: a stricter reviewer checklist (merged numbers, qualifiers, outcomes, names, verb
  level, skills, verify warnings). Bullets now echo the posting's own words where a fact
  supports them. Radar wording is used only in lines that cite its facts and only when the
  posting uses the term.

Fixes from an end to end test with a new user.

- Scan: "Senior" or "Staff" alone no longer makes a title match. Remote-only searches skip
  city-only postings that do not say they are remote. "Remote Eligible" counts as remote.
  More countries are recognized, so a US-only search skips Serbia, Denmark and others.
- Scoring picks the best title matches first (`jobctl.py list --rank`) and scores a role posted
  in several cities only once. The gaps list counts such a role once.
- Onboarding no longer guesses years per skill from role dates.
- New `check_answers.py` checks cover notes and screening answers for numbers that are not in
  your fact bank, and for dashes.
- Screening answers no longer offer your salary floor as your expectation.
- A resume you edit by hand gets a fresh HTML and PDF on the next run.
- Feedback: a standing rule ("stop doing X") becomes a lesson the first time and fixes resumes
  that are ready but not sent.
- Lessons that would round numbers up or inflate titles are refused.
- Scheduling steps match the current Claude Desktop screens ("Set up manually", approval mode).

## 0.1.0 (2026-10-24)

First release.

- Onboarding: imports your resume into a fact bank you confirm, sets preferences and sources.
- Sources: Greenhouse, Lever and Ashby APIs; Indeed, Dice and LinkedIn through your Chrome.
- Fit scores from 1 to 5 with matched, partial and missing requirements.
- Truthful resume tailoring with a verify check and an approval step for major changes.
- Skills gap ledger with a weekly nudge.
- Static HTML dashboard with pipeline, approvals, gaps, lessons and run log.
- Memory: signals, lessons and proposals, with a weekly retro.
- Daily and weekly runs for Claude Desktop scheduled tasks.
- Apply helper that prefills Greenhouse, Lever and Ashby forms and leaves Submit to you.
- `jobctl.py doctor` setup check.
