# Other job connectors

The plugin ships two job connectors: Dice and Indeed (`.mcp.json`). The user can add any
other job search connector from the Claude directory (Customize > Connectors, then +), for
example ZipRecruiter or a job aggregator. The scan then uses it with the same searches.

## How the user adds one

1. Go to **Customize > Connectors** and click **+** next to **Connectors** to open the
   directory. Search for the job site. Click it, then **Connect** (or **Install**), and
   finish the sign-in if it asks.
2. Select the connector under **Customize > Connectors**, find **Tool permissions** and
   choose **Always allow**. Scheduled runs cannot stop to ask for approval, so a connector
   on "Needs approval" is skipped in those runs.
3. Tell Claude "add <name> as a job source", or run `/job-search:onboard` and pick
   "Job sources". It adds the connector to `profile/sources.json`:

```json
"extra_connectors": [{"name": "ZipRecruiter", "enabled": true, "max_per_run": 20}]
```

`extra_connectors` sits next to `sources` at the top level of the file.

A site that is not in the directory but runs a public MCP server can be added as a custom
connector: **Customize > Connectors**, **Add**, **Custom**, **Web**, then its server URL.
On Team and Enterprise plans an Owner adds connectors and sets tool permissions.

Anthropic's guides:
- Use connectors: https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities
- Browse the directory: https://support.claude.com/en/articles/14328846-browse-skills-connectors-and-plugins-in-one-directory
- Custom connectors: https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp

## How the scan uses one

For each entry with `enabled: true`:
1. ToolSearch with `<name> search jobs`. Use the connector's job search tool (its name
   usually ends in `search_jobs`). Read its input schema. Not found: note
   `<name>: connector not available in this run` and go on.
2. Call it once per query in `sources.indeed.queries` (target title and location), asking
   for recent jobs if the tool allows it. If it has a details tool, call it for each new
   result to get the full description. Stop at `max_per_run`.
3. Write the results as one JSON list in the shape from `sources/README.md`, with
   `source` set to the connector name in lower case (for example `ziprecruiter`), the
   tool's job id as `source_job_id`, and its job URL as `url`. Run `add_job.py` as the other
   guides do. It applies the same filters and dedupe.

Read only. Never apply, save, or message through a connector.
