# Install and set up

This takes about 15 minutes, most of it answering the setup questions.

## Before you start

You need:

- A paid Claude plan (Pro, Max, Team or Enterprise). Plugins and scheduled tasks are paid features.
- Claude Desktop for scheduled runs. Claude Code in the terminal also works for everything except
  the Desktop scheduler.
- Python 3.9 or newer. macOS already has it. Check with `python3 --version`.
- Google Chrome. It turns tailored resumes into PDFs and reads LinkedIn with your own
  sign-in. Without Chrome you still get HTML resumes and every other source.
- Your resume as a PDF, Word file, Markdown or plain text.

The plugin lives at [github.com/anujg21/job-search-plugin](https://github.com/anujg21/job-search-plugin).

## Option A: Claude Desktop (recommended)

1. Open Claude Desktop and switch to the **Cowork** tab.
2. Click **Customize** in the left sidebar, then open **Plugins**.
3. Click **Add**, choose **Add marketplace**, then **Add from a repository**.
4. Enter `anujg21/job-search-plugin` (or the full `https://github.com/anujg21/job-search-plugin`
   URL) and confirm.
5. Open the **Discover** tab, find **job-search**, and click **Install**.
6. Start a new Cowork task. When it asks which folder to work in, create or pick a folder
   called `JobSearch` in your home folder. The plugin keeps all your data there.
7. Connect the bundled connectors: in **Customize**, **Plugins**, open **Job search**, then
   the **Connectors** tab. Click **Connect** next to **Dice** (no account needed) and next to
   **Indeed** (sign in with your Indeed account). Only you can do this step.
8. Type `/job-search:onboard` and press Enter. You can also type `/` to browse the plugin's
   commands.

Run onboarding in Claude Desktop, not in claude.ai in a browser. A browser session runs in
a cloud sandbox: it can reach your data folder through your connected Mac, but it cannot
check job boards, your Chrome sign-ins, or run the setup check. Use the browser for quick
questions and the dashboard commands.

Menu labels can differ a little between app versions. Anthropic's guide is
[Use plugins in Claude](https://support.claude.com/en/articles/13837440-use-plugins-in-claude).

## Option B: Claude Code in the terminal

```bash
claude plugin marketplace add anujg21/job-search-plugin
claude plugin install job-search@job-search-tools
cd ~ && mkdir -p JobSearch && cd JobSearch
claude
```

Then run `/mcp`, pick `dice` and `indeed` in turn, and connect them (Indeed asks you to sign
in). Then type `/job-search:onboard` in the session. Inside a session you can also run
`/plugin marketplace add anujg21/job-search-plugin` and install from the `/plugin` panel.

## Option C: a local copy (for testing changes)

Clone the repo and point Claude Code at the folder:

```bash
git clone https://github.com/anujg21/job-search-plugin.git
claude plugin marketplace add ./job-search-plugin
claude plugin install job-search@job-search-tools
```

Edits to the local files take effect at the next session start, or after `/reload-plugins`.
For a one-off session without installing, use
`claude --plugin-dir ./job-search-plugin/plugins/job-search`.

## Set up with onboarding

`/job-search:onboard` walks you through five steps. You can stop and rerun it at any time; it
edits what is there instead of starting over.

1. **Data folder.** The default is `~/JobSearch`.
2. **Resume.** Give it the file path. It turns the resume into a fact bank: every role,
   bullet, number, skill, certificate and date, each with an id. It shows you the result.
   Correct anything wrong. This fact bank is the only thing a tailored resume can draw from,
   so it is worth five careful minutes.
3. **Preferences.** It asks where you want to work, then runs the Career Trend Radar (about
   5 to 10 minutes of research) and shows the job titles that fit your resume. Pick the ones
   you want and add any others. Then come seniority, salary floor, deal breakers, title words
   to skip, countries you can work in, how many resumes to prepare per day, and the minimum
   fit score. Say "skip" during the research to name titles yourself. The radar runs once
   here; later chats reuse it and ask before running it again.
4. **Job sources.** Naming companies is optional. It offers the company job boards the radar
   found, and checks any company you name on Greenhouse, Lever and Ashby. Dice is on with no
   account. For Indeed it asks you to connect the Indeed connector (one Indeed sign-in). For
   LinkedIn it opens the site in your Chrome and checks whether you are signed in. If you are
   not, it leaves the site open so you can sign in, or you can skip it. It builds the searches
   from your titles and locations.
5. **Health check.** It runs `jobctl.py doctor` and offers to set up the schedule and do a
   first run.

## Schedule it

Run `/job-search:schedule`. It prints the values to paste into Claude Desktop for two tasks:

| Task | Prompt | When |
|---|---|---|
| Job search daily | `/job-search:run daily` | Every day, at a time your Mac is on |
| Job search weekly | `/job-search:run weekly` | Sundays |

Set each task's folder to your data folder. [SCHEDULING.md](SCHEDULING.md) has the full steps
and troubleshooting.

## Open the dashboard

After the first run, open `~/JobSearch/dashboard.html` in your browser (double-click it in
Finder). Bookmark it. Every run rebuilds it, so a refresh shows the latest.

If you prefer a local web address, run `/job-search:dashboard` and accept the offer to start
the local server. It serves the page at `http://127.0.0.1:8765/dashboard.html`, on your
computer only.

[USER_GUIDE.md](USER_GUIDE.md) explains each part of the dashboard.

## Check that everything works

```bash
python3 <plugin folder>/scripts/jobctl.py doctor
```

Or ask Claude: "run the job-search doctor". It checks the data folder, your profile files, the
fact bank, enabled sources, Python and Chrome, and prints a pass or fail list.

## Update

- **Claude Desktop:** Customize, Plugins, open the marketplace, click **Check for updates**.
  Turn on **Sync automatically** to skip this step.
- **Claude Code:** `claude plugin marketplace update job-search-tools`, then
  `claude plugin update job-search@job-search-tools`.

Updates never touch your data folder.

## Uninstall

- **Claude Desktop:** Customize, Plugins, open job-search, click **Remove**. Delete the two
  scheduled tasks from the Scheduled page.
- **Claude Code:** `claude plugin uninstall job-search@job-search-tools`.

Your data stays in `~/JobSearch` until you delete that folder yourself.

## Troubleshooting

| Problem | Fix |
|---|---|
| Desktop still runs the old version after an update | claude.ai can show the new version before Claude Desktop does. Quit and reopen Claude Desktop so it syncs plugins again. |
| Not sure what to do next | Type `/job-search:help`. It looks at your setup and suggests the next step. |
| `/job-search:...` commands do not show up | Check the plugin is installed and enabled under Customize, Plugins. Start a new task or session after installing. |
| "No job-search home" | Run `/job-search:onboard`, or pick your data folder as the task's working folder. |
| A scheduled run cannot find your data | Set the task's folder to your data folder. See [SCHEDULING.md](SCHEDULING.md). |
| No PDF next to a tailored resume | Scheduled and claude.ai runs happen in a cloud sandbox without Chrome. `/job-search:apply <job_id>` makes the PDF on a computer with Chrome. Or open `resume.html` in your browser and print it to PDF. |
| Doctor says "Connector dice" or "Connector indeed" | Customize, Plugins, Job search, Connectors tab, then Connect next to it (in Claude Code, `/mcp`). The warning clears after the next scan sees it working. |
| Indeed found little | Connect the Indeed connector as above. Without it, Indeed uses Chrome or web search. |
| Dice found nothing in a cloud run | Connect the Dice connector as above, or add `mcp.dice.com` to the domain allowlist (Settings, Capabilities). |
| LinkedIn found nothing | Sign in to LinkedIn in Chrome and make sure the Claude in Chrome extension is connected. Then run `/job-search:onboard`, pick Job sources, and it checks access again. A login wall or CAPTCHA is logged and skipped, never solved. Scheduled cloud runs have no Chrome and skip LinkedIn. |
| Too many or too few jobs | Change target titles, title words to skip, or countries with `/job-search:onboard`. Jobs still waiting to be scored are re-filtered on the next run. |
