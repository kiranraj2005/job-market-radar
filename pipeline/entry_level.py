from google import genai
from pipeline.analyze import generate_with_retry

# Deliberately NOT reusing analyze.py's GENERATION_MODEL ("gemini-3.6-flash"): that
# model returned 503 UNAVAILABLE on every call across two separate days (8 Oct 2026),
# confirmed on Google's own dev forum as a known issue. gemini-3.8-flash (current
# flagship, separate daily quota bucket) succeeded on 2/2 real judge_seniority() calls
# with correct output, so it's used here specifically - independent of analyze.py's
# model, which is still pinned to 3.6-flash pending its OWN re-verification (its much
# longer prompt hasn't been confirmed against 3.8 yet - see portfolio build log).
JUDGMENT_MODEL = "gemini-3.8-flash"

JUDGMENT_PROMPT_TEMPLATE = """You are screening a job posting to check whether it is genuinely suitable for an entry-level / junior candidate, or whether it actually demands significant prior experience without stating an explicit number of years.

JOB TITLE:
{title}

JOB DESCRIPTION:
{description}

Base your judgment ONLY on what this description actually says - do not assume seniority just because the role sounds technical. Look for phrases that imply real-world experience is required (e.g. "proven track record", "independently led", "mentored other engineers", "X years leading..."), as opposed to phrases that are genuinely entry-level-friendly (e.g. "no prior experience required", "training provided", "recent graduates welcome").

Respond with ONLY a JSON object, no other text, in exactly this shape:
{{"implies_experienced": true or false, "estimated_min_years": <integer or null>, "reasoning": "<one sentence citing the specific phrase that drove your judgment>"}}"""


def judge_seniority(title, description):
    client = genai.Client()
    prompt = JUDGMENT_PROMPT_TEMPLATE.format(title=title, description=description)
    response = generate_with_retry(client, JUDGMENT_MODEL, prompt)

    import json
    text = response.text.strip()
    # Gemini sometimes wraps JSON in ```json ... ``` - strip that if present
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    return json.loads(text)


if __name__ == "__main__":
    genuinely_entry_level = (
        "No prior experience required - we provide full training. Recent graduates "
        "and career changers welcome. You'll learn SQL and Python on the job."
    )
    hidden_seniority = (
        "Join as our (Junior) Data Platform Engineer. You will independently own "
        "our production data infrastructure and have a proven track record of "
        "mentoring other engineers on best practices."
    )

    for label, desc in [("genuinely entry-level", genuinely_entry_level), ("hidden seniority", hidden_seniority)]:
        result = judge_seniority("Junior Data Engineer", desc)
        print(f"--- {label} ---")
        print(result)