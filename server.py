"""
Job Application Tracker -- a real MCP server.

Exposes Hanjot's actual ~150-application job search (parsed from her real
resume filenames and file timestamps in parse_applications.py) as a set of
MCP tools, so an AI assistant can query and update it in natural language:
  "how many applications listed AI as a required skill?"
  "which companies have I applied to more than once?"
  "add the skill 'Workday Adaptive Planning' to application 42"

This tracker deliberately does NOT track callback/interview status -- by
request, it's about what skills the market is asking for across the whole
search, not about tracking outcomes per application.

Run it:
    pip install "mcp[cli]"
    python parse_applications.py      # (re)builds applications.json from raw_listing.json
    mcp dev server.py                 # opens the MCP Inspector to test tools by hand
    # or, to connect it to Claude Desktop / another MCP client, add it as a
    # stdio server pointing at: python /path/to/server.py

Data lives in applications.json next to this file -- a plain JSON list, so
it's easy to read, back up, or diff in git.
"""
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

HERE = Path(__file__).parent
DATA_FILE = HERE / "applications.json"

mcp = FastMCP("job-application-tracker")


def _load():
    return json.loads(DATA_FILE.read_text())


def _save(apps):
    DATA_FILE.write_text(json.dumps(apps, indent=2))


def _active(apps):
    return [a for a in apps if not a.get("excluded")]


@mcp.tool()
def list_applications(
    company: Optional[str] = None,
    skill: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 25,
) -> list[dict]:
    """List job applications, optionally filtered by company (substring
    match, case-insensitive), by a required skill/skill-category (substring
    match against each application's skills_required list), or by applied
    date on/after a given date (YYYY-MM-DD). Returns the most recent
    `limit` matches, newest first."""
    apps = _active(_load())
    if company:
        apps = [a for a in apps if company.lower() in (a["company"] or "").lower()]
    if skill:
        apps = [
            a for a in apps
            if any(skill.lower() in s.lower() for s in a.get("skills_required", []))
        ]
    if since:
        apps = [a for a in apps if a["applied_date"] >= since]
    apps.sort(key=lambda a: a["applied_date"], reverse=True)
    return apps[:limit]


@mcp.tool()
def get_application(id: int) -> dict:
    """Get full detail for a single application by its id."""
    apps = _load()
    for a in apps:
        if a["id"] == id:
            return a
    return {"error": f"no application with id {id}"}


@mcp.tool()
def add_application(
    company: str,
    role: str,
    applied_date: str,
    skills_required: Optional[list[str]] = None,
    notes: str = "",
) -> dict:
    """Add a new job application to the tracker. applied_date is YYYY-MM-DD.
    skills_required is a free-form list of skills/technologies the posting
    asked for (e.g. ["Salesforce", "SAP", "AI/ML", "Cybersecurity"])."""
    apps = _load()
    new_id = max((a["id"] for a in apps), default=0) + 1
    entry = {
        "id": new_id,
        "company": company,
        "role": role,
        "source_file": None,
        "applied_date": applied_date,
        "date_source": "manual",
        "skills_required": skills_required or [],
        "notes": notes,
        "excluded": False,
    }
    apps.append(entry)
    _save(apps)
    return entry


@mcp.tool()
def update_application(
    id: int,
    company: Optional[str] = None,
    role: Optional[str] = None,
    skills_required: Optional[list[str]] = None,
    add_skill: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """Update an existing application's company, role, notes, and/or
    required skills. Pass skills_required to replace the whole skill list
    (e.g. once you've read the real job posting and want the accurate
    list), or add_skill to append a single skill without touching the
    rest. Only the fields you pass are changed."""
    apps = _load()
    for a in apps:
        if a["id"] == id:
            if company:
                a["company"] = company
            if role:
                a["role"] = role
            if skills_required is not None:
                a["skills_required"] = skills_required
            if add_skill and add_skill not in a.get("skills_required", []):
                a.setdefault("skills_required", []).append(add_skill)
            if notes is not None:
                a["notes"] = notes
            _save(apps)
            return a
    return {"error": f"no application with id {id}"}


@mcp.tool()
def get_summary() -> dict:
    """Get an overview of the whole job search: total applications, date
    range, applications per week, companies applied to more than once, and
    -- most importantly -- how often each skill/technology showed up
    across all the postings (skills_frequency), so you can see what the
    market is actually asking for."""
    apps = _active(_load())
    if not apps:
        return {"total": 0}

    dates = sorted(a["applied_date"] for a in apps)
    company_counts = Counter(a["company"] for a in apps)
    repeat_companies = {c: n for c, n in company_counts.items() if n > 1}

    skill_counts = Counter()
    for a in apps:
        for s in a.get("skills_required", []):
            skill_counts[s] += 1
    untagged = sum(1 for a in apps if not a.get("skills_required"))

    by_week = Counter()
    for a in apps:
        y, w, _ = date.fromisoformat(a["applied_date"]).isocalendar()
        by_week[f"{y}-W{w:02d}"] += 1

    return {
        "total_applications": len(apps),
        "date_range": {"first": dates[0], "last": dates[-1]},
        "unique_companies": len(company_counts),
        "companies_applied_to_more_than_once": dict(
            sorted(repeat_companies.items(), key=lambda kv: -kv[1])
        ),
        "skills_frequency": dict(
            sorted(skill_counts.items(), key=lambda kv: -kv[1])
        ),
        "applications_with_no_skill_tag_yet": untagged,
        "applications_per_week": dict(sorted(by_week.items())),
    }



# Skill category -> recommended course, drawn from Hanjot's real
# "AI Course Priority Plan" spreadsheet where a matching course exists.
# "Program / Project Management" is intentionally left unmapped -- it's
# her existing core strength, not a skill gap to close.
SKILL_COURSE_MAP = {
    "AI / GenAI / ML": "MCP: Build Rich-Context AI Apps with Anthropic (DeepLearning.AI) -- "
                        "then AI Agents, Clearly Explained and Agentic AI (Andrew Ng).",
    "Cybersecurity": "Certified in Cybersecurity (CC) -- ISC2, or Security/Compliance/Identity "
                      "Fundamentals (Microsoft SC-900) as the free-first option.",
    "Data / Analytics": "Power BI (PL-300) Guided Learning Path -- builds on dashboards already "
                         "built weekly.",
    "Infrastructure / DevOps": "AWS Cloud Practitioner Essentials.",
    "Cloud (general)": "AWS Cloud Practitioner Essentials.",
    "Compliance / Risk / Governance": "AI Risk Management Framework (NIST) + AI Security & "
                                       "Governance Certificate (Securiti).",
    "Agile / Scrum": "Already CSM-certified -- Scalable Agile for Teams & Leaders (Jira Align) "
                      "only if a specific role names it.",
    "Payments / FinTech": "No dedicated course yet -- Visa payments background already covers "
                           "this; low priority to add a course.",
    "Salesforce": "Trailhead (Salesforce's own free training) if a specific role requires it -- "
                  "not a standing priority given how rarely it appears.",
    "SAP": "No course in the current plan -- hasn't appeared in the real application data at all.",
}


@mcp.tool()
def get_course_priority() -> list[dict]:
    """Rank which course/certification to prioritize next, based on how
    often each skill category actually appears across all real job
    applications (not a generic list -- ordered by this specific job
    search's real demand signal). Excludes Program/Project Management,
    which is an existing strength rather than a gap to close."""
    apps = _active(_load())
    skill_counts = Counter()
    for a in apps:
        for s in a.get("skills_required", []):
            if s != "Program / Project Management":
                skill_counts[s] += 1

    ranked = []
    for rank, (skill, count) in enumerate(
        sorted(skill_counts.items(), key=lambda kv: -kv[1]), start=1
    ):
        ranked.append({
            "priority_rank": rank,
            "skill": skill,
            "applications_requiring_it": count,
            "recommended_course": SKILL_COURSE_MAP.get(
                skill, "No mapped course yet -- add one once you know what this role needs."
            ),
        })
    return ranked


@mcp.tool()
def find_duplicates() -> list[dict]:
    """Find companies Hanjot applied to more than once, with the role and
    date of each application -- useful for spotting re-applications or
    accidental duplicate submissions."""
    apps = _active(_load())
    by_company = {}
    for a in apps:
        by_company.setdefault(a["company"], []).append(a)
    return [
        {"company": c, "applications": sorted(v, key=lambda a: a["applied_date"])}
        for c, v in by_company.items() if len(v) > 1
    ]


if __name__ == "__main__":
    mcp.run()
