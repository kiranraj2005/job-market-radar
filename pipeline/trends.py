"""
pipeline/trends.py

RAG-6: trend tracking on the living dataset.

jobs rows get upserted by job_id, so a job's OWN row doesn't preserve
history - a re-fetched posting just overwrites its old values. To see a
trend at all, something has to survive across runs. capture_snapshot()
computes a handful of aggregate metrics from the current state of `jobs`
and inserts ONE new row into trend_snapshots each time it's called. Call
it once per pipeline run, after load_jobs() - it only reads jobs/job_skills,
nothing from embed.py, so it doesn't need to wait on embeddings.
"""

from psycopg2.extras import Json

from pipeline.db import get_connection
from pipeline.transform import looks_entry_level


def capture_snapshot():
    """Compute this run's aggregate metrics and insert one trend_snapshots row."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM jobs")
    total_postings = cur.fetchone()[0]

    # Entry-level mismatch rate: of postings whose TITLE reads as entry-level,
    # what fraction were flagged as secretly requiring real experience? Reuses
    # the exact same looks_entry_level() + experience_mismatch combination as
    # EL-1's own browse.py filter - the same honesty check, not a new metric
    # invented separately, so this can never silently drift from what the
    # "genuinely entry-level only" filter actually means.
    cur.execute("SELECT title, experience_mismatch FROM jobs")
    rows = cur.fetchall()
    entry_level_titled = [r for r in rows if looks_entry_level(r[0])]
    if entry_level_titled:
        mismatched = sum(1 for _, mismatch in entry_level_titled if mismatch)
        mismatch_rate = round(100.0 * mismatched / len(entry_level_titled), 2)
    else:
        mismatch_rate = None

    cur.execute("SELECT AVG(min_years_required) FROM jobs WHERE min_years_required IS NOT NULL")
    avg_years = cur.fetchone()[0]
    avg_years = round(float(avg_years), 2) if avg_years is not None else None

    cur.execute(
        """
        SELECT skills.skill_name, COUNT(*)
        FROM job_skills
        JOIN skills ON skills.skill_id = job_skills.skill_id
        GROUP BY skills.skill_name
        """
    )
    skill_counts = {name: count for name, count in cur.fetchall()}

    cur.execute(
        "SELECT role_type, COUNT(*) FROM jobs WHERE role_type IS NOT NULL GROUP BY role_type"
    )
    role_type_counts = {role: count for role, count in cur.fetchall()}

    # psycopg2 can't adapt a plain Python dict into JSONB on its own - Json(...)
    # from psycopg2.extras wraps it so it's serialized correctly. Same class of
    # gotcha as embed.py's vector_literal() string-cast for the vector column:
    # a Python-native type that needs an explicit adapter for this one Postgres
    # column type, not something psycopg2 infers automatically.
    cur.execute(
        """
        INSERT INTO trend_snapshots
            (total_postings, entry_level_mismatch_rate, avg_min_years_required,
             skill_counts, role_type_counts)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (total_postings, mismatch_rate, avg_years, Json(skill_counts), Json(role_type_counts)),
    )
    conn.commit()
    conn.close()

    return {
        "total_postings": total_postings,
        "entry_level_mismatch_rate": mismatch_rate,
        "avg_min_years_required": avg_years,
        "skill_counts": skill_counts,
        "role_type_counts": role_type_counts,
    }


def get_trend_history():
    """Return every snapshot captured so far, oldest first, for charting."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT captured_at, total_postings, entry_level_mismatch_rate,
               avg_min_years_required, skill_counts, role_type_counts
        FROM trend_snapshots
        ORDER BY captured_at ASC
        """
    )
    rows = cur.fetchall()
    conn.close()
    # psycopg2 returns NUMERIC columns (entry_level_mismatch_rate,
    # avg_min_years_required) as Python Decimal objects, not plain floats.
    # Decimal prints correctly on its own (that's why the single-snapshot
    # st.metric() fallback in app.py never showed a problem), but Altair's
    # JSON serialization of a Decimal-typed pandas column silently drops the
    # decimal point - 4.54 was rendering as 454 on the trend charts. Casting
    # to float() here, right at the DB boundary, means nothing downstream
    # (pandas, Altair, Vega-Lite) ever has to handle a Decimal at all.
    return [
        {
            "captured_at": r[0],
            "total_postings": r[1],
            "entry_level_mismatch_rate": float(r[2]) if r[2] is not None else None,
            "avg_min_years_required": float(r[3]) if r[3] is not None else None,
            "skill_counts": r[4],
            "role_type_counts": r[5],
        }
        for r in rows
    ]


if __name__ == "__main__":
    snapshot = capture_snapshot()
    print(f"Captured snapshot: {snapshot}")
