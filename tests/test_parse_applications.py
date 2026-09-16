"""
Unit tests for the filename-parsing logic in parse_applications.py.

These run against known real filenames pulled from the actual dataset
(raw_listing.json) so a regression here means the parser broke on data
that genuinely exists, not a made-up edge case.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from parse_applications import tag_skills, extract_date, clean_role


def test_tag_skills_matches_cybersecurity():
    assert "Cybersecurity" in tag_skills("Senior TPM, Product Security")


def test_tag_skills_matches_infrastructure_platform_role():
    tags = tag_skills("TechnicalProgramManagerPlatform")
    assert "Infrastructure / DevOps" in tags
    assert "Program / Project Management" in tags
    # "Platform" alone should not falsely trigger an AI tag
    assert "AI / GenAI / ML" not in tags


def test_tag_skills_splits_camelcase_before_matching():
    # "ProgramManagerAI" has no spaces -- the camelCase splitter must run
    # before keyword matching, or this regresses to zero tags.
    tags = tag_skills("SrTechnicalProgramManagerAI")
    assert "AI / GenAI / ML" in tags
    assert "Program / Project Management" in tags


def test_tag_skills_salesforce():
    assert "Salesforce" in tag_skills("Workday Tundra Salesforce TPM")


def test_extract_date_from_filename_takes_priority_over_mtime():
    date_str, source = extract_date("Amex_SecureAI_PM_15Sept", fallback_ms=1789534473220)
    assert date_str == "2026-09-15"
    assert source == "filename"


def test_extract_date_does_not_false_match_month_substring_in_a_word():
    # Regression test: "Marketing" contains "mar" (March) as a substring.
    # The parser must not mistake that for a date.
    date_str, source = extract_date("Apple_Apple_EPM_Marketing_4Sept", fallback_ms=1788557644193)
    assert date_str == "2026-09-04"
    assert source == "filename"


def test_extract_date_falls_back_to_mtime_when_no_month_found():
    date_str, source = extract_date("SomeCompany_SomeRole_NoDateHere", fallback_ms=1786519000076)
    assert source == "mtime"


def test_clean_role_strips_location_words():
    role = clean_role("_TechnicalProgramManager_SanJose18AUG")
    assert "sanjose" not in role.lower()
    assert "18AUG".lower() not in role.lower() or "aug" not in role.lower()


def test_clean_role_never_returns_empty_string():
    assert clean_role("_18AUG_") == "(role unclear from filename)"
