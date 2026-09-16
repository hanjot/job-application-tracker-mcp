"""
Real end-to-end test: spawns server.py as an actual MCP stdio server and
talks to it as a real MCP client would (list tools, call tools, read
results) -- this is not testing the python functions directly, it's
testing the real MCP protocol round trip.
"""
import asyncio
import json
import shutil

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _result(r):
    if r.structuredContent is not None:
        return r.structuredContent.get("result", r.structuredContent)
    return json.loads(r.content[0].text)


async def main():
    params = StdioServerParameters(
        command=shutil.which("python3") or "python3",
        args=["server.py"],
        cwd=".",
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("=== TOOLS EXPOSED ===")
            for t in tools.tools:
                print(f"- {t.name}: {t.description.strip().splitlines()[0]}")

            print("\n=== get_summary() ===")
            r = await session.call_tool("get_summary", {})
            print(json.dumps(_result(r), indent=2)[:1400])

            print("\n=== list_applications(skill='AI') ===")
            r = await session.call_tool("list_applications", {"skill": "AI", "limit": 8})
            for a in _result(r):
                print(f"  #{a['id']} {a['applied_date']} {a['company']} - {a['role'][:40]} -> {a['skills_required']}")

            print("\n=== add_application(...) ===")
            r = await session.call_tool("add_application", {
                "company": "TestCo",
                "role": "Test Role for verification",
                "applied_date": "2026-09-16",
                "skills_required": ["Salesforce", "AI/ML (general)"],
                "notes": "added by test_client.py to verify write path",
            })
            new_app = _result(r)
            print(json.dumps(new_app, indent=2))

            print("\n=== update_application(add_skill='SAP') ===")
            r = await session.call_tool("update_application", {
                "id": new_app["id"],
                "add_skill": "SAP",
            })
            print(json.dumps(_result(r), indent=2))

            print("\n=== update_application(job_description=...) re-tags from real JD text ===")
            r = await session.call_tool("update_application", {
                "id": new_app["id"],
                "job_url": "https://example.com/jobs/testco-pm",
                "job_description": "Looking for a Program Manager with Cybersecurity and Compliance experience.",
            })
            retagged = _result(r)
            print(json.dumps(retagged, indent=2))
            assert "Cybersecurity" in retagged["skills_required"], "job_description should re-tag skills_required"
            assert retagged["job_url"] == "https://example.com/jobs/testco-pm"

            print("\n=== get_course_priority() ===")
            r = await session.call_tool("get_course_priority", {})
            for row in _result(r)[:5]:
                print(f"  #{row['priority_rank']} {row['skill']} ({row['applications_requiring_it']} apps): {row['recommended_course'][:70]}")

            print("\n=== find_duplicates() sample ===")
            r = await session.call_tool("find_duplicates", {})
            dups = _result(r)
            print(f"{len(dups)} companies with repeat applications, e.g.:")
            print(json.dumps(dups[0], indent=2)[:400])


if __name__ == "__main__":
    asyncio.run(main())
