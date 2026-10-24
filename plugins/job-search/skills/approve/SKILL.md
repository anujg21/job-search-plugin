---
name: approve
description: Shows tailored resumes waiting for approval (major changes or failed checks) with the reasons and before and after text, and records the user's approve or reject decision. When run unattended it only lists them. Use when the user runs /job-search:approve [job_id] or asks what needs their approval.
---

# Approve

Argument: an optional job id. With none, go through every job with status `needs_approval`.

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

1. Find the jobs: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" list --status needs_approval --json`
   (or just the one id given). If there are none, say so and stop.
2. For each job, read `jobs/<id>/job.json` and `jobs/<id>/changes.json` and show:
   - Company, title, score.
   - Why it needs approval: each entry in `reasons`.
   - The major changes, before and after: `headline_change`, `title_change`,
     `add_section`, `remove_section`, `skill_promote`. If the rewrite ratio is the reason,
     show the three `reword` changes with the biggest difference.
   - If `verify.passed` is false: list each `block` issue. Say plainly that this resume
     cannot be approved until it is fixed; offer to re-tailor instead.
   - Paths to `resume.pdf` (or `resume.html`) so they can look at the whole thing.
3. Ask: approve, reject (with a short reason), or skip for now.
4. Record the decision:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/approve.py" <id> approve
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/approve.py" <id> reject --reason "<their reason>"
   ```
   The script updates `changes.json` and `job.json` and logs the `approve_change` or
   `reject_change` signal itself. Do not log a second signal.
   Approve moves the job to `prepared`. Reject moves it back to `scored` so it can be
   tailored again. If the user wants that now, follow
   `${CLAUDE_PLUGIN_ROOT}/skills/tailor/SKILL.md` for this job and keep their reason in mind.
5. If the user asks for a small fix instead ("keep my headline, the rest is fine"), edit
   `resume.json` for that, then run `verify_resume.py`, `classify_changes.py` and
   `render_resume.py` for the job, and show the result again.

## Unattended runs
If no one is there to answer (scheduled task), do not wait. Print the list from step 2 and
stop. Decisions only come from the user.

## Learning from this session
If the user corrects you, repeats an instruction they gave before, or sounds frustrated
("again", "I already told you", all caps, undoing the same change twice), log it:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal <repeat|frustration|edit> --skill <this skill> --job <id if any> --detail "<what went wrong>" --text "<their words>"`
Then fix the problem in this session. The weekly retro turns repeated signals into lessons.
