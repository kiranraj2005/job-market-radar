import html
import re

def normalize_entities(text):
    """
    Unescape HTML entities repeatedly until nothing changes.

    NVISO's postings arrive as plain HTML (<p>...</p>). sumup's and
    JetBrains' arrive double-encoded (&lt;div ...&gt;) - the real < and >
    got escaped into &lt; and &gt; text by whatever ATS exported them.
    A single unescape() only undoes one layer, so looping to a fixed
    point handles both cases (and any deeper nesting) without assuming
    which format a given source uses.
    """
    previous = None
    while text != previous:
        previous = text
        text = html.unescape(text)
    return text




_TAG_RE = re.compile(r"<[^>]+>")
_BLOCK_TAG_RE = re.compile(r"</?(p|div|br|li|ul|ol|h[1-6])\s*/?>", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{2,}")


def strip_html_tags(text):
    """
    Remove HTML tags, but first convert block-level tags (<p>, <li>, <br>,
    etc.) to newlines - otherwise "<li>Python</li><li>SQL</li>" collapses
    into "PythonSQL" instead of two separate lines. Call this AFTER
    normalize_entities(), never before - see that function's docstring
    for why the order matters.
    """
    with_breaks = _BLOCK_TAG_RE.sub("\n", text)
    no_tags = _TAG_RE.sub("", with_breaks)
    collapsed = _WHITESPACE_RE.sub(" ", no_tags)
    collapsed = _BLANK_LINES_RE.sub("\n", collapsed)
    return collapsed.strip()


def clean_description(raw_html):
    """Entity-decode THEN strip tags — in that order."""
    return strip_html_tags(normalize_entities(raw_html))


SKILL_ALIASES = {
    "Python": ["python"],
    "SQL": ["sql"],
    "PostgreSQL": ["postgresql", "postgres"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services"],
    "Git": ["git"],
    "CI/CD": ["ci/cd", "cicd"],
    "pandas": ["pandas"],
    "Machine Learning": ["machine learning", "ml"],
    "LLM": ["llm", "large language model"],
    "REST API": ["rest api", "restful api"],
    "Power BI": ["power bi", "powerbi"],
}


def _boundary_pattern(phrase):
    """
    Case-insensitive regex matching `phrase` as a whole "word" - using a
    custom boundary instead of \\b, because \\b behaves oddly around
    phrases with non-word characters like "/" (e.g. "CI/CD"). This
    boundary just requires the character immediately before/after the
    match isn't itself a letter or digit.
    """
    escaped = re.escape(phrase)
    return re.compile(rf"(?<![A-Za-z0-9])({escaped})(?![A-Za-z0-9])", re.IGNORECASE)


_SKILL_PATTERNS = {
    canonical: [_boundary_pattern(alias) for alias in aliases]
    for canonical, aliases in SKILL_ALIASES.items()
}


def extract_skills(cleaned_text):
    """
    Scan CLEANED text (output of clean_description, not raw HTML) for
    known skill keywords. Returns canonical names, deduplicated.
    """
    return [
        canonical
        for canonical, patterns in _SKILL_PATTERNS.items()
        if any(p.search(cleaned_text) for p in patterns)
    ]