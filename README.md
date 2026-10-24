# Job Search for Claude

A Claude plugin that runs your job search every day. It finds jobs on the boards you pick,
scores how well each one fits you, tailors your resume for the best few without inventing
anything, tracks the skills your target jobs keep asking for, and learns from your feedback.
Once a month its Career Trend Radar checks where your field is heading.

It runs on your own Claude plan. There is no server, no account and no API key. Your data
stays in one folder on your computer.

## Start here

| I want to | Read |
|---|---|
| Install it and set it up | [docs/INSTALL.md](docs/INSTALL.md) |
| Make it run every day | [docs/SCHEDULING.md](docs/SCHEDULING.md) |
| Learn the dashboard and everyday tasks | [docs/USER_GUIDE.md](docs/USER_GUIDE.md) |
| Publish or maintain this repo | [docs/PUBLISHING.md](docs/PUBLISHING.md) |
| Understand the files and data | [docs/DATA_MODEL.md](docs/DATA_MODEL.md) |

## Set up in Claude Desktop

1. In the **Cowork** tab, open **Customize**, then **Plugins**. Click **Add**, then
   **Add marketplace**, and enter `anujg21/job-search-plugin`.
2. Under **Discover**, install **job-search**.
3. Connect the Dice and Indeed connectors and set them to Always allow (see
   [Connectors](#connectors)).
4. Start a Cowork task in a folder called `JobSearch` and type `/job-search:onboard`. It reads
   your resume, researches job titles that fit it, and sets up which boards to search.
5. Type `/job-search:schedule` and copy its values into two scheduled tasks, one daily and one
   weekly.
6. After the first run, open `~/JobSearch/dashboard.html` in your browser.

Stuck at any point? Type `/job-search:help`, or just ask how something works.

Claude Code users: `claude plugin marketplace add anujg21/job-search-plugin`, then
`claude plugin install job-search@job-search-tools`. Details for both are in
[INSTALL.md](docs/INSTALL.md).

## What using it looks like

Each morning the daily run scans your boards, scores new jobs, and prepares a tailored resume,
cover note and screening answers for the top few. The dashboard shows a funnel from found to
interview, each job's fit, what changed in its resume, the skills you are missing most often,
and the radar's view of titles and trends.

A few times a week you open the dashboard, approve or reject what is waiting, apply to the jobs
you like (the plugin can fill in the form, you click Submit), and log replies. Each dashboard
button copies a short command to paste into Claude. On Sundays it sends a skills nudge and
turns your feedback into lessons.

## The truth rule

The tailored resume can only say what your fact bank says. Onboarding turns your resume into a
list of facts, each with an id, and you confirm it. Tailoring may reword, reorder, merge and
drop those facts, and use the job post's own words when a fact supports them. It may not add a
skill, number, title, employer, date or scope you do not have. A check runs on every tailored
resume and blocks anything it cannot trace to a fact.

Skills a job asks for that you lack go to your skills gap list, never into the resume. Big
resume changes wait for your approval. The plugin never submits an application.

## Commands

| Command | What it does |
|---|---|
| `/job-search:onboard` | Setup, or change your fact bank, preferences and sources |
| `/job-search:schedule` | Set up the daily and weekly runs |
| `/job-search:run daily` | Scan, score, tailor the top few, update gaps and the dashboard |
| `/job-search:run weekly` | The daily run plus the skills nudge, the retro and the monthly radar |
| `/job-search:scan` | Fetch new jobs from your sources |
| `/job-search:score` | Score jobs against your fact bank |
| `/job-search:tailor <job_id>` | Tailor your resume for one job |
| `/job-search:approve` | Review resume changes waiting for you |
| `/job-search:apply <job_id>` | Get the resume, answers and link ready to apply |
| `/job-search:gaps` | Your top skill gaps and what to do about each |
| `/job-search:radar` | Career Trend Radar: titles that fit, rising skills, where your field is heading |
| `/job-search:dashboard` | Rebuild the dashboard and open it |
| `/job-search:feedback <text>` | Tell it what is wrong, or paste a dashboard command |
| `/job-search:retro` | Turn recent feedback into lessons and suggestions |
| `/job-search:help` | Ask how anything works, or what to do next |

## Job sources

| Source | How | Login |
|---|---|---|
| Greenhouse, Lever, Ashby | Public job board APIs, per company | None |
| Dice | Dice's public connector, searched by your titles | None |
| Indeed | The Indeed connector (bundled), else your Chrome or web search | Your Indeed account, once, to connect it |
| LinkedIn | Read in your Chrome, a few saved searches only | Your LinkedIn account |

The plugin bundles the Dice and Indeed connectors. LinkedIn has no job search connector.

### Connectors

The plugin ships two job connectors, **Dice** and **Indeed**, and keeps it at that. LinkedIn
has no job search connector. You can add other job connectors yourself.

**Connect Dice and Indeed (one time, only you can do this):**

1. In Claude Desktop or claude.ai, open **Customize**, then **Plugins**, then **Job search**,
   and open the **Connectors** tab.
2. Click **Connect** next to **Dice**. It needs no account.
3. Click **Connect** next to **Indeed** and sign in with your Indeed account.
4. Go to **Customize > Connectors**, select each one, find **Tool permissions** and choose
   **Always allow**. Scheduled runs cannot stop to ask, so a connector left on
   "Needs approval" is skipped in them.

In Claude Code, run `/mcp`, pick `dice` or `indeed`, and follow the prompt. Also add
`mcp.dice.com` to the claude.ai domain allowlist (Settings, Capabilities), next to the job
board domains, so Dice works even without its connector. Onboarding shows these steps, and
`jobctl.py doctor` warns "Connector dice" or "Connector indeed" until each one works.

**Add another job connector (optional):**

1. Go to **Customize > Connectors** and click **+** next to **Connectors** to open the
   directory. Search for the job site, for example ZipRecruiter.
2. Click it, then **Connect**, and finish the sign-in if it asks.
3. Under **Tool permissions**, choose **Always allow**.
4. Tell Claude "add ZipRecruiter as a job source", or run `/job-search:onboard` and pick
   "Job sources". It is saved under `extra_connectors` in `profile/sources.json`, and every
   scan searches it with your target titles.

A job site that is not in the directory but runs its own MCP server can be added as a
custom connector: **Customize > Connectors**, **Add**, **Custom**, **Web**, then its server
URL. On Team and Enterprise plans an Owner adds connectors and sets tool permissions for
everyone. Details: `plugins/job-search/sources/other-connectors.md`.

Anthropic's guides:
[Use connectors](https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities),
[Browse the directory](https://support.claude.com/en/articles/14328846-browse-skills-connectors-and-plugins-in-one-directory),
[Custom connectors with remote MCP](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp),
[Scheduled tasks in Cowork](https://support.claude.com/en/articles/13854387-schedule-recurring-tasks-in-cowork).

LinkedIn is read only and low volume on purpose. Its terms forbid scraping and bots, so the
plugin reads a few of your saved searches and never applies or messages anyone.

## Requirements

- A paid Claude plan. Scheduled runs need Claude Desktop.
- Python 3.9 or newer (macOS includes it).
- Google Chrome, for the LinkedIn source and PDF resumes on your computer. Cloud runs make
  PDFs without it.

## Privacy

Everything stays in your data folder. The plugin reads public job boards, plus the sites you
are signed in to through your own Chrome. It does not send your resume or profile anywhere.
Claude processes your data as part of your normal Claude use. If you choose to file a plugin
bug from a retro suggestion, the draft has your name, email, phone and employers removed, and
you review it before posting.

## ChatGPT and Codex

The skills are plain Markdown and the scripts are plain Python, so the same repo can serve
Codex later. That is planned. ChatGPT desktop tasks cannot work with local files, so they are
out of scope for now.

## Credits

The Career Trend Radar is anujg21's own skill, written for this plugin and also usable on
its own.

This plugin borrows ideas from these open source projects, all MIT licensed. Thank you to their
authors.

- [career-ops](https://github.com/career-ops-hq/career-ops): Greenhouse, Lever and Ashby
  adapters, the liveness check, the 1 to 5 fit score, and "reformulate, never fabricate".
- [ai-job-search](https://github.com/MadsLorentzen/ai-job-search): missing keywords become
  gaps, the reviewer pass, the gap heatmap and the offline HTML report.
- [JobPilot](https://github.com/suxrobgm/jobpilot): plugin packaging, source toggles and
  reading boards in your real browser.
- [Job-Agent-Public](https://github.com/MikaIsmayilov/Job-Agent-Public): the onboard
  interview and the daily top N queue.
- [ResumeSkills](https://github.com/Paramchoudhary/ResumeSkills): truthful resume tailoring
  prompt wording.
- [JobSpy](https://pypi.org/project/python-jobspy/): Indeed and LinkedIn search fields and
  rate limit habits.

## License

MIT. See [LICENSE](LICENSE).
