# Install and set up

This takes about 15 minutes, most of it answering the setup questions.

## Before you start

You need:

- A paid Claude plan (Pro, Max, Team or Enterprise). Plugins and scheduled tasks are paid features.
- Claude Desktop for scheduled runs. Claude Code in the terminal also works for everything except
  the Desktop scheduler.
- Python 3.9 or newer. macOS already has it. Check with `python3 --version`.
- Google Chrome. It turns tailored resumes into PDFs and reads Indeed, Dice and LinkedIn with
  your own sign-in. Without Chrome you still get HTML resumes and the Greenhouse, Lever and
  Ashby job boards.
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
7. Type `/job-search:onboard` and press Enter. You can also type `/` to browse the plugin's
   commands.

Menu labels can differ a little between app versions. Anthropic's guide is
[Use plugins in Claude](https://support.claude.com/en/articles/13837440-use-plugins-in-claude).

## Option B: Claude Code in the terminal

```bash
claude plugin marketplace add anujg21/job-search-plugin
claude plugin install job-search@job-search-tools
cd ~ && mkdir -p JobSearch && cd JobSearch
claude
```

Then type `/job-search:onboard` in the session. Inside a session you can also run
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
3. **Preferences.** Target titles, seniority, locations and remote, salary floor, deal
   breakers, title words to skip, countries you can work in, how many resumes to prepare per
   day, and the minimum fit score. Not sure which titles to target? Say yes when it offers the
   Career Trend Radar (about 5 to 10 minutes of research).
4. **Job sources.** Name companies you like; it finds their Greenhouse, Lever or Ashby job
   boards. For Indeed, Dice and LinkedIn it asks whether you are signed in to them in Chrome.
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
| `/job-search:...` commands do not show up | Check the plugin is installed and enabled under Customize, Plugins. Start a new task or session after installing. |
| "No job-search home" | Run `/job-search:onboard`, or pick your data folder as the task's working folder. |
| A scheduled run cannot find your data | Set the task's folder to your data folder. See [SCHEDULING.md](SCHEDULING.md). |
| No PDF next to a tailored resume | Chrome was not available where the run happened. Open `resume.html` and print it to PDF, or install Chrome. |
| Indeed, Dice or LinkedIn found nothing | Sign in to that site in Chrome and make sure the Claude in Chrome extension is connected. A login wall or CAPTCHA is logged and skipped, never solved. |
| Too many or too few jobs | Change target titles, title words to skip, or countries with `/job-search:onboard`. Jobs still waiting to be scored are re-filtered on the next run. |
