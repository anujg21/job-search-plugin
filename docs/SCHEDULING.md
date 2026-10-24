# Scheduling the job search

The plugin does its work in two runs:

| Run | Prompt | When | What it does |
|---|---|---|---|
| Daily | `/job-search:run daily` | Every day | Scan sources, score new jobs, tailor the top few, update gaps, rebuild the dashboard |
| Weekly | `/job-search:run weekly` | Sunday | The daily steps, plus the skills gap nudge and the retro that turns feedback into lessons |

Both runs are unattended. They never ask questions and never submit anything. Anything that
needs you (a major resume change, a login wall) waits on the dashboard.

The quickest way to set this up is `/job-search:schedule`. This page is the long version.

## Claude Desktop (recommended)

A Cowork scheduled task runs in Claude's cloud sandbox and reaches your data folder through
your connected Mac
([Anthropic help article](https://support.claude.com/en/articles/13854387-schedule-recurring-tasks-in-cowork)).
So the Mac should be awake, with Claude Desktop open, at the scheduled time. The sandbox only
reaches the web domains your account allows, so add the job board domains first (see
"network blocked" under Troubleshooting). Connectors are not affected by the allowlist, so
connect the Indeed connector for the best Indeed results. The sandbox has no Chrome, so
LinkedIn is skipped and resumes come as HTML. `/job-search:apply` makes the PDF when you
apply, or open `resume.html` and print it to PDF.

1. Open Claude Desktop and switch to Cowork.
2. Click **Scheduled** in the left sidebar.
3. Click **New task** in the upper right, then **Set up manually**.
4. In **Create scheduled task**, fill in:

   | Field | Value |
   |---|---|
   | Task name | `Job search daily` |
   | Prompt | `/job-search:run daily` |
   | Approval mode | The option that runs without stopping to ask you. Nobody is there to answer, and the run never submits anything. |
   | Frequency | Daily, at a time your Mac is usually awake (for example 8:00 AM) |
   | Model | Leave the default |
   | Folder | Your data folder, for example `/Users/you/JobSearch` |

5. Click **Save**.
6. Make a second task the same way:

   | Field | Value |
   |---|---|
   | Task name | `Job search weekly` |
   | Prompt | `/job-search:run weekly` |
   | Frequency | Weekly, Sunday, same time |
   | Folder | Same data folder |

You can also pick **Create with Claude** instead of **Set up manually**, answer its
questions with the values above, review what it proposes, and click **Schedule**.

On Sunday both tasks run. That is fine: the second run finds nothing new and finishes fast.

The Scheduled page lists upcoming and past runs. Click a task to edit its prompt or
frequency, pause or resume it, run it on demand, or delete it.

### Why the working folder matters

Scripts look for the data folder in this order: a `--home` argument, the `JOBSEARCH_HOME`
environment variable, the current working folder if it has a `jobsearch.json` file, then
`~/JobSearch`. Setting the task's working folder to your data folder makes the run find it
even if you keep it somewhere other than `~/JobSearch`.

### Test it

Open the new task on the **Scheduled** page and run it on demand. When it finishes:
- `runs/run-log.jsonl` in your data folder has a new line.
- `dashboard.html` shows today's date in the run log.
- The task output ends with a five line summary.

## Claude Code CLI

If your Claude Code has a scheduling tool, `/job-search:schedule` offers to create the two
tasks for you. Check where the tool runs the task:
- **On your computer**: works the same as Claude Desktop.
- **In the cloud**: will not work. A cloud task cannot see your data folder or your Chrome.

You can also use your operating system's scheduler to start Claude Code headless. On macOS
with cron, for example:

```
0 8 * * *  cd ~/JobSearch && claude -p "/job-search:run daily"
0 9 * * 0  cd ~/JobSearch && claude -p "/job-search:run weekly"
```

This needs the plugin installed in Claude Code and the `claude` command on cron's `PATH`.

## Troubleshooting

**The task says "No job-search home".**
The working folder is wrong, or onboarding has not run. Set the task's working folder to
your data folder, or run `/job-search:onboard`.

**The task says the skill or command is unknown.**
The plugin is not installed where the task runs. In Claude Desktop, add it in the Cowork
plugins panel. In Claude Code, run `/plugin install job-search@job-search-tools`.

**The run did not happen, or says it could not reach the data folder.**
A Cowork scheduled task runs in Claude's cloud sandbox and reaches your data folder through
your connected Mac. If the Mac was asleep or Claude Desktop was closed, it cannot reach the
folder. Pick a time the Mac is usually on and keep Claude Desktop running.

**Every board failed with "network blocked" or HTTP 403.**
The cloud sandbox only reaches allowed domains. On claude.ai open Settings, then
Capabilities, and under Domain allowlist add `boards-api.greenhouse.io`, `api.lever.co`,
`api.ashbyhq.com` and `mcp.dice.com`. Your company list is fine; the next run picks the
boards up. Indeed still runs in the meantime through its connector or web search, and Dice
through its connector if you turned it on. Commands the cloud session runs on your Mac go
through the same allowlist, so they fail too. Running `/job-search:run daily` from Claude
Code in your own terminal is not affected.

**The run stopped halfway, waiting for approval.**
The task's approval mode asks before each step. Edit the task and pick the approval mode that
runs without asking. The run never submits applications or sends messages, whatever the mode.

**LinkedIn shows "not signed in" or "no browser" in the run log.**
A scheduled cloud run has no Chrome, so it always skips LinkedIn. To include LinkedIn, run
`/job-search:scan linkedin` in a chat while Chrome is open and you are signed in. If you do
not want LinkedIn, turn it off with `/job-search:onboard`.

**Dice or Indeed say "connector did not load in this run".**
Scheduled runs sometimes start before connectors load, even when they are connected. Add
`mcp.dice.com` to the domain allowlist so Dice works without its connector. Indeed falls
back to web search in that run; `/job-search:scan indeed` in a chat uses the connector.

**Indeed shows "connector not connected".**
Connect it once: Customize, then Connectors, find Indeed and click Connect, then sign in to
Indeed. Until then Indeed uses web search.

**No PDF resumes, only HTML.**
Google Chrome is not installed in a standard place. Install it, or set `CHROME_PATH` to its
binary. `jobctl.py doctor` shows what it found.

**Runs take too long.**
Lower `daily_cap` in `profile/preferences.json`, or watch fewer companies. Scoring is capped
at three times the daily cap per run.

**Check everything at once.**
```
python3 "<plugin folder>/scripts/jobctl.py" doctor
```
It checks the data folder, profile files, fact bank, sources, Python and Chrome.
