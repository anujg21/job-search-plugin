---
name: dashboard
description: Rebuilds the local job search dashboard (one static HTML file with the pipeline, job details, approvals, skills gaps, lessons and run log) and tells the user how to open it, as a file or at a local URL. Use when the user runs /job-search:dashboard or asks to see, open or refresh their dashboard.
---

# Dashboard

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

1. Rebuild the skills gap ledger so the gaps view is current:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gaps.py"`
2. Build the dashboard:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_dashboard.py"`
   It writes `<home>/dashboard.html`. The page makes no network requests and works offline.
3. Check whether the local server is already running:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/serve_dashboard.py" --check`
   Exit code 0 means it is running and `http://127.0.0.1:8765/dashboard.html` already works.
4. Tell the user, in a few short lines:
   - The file path, `<home>/dashboard.html`, and that they can open it in any browser
     (on a Mac: `open "<home>/dashboard.html"`).
   - If the server is running: the URL. Reload the page to see the new data.
   - If it is not running: offer to start it. A local URL is handy for bookmarking and makes
     the copy buttons work in every browser. If they say yes, start it in the background:
     `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/serve_dashboard.py"`
     (use the Bash tool's background mode) and give them the URL it prints. It listens on
     127.0.0.1 only, is read-only, and serves just the dashboard, each job's resume and
     answers files, and the career radar reports. Stop it any time by ending that background task.
5. Explain the buttons once, briefly: buttons on the page copy a command such as
   `/job-search:feedback applied <job_id>`. The user pastes it here, and the `feedback` skill
   acts on it. The page itself never changes any files.

If this skill runs unattended (from `run` or a scheduled task), do steps 1 and 2 only and
do not offer to start the server.

## Learning from this session
If the user corrects you, repeats an instruction they gave before, or sounds frustrated
("again", "I already told you", all caps, undoing the same change twice), log it:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal <repeat|frustration|edit> --skill <this skill> --job <id if any> --detail "<what went wrong>" --text "<their words>"`
Then fix the problem in this session. The weekly retro turns repeated signals into lessons.
