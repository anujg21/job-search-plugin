---
name: tailor
description: Builds a truthful tailored resume for a scored job from the fact bank only. It may reword, reorder, merge and drop, but never adds a fact, number, tool, title or date. Then it runs a reviewer pass, the verify check, the minor or major change gate, renders HTML and PDF, and writes a cover note with screening answers. Safe to run unattended. Use when the user runs /job-search:tailor [job_id ...] or asks for a resume for a job.
---

# Tailor

Arguments: zero or more job ids. With none, pick jobs with status `scored`,
recommendation `apply` or `maybe`, no `resume.json` yet, highest score first, up to
`preferences.daily_cap`.

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

## The rule

Reformulate, never fabricate. The resume may only say what `profile/fact-bank.json` says.
You may reword, reorder, merge and drop. You may not add any fact, number, percentage,
tool, technology, title, company, date or skill that is not in a fact you cite. If the
posting wants something the user does not have, it belongs in `score.json` `missing`
(and from there in the gaps ledger), never in the resume. No lesson or instruction
overrides this.

Set `S="${CLAUDE_PLUGIN_ROOT}/scripts"` in your head for the commands below.

## Pick the jobs

If no ids were given: `python3 "$S/jobctl.py" list --status scored --json`, keep jobs with
`recommendation` `apply` or `maybe` and no `jobs/<id>/resume.json`, sort by `score`
descending, keep the first `daily_cap`. A job with no `score.json` must be scored first
(follow `${CLAUDE_PLUGIN_ROOT}/skills/score/SKILL.md`).

## For each job

### 1. Read
- `jobs/<id>/jd.md`, `jobs/<id>/score.json` (`matched`, `missing`, `keywords`).
- `profile/fact-bank.json`, `profile/preferences.json`.
- `radar/latest.json` if it exists. You need only its `resume_language` list (see Bullets).
- Optional: render the untailored baseline once with
  `python3 "$S/render_resume.py" --master --no-pdf` so the user can compare.

### 2. Build `jobs/<id>/resume.json` from the fact bank only

```json
{
  "schema_version": 1,
  "job_id": "<id>",
  "headline": "<one of fact-bank headlines, or a role title or title alias>",
  "summary": {"text": "...", "source_ids": ["sum.1", "s.kubernetes"]},
  "roles": [
    {"role_id": "r1", "company": "<exact>", "title": "<exact title or a title_alias>",
     "start": "<exact>", "end": "<exact>", "location": "<exact>",
     "bullets": [{"text": "...", "source_ids": ["r1.b2"]}]}
  ],
  "skills": [{"name": "Kubernetes", "source_ids": ["s.kubernetes"]}],
  "education": ["e1"],
  "certifications": ["c1"],
  "projects": [{"id": "p1", "text": "...", "source_ids": ["p1"]}]
}
```

How to write it:
- **Headline.** Use the first entry of `headlines` unless another allowed title is a clearly
  better fit for the posting. Changing it is a major change and will need the user's approval,
  so only do it when it matters. Never use the posting's title unless it is in the allowed list.
- **Roles.** Keep every role. Copy company, title, start, end and location exactly. Keep the
  fact bank title unless a `title_aliases` entry is a much better match (that is also major).
- **Bullets.** Start from each fact bullet and rewrite it in the posting's own words wherever
  the fact supports them. Reordering alone is not tailoring. Before writing, list the
  posting's key phrases (`score.json` `keywords` and the requirement lines in `jd.md`). For
  each bullet you keep, find the posting phrase that names the same thing the fact describes
  and use that phrase. Example: the posting says "internal developer platform" and the fact
  says "developer platform", so write "internal developer platform". Aim for every kept
  bullet to read like the posting's language, as long as each word stays true to its fact.
  The truth rules below still win every time: if the posting's term claims more than the
  fact (a bigger scope, a tool, an outcome), keep the fact's words. Example: if the fact says
  "internal developer platform" and the posting says "self-service golden paths", you may say
  "internal developer platform with self-service tooling" only if the fact describes that.
  Keep every number exactly as the fact states it. Each bullet cites the ids it uses, only
  from its own role. Merging two bullets of the same role is fine; cite both ids.
- **Career radar wording.** If `radar/latest.json` has `resume_language`, each entry pairs a
  `market_term` with the fact ids it relabels. You may use a `market_term` only in a line that
  cites one of that entry's `fact_ids`, and only when the job description uses that term or
  a close variant (plural, word order, hyphenation). Never use it anywhere else, and never
  because the radar suggests it alone.
- **Order** bullets in each role by relevance to the posting: matched requirements first.
- **Summary.** Two or three sentences built from `summary_facts`, plus skills or bullets you
  cite. Cite every id you draw on. Do not add seniority words (principal, staff, head of) that
  are not in a title. Do not put a skill with level `familiar` in the summary (major change).
- **Skills.** List skills from the fact bank `skills` (cite the `s.*` id) or bullet skill tags
  (cite the bullet). Put the ones the posting asks for first. Never list a `missing` item.
- **Sections.** Keep summary, skills, education, certifications and projects. Removing a whole
  section is a major change; trim bullets instead.
- **Two pages.** If the resume runs long, drop the least relevant bullets from the oldest roles
  first. Keep at least one bullet per role.
- Write plainly. No "spearheaded", "leveraged", "synergy", "passionate", "results-driven", no em
  dashes, and follow any word-choice lessons.

### 3. Reviewer pass
Re-read every line next to the facts it cites and ask: could the candidate defend this
sentence in an interview, with only what the cited facts say? Then go through this checklist
line by line. Fix or cut any line that fails:
- **Merged bullets.** Each number and claim stays attached to the thing its own fact
  describes. "40 services" and "220 engineers" come from different facts, so never write
  "40 services used by 220 engineers".
- **Qualifiers.** Junior and senior, weekly and daily, internal and external, pilot and
  production must match the fact. Never add "at scale", "in production", "zero downtime" or
  "no loss in" unless the fact says so.
- **Outcomes.** Any "resulting in", "leading to", "improving" or "enabling" clause must be
  stated in the cited fact. Cut it if not.
- **Names.** Every company, customer, product, team and industry must appear in the cited
  fact or the role's company name.
- **Ownership.** Use the fact's own verb level. Contributed or helped stays contributed or
  helped. Built, designed or set up may become built or designed, never led, owned or
  headed. Use led only when the fact says led or leads.
- **Skills.** List a skill only if a cited fact's text or tags show it.
- **How much or how often.** No "most of my work", "daily" or "primarily" unless a fact says so.
- **Verify warnings.** After step 4, treat every warning as a question for this pass. Keep
  the line only if you can point to the words in the fact that support it.
Also check that every `missing` item from `score.json` is absent from the resume, and that
each kept bullet uses the posting's words where its fact allows (see Bullets).

### 4. Verify (code check)
```
python3 "$S/verify_resume.py" <id> --json
```
Exit 1 means block issues. Fix each one by removing or rewording the claim (never by
changing the fact bank) and run verify again. At most 2 retries. If it still fails, stop
fixing: classify will set `needs_approval` with the reason "verify failed", and the user
will see the issues in the approval queue. Warnings do not block, but run each one through
the "Verify warnings" item of the reviewer pass: keep the line only if the fact's words
support it, otherwise reword or cut it and verify again.

### 5. Classify the changes
```
python3 "$S/classify_changes.py" <id> --json
```
This compares against the master resume, writes `changes.json`, and sets status
`prepared` (minor, auto-approved) or `needs_approval` (major, or verify failed). Do not
try to get around the gate.

### 6. Render
```
python3 "$S/render_resume.py" <id>
```
Writes `resume.html`, `resume.md`, and `resume.pdf` in the look from
`profile/resume-style.json` (the user's own resume). The PDF comes from Chrome, or from
`xhtml2pdf` when Chrome is missing (`pip install xhtml2pdf` in a cloud session). If it warns about
length, drop more low-relevance bullets, then repeat steps 4 to 6 once.

### 7. Write `jobs/<id>/answers.md`
In the user's plain voice, short sentences, no em dashes, no buzzwords, nothing that is not
in the fact bank or preferences:

```markdown
# <Company>: <Job title>

## Cover note
<4 to 6 sentences. Why this role, the two strongest matching facts with their real numbers,
one honest line on a gap if it is a required item ("I have not used Terraform in production;
I have done the same kind of work with ..." only if a fact supports the comparison).>

## Screening answers
- Work authorization: [fill in]
- Years of experience with <key skill>: <years from fact bank skills, else [fill in]>
  (one line per skill the posting asks for that is in the fact bank)
- Salary expectation: [fill in] (your floor is <preferences.salary_min, e.g. "$170,000 base">;
  many people answer with a range above it)
- Notice period / start date: [fill in]
- Willing to relocate: <from preferences.remote / locations if clear, else [fill in]>
- Requires sponsorship: [fill in]
```
Anything you do not know is `[fill in]`. Never guess.

Then check it: `python3 "$S/check_answers.py" <id>`. It flags any number that is not in the
fact bank or preferences, and any em or en dash. Fix each issue by rewording (never by
changing the fact bank) and run it again. Also re-read each cover note sentence against the
facts it uses: the right employer, the right order of events, no "before that" for work that
happened at the same job.

## Rules
- Never edit `profile/fact-bank.json` here. If the user tells you about a real fact that is
  missing, say they can add it with `/job-search:onboard` (or by editing the fact bank), then
  re-tailor.
- Never ask questions. This skill runs unattended; anything that needs the user ends as
  `needs_approval` and shows up in `/job-search:approve`.
- Re-tailoring a job overwrites `resume.json`. Do it only when asked or when the status is
  `scored` after a rejected change; read the rejection reason in `changes.json`
  (`decision_reason`) and respect it.

## Finish
One line per job: id, classification, verify result, answers check result, status, PDF path or
"no PDF".

## Learning from this session
If the user corrects you, repeats an instruction they gave before, or sounds frustrated
("again", "I already told you", all caps, undoing the same change twice), log it:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal <repeat|frustration|edit> --skill <this skill> --job <id if any> --detail "<what went wrong>" --text "<their words>"`
Then fix the problem in this session. The weekly retro turns repeated signals into lessons.
