---
name: gaps
description: Rebuilds the skills gap ledger from every scored job and writes a short weekly nudge about the top 3 gaps that matter for the user's goals, with an honest link to their existing experience and one concrete next step each. Saves it to the runs folder as a dated nudge file. Safe to run unattended. Use when the user runs /job-search:gaps, asks what skills they are missing, or the weekly run calls it.
---

# Gaps

Runs without asking questions, so a scheduled task can call it.

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

1. Rebuild the ledger and see the ranking:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gaps.py" --top 15`
   Then get the draft nudge: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gaps.py" --nudge`
   and read `<home>/gaps.json` for the details (`items`, `ranking`).
   If there are no ranked gaps, write a one-line nudge that says so, save it (step 4) and stop.
   If `radar_only_rising` in `gaps.json` is not empty, add one closing line to the nudge:
   "Trending but not in your jobs yet: <skills>." Do not rank them; they are not your gaps yet.
2. Pick the top 3 gaps from `ranking` that fit the user's goals. The ranking already skips
   gaps marked `ignore` or `done` in `profile/gap-notes.json`, and boosts gaps that relate
   to `preferences.json` keywords and target titles (`related: true`). Skip a gap if it
   clearly conflicts with the user's preferences (for example, a deal breaker such as a
   security clearance, or a people-management gap when they target individual contributor
   roles). If a gap is marked `learning`, keep it and say how it is going in the ledger.
3. For each of the 3, write:
   - **How often:** "In N of M jobs (X%)" from `count` and `total_jds`, and whether it is
     usually required (`required_count` of `count`). Mention if it is rising, from `weekly`,
     or if the career radar marks it `rising` (say "your career radar marks it as rising").
   - **What you already have:** read `profile/fact-bank.json` and name the closest real
     experience by fact id (for example, Kubernetes on AWS EKS in `r1.b1` is close to GCP
     GKE work). Be honest. If nothing in the fact bank is close, say so plainly.
     Never suggest claiming experience the user does not have.
   - **One next step,** concrete and small. Pick one:
     a specific free course or official doc (name it, for example "HashiCorp's Terraform
     'Get Started - AWS' tutorials"), a weekend project that builds on their real work
     (for example, "rewrite the kube-cost-report CLI's deploy in Terraform"), or a resume
     bullet they could truthfully add **after** doing it, written in their voice, with
     no invented numbers. Only name courses or docs you are confident exist. Prefer
     official vendor docs and free material.
   - **Track it:** the command `/job-search:feedback gap <key> learning` (and `ignore` if
     they do not care about it).
4. Save the nudge as Markdown to `<home>/runs/nudge-<YYYY-MM-DD>.md` (today's date, UTC).
   Overwrite the file if it already exists for today. Format:

   ```
   # Skills nudge, <YYYY-MM-DD>

   From <M> scored jobs. Top gaps that fit your goals:

   ## 1. <Gap name>
   - How often: ...
   - What you already have: ...
   - Next step: ...
   - Track it: `/job-search:feedback gap <key> learning`

   (same for 2 and 3)
   ```
   Keep it under about 250 words. Plain words, short sentences, no em or en dashes.
5. Show the nudge to the user (or, when unattended, return it as the result) and mention
   the file path. If the dashboard is open, the Skills gaps tab shows the full ranked list
   and weekly trend after the next `/job-search:dashboard`.

Do not change `gap-notes.json` yourself. The user decides that through `/job-search:feedback`.

## Learning from this session
If the user corrects you, repeats an instruction they gave before, or sounds frustrated
("again", "I already told you", all caps, undoing the same change twice), log it:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal <repeat|frustration|edit> --skill <this skill> --job <id if any> --detail "<what went wrong>" --text "<their words>"`
Then fix the problem in this session. The weekly retro turns repeated signals into lessons.
