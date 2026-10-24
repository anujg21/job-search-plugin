# Check access to Indeed, Dice and LinkedIn

Indeed, Dice and LinkedIn have no public API. The plugin reads them in the user's own Chrome
through the Claude in Chrome extension (`mcp__claude-in-chrome__*` tools), so it sees what the
user sees when signed in. This guide checks that, instead of asking the user.

Use it during onboarding, or when the user says a browser source found nothing or asks to
"check my job site sign-ins". It needs the user in the chat. Scheduled runs never use it.

## Rules

- Read only. Only open pages and read them. Never type into a sign-in form, never enter a
  password or code, never click "Sign in" or "Continue with Google" for the user.
- A CAPTCHA or "verify you are human" page is not solved. It counts as no access.
- Nothing here blocks setup. A site you cannot confirm stays off, and setup goes on.

## Steps

1. Load the Chrome tools in one ToolSearch call:
   `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__find,mcp__claude-in-chrome__tabs_close_mcp`
2. **No Chrome tools, or no browser connected.** Tell the user in two or three lines:
   - Indeed, Dice and LinkedIn are read in their Chrome through the Claude in Chrome extension.
   - To turn them on: install Claude in Chrome from the Chrome Web Store, sign in to it with
     the same Claude account, and keep Chrome open when runs happen. Then run
     `/job-search:onboard` and pick "Job sources".
   - Until then the plugin uses the Greenhouse, Lever and Ashby boards, plus public Indeed
     postings found by web search.
   Set `indeed` to `enabled: true, has_access: false` (the scan uses its web search fallback;
   see `sources/indeed.md`), leave `dice` and `linkedin` off, and stop here.
3. Call `tabs_context_mcp`, then open one new tab with `tabs_create_mcp`. Use only that tab.
4. Check each site the user wants. Open the page, wait 2 to 3 seconds, then read the final
   URL and the page text with `get_page_text` (or `find` "account menu or sign in button").

   | Site | Open | Has access when | No access when |
   |---|---|---|---|
   | Indeed | `https://www.indeed.com/jobs?q=engineer&l=Remote` | Job result cards show | CAPTCHA, "verify you are human", block page |
   | Dice | `https://www.dice.com/home-feed` | The page shows the user's profile or account menu, no "Log in" or "Sign in" button | Redirected to a login page, or only "Log in" / "Register" shows |
   | LinkedIn | `https://www.linkedin.com/feed/` | The URL stays on `/feed` and the feed shows | The URL has `/login`, `/authwall`, `/uas/login`, `/signup` or `/checkpoint`, or a sign-in form shows |

   Indeed works without signing in, so only a block page means no access.
5. **For each site without access**, leave the tab on that site's sign-in page and tell the
   user: "I opened <site> in your Chrome. Sign in there, then say done (or skip)." When they
   say done, check that site once more. If it still has no access, say so in one line,
   leave it off and move on. Ask at most once per site.
6. Close your tab with `tabs_close_mcp`.
7. Set `has_access` to what you saw and `enabled: true` for each site with access that the
   user wants. Report one line per site, for example:
   `Indeed: works. Dice: signed in. LinkedIn: not signed in, left off.`

## Later

Sign-ins expire. When a scheduled scan meets a sign-in page, it logs a `source_error`, skips
that site for the run, and the run summary and dashboard say which site needs a sign-in. The
user signs in to that site in Chrome. Nothing else needs to change, unless the site was turned
off, in which case running this check again turns it back on.
