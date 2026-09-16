# Job Application Tracker (MCP Server)

A real [Model Context Protocol](https://modelcontextprotocol.io) server that
turns my own job search — 151 real applications sent between August 10 and
September 16, 2026 — into something an AI assistant can query and update in
plain language.

This is a follow-up to my first MCP project
([mcp-filesystem-connection](https://github.com/hanjot/mcp-filesystem-connection)),
which proved the basic AI-to-local-file connection. This one is built on my
actual job-search data and does real read/write work: querying, filtering,
and updating applications through MCP tools, not just reading a file.

## Why I built it — and what it's actually for

I'm a Lead Technical Program Manager currently in an active job search, and
by the time I built this I had sent 150+ applications with no single place
to see them — just a folder of PDFs named inconsistently
(`Company_Role_Date.pdf`, `RoleCompanyDate.pdf`, some with location, some
without).

This tracker is deliberately **not** about callbacks or interview status.
The question I actually care about is: across everything I've applied to,
what skills is the market asking for — Salesforce, SAP, cybersecurity, AI,
and to what depth? Seeing that pattern across 151 applications, instead of
one job description at a time, is the actual value.

## What it does

`parse_applications.py` reads the raw filenames and file timestamps from my
Applications folder and parses each one into: company, role, applied date,
and a `skills_required` tag list (Salesforce, SAP, AI/ML, AI/GenAI,
Cybersecurity, Cloud, Data/Analytics, Compliance, Payments, Agile, and so
on), using a keyword dictionary matched against the role/title text.

`server.py` is the MCP server. It loads `applications.json` (the parsed
output) and exposes these tools to any MCP client:

| Tool | What it does |
|---|---|
| `list_applications` | Filter by company, by required skill, or by date |
| `get_application` | Full detail on one application by id |
| `add_application` | Log a new application, with its required skills |
| `update_application` | Correct company/role/notes, replace or append to `skills_required` |
| `get_summary` | Totals, date range, repeat companies, and — the main point — **skills_frequency**: how often each skill/technology showed up across every posting |
| `get_course_priority` | Ranks which course/certification to prioritize next, based on real demand across all 151 applications (pulls from my existing AI Course Priority Plan where a matching course exists) |
| `find_duplicates` | Companies applied to more than once, with each application listed |

`skills_report.html` is a standalone chart + table view of the same data (open it in any browser) — a horizontal bar chart of skill frequency across all 151 applications, plus the course-priority ranking below it.

## Real numbers from my own search (as of Sept 16, 2026)

- **151 applications** tracked, spanning **Aug 10 – Sept 16, 2026**, across **111 unique companies**
- Skills flagged from job titles so far: **Program/Project Management** (105),
  **AI/ML** (19), **Cybersecurity** (7), **Data/Analytics** (4),
  **Infrastructure/DevOps** (4), plus smaller counts for GenAI, Compliance,
  Payments, Agile/Scrum, Cloud, and Salesforce
- 35 applications have no skill tag yet — their titles didn't contain a
  recognizable keyword (see limitation below)

## Running it

```bash
pip install -r requirements.txt
python parse_applications.py      # rebuilds applications.json from raw_listing.json
mcp dev server.py                 # opens the MCP Inspector to try the tools by hand
```

To connect it to an MCP-compatible client, add it as a stdio server that
runs `python server.py` from this folder.

## Verifying it's real

I tested this the same way a real MCP client would use it: a script
(`test_client.py`) spawns `server.py` as an actual MCP server over stdio,
calls `initialize`, lists the tools, and calls `get_summary`,
`list_applications`, `add_application`, `update_application`, and
`find_duplicates` — reading back real results and confirming the write
tools actually persisted changes to `applications.json`. That's a genuine
protocol round trip, not a mocked call.

## Honest limitations

- **`skills_required` is inferred from the job title/filename only** — I
  don't have the original job description text saved anywhere, so this is
  a best-effort keyword match against the role text (e.g. a title
  containing "Security" gets tagged "Cybersecurity"), not a transcription
  of each posting's actual requirements. It's a starting point per entry,
  not a finished answer — I'm refining individual entries with
  `update_application` as I go back through real postings.
- The filename parser is heuristic in general. A small number of
  applications (roughly 5%) come through with an unclear role because the
  original filename ran words together with no separator.
- There is no status/callback field by design — this tracker is about
  required skills across the whole search, not per-application outcomes.
- Three files that were saved copies of my base resume (not tied to a
  specific employer) are excluded from the counts rather than counted as
  applications.

## Stack

Python, the official [`mcp`](https://pypi.org/project/mcp/) SDK
(`FastMCP`), plain JSON for storage.
