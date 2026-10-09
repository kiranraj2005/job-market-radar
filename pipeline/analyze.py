import time
from google import genai
from google.genai.errors import ServerError
from pipeline.retrieve import find_matching_jobs

GENERATION_MODEL = "gemini-3.8-flash"  # migrated from 3.6-flash 9 Oct 2026 - 3.6
# failed 100% of calls across three separate days (7, 8, 9 Oct), confirmed via
# Google's own dev forum as a known issue with that specific model. 3.8 (current
# flagship) verified working with real, good-quality output on this exact prompt.

PROMPT_TEMPLATE = """You are a career advisor helping a job seeker understand how their CV compares to real, current job postings in the German job market.

CANDIDATE'S CV / SKILLS:
{cv_text}

REAL JOB POSTINGS RETRIEVED AS THE CLOSEST MATCHES TO THIS CV (use ONLY these as your evidence — do not invent requirements that are not stated in these postings):
{postings_block}

Write a short, specific gap analysis:
1. Which 3-5 skills or technologies appear repeatedly across these postings but are NOT clearly present in the candidate's CV?
2. For each one, name exactly which posting(s) (by number) mention it.
3. Suggest one concrete way the candidate could reword or add to their CV to better match the real language used in these postings.

Do not make any claim that isn't directly supported by the postings above. If the postings don't support a claim, don't make it."""


def build_postings_block(matches):
    lines = []
    for i, m in enumerate(matches, start=1):
        lines.append(
            f"[{i}] {m['title']} @ {m['company']} (posted {m['posted_at']})\n"
            f"{m['description'][:1500]}"
        )
    return "\n\n".join(lines)


def generate_with_retry(client, model, contents, max_retries=4, base_delay=5):
    """Call generate_content, retrying on transient 503 'high demand' errors
    with exponential backoff (5s, 10s, 20s, 40s). Real external APIs fail
    transiently sometimes — handling that gracefully is expected production
    behavior, not a workaround for a bug."""
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(model=model, contents=contents)
        except ServerError:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            print(f"Gemini overloaded (attempt {attempt + 1}/{max_retries}), retrying in {delay}s...")
            time.sleep(delay)


def analyze_cv(cv_text, k=5):
    matches = find_matching_jobs(cv_text, k=k)
    postings_block = build_postings_block(matches)
    prompt = PROMPT_TEMPLATE.format(cv_text=cv_text, postings_block=postings_block)

    client = genai.Client()
    response = generate_with_retry(client, GENERATION_MODEL, prompt)

    citations = [
        {"title": m["title"], "company": m["company"], "url": m["posting_url"], "posted_at": str(m["posted_at"])}
        for m in matches
    ]
    return response.text, citations


if __name__ == "__main__":
    sample_cv = """
    MSc Computer Science graduate. Skilled in Python, SQL, Docker, and building
    ETL pipelines. Experience with PostgreSQL and CI/CD using GitHub Actions.
    Looking for Data Engineer or Data Analyst roles in Germany.
    """
    answer, citations = analyze_cv(sample_cv)
    print("=== GAP ANALYSIS ===")
    print(answer)
    print("\n=== SOURCES ===")
    for c in citations:
        print(f"- {c['title']} @ {c['company']} ({c['posted_at']}) {c['url']}")