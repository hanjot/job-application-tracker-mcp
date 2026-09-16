"""
parse_applications.py

Turns Hanjot's real, messily-named job-application PDF filenames into a
clean, structured dataset (applications.json) that the MCP server reads
and writes.

Why this exists: across ~150 real applications, filenames were saved with
no consistent convention (Company_Role_Location_Date.pdf, RoleCompanyDate.pdf,
Company_Role.pdf, etc). Rather than inventing sample data for a portfolio
project, this parses her actual application history -- messy real-world
data cleanup is exactly the kind of problem a TPM solves in their day job.

Fields per application: company, role, applied_date, skills_required,
source_file, notes. No status/callback tracking -- by request, this
tracker is about what skills the market is asking for, not about outcomes.

Honest limitation on skills_required: the only text available per
application is the filename/title (we don't have the original job
description saved anywhere), so skills_required is a best-effort tag list
matched against a keyword dictionary run over the company+role text -- not
a transcription of the real job posting's requirements. Treat it as a
starting point per entry; refine it with update_application once you've
looked at the actual posting.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "raw_listing.json"
OUT = HERE / "applications.json"

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

DATE_RE = re.compile(
    r"(?P<d1>\d{1,2})?\s*(?:st|nd|rd|th)?\s*(?<![A-Za-z])"
    r"(?P<mon>jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec)(?![A-Za-z])"
    r"\s*(?P<d2>\d{1,2})?\s*(?P<year>20\d{2})?",
    re.IGNORECASE,
)

LOCATION_WORDS = {
    "remote", "hybrid", "contract", "fte", "fulltime", "full-time",
    "sfo", "sf", "sanjose", "san jose", "sanramon", "san ramon",
    "fremont", "sunnyvale", "mountainview", "mountain view", "paloalto",
    "palo alto", "fostercity", "foster city", "fc", "pleasonton",
    "pleasanton", "redwood", "cupertino", "sanmateo", "san mateo",
    "livermore", "austin", "hawaii", "van", "west", "melopark",
    "menlo park",
}

# Keyword -> skill-category tags, matched against the role/title text only
# (not the company name -- otherwise a company like "ScaleAI" or "OpenAI"
# would get tagged "AI" on every application regardless of the actual role).
# This is intentionally simple (substring/word match on the title only) --
# see the module docstring for why it can't be more than a starting point.
SKILL_KEYWORDS = [
    (r"\bgen\s?ai\b|\bagentic\b|\bllm\b|\bai\s?agent\b|\bai\b|artificial intelligence|\bml\b|machine learning", "AI / GenAI / ML"),
    (r"cyber\s?security|\bsecurity\b|infosec|vulnerabilit", "Cybersecurity"),
    (r"\bsalesforce\b", "Salesforce"),
    (r"\bsap\b", "SAP"),
    (r"\baws\b|amazon web services", "AWS"),
    (r"\bazure\b", "Azure"),
    (r"\bgcp\b|google cloud", "GCP"),
    (r"\bcloud\b", "Cloud (general)"),
    (r"\bsql\b|\bpower\s?bi\b|\bdata\b|analytics", "Data / Analytics"),
    (r"complian|governance|\baudit\b|\brisk\b", "Compliance / Risk / Governance"),
    (r"payment|fintech|\bfinancial\b", "Payments / FinTech"),
    (r"devops|infrastructure|\bplatform\b", "Infrastructure / DevOps"),
    (r"\bagile\b|\bscrum\b", "Agile / Scrum"),
    (r"program\s*manager|project\s*manager|\btpm\b|\bepm\b", "Program / Project Management"),
    (r"privacy|\bgdpr\b|\bccpa\b", "Data Privacy"),
]


def tag_skills(text):
    # Many filenames run words together in camelCase (e.g. "ProgramManagerAI")
    # with no separators -- split on lower->upper transitions first so word-
    # boundary keyword matching actually sees "Program Manager AI".
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text_l = spaced.lower()
    tags = []
    for pattern, label in SKILL_KEYWORDS:
        if re.search(pattern, text_l) and label not in tags:
            tags.append(label)
    return tags


def mtime_to_date(mtime_ms):
    return datetime.fromtimestamp(mtime_ms / 1000, tz=timezone.utc).date()


def extract_date(stem, fallback_ms):
    m = DATE_RE.search(stem)
    fallback = mtime_to_date(fallback_ms)
    if not m or not m.group("mon"):
        return fallback.isoformat(), "mtime"
    mon = MONTHS[m.group("mon").lower()]
    day = m.group("d1") or m.group("d2")
    year = m.group("year")
    try:
        day = int(day) if day else fallback.day
        year = int(year) if year else fallback.year
        return datetime(year, mon, day).date().isoformat(), "filename"
    except ValueError:
        return fallback.isoformat(), "mtime"


def clean_role(text):
    text = DATE_RE.sub(" ", text)
    text = re.sub(r"[_]+", " ", text)
    words = [w for w in text.split() if w.strip(",.- ").lower() not in LOCATION_WORDS]
    role = " ".join(words)
    role = re.sub(r"\s+", " ", role).strip(" ,-_")
    return role or "(role unclear from filename)"


def parse_entry(entry):
    name = entry["name"]
    stem = name.rsplit("/", 1)[-1]
    stem = re.sub(r"\.pdf$", "", stem, flags=re.IGNORECASE)
    folder = name.rsplit("/", 1)[0] if "/" in name else None

    if entry.get("masterResume"):
        return {
            "company": None,
            "role": None,
            "source_file": name,
            "applied_date": mtime_to_date(entry["mtimeMs"]).isoformat(),
            "date_source": "mtime",
            "skills_required": [],
            "notes": "Not an application; a saved copy of the base resume.",
            "excluded": True,
        }

    if folder:
        # e.g. "IS Project Manager_Fox Rothschild/Intuit.pdf"
        company = folder.split("_")[-1].strip()
        role = folder.split("_")[0].strip()
        applied_date, date_source = extract_date(stem, entry["mtimeMs"])
        return {
            "company": company,
            "role": role,
            "source_file": name,
            "applied_date": applied_date,
            "date_source": date_source,
            "skills_required": tag_skills(role),
            "notes": f"via recruiter folder '{folder}'",
            "excluded": False,
        }

    if stem.lower().startswith("gagandeep") and "askconsulting" in stem.lower().replace(" ", ""):
        # her own resume filename, but tailored for a specific staffing company
        applied_date, date_source = extract_date(stem, entry["mtimeMs"])
        after = re.split(r"askconsulting", stem, flags=re.IGNORECASE)[-1]
        role = clean_role(after)
        return {
            "company": "ASK Consulting",
            "role": role,
            "source_file": name,
            "applied_date": applied_date,
            "date_source": date_source,
            "skills_required": tag_skills(role),
            "notes": entry.get("note", ""),
            "excluded": False,
        }

    parts = stem.split("_", 1)
    if len(parts) == 2:
        company, rest = parts
    else:
        # no underscore at all -- everything ran together
        m = re.match(r"^([A-Z][a-zA-Z]+)", stem)
        company = m.group(1) if m else stem
        rest = stem[len(company):]

    company = company.strip(" ,-_")
    role = clean_role(rest)
    applied_date, date_source = extract_date(stem, entry["mtimeMs"])

    return {
        "company": company,
        "role": role,
        "source_file": name,
        "applied_date": applied_date,
        "date_source": date_source,
        "skills_required": tag_skills(role),
        "notes": "",
        "excluded": False,
    }


def main():
    raw = json.loads(RAW.read_text())
    applications = []
    for i, entry in enumerate(raw, start=1):
        parsed = parse_entry(entry)
        parsed["id"] = i
        applications.append(parsed)

    applications.sort(key=lambda a: a["applied_date"])
    for i, a in enumerate(applications, start=1):
        a["id"] = i

    OUT.write_text(json.dumps(applications, indent=2))
    included = [a for a in applications if not a["excluded"]]
    tagged = [a for a in included if a["skills_required"]]
    print(f"Parsed {len(applications)} files -> {len(included)} applications "
          f"({len(applications) - len(included)} excluded as master-resume copies).")
    print(f"{len(tagged)}/{len(included)} got at least one skill tag from their title.")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
