# Publishing and maintaining

For whoever hosts this repo. Users only need [INSTALL.md](INSTALL.md).

## How the repo is laid out

The repo root is a plugin marketplace. It lists one plugin.

```
.claude-plugin/marketplace.json     marketplace "job-search-tools", lists the plugin
plugins/job-search/
  .claude-plugin/plugin.json        plugin "job-search", version
  skills/<name>/SKILL.md            one folder per /job-search:<name> command
  scripts/*.py                      Python 3.9 standard library only
  sources/*.md                      one guide per job source
  templates/                        resume and dashboard templates
docs/                               these guides, plus DATA_MODEL.md and CONVENTIONS.md
tests/                              unit tests and fixtures
```

Users install it as `job-search@job-search-tools`. Keep both names as they are: changing either
breaks existing installs.

## First publish

The repo is [github.com/anujg21/job-search-plugin](https://github.com/anujg21/job-search-plugin).
Users add it as `anujg21/job-search-plugin`. A public repository is the simplest for other
people to add. If the repo ever moves, update that name in README.md and docs/INSTALL.md.

1. Run the checks below, then push.
2. Send people the link to
   [docs/INSTALL.md](https://github.com/anujg21/job-search-plugin/blob/main/docs/INSTALL.md).

## Checks before every release

```bash
python3 -m unittest discover -s tests
claude plugin validate .
claude plugin validate plugins/job-search
```

Then test the real thing on your own machine: install from the local folder (INSTALL.md,
option C) and run `/job-search:run daily` against a test data folder. A full headless run:

```bash
cd /path/to/test/JobSearch
JOBSEARCH_HOME=$PWD claude -p "/job-search:run daily" \
  --plugin-dir /path/to/job-search-plugin/plugins/job-search \
  --allowedTools "Bash Read Write Edit Glob Grep Skill"
```

`tests/fixtures/make_demo_home.py <dir>` builds a demo data folder with 25 jobs, approvals,
lessons and runs, which is handy for checking the dashboard.

## Releasing an update

1. Bump `version` in `plugins/job-search/.claude-plugin/plugin.json`.
2. Move the `Unreleased` notes in CHANGELOG.md under the new version.
3. Run the checks and push to the default branch.

Users get it when they click **Check for updates** in Claude Desktop (or have
**Sync automatically** on), or run `claude plugin marketplace update job-search-tools` and
`claude plugin update job-search@job-search-tools` in Claude Code.

Updates replace plugin files only. A user's data folder is never touched, so keep data
changes backward compatible: add fields instead of renaming them, and bump `schema_version`
in docs/DATA_MODEL.md only with a migration step in the scripts.

## Rules that keep the plugin trustworthy

- Never loosen `verify_resume.py` or the approval gate without a test that shows why.
- Lessons and suggestions can never change the truth rules or `auto_approve_minor` and
  `major_rewrite_ratio`. `memory.py` enforces this; keep its tests passing.
- Skills called by the schedule must never wait for input.
- No new Python dependencies. Users should not need `pip install`.
- User-facing text: plain words, no em or en dashes. A test checks the dashboard template.

## Support

- The weekly retro can draft an anonymized GitHub issue when it sees a plugin problem (a
  source that keeps failing, a score users keep overriding). The user reviews it before
  posting. These issues say they were drafted by the plugin and anonymized.
- Ask users for the output of `jobctl.py doctor` and the last lines of
  `~/JobSearch/runs/run-log.jsonl`. Never ask for their fact bank or resume.

## Adding a job source

Add `plugins/job-search/sources/<name>.md` with step by step instructions, add the source to
the `sources.json` template in `scripts/jobctl.py`, and if it has a public API add a parser to
`scripts/scan.py` with a recorded fixture in `tests/fixtures/api/`. See
`plugins/job-search/sources/README.md`.

## Later: a hosted version

PLAN.md section 5 keeps the path to a hosted product open: skills are the business logic, the
data folder maps one to one to tables, and source adapters are one file each. Nothing in the
current design needs to change to start that work.
