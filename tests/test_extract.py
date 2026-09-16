"""
tests/test_extract.py

Unit tests for the pure filter functions in pipeline/extract.py.
No network calls - fetch_all_pages() isn't tested here, only the
filtering logic that runs on already-fetched data.

Run with:
    python3 -m pytest tests/test_extract.py -v
"""

from pipeline.extract import is_german, match_role_type


def test_is_german_plain_city():
    assert is_german("Berlin") is True


def test_is_german_city_with_umlaut():
    assert is_german("München") is True


def test_is_german_country_word():
    assert is_german("Some Region, Germany") is True


def test_is_german_non_german_city():
    assert is_german("Paris") is False


def test_is_german_blank():
    assert is_german("") is False
    assert is_german(None) is False


def test_match_role_type_data_engineer():
    assert match_role_type("Senior Data Engineer") == "engineer"


def test_match_role_type_no_match():
    assert match_role_type("Senior Account Executive") is None


# Regression tests for the 7 real postings found dropped via inspect_dropped_roles.py
# and fixed by growing ROLE_KEYWORDS - these lock the fix in so it can't silently regress.

def test_match_role_type_data_platform():
    assert match_role_type("Data Platform Engineer Working Student (m/w/d)") == "engineer"


def test_match_role_type_data_architecture():
    assert match_role_type("Data Architecture Consultant (m/w/d)") == "engineer"


def test_match_role_type_data_science_noun_form():
    assert match_role_type("Weiterbildung: Data Science & Business Analytics (IHK) (m/w/d)") == "scientist"


def test_match_role_type_ai_analyst():
    assert match_role_type("Data Management & AI Analyst im Gesundheitswesen (m/w/d)") == "analyst"


def test_match_role_type_ai_architect():
    assert match_role_type("Senior AI Architect & Consultant (m/w/d)") == "ai"


def test_match_role_type_ai_developer():
    assert match_role_type("AI (Senior) Developer (m/w/d)") == "ai"


def test_match_role_type_agentic_ai():
    assert match_role_type("AI Application Engineer - LangGraph & Agentic AI") == "ai"