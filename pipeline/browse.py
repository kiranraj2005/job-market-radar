"""
pipeline/browse.py

Plain filtered browsing of the jobs table - no embeddings, no Gemini,
just SQL (plus one pure-function re-check, see below). Kept separate
from retrieve.py (which is specifically RAG vector search) because this
is a different concern: letting the web app list/filter postings directly.
"""

from pipeline.db import get_connection
from pipeline.transform import looks_entry_level


def list_jobs(entry_level_only=False, role_type=None, remote_only=False, limit=200):
    """
    Return jobs matching the given filters, most recently fetched first.

    IMPORTANT about entry_level_only: experience_mismatch alone is NOT
    enough to mean "genuinely entry-level". experience_mismatch is only
    ever set True for postings whose TITLE claimed entry-level AND we
    found evidence of a real experience requirement. For a posting that
    never claimed entry-level in the first place (e.g. "Principal AI
    Engineer"), experience_mismatch is also False - not because it's
    entry-level-friendly, but because that question was never asked of
    it. Filtering on experience_mismatch = FALSE alone would therefore
    let every senior/unrelated posting through alongside the genuine
    entry-level ones.

    The correct check is two-part: the title has to actually read as
    entry-level (looks_entry_level, same pure function used at load
    time) AND it must not have been flagged as a mismatch. This is done
    in Python rather than SQL since looks_entry_level is a cheap regex
    check on text we're already fetching, not something worth a second
    DB round trip or a new persisted column for.
    """
    conn = get_connection()
    cur = conn.cursor()

    clauses = []
    params = []

    if role_type:
        clauses.append("role_type = %s")
        params.append(role_type)
    if remote_only:
        clauses.append("remote = TRUE")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit if not entry_level_only else limit * 4)
    # When filtering to entry-level-only, over-fetch before the Python-side
    # filter narrows it down, so a real limit-sized page still comes back
    # instead of being cut short by rows that get filtered out afterward.

    cur.execute(
        f"""
        SELECT job_id, title, company, city, remote, role_type, posting_url,
               posted_at, min_years_required, experience_mismatch
        FROM jobs
        {where}
        ORDER BY fetched_at DESC
        LIMIT %s
        """,
        params,
    )
    rows = cur.fetchall()
    conn.close()

    jobs = [
        {
            "job_id": r[0], "title": r[1], "company": r[2], "city": r[3],
            "remote": r[4], "role_type": r[5], "posting_url": r[6],
            "posted_at": r[7], "min_years_required": r[8], "experience_mismatch": r[9],
        }
        for r in rows
    ]

    if entry_level_only:
        jobs = [
            j for j in jobs
            if looks_entry_level(j["title"]) and not j["experience_mismatch"]
        ]
        jobs = jobs[:limit]

    return jobs


def distinct_role_types():
    """Role types actually present in the data, for populating a filter dropdown
    without hardcoding values that could drift from what extract.py classifies."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT role_type FROM jobs WHERE role_type IS NOT NULL ORDER BY role_type")
    values = [r[0] for r in cur.fetchall()]
    conn.close()
    return values


if __name__ == "__main__":
    all_jobs = list_jobs()
    entry_level_jobs = list_jobs(entry_level_only=True)
    print(f"Total jobs (up to limit): {len(all_jobs)}")
    print(f"Genuinely entry-level only: {len(entry_level_jobs)}")
    for j in entry_level_jobs:
        print(f"  - {j['title']} @ {j['company']}")
    print(f"Role types in data: {distinct_role_types()}")
