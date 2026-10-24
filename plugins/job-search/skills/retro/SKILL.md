---
name: retro
description: Weekly review of the user's feedback. Finds repeated corrections, dismissals and complaints, turns small ones into lessons the plugin follows from now on, and writes proposals for bigger changes (preferences, sources, daily cap, fact bank, plugin bugs). Safe to run unattended. Use when the user runs /job-search:retro or the weekly run calls it.
---

# Retro

Runs without asking questions. It may be called from a scheduled task.

`JOBCTL` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py"` and `MEMORY` means
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/memory.py"`.

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

## Steps

1. **Pick up resume edits.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/detect_edits.py"`.
   It compares the resumes we wrote with the ones the user changed, logs `edit` signals and
   re-renders the edited resumes.
   If the script is missing or fails, note it and continue.

2. **Find patterns.** Run `MEMORY candidates --json`. You get:
   - `groups`: repeated signals. Each has `type`, `skill`, `detail`, `count`, `frustration`,
     `texts` (the user's words), `signal_ts` (the signal ids) and a `hint`.
   - `stats`: dismiss reasons, dismissed jobs by score with an optional `min_score`
     suggestion, approve and reject rates by change type, sources that keep failing,
     score overrides.
   Groups already covered by a lesson or proposal are left out for you.

3. **Write lessons for small things** (kind `auto`). Small means: word choice, tone, a type
   of job or company to skip, a small nudge to how scores weigh something.
   ```
   MEMORY lesson-add --text "<one plain rule>" --scope <tailor|score|scan|dashboard|run|all> --kind auto --source retro --evidence "<signal_ts joined by commas>"
   ```
   Good lesson text is short, concrete and says what to do: "Never use 'spearheaded'. Use
   'led'." or "Score agency postings at most 2." Not: "Be more careful with wording."

4. **Write proposals for bigger things.** Bigger means: preferences, turning a source on or
   off, the daily cap, the fact bank, or a problem in the plugin itself.
   ```
   MEMORY proposal-add --text "<question for the user, with the numbers>" --kind <preference|source|cap|fact_bank|maintainer> --patch '<json or omit>' --evidence "<signal_ts>"
   ```
   - The `min_score` suggestion in `stats.dismissed_vs_score.suggestion` already has `text`
     and `patch`. Use them as given.
   - A dismiss reason seen 3 or more times ("contract", "too junior") becomes a preference
     proposal: append to `deal_breakers`, or change `seniority`.
   - A change type the user rejects most of the time becomes a lesson for the tailor skill
     ("Do not change the headline unless the user's headlines list has a closer match").
   - A source in `repeated_source_errors` with hint `maintainer proposal`, or a score the user
     keeps overriding, becomes a `maintainer` proposal. Write it about the plugin, not about
     the user: "Dice adapter failed 4 times this week with 'not signed in' although the user
     confirmed access." Never put names, emails or company names in it.
   - Fact bank proposals only describe the change. The user confirms it later in onboard.

5. **Hard limits.** Never write a lesson or proposal that adds facts, invents metrics, skips
   the verify step, auto-approves major changes, or stops asking for approval. `memory.py`
   refuses these, and you should not try to rephrase around it.

6. **Retire old lessons.** Run `MEMORY retire-stale --days 60`.

7. **Write the summary** to `<home>/runs/retro-<YYYY-MM-DD>.md`:
   ```
   # Retro <date>
   Signals this week: <n> (<frustration count> frustrated)
   New lessons: <id: text> ...
   New proposals waiting for you: <id: text> ...
   Retired lessons: ...
   Nothing to learn from: <patterns you saw but did not act on, and why>
   ```

8. **Rebuild the dashboard.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_dashboard.py"`.

9. Reply in three lines or fewer: new lessons, proposals waiting, path to the retro file.

## Learning from this session
If the user corrects you, repeats an instruction they gave before, or sounds frustrated
("again", "I already told you", all caps, undoing the same change twice), log it:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal <repeat|frustration|edit> --skill <this skill> --job <id if any> --detail "<what went wrong>" --text "<their words>"`
Then fix the problem in this session. The weekly retro turns repeated signals into lessons.
