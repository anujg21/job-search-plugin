# Lever

Handled by `scripts/scan.py`. No login and no browser needed.

API: `https://api.lever.co/v0/postings/<company>?mode=json`

## Finding the company token

It is the first path part of the job board URL: `https://jobs.lever.co/spotify` gives `spotify`.
Careers pages that link to `jobs.lever.co/<company>/<posting id>` use the same token.

Check it with:
`curl -s https://api.lever.co/v0/postings/<company>?mode=json | head -c 200`
A 404 with `Document not found` means the token is wrong. An empty list `[]` means the board
exists but has no open jobs right now.

## Config

```json
"lever": {"enabled": true, "has_access": true, "companies": ["spotify"]}
```

Lever does not return a display name, so scan.py title-cases the token. Use
`{"token": "acme-corp", "name": "Acme"}` to set it.

## What scan.py fills

title (`text`), location (`categories.allLocations`), remote (`workplaceType`), url
(`hostedUrl`), apply_url (`applyUrl`), posted_at (`createdAt`), salary (`salaryRange` or a
range in the text). The description joins the intro, each section in `lists`, and
`additional`. `categories.commitment` (for example "Contract") is checked against deal breakers.
