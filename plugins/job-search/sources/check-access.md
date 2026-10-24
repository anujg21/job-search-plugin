# Check access to Indeed, Dice and LinkedIn

- **Dice** needs no check. `scan.py` uses Dice's public connector server, with no account.
  Turn Dice on whenever the user has target titles.
- **Indeed** works best through its connector, which the plugin bundles. The user signs in
  to Indeed once to connect it. Without it, Indeed is read in Chrome or through web search.
- **LinkedIn** has no job search connector. It is read in the user's own Chrome through the
  Claude in Chrome extension (`mcp__claude-in-chrome__*` tools), while they are signed in.

This guide checks those instead of asking the user. Use it during onboarding, or when the
user says a source found nothing or asks to "check my job site sign-ins". It needs the user
in the chat. Scheduled runs never use it.

## Connectors first (Dice and Indeed)

The plugin bundles both connectors, but each one is connected once by the user. Claude
cannot click Connect or sign in for them.

1. For each of `dice` and `indeed`: ToolSearch with `<name> search_jobs`. If a tool is
   found, call `search_jobs` once with the first target title and "Remote".
2. Results came back: record it with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" connector <name> ok`.
3. No tool, or the call asks for sign-in: record `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobctl.py" connector <name> missing`,
   and show the user these steps once, for all missing connectors together:

   > To connect Dice and Indeed (one time):
   > 1. In Claude Desktop or claude.ai, open **Customize**, then **Plugins**, then **Job search**.
   > 2. Open the **Connectors** tab.
   > 3. Click **Connect** next to Dice. It needs no account.
   > 4. Click **Connect** next to Indeed and sign in with your Indeed account.
   > 5. Go to **Customize > Connectors**, select each one, find **Tool permissions** and
   >    choose **Always allow**. Scheduled runs cannot stop to ask for approval.
   > Guide: https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities
   > In Claude Code, run `/mcp`, pick `dice` or `indeed`, and follow the prompt.

   Ask them to say done or skip. After done, check once more and record the result.
   Either way, go on: Dice still works through `scan.py`, and Indeed through Chrome or web
   search. The connectors matter most for scheduled runs.

## Rules

- Read only. Only open pages and read them. Never type into a sign-in form, never enter a
  password or code, never click "Sign in" or "Continue with Google" for the user.
- A CAPTCHA or "verify you are human" page is not solved. It counts as no access.
- Nothing here blocks setup. A site you cannot confirm stays off, and setup goes on.

## Chrome check (LinkedIn, and Indeed without its connector)

1. Load the Chrome tools in one ToolSearch call:
   `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__find,mcp__claude-in-chrome__tabs_close_mcp`
2. **No Chrome tools, or no browser connected.** Tell the user in two or three lines:
   - LinkedIn (and Indeed, without its connector) is read in their Chrome through the
     Claude in Chrome extension.
   - To turn them on: install Claude in Chrome from the Chrome Web Store, sign in to it with
     the same Claude account, and keep Chrome open when runs happen. Then run
     `/job-search:onboard` and pick "Job sources".
   - Until then the plugin uses the Greenhouse, Lever, Ashby and Dice boards, plus Indeed
     through its connector or web search.
   Set `indeed` to `enabled: true` and keep its `has_access` as it was (false if unknown),
   leave `linkedin` off, and stop here.
3. Call `tabs_context_mcp`, then open one new tab with `tabs_create_mcp`. Use only that tab.
4. Check each site the user wants (Indeed only if its connector is not connected). Open the page, wait 2 to 3 seconds, then read the final
   URL and the page text with `get_page_text` (or `find` "account menu or sign in button").

   | Site | Open | Has access when | No access when |
   |---|---|---|---|
   | Indeed | `https://www.indeed.com/jobs?q=engineer&l=Remote` | Job result cards show | CAPTCHA, "verify you are human", block page |
   | LinkedIn | `https://www.linkedin.com/feed/` | The URL stays on `/feed` and the feed shows | The URL has `/login`, `/authwall`, `/uas/login`, `/signup` or `/checkpoint`, or a sign-in form shows |

   Indeed works without signing in, so only a block page means no access.
5. **For each site without access**, leave the tab on that site's sign-in page and tell the
   user: "I opened <site> in your Chrome. Sign in there, then say done (or skip)." When they
   say done, check that site once more. If it still has no access, say so in one line,
   leave it off and move on. Ask at most once per site.
6. Close your tab with `tabs_close_mcp`.
7. Set `has_access` to what you saw and `enabled: true` for each site with access that the
   user wants. Report one line per site, for example:
   `Indeed: connected. Dice: on, no account needed. LinkedIn: not signed in, left off.`

## Later

Sign-ins expire. When a scheduled scan meets a sign-in page, it logs a `source_error`, skips
that site for the run, and the run summary and dashboard say which site needs a sign-in. The
user signs in to that site in Chrome. Nothing else needs to change, unless the site was turned
off, in which case running this check again turns it back on.
