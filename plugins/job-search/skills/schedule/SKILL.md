---
name: schedule
description: Sets up the daily and weekly job search runs as scheduled tasks. Gives exact Claude Desktop steps with copy and paste values, or creates the schedule with a scheduling tool in Claude Code when one is available, then offers a test run. Use when the user runs /job-search:schedule or asks to automate or schedule the job search.
---

# Schedule

Keep this short and concrete. The user should be able to follow it with the app open next to
the chat.

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

## Step 1: pick a time

Ask what time the daily run should happen. Suggest a time the computer is usually on and
awake, like 8:00 AM. Weekly runs on Sunday at the same time unless they say otherwise.

## Step 2a: Claude Desktop (main path)

Print this, with `<home>` and `<time>` filled in:

```
In Claude Desktop:
1. Click "Scheduled" in the left sidebar.
2. Click "New task" (top right), then "Set up manually".
3. In "Create scheduled task", fill in:
   Task name:      Job search daily
   Prompt:         /job-search:run daily
   Approval mode:  the option that runs without stopping to ask you
   Frequency:      Daily, <time>
   Model:          leave the default
   Folder:         <home>
4. Click "Save".

Then make a second task the same way:
   Task name:      Job search weekly
   Prompt:         /job-search:run weekly
   Frequency:      Weekly, Sunday, <time>
   Folder:         <home>
```

Then add these notes, one line each:
- The folder matters. It is how each run finds your data, and because the task uses a folder
  on this computer, it runs on this computer. Keep the Mac awake and Claude Desktop open at
  that time, or that run may not happen.
- The approval mode matters too. If the task stops to ask before each step, nobody is there
  to answer. The run itself never submits an application or sends anything.
- The job-search plugin has to be installed in Claude Desktop (Customize, Plugins), or the task
  will not know `/job-search:run`.
- On Sunday both tasks run. That is fine. The second run finds nothing new and finishes fast.
- Instead of "Set up manually" you can pick "Create with Claude" and paste the values above
  when it asks. Or, from any conversation, ask Claude to run `/job-search:run daily` every day
  at <time> in <home>, check what it proposes, and click "Schedule".

## Step 2b: Claude Code CLI (other path)

If a scheduling tool is available in this session (for example a `schedule` skill, or a tool
that creates scheduled or cron tasks), offer to create both tasks with it:
- Daily at the chosen time: prompt `/job-search:run daily`, working folder `<home>`.
- Weekly on Sunday: prompt `/job-search:run weekly`, working folder `<home>`.
If the tool runs tasks in the cloud, warn that a cloud task cannot see files on this
computer or the user's signed-in Chrome, so it will not work for this plugin. Recommend the
Claude Desktop path instead.

If no scheduling tool is available, give the Claude Desktop steps above.

## Step 3: test it

Offer a test run now: "Want me to do a run now so you can see it work?" If yes, follow
`${CLAUDE_PLUGIN_ROOT}/skills/run/SKILL.md` with `daily`. For Claude Desktop, also suggest
they open the new task on the Scheduled page and run it on demand once, then check that
`<home>/runs/run-log.jsonl` got a new line and `<home>/dashboard.html` updated.

More help, including troubleshooting: `docs/SCHEDULING.md` in the plugin's GitHub repo.

## Learning from this session
If the user corrects you, repeats an instruction they gave before, or sounds frustrated
("again", "I already told you", all caps, undoing the same change twice), log it:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal <repeat|frustration|edit> --skill <this skill> --job <id if any> --detail "<what went wrong>" --text "<their words>"`
Then fix the problem in this session. The weekly retro turns repeated signals into lessons.
