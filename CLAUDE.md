# Working on this repo

## Releasing changes: bump the version in the same commit

Users only get an update when `version` in `plugins/job-search/.claude-plugin/plugin.json`
changes. So any change to the plugin (skills, scripts, sources, templates) ships with a
version bump in the same commit as the change, before the push. Never push the change first
and bump in a second push.

Before every push of plugin changes:

1. Bump `version` in `plugins/job-search/.claude-plugin/plugin.json`:
   patch (0.2.0 to 0.2.1) for fixes and wording, minor (0.2.0 to 0.3.0) for new skills,
   new behaviour or data changes.
2. Move the `Unreleased` notes in CHANGELOG.md under the new version with today's date
   (or add the notes there directly).
3. Run the checks:
   ```bash
   python3 -m unittest discover -s tests
   claude plugin validate .
   claude plugin validate plugins/job-search
   ```
4. Commit everything together, then push once.

Changes that only touch docs outside the plugin folder (README.md, docs/) or tests do not
need a bump.

## Other rules

- No personal names or emails in the repo. The owner is `anujg21`; commits use
  `anujg21 <anujg21@users.noreply.github.com>`.
- See docs/CONVENTIONS.md for script, skill and test rules, and docs/PUBLISHING.md for the
  full release notes.
