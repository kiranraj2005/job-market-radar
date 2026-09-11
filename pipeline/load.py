from pipeline.db import get_connection
from pipeline.transform import clean_description, extract_skills

def upsert_skill(cur, skill_name):
    """
    Get-or-create a skill, returning its skill_id.

    skill_name is UNIQUE, so a plain INSERT would fail on a repeat skill.
    The standard Postgres trick: INSERT ... ON CONFLICT DO UPDATE SET
    (updating the column to its own value - a harmless no-op) instead of
    DO NOTHING, specifically because DO NOTHING doesn't let you RETURNING
    a row on conflict, but DO UPDATE does. This gets us the skill_id in
    one round trip whether the skill is new or already exists.
    """
    cur.execute(
        """
        INSERT INTO skills (skill_name)
        VALUES (%s)
        ON CONFLICT (skill_name) DO UPDATE SET skill_name = EXCLUDED.skill_name
        RETURNING skill_id
        """,
        (skill_name,),
    )
    return cur.fetchone()[0]


def upsert_job(cur, job):
    """
    Upsert one job row, keyed on job_id. On conflict, update every field
    a re-scrape might change, and always bump fetched_at.

    Uses clock_timestamp(), not now() - now() returns the time the
    CURRENT TRANSACTION began and stays frozen for every statement in
    that transaction, which silently breaks "did fetched_at actually
    update" style checks if multiple upserts share one transaction.
    clock_timestamp() always reflects the real moment this statement runs.
    """
    cur.execute(
        """
        INSERT INTO jobs (job_id, title, company, city, remote, role_type, posted_at, fetched_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, clock_timestamp())
        ON CONFLICT (job_id) DO UPDATE SET
            title = EXCLUDED.title,
            company = EXCLUDED.company,
            city = EXCLUDED.city,
            remote = EXCLUDED.remote,
            role_type = EXCLUDED.role_type,
            posted_at = EXCLUDED.posted_at,
            fetched_at = clock_timestamp()
        """,
        (
            job["job_id"], job["title"], job["company"], job["city"],
            job["remote"], job["role_type"], job["posted_at"],
        ),
    )


def link_job_skills(cur, job_id, skill_ids):
    """
    Replace a job's skill links with the current set, rather than only
    ever adding new ones. This matters because SKILL_ALIASES keeps
    growing (we just added Azure, C++, Excel this week) - without a
    delete-then-reinsert, a posting loaded before those additions would
    keep an incomplete skill list forever, even after re-running the
    pipeline with the updated code. Delete-then-reinsert makes each run
    reflect the CURRENT code's understanding of the posting, not a
    historical accumulation across every past run.
    """
    cur.execute("DELETE FROM job_skills WHERE job_id = %s", (job_id,))
    for skill_id in skill_ids:
        cur.execute(
            "INSERT INTO job_skills (job_id, skill_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (job_id, skill_id),
        )





def load_jobs(jobs):
    """
    Load a batch of extracted postings into Postgres. Commits once PER
    JOB (not once for the whole batch), so one malformed posting can't
    roll back everything else already loaded that run - it's skipped
    with a printed warning instead of crashing the whole pipeline.
    """
    conn = get_connection()
    cur = conn.cursor()
    loaded = 0
    skipped = 0

    for job in jobs:
        try:
            upsert_job(cur, job)
            cleaned = clean_description(job.get("description_html", ""))
            skills = extract_skills(cleaned)
            skill_ids = [upsert_skill(cur, name) for name in skills]
            link_job_skills(cur, job["job_id"], skill_ids)
            conn.commit()
            loaded += 1
        except Exception as e:
            conn.rollback()
            print(f"Skipped job {job.get('job_id')}: {e}")
            skipped += 1

    conn.close()
    return loaded, skipped