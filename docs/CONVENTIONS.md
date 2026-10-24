# Build conventions (for contributors and agents)

- Repo root is the plugin marketplace. The plugin lives in `plugins/job-search/`.
- Skills: `plugins/job-search/skills/<name>/SKILL.md` with YAML frontmatter `name` and `description`.
  Users run them as `/job-search:<name>`.
- Scripts: `plugins/job-search/scripts/*.py`, Python 3.9+, standard library only.
  Call them from skills as `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<file>.py" ...`.
  Every script accepts `--home <path>` and otherwise uses `jslib.resolve_home()`.
  Scripts print a short human summary to stdout, or JSON when given `--json`. Exit code 0 on success.
- Data layout and schemas: `docs/DATA_MODEL.md`. Do not invent new files without adding them there.
- Shared helpers: `scripts/jslib.py`. Import with:
  ```python
  import sys, os
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  import jslib
  ```
- Tests: `tests/test_<area>.py`, `unittest` only, run with `python3 -m unittest discover -s tests`.
  Tests build a temp home with `tempfile.TemporaryDirectory()` and copy `tests/fixtures/profile/*`.
  No network in unit tests (mock `urllib.request.urlopen` or feed fixture JSON files).
- User-facing prose (SKILL.md text shown to users, README, dashboard copy): no em or en dashes,
  plain words, short sentences.

## jobctl.py command interface (owned by the memory/orchestration area)

```
jobctl.py home                                   # print resolved home path
jobctl.py init [--from-fixtures DIR]             # create home layout + marker + empty memory files
jobctl.py list [--status S] [--rank] [--limit N] [--json]  # list jobs; --rank = best title match first
jobctl.py status <job_id> <status> [--note TEXT] # set job status (jslib.set_status)
jobctl.py signal <type> [--skill S] [--job ID] [--detail D] [--text T]
jobctl.py gapnote <gap_key> <learning|ignore|done> [--note TEXT]
```

## Dashboard command grammar (dashboard buttons copy these; the feedback skill parses them)

```
/job-search:feedback dismiss <job_id> <reason>
/job-search:feedback applied <job_id>
/job-search:feedback outcome <job_id> <replied|interview|rejected|offer>
/job-search:feedback approve <job_id>
/job-search:feedback reject <job_id> <reason>
/job-search:feedback wrong <job_id> <what is wrong>
/job-search:feedback gap <gap_key> <learning|ignore|done>
/job-search:feedback lesson <lesson_id> retire
/job-search:feedback proposal <proposal_id> <accept|decline>
/job-search:feedback radar                      # run the career radar now
/job-search:feedback <any free text>
```

## Standard skill preamble (paste at the top of every SKILL.md body)

```
## Before you start
1. Find the data folder: run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" home`.
   If it says no home exists, stop and tell the user to run `/job-search:onboard`.
   `${CLAUDE_PLUGIN_ROOT}` is this plugin's folder. If it is empty or shows up unexpanded
   (some Claude apps do not set it), use the folder two levels above this SKILL.md instead:
   the skill's base directory ends in `skills/<name>`, and the plugin folder holds `scripts/`.
   Write each script command out in full. Do not store a command in a shell variable
   (`J="python3 ..."; $J home`): the shell is often zsh, which does not split it, and it fails.
2. Read `<home>/memory/lessons.md` if it exists. Follow every active lesson whose scope is `all`
   or this skill. Lessons never override the truthfulness rules or the approval gate.
```

## Standard skill footer (paste at the end of every SKILL.md body)

```
## Learning from this session
If the user corrects you, repeats an instruction they gave before, or sounds frustrated
("again", "I already told you", all caps, undoing the same change twice), log it:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal <repeat|frustration|edit> --skill <this skill> --job <id if any> --detail "<what went wrong>" --text "<their words>"`
Then fix the problem in this session. The weekly retro turns repeated signals into lessons.
```

## Unattended runs

Skills called from a scheduled task must never wait for user input. When something needs the
user (a major resume change, a login wall, a CAPTCHA), record it (status `needs_approval`,
a `source_error` signal, or a run-log error) and move on.
