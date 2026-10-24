---
name: score
description: Scores how well the user fits each job on a 1 to 5 scale, with matched requirements backed by fact bank ids, missing skills sorted into gap categories, and deal breakers. Saves score.json and moves the job to scored or skipped. Safe to run unattended. Use when the user runs /job-search:score [job_id ...] or asks how well they fit a job.
---

# Score

Arguments: zero or more job ids. With none, score jobs with status `found`, best title match
first, up to `preferences.daily_cap * 3` jobs.

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

## Pick the jobs

If no ids were given, run
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" list --status found --rank --limit <daily_cap * 3> --json`.
It lists the best matches to the target titles first, then the newest. A job with a
`duplicate_of` field is the same role posted in another city. Do not score it. Mark it with
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" status <id> skipped --note "same role as <duplicate_of>"`
and do not count it.

Read these once for the whole batch:
- `<home>/profile/fact-bank.json`: the only evidence you may cite.
- `<home>/profile/preferences.json`: target titles, seniority, locations, remote, salary floor,
  must haves, deal breakers, industries, `min_score`.

## For each job

1. Read `<home>/jobs/<job_id>/job.json` and `jd.md`. If `jd.md` is empty or only a title,
   score from what is there, keep the score at 3 or below, and say so in the summary.
2. List the requirements in the posting. Mark each one required (under "requirements",
   "must have", "you have") or nice to have ("bonus", "preferred", "nice to have").
3. For each requirement, look for proof in the fact bank:
   - `matched`: there is a bullet, skill, project, certification or summary fact that shows it.
     `evidence` must list the real ids (`r1.b2`, `s.kubernetes`, `c1`). Use `strong` when the
     fact clearly covers it, `partial` when it is adjacent (Jenkins for "GitHub Actions",
     2 years for "5+ years"). No id, no match.
   - `missing`: nothing in the fact bank shows it. Write the plain name of the thing
     (`Terraform`, not "Strong experience with Terraform") with a category:
     `hard_skill`, `tool`, `cert`, `domain`, `seniority`, `soft_skill` or `other`, and
     `required` true or false. These feed the skills gap ledger, so be complete and specific.
     One thing per item, named the way most postings name it: `MySQL` and `Aurora`, not
     `MySQL/Aurora`; `dbt`, not "dbt or SQL transformation frameworks". When the posting
     accepts any one of several ("PyTorch, TensorFlow or JAX"), list each one the user lacks
     as its own item with `required: false`. Skip vague items ("production ML experience")
     unless you can name the concrete skill.
     Only list things a person can learn or earn. Work authorization, visas, citizenship,
     clearance, location, relocation, travel and on-site rules are not gaps: mention them in
     `summary`, and add them to `deal_breakers_hit` when they clash with the user's preferences.
4. `keywords`: 8 to 15 short terms and phrases the posting leans on (tools, practices, domain
   words). The tailor skill uses them to echo the posting's wording where facts allow.
5. `deal_breakers_hit`: any entry from `preferences.deal_breakers` the posting clearly
   triggers (for example "contract", "clearance required"), plus `industries_avoid` matches.
   Only list what the posting actually says.
6. Score honestly, 1.0 to 5.0, one decimal:
   - 5: meets every required item with strong evidence, title and seniority match.
   - 4: meets most required items, one or two gaps that are learnable.
   - 3: meets about half, or the level or location is off.
   - 2: big gaps in required items.
   - 1: different field.
   Take off up to 0.5 for location, remote or salary mismatches with preferences. Do not
   inflate a score to make the list look better.
7. `recommendation`: `apply` if score is at least `min_score`, `maybe` if within 0.5 below it,
   `skip` below that or when a deal breaker is hit. You may leave it out and the script fills it.
8. `summary`: two plain sentences on why, naming the biggest strength and the biggest gap.
9. Write the JSON to a temp file and save it:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/save_score.py" <job_id> --file <tmpfile> --json
   ```
   The script checks the shape, drops evidence ids that do not exist (with a warning),
   clamps the score, writes `jobs/<job_id>/score.json`, and sets status `scored` or `skipped`.
   If it reports dropped evidence, fix the ids and save again. If it exits 1, read the error,
   fix the JSON and retry once; if it still fails, skip the job and note it.

Shape to write:
```json
{
  "schema_version": 1,
  "score": 4.1,
  "recommendation": "apply",
  "summary": "Two sentences.",
  "matched": [{"requirement": "Kubernetes in production", "evidence": ["r1.b1", "s.kubernetes"], "strength": "strong"}],
  "missing": [{"item": "Terraform", "category": "tool", "required": true}],
  "keywords": ["kubernetes", "terraform", "developer platform"],
  "deal_breakers_hit": []
}
```

## Rules
- Never claim a match without a fact bank id. When in doubt, it goes in `missing`.
- Never ask questions. This skill runs unattended. If a job cannot be scored, skip it and
  mention it in the final summary.
- Do not change the fact bank or preferences here.

## Finish
Print one line per job: id, score, recommendation, top gap. Then a count of jobs scored and
skipped.

## Learning from this session
If the user corrects you, repeats an instruction they gave before, or sounds frustrated
("again", "I already told you", all caps, undoing the same change twice), log it:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal <repeat|frustration|edit> --skill <this skill> --job <id if any> --detail "<what went wrong>" --text "<their words>"`
Then fix the problem in this session. The weekly retro turns repeated signals into lessons.
