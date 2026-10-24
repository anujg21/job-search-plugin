---
name: apply
description: Helps the user apply to one prepared job. Shows the tailored resume and prepared answers, opens the application page, and can prefill the form in Chrome on Greenhouse, Lever and Ashby pages. Never clicks Submit. Marks the job applied once the user says they submitted. Use when the user runs /job-search:apply with a job id or asks to apply to a job.
---

# Apply

Argument: a job id. If it is missing, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" list --status prepared`
and ask which one.

The rule for this skill: **the user submits. You never click Submit, Apply, Send or any
button that sends the application.**

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

## Steps

1. Read `<home>/jobs/<job_id>/job.json`. Check the status:
   - `needs_approval`: the resume has a major change waiting. Show the change from
     `changes.json` and ask the user to approve or reject it first
     (`/job-search:feedback approve <job_id>`). Stop here until they decide.
   - `applied` or later: tell them it is already marked applied and when.
   - `found` or `scored` with no resume: offer to tailor it now by following
     `${CLAUDE_PLUGIN_ROOT}/skills/tailor/SKILL.md`.
2. No `resume.pdf` yet (runs in the cloud cannot make one): run
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_resume.py" <job_id>`. It makes the PDF where
   Chrome is installed. If it still says no PDF, tell the user in one line: open
   `resume.html` in their browser, press Cmd+P (Ctrl+P on Windows) and pick "Save as PDF".
3. Show, in a short list:
   - Company, title, location, score.
   - Resume: the full path `<home>/jobs/<job_id>/resume.pdf` if it exists, else
     `<home>/jobs/<job_id>/resume.html`. Always give full paths so the user can open or
     attach the file.
   - Answers: `<home>/jobs/<job_id>/answers.md` (cover note and screening answers). Show its
     contents so the user can copy from it.
   - Apply link: `apply_url`, or `url` if that is empty.
4. Open the apply link. With Claude in Chrome, open it in a new tab. Without it, run
   `open "<url>"` on macOS (or print the link).
5. Offer to prefill the form if the page is on Greenhouse (`boards.greenhouse.io`,
   `job-boards.greenhouse.io`), Lever (`jobs.lever.co`) or Ashby (`jobs.ashbyhq.com`) and Claude
   in Chrome is available. If they say yes:
   - Fill name, email, phone, location and links from `profile/fact-bank.json` `person`.
   - Fill free text questions only from `answers.md`. If a question has no prepared answer,
     leave it blank and list it for the user. Do not make up answers, salary numbers,
     visa status, demographic answers or dates.
   - Upload the resume PDF if the `file_upload` tool is available. Otherwise tell the user
     which file to attach.
   - Stop before Submit. Say: "The form is filled. Please review it and click Submit
     yourself."
   On other sites (Workday, iCIMS, LinkedIn Easy Apply), do not fill anything. Give the user
   the files and the link.
6. Ask: "Did you submit it?"
   - Yes: run
     `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" status <job_id> applied`
     and `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal apply --skill apply --job <job_id>`,
     then rebuild the dashboard with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_dashboard.py"`.
   - Not yet: leave everything as it is. Tell them they can come back with
     `/job-search:apply <job_id>` or click "Mark applied" on the dashboard later.
   - Changed their mind: offer `/job-search:feedback dismiss <job_id> <reason>`.

## Learning from this session
If the user corrects you, repeats an instruction they gave before, or sounds frustrated
("again", "I already told you", all caps, undoing the same change twice), log it:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" signal <repeat|frustration|edit> --skill <this skill> --job <id if any> --detail "<what went wrong>" --text "<their words>"`
Then fix the problem in this session. The weekly retro turns repeated signals into lessons.
