from pipeline.db import get_connection
from pipeline.transform import clean_description, extract_skills, extract_min_years, looks_entry_level
from pipeline.entry_level import judge_seniority


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
    Insert or update one posting. Works for every source: fields that only
    some sources provide (changed_at, employment_type, ...) come in via
    job.get(), so an arbeitnow posting simply stores NULL for them.
    """
    cur.execute(
        """
        INSERT INTO jobs (job_id, title, company, city, remote, role_type, posting_url, posted_at,
                          description, min_years_required, experience_mismatch,
                          source, changed_at, employment_type, career_changer_ok, is_temp_agency,
                          fetched_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, clock_timestamp())
        ON CONFLICT (job_id) DO UPDATE SET
            title = EXCLUDED.title,
            company = EXCLUDED.company,
            city = EXCLUDED.city,
            remote = EXCLUDED.remote,
            role_type = EXCLUDED.role_type,
            posting_url = EXCLUDED.posting_url,
            posted_at = EXCLUDED.posted_at,
            description = EXCLUDED.description,
            min_years_required = EXCLUDED.min_years_required,
            experience_mismatch = EXCLUDED.experience_mismatch,
            source = EXCLUDED.source,
            changed_at = EXCLUDED.changed_at,
            employment_type = EXCLUDED.employment_type,
            career_changer_ok = EXCLUDED.career_changer_ok,
            is_temp_agency = EXCLUDED.is_temp_agency,
            fetched_at = clock_timestamp()
        """,
        (
            job["job_id"], job["title"], job["company"], job["city"],
            job["remote"], job["role_type"], job["posting_url"], job["posted_at"], job["description"],
            job["min_years_required"], job["experience_mismatch"],
            job.get("source", "arbeitnow"), job.get("changed_at"), job.get("employment_type"),
            job.get("career_changer_ok"), job.get("is_temp_agency"),
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


def resolve_experience(title, cleaned_description, allow_llm=True):
    """
    EL-1: combine the two detection layers into (min_years_required, experience_mismatch,
    used_llm).

    Layer 1 (extract_min_years) runs first - free, no API call. Layer 2
    (judge_seniority) only runs when Layer 1 found nothing AND the title
    itself claims entry-level/junior, since that's the only situation
    where there's something worth verifying (don't spend a Gemini
    request on every row - only the genuinely ambiguous ones). If Layer 2
    fails for any reason (quota, API hiccup), that's caught here so one
    job's judgment call can't take down the whole load_jobs() run.

    allow_llm=False skips Layer 2 entirely: used when the run's Gemini
    budget is spent, or the posting is only a short summary.
    """
    entry_level_title = looks_entry_level(title)
    min_years = extract_min_years(cleaned_description)
    used_llm = False

    if min_years is None and entry_level_title and allow_llm:
        used_llm = True
        try:
            judgment = judge_seniority(title, cleaned_description)
            if judgment.get("implies_experienced"):
                min_years = judgment.get("estimated_min_years")
        except Exception as e:
            print(f"Layer 2 judgment skipped for {title!r}: {e}")

    experience_mismatch = (
        entry_level_title and min_years is not None and min_years >= 2
    )
    return min_years, experience_mismatch, used_llm


def load_jobs(jobs, llm_budget=5):
    """
    Load postings from any source. llm_budget caps the Gemini (Layer 2)
    calls per run: the free tier allows about 20 requests a day per model,
    and the app's CV gap analysis needs some of them too. Postings past the
    budget keep min_years = None (unknown), as if the call had failed.
    """
    conn = get_connection()
    cur = conn.cursor()
    loaded = 0
    skipped = 0
    llm_used = 0

    for job in jobs:
        try:
            cleaned = clean_description(job.get("description_html", ""))
            job["description"] = cleaned
            allow_llm = llm_used < llm_budget and not job.get("is_summary", False)
            min_years, mismatch, used_llm = resolve_experience(job["title"], cleaned, allow_llm)
            llm_used += used_llm
            job["min_years_required"] = min_years
            job["experience_mismatch"] = mismatch
            upsert_job(cur, job)
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
    print(f"Gemini Layer 2 calls used: {llm_used} of {llm_budget}")
    return loaded, skipped