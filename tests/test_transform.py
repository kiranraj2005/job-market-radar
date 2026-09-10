"""
tests/test_transform.py

Unit tests for pipeline/transform.py. No Docker, no Postgres, no real API
calls - these run in under a second.

Run with:
    python3 -m pytest tests/test_transform.py -v
"""

from pipeline.transform import normalize_entities, strip_html_tags, clean_description, extract_skills


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