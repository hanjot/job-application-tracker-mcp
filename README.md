# Job Application Tracker (MCP Server)

![CI](https://github.com/hanjot/job-application-tracker-mcp/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

**[Live dashboard →](https://hanjot.github.io/job-application-tracker-mcp/)**

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
| `add_application` | Log a new application, with the real job link + job description text if available |
| `update_application` | Correct company/role/notes, add a real `job_url`/`job_description` retroactively (auto re-tags `skills_required` from the real text), or replace/append to `skills_required` directly |
| `get_summary` | Totals, date range, repeat companies, and — the main point — **skills_frequency**: how often each skill/technology showed up across every posting |
| `get_course_priority` | Ranks which course/certification to prioritize next, based on real demand across all 151 applications (pulls from my existing AI Course Priority Plan where a matching course exists) |
| `find_duplicates` | Companies applied to more than once, with each application listed |

`skills_report.html` is a standalone chart + table view of the same data (open it in any browser) — a horizontal bar chart of skill frequency across all 151 applications, plus the course-priority ranking below it.

**Real job descriptions, going forward:** each application also has a
`job_url` and `job_description` field. When a real posting's text is saved
(via `add_application` or `update_application`), `skills_required` is
automatically re-tagged from that actual text instead of guessed from the
title — the same keyword matcher, just run against real content. This is
how new applications get added from here on: job link + full JD text in,
accurate skill tags out.

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

Two layers of testing, both run automatically on every push via GitHub
Actions (see the CI badge above):

1. **Unit tests** (`tests/test_parse_applications.py`, run with `pytest`) —
   check the filename-parsing logic against real, tricky cases from the
   actual dataset: camelCase titles with no separators, a company name
   ("Marketing") that contains a month abbreviation as a substring
   ("mar"), and dates that must fall back to the file's save time when the
   filename has none.
2. **End-to-end protocol test** (`test_client.py`) — spawns `server.py` as
   an actual MCP server over stdio, calls `initialize`, lists the tools,
   and calls `get_summary`, `list_applications`, `add_application`,
   `update_application`, `get_course_priority`, and `find_duplicates` —
   reading back real results and confirming the write tools actually
   persisted changes to `applications.json`. That's a genuine protocol
   round trip, not a mocked call.

Run both locally with:

```bash
pip install -r requirements.txt pytest
python parse_applications.py
python -m pytest tests/ -v
python test_client.py
```

## Honest limitations

- **For the 151 applications parsed from filenames, `skills_required` is
  still inferred from the job title only** — I don't have the original
  posting text saved for those, so it's a best-effort keyword match
  against the role text, not a transcription of each posting's actual
  requirements. Going forward, any application added with a real
  `job_description` gets accurate, text-based tags instead (see above);
  I'm backfilling the older ones with `update_application` as I revisit
  real postings.
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
