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
    "Azure": ["azure"],
    "C++": ["c++"],
    "Excel": ["excel"],
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

_NUMBER_WORDS = {
    "ein": 1, "einem": 1, "einen": 1, "one": 1,
    "zwei": 2, "two": 2,
    "drei": 3, "three": 3,
    "vier": 4, "four": 4,
    "fünf": 5, "fuenf": 5, "five": 5,
    "sechs": 6, "six": 6,
}
_NUM = r"\b(\d{1,2}|" + "|".join(_NUMBER_WORDS) + r")\b"   # \b: the "00" in "100" never counts
_GAP = r"(?:[\w\-]+\s+){0,3}?"          # up to 3 words in between, e.g. "relevante praktische"
_MAX_PLAUSIBLE_YEARS = 15               # "over 100 years of history" is company age, not a requirement

# Explicit numbers, most reliable first
_YEAR_PATTERNS = [
    re.compile(_NUM + r"\s*(?:-|–|to|bis)\s*\d{1,2}\s*\+?\s*(?:years?|jahre?n?)", re.IGNORECASE),
    re.compile(r"(?:mindestens|mind\.|at least|minimum(?: of)?)\s+" + _NUM + r"\s*\+?\s*(?:years?|jahre?n?)", re.IGNORECASE),
    re.compile(_NUM + r"\s*\+?\s*(?:years?|jahre?n?)\s+" + _GAP + r"(?:of\s+)?" + r"\w*(?:experience|erfahrung)", re.IGNORECASE),
    re.compile(_NUM + r"\s*\+\s*(?:years?|jahre?n?)", re.IGNORECASE),
    re.compile(r"\w*erfahrung\s+von\s+(?:mindestens\s+)?" + _NUM + r"\s*jahre?n?", re.IGNORECASE),
]

# No number, but clearly senior. Only counts when "Erfahrung"/"experience" follows,
# so "langjährige Kunden" is ignored. The values are estimates.
_VAGUE_SENIORITY_PATTERNS = [
    (re.compile(r"\blangj[äa]hrig\w*\s+" + _GAP + r"\w*erfahrung", re.IGNORECASE), 5),
    (re.compile(r"\bmehrj[äa]hrig\w*\s+" + _GAP + r"\w*erfahrung", re.IGNORECASE), 3),
    (re.compile(r"\bmany\s+years\s+(?:of\s+)?" + _GAP + r"experience", re.IGNORECASE), 5),
    (re.compile(r"\bseveral\s+years\s+(?:of\s+)?" + _GAP + r"experience", re.IGNORECASE), 3),
]


def _to_int(token):
    token = token.lower()
    return int(token) if token.isdigit() else _NUMBER_WORDS.get(token)


def extract_min_years(cleaned_text):
    """
    Scan CLEANED text (output of clean_description, same contract as
    extract_skills) for a years-of-experience requirement and return the
    minimum number of years as an int, or None if none is found.

    This is Layer 1 (cheap, deterministic regex) of the two-layer
    entry-level detector - Layer 2 is a separate Gemini judgment pass for
    cases that imply seniority in other ways (e.g. "proven track record of
    independently delivering production systems").

    Order matters: explicit numbers win over vague phrases.
    - Ranges ("2-4 years", "3-5 Jahre") return the LOWER bound.
    - Digits and number words: "mindestens zwei Jahre", "3+ years",
      "Berufserfahrung von mindestens 3 Jahren".
    - Numbers above 15 are ignored ("seit über 100 Jahren" is company age).
    - No number: "mehrjährige Berufserfahrung" / "several years of
      experience" -> 3, "langjährige Erfahrung" / "many years of
      experience" -> 5 (estimates).
    """
    if not cleaned_text:
        return None
    for pattern in _YEAR_PATTERNS:
        for match in pattern.finditer(cleaned_text):
            years = _to_int(match.group(1))
            if years is not None and years <= _MAX_PLAUSIBLE_YEARS:
                return years
    for pattern, estimate in _VAGUE_SENIORITY_PATTERNS:
        if pattern.search(cleaned_text):
            return estimate
    return None

_ENTRY_LEVEL_KEYWORDS = [
    "junior", "entry level", "entry-level", "graduate", "trainee",
    "werkstudent", "berufseinsteiger",
]


def looks_entry_level(title):
    """
    Check whether a job TITLE itself claims to be entry-level/junior -
    independent of whether the description backs that up. Used to decide
    when it's worth spending a Gemini judge_seniority() call: only on
    titles that claim entry-level but where extract_min_years() found no
    explicit number, since that's the only case where there's something
    to actually verify.
    """
    if not title:
        return False
    t = title.lower()
    return any(keyword in t for keyword in _ENTRY_LEVEL_KEYWORDS)

