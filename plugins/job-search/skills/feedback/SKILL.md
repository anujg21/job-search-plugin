---
name: feedback
description: Takes a correction, a decision or a complaint about the job search and acts on it. Parses the commands the dashboard buttons copy (dismiss, applied, outcome, approve, reject, wrong, gap, lesson, proposal, radar) and free text. Logs a memory signal for each, and turns repeated or frustrated feedback into a lesson right away. Use when the user runs /job-search:feedback or pastes a command from the dashboard.
---

# Feedback

The goal: the user never has to say the same thing twice.

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

## Parse the command

The text after `/job-search:feedback` is one of these. Match the first word exactly
(case-insensitive). Anything else is free text.

| Command | Do this | Then log |
|---|---|---|
| `dismiss <job_id> <reason>` | `JOBCTL status <job_id> dismissed --note "<reason>"` | `JOBCTL signal dismiss --skill feedback --job <job_id> --detail "<reason>" --text "<reason>"` |
| `applied <job_id>` | `JOBCTL status <job_id> applied` | `JOBCTL signal apply --skill feedback --job <job_id>` |
| `outcome <job_id> <replied\|interview\|rejected\|offer>` | `JOBCTL status <job_id> <outcome>` | `JOBCTL signal outcome --skill feedback --job <job_id> --detail <outcome>` |
| `approve <job_id>` | `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/approve.py" <job_id> approve` | Nothing extra. `approve.py` logs `approve_change` itself. |
| `reject <job_id> <reason>` | `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/approve.py" <job_id> reject --reason "<reason>"`, then re-tailor (see below) | Nothing extra. `approve.py` logs `reject_change` with the change types itself. |
| `wrong <job_id> <what is wrong>` | Read the job's files, fix what you can (see below) | `override_score` if it is about the score or fit, otherwise `note` |
| `gap <gap_key> <learning\|ignore\|done>` | `JOBCTL gapnote <gap_key> <status>` | `JOBCTL signal note --skill gaps --detail "gap <gap_key> <status>"` |
| `lesson <lesson_id> retire` | `MEMORY lesson-retire <lesson_id> --reason "user retired it"` | `JOBCTL signal note --skill feedback --detail "retired <lesson_id>"` |
| `proposal <proposal_id> <accept\|decline>` | `MEMORY proposal-decide <proposal_id> <accept\|decline>` and show its output | `JOBCTL signal note --skill feedback --detail "proposal <proposal_id> <decision>"` |
| `radar` | Run the career radar now: follow `${CLAUDE_PLUGIN_ROOT}/skills/radar/SKILL.md` interactively (confirm inputs with the user), then `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/radar.py" propose` and `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gaps.py"` | `JOBCTL signal note --skill feedback --detail "radar run"` |

Details:
- For `dismiss`, write the reason in a short, reusable form in `--detail` ("too junior",
  "contract role", "agency") and keep the user's words in `--text`.
- After `reject`, the job goes back to `scored`. Re-tailor it by following
  `${CLAUDE_PLUGIN_ROOT}/skills/tailor/SKILL.md` and avoid the rejected change, unless the
  user said they are not interested in the job.
- For `wrong`: if the complaint is about the score, recommendation or fit, log
  `override_score` with `--detail "score <old> should be <their view>: <why>"`. If it is about
  resume wording, log `edit`. Otherwise log `note`. Then fix it: re-score by following
  `${CLAUDE_PLUGIN_ROOT}/skills/score/SKILL.md`, or re-tailor by following
  `${CLAUDE_PLUGIN_ROOT}/skills/tailor/SKILL.md`, for that one job.
- For a `proposal` that changes the fact bank, the script prints instructions. Follow them:
  show the exact change, ask the user to confirm the wording, then edit
  `profile/fact-bank.json` and run `JOBCTL doctor --quick`.
- If `approve.py` refuses because verify failed, show the block issues in plain words. Fix
  them by rewording toward the cited facts (never by changing the fact bank), then run
  `verify_resume.py`, `classify_changes.py` and `render_resume.py` for the job. Do not guess
  who wrote the bad line: if `resume.json` differs from `resume.generated.json`, the user
  edited it after tailoring; otherwise the tailor wrote it.
- If a job id does not exist, run `JOBCTL list` and suggest the closest match.

## Free text

Work out what the user wants. Examples:
- "no more contract roles" means a filter. Add `contract` to `deal_breakers` with the user's
  OK, or as a lesson (see below).
- "stop using 'spearheaded'" means a tailoring word choice.
- "the Stripe job is a 2, not a 4" means a score override.

Act on it in this session, then log one signal: `note` for a plain request, `edit` for a resume
wording fix, `override_score` for a score complaint, `frustration` if they sound annoyed.

A standing rule about what to do from now on ("stop ...", "never ...", "always ...", "no more
...") is a lesson the first time. Add it right away as in step 4 below, with this signal's id as
evidence, so the user never has to say it twice.

When a new tailoring rule (word choice, a skill to leave out) is added, also fix the resumes
that are ready but not sent yet. Find them with `JOBCTL list --status prepared --json` and
`JOBCTL list --status needs_approval --json`, then search each `jobs/<id>/resume.json` for the
thing the user named. For each hit: edit `resume.json`, then run `verify_resume.py <id>`,
`classify_changes.py <id>` and `render_resume.py <id>` (in `${CLAUDE_PLUGIN_ROOT}/scripts`).
For a cover note rule, edit `jobs/<id>/answers.md` and run `check_answers.py <id>`.
Leave jobs at `applied` or later alone: that resume was already sent. Tell the user exactly
which job ids you changed and which you left alone.

## Repeats and frustration: learn now, not next week

1. Check whether they said this before. Run `MEMORY candidates --json --since 90` and also read
   the last 50 lines of `<home>/memory/signals.jsonl`. Look for an earlier signal with a similar
   `text` or the same `detail`.
2. If you find one, log `JOBCTL signal repeat --skill feedback --detail "<same detail as before>" --text "<their words>"`.
   If an active lesson already covers it, the lesson did not work. Find out why (an old
   resume made before the lesson, or the lesson text is unclear), fix that, and add the new
   signal ids to the lesson by running `MEMORY lesson-add` again with the lesson's exact text, its scope
   and `--evidence "<new signal ids>"`. It merges into the existing lesson.
3. Frustration looks like: "again", "I already told you", "still", "how many times", all caps,
   or undoing the same change twice. Log `frustration` with the same detail.
4. If this is the second time or later, or the user sounds frustrated, create the fix at once:
   - Small things (word choice, tone, a type of job to skip, a small score nudge):
     `MEMORY lesson-add --text "<rule in plain words>" --scope <tailor|score|scan|all> --kind auto --source feedback --evidence "<the id field of each matching signal, comma separated, like S-1a2b3c4d5e6f,S-0f9e8d7c6b5a>"`
   - Bigger things (preferences, sources, daily cap, fact bank):
     `MEMORY proposal-add --text "<question for the user>" --kind <preference|source|cap|fact_bank> --patch '<json>'`
     then ask the user right now whether to accept, and run `MEMORY proposal-decide`.
   - Patch format: `{"file": "profile/preferences.json", "set": {"min_score": 4.0}}` or
     `{"file": "profile/preferences.json", "append": {"deal_breakers": ["contract"]}}`. For
     sources use dotted keys: `{"file": "profile/sources.json", "set": {"sources.dice.enabled": false}}`.
5. Tell the user in one line what you will do differently, for example:
   "Got it. I won't use 'spearheaded' again (lesson L-004)."

`memory.py` refuses any lesson that would add facts, skip the verify step, or skip approval.
If it refuses, explain that those rules protect the user and cannot be turned off.

## Finish

Rebuild the dashboard: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_dashboard.py"`. Reply
with one or two lines on what changed. If the dashboard is open, tell them to refresh it.

## Learning from this session
If the user corrects you, repeats an instruction they gave before, or sounds frustrated
("again", "I already told you", all caps, undoing the same change twice), log it:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal <repeat|frustration|edit> --skill <this skill> --job <id if any> --detail "<what went wrong>" --text "<their words>"`
Then fix the problem in this session. The weekly retro turns repeated signals into lessons.
