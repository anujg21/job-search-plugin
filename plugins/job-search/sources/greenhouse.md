# Greenhouse

Handled by `scripts/scan.py`. No login and no browser needed.

API: `https://boards-api.greenhouse.io/v1/boards/<token>/jobs?content=true`

## Finding a company's board token

The token is the part of the job board URL after the host:

- `https://boards.greenhouse.io/stripe` gives `stripe`
- `https://job-boards.greenhouse.io/datadog/jobs/123` gives `datadog`
- A company careers page that links to `...greenhouse.io/<token>/...` or embeds
  `boards.greenhouse.io/embed/job_board?for=<token>` uses that token.
- Some companies host jobs on their own site (for example `stripe.com/jobs/search?gh_jid=...`).
  The `gh_jid` parameter means Greenhouse; try the company name in lower case as the token.

Check a token with:
`curl -s -o /dev/null -w "%{http_code}" https://boards-api.greenhouse.io/v1/boards/<token>/jobs`
200 means it works. 404 means the token is wrong or the company left Greenhouse.

## Config

```json
"greenhouse": {"enabled": true, "has_access": true, "companies": ["stripe", "datadog"]}
```

A company can also be `{"token": "abc123", "name": "Nice Name"}` when the token is not the
company name. Greenhouse returns the company name itself, so this is rarely needed.

## What scan.py fills

title, company (`company_name`), location, remote (from the location text, then from clear
phrases in the description), url and apply_url (`absolute_url`), posted_at (`first_published`),
salary (a dollar range found in the description, if any). The description HTML comes back
double escaped; scan.py unescapes it and writes readable text to `jd.md`.
