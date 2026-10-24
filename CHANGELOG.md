# Changelog

## Unreleased

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
- Onboarding offers to run the radar when you are not sure which titles to target.
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
