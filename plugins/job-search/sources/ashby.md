# Ashby

Handled by `scripts/scan.py`. No login and no browser needed.

API: `https://api.ashbyhq.com/posting-api/job-board/<name>?includeCompensation=true`

## Finding the board name

It is the first path part of the job board URL: `https://jobs.ashbyhq.com/ramp` gives `ramp`.
Careers pages that embed an Ashby board load `jobs.ashbyhq.com/<name>` in an iframe.

Check it with:
`curl -s -o /dev/null -w "%{http_code}" https://api.ashbyhq.com/posting-api/job-board/<name>`
200 means it works, 404 means it does not.

## Config

```json
"ashby": {"enabled": true, "has_access": true, "companies": ["ramp"]}
```

Ashby does not return a display name. Use `{"token": "ramp", "name": "Ramp"}` if the
title-cased token looks wrong.

## What scan.py fills

title, location (primary plus `secondaryLocations`), remote (`isRemote` and `workplaceType`),
url (`jobUrl`), apply_url (`applyUrl`), posted_at (`publishedAt`), salary
(`compensation.scrapeableCompensationSalarySummary`). Postings with `isListed: false` are skipped.
`employmentType` (for example "Contract") is checked against deal breakers.
