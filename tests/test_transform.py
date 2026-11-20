"""
tests/test_transform.py

Unit tests for pipeline/transform.py. No Docker, no Postgres, no real API
calls - these run in under a second.

Run with:
    python3 -m pytest tests/test_transform.py -v
"""

from pipeline.transform import normalize_entities, strip_html_tags, clean_description, extract_skills, extract_min_years, looks_entry_level


def test_normalize_entities_single_escaped():
    assert normalize_entities("Machine Learning &amp; AI") == "Machine Learning & AI"


def test_normalize_entities_double_escaped():
    # the sumup/JetBrains case - real < and > escaped into literal &lt; &gt; text
    assert normalize_entities("&lt;div&gt;") == "<div>"


def test_normalize_entities_is_safe_on_clean_text():
    assert normalize_entities("Already clean.") == "Already clean."


def test_strip_html_tags_keeps_list_items_on_separate_lines():
    assert strip_html_tags("<ul><li>Python</li><li>SQL</li></ul>") == "Python\nSQL"


def test_strip_html_tags_collapses_whitespace():
    assert strip_html_tags("<p>Hello    world</p>") == "Hello world"


def test_clean_description_handles_double_escaped_nviso_style():
    raw = "<p>It all starts with the mission.</p>"
    assert clean_description(raw) == "It all starts with the mission."


def test_clean_description_handles_double_escaped_sumup_style():
    raw = "&lt;div&gt;&lt;p&gt;We use Python daily.&lt;/p&gt;&lt;/div&gt;"
    assert clean_description(raw) == "We use Python daily."


def test_extract_skills_basic():
    text = "You'll work with Python, PostgreSQL, and Docker on AWS."
    assert set(extract_skills(text)) == {"Python", "PostgreSQL", "Docker", "AWS"}


def test_extract_skills_alias_maps_to_canonical_name():
    # 'postgres' should be reported as 'PostgreSQL', not as a separate skill
    skills = extract_skills("We use postgres here.")
    assert "PostgreSQL" in skills
    assert "postgres" not in skills


def test_extract_skills_handles_slash_in_phrase():
    assert "CI/CD" in extract_skills("Experience with CI/CD required.")


def test_extract_skills_no_match_returns_empty_list():
    assert extract_skills("We are a friendly team that values collaboration.") == []


def test_extract_min_years_simple_english():
    assert extract_min_years("We require 3 years of experience in Python.") == 3

def test_extract_min_years_range():
    assert extract_min_years("Looking for someone with 2-4 years experience.") == 2

def test_extract_min_years_german():
    assert extract_min_years("Mindestens 3 Jahre Erfahrung erforderlich.") == 3

def test_extract_min_years_none_found():
    assert extract_min_years("Join our fast-growing team as a data engineer.") is None

def test_looks_entry_level_junior():
    assert looks_entry_level("Junior Data Engineer") is True


def test_looks_entry_level_graduate():
    assert looks_entry_level("Graduate Software Developer") is True


def test_looks_entry_level_german_werkstudent():
    assert looks_entry_level("Werkstudent Data Analytics (m/w/d)") is True


def test_looks_entry_level_senior_is_false():
    assert looks_entry_level("Senior Data Platform Engineer") is False


def test_looks_entry_level_blank():
    assert looks_entry_level("") is False
    assert looks_entry_level(None) is False

import pytest


@pytest.mark.parametrize("text, expected", [
    ("3+ years of experience in Python", 3),
    ("2-4 years experience", 2),
    ("3-5 Jahre Erfahrung", 3),
    ("mindestens 3 Jahre Erfahrung", 3),
    ("3 Jahren Berufserfahrung", 3),
    ("3 Jahre relevante Berufserfahrung", 3),
    ("mindestens zwei Jahre Berufserfahrung im Bereich BI", 2),
    ("Berufserfahrung von mindestens 3 Jahren", 3),
    ("Du hast mehrjährige Berufserfahrung im Data Engineering", 3),
    ("mehrjährige praktische Erfahrung mit SQL", 3),
    ("langjährige Projekterfahrung", 5),
    ("several years of hands-on experience", 3),
    ("Seit 25 Jahren entwickeln wir Software. Du bringst 2 Jahre Erfahrung mit", 2),
    ("Wir blicken auf über 100 Jahre Erfahrung zurück", None),
    ("a company with 100 years of history", None),
    ("unsere langjährigen Kunden schätzen uns", None),
    ("erste Erfahrungen mit Python", None),
    ("", None),
])
def test_extract_min_years_german_and_vague(text, expected):
    assert extract_min_years(text) == expected

@pytest.mark.parametrize("text, expected", [
    # Real postings from the database, 20 Nov 2026: each was wrong under the old rules
    ("starting today and not in 10 years. What is expected of you 3+ years of professional "
     "experience outside academia", 3),
    ("starting today and not in 10 years. What is expected of you 8+ years of professional "
     "experience in data science", 8),
    ("At least 3 years of experience building and shipping production AI systems; 5+ years "
     "preferred. ... facilities over the next 10–20 years.", 3),
    ("4 bis 5 Jahre Berufserfahrung im Cloud Engineering", 4),
    ("raised €18M in funding (last round 4.5 years ago). You bring 3+ years of building and "
     "running data pipelines", 3),
    ("shape industrial facilities over the next 10–20 years.", None),
])
def test_extract_min_years_real_postings(text, expected):
    assert extract_min_years(text) == expected

@pytest.mark.parametrize("text, expected", [
    # Senior postings: the overall bar comes first, sub-requirements after it
    ("What we're looking for 8+ years in data science or machine learning, including 3+ years "
     "leading teams", 8),
    ("über 30 Jahren Erfahrung steuern Kunden. Mindestens 5 Jahre Erfahrung in der "
     "IT-Administration oder im IT-Management, davon mindestens 2 Jahre in verantwortlicher Rolle", 5),
    ("You have 10+ years in ML/AI with 3+ years at Staff+ or Principal level", 10),
    ("5+ years of experience developing and deploying production software 2+ years of "
     "experience delivering software services", 5),
    ("Du bringst mindestens 2 Jahre Berufserfahrung im Bereich Business Intelligence mit. "
     "Du hast mindestens 1 Jahr Erfahrung mit einem gängigen BI Tool", 2),
    ("5+ years of experience in cloud engineering or DevOps 3+ years of experience designing "
     "and implementing Microsoft Azure", 5),
])
def test_extract_min_years_overall_requirement_first(text, expected):
    assert extract_min_years(text) == expected