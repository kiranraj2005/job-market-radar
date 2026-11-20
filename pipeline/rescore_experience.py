"""Recalculate min_years_required / experience_mismatch for stored postings with the current rules.

No Gemini calls: uses the stored description. Run after changing extract_min_years.
Rows where the new rules find nothing keep their old value (it may come from a
Gemini judgment), except impossible values above 15, which are cleared.

Usage:  python3 -m pipeline.rescore_experience           (dry run, shows changes)
        python3 -m pipeline.rescore_experience --apply   (writes them)
"""
import argparse

from pipeline.db import get_connection
from pipeline.transform import extract_min_years, looks_entry_level, _MAX_PLAUSIBLE_YEARS


def rescore(apply=False):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT job_id, title, description, min_years_required FROM jobs")
            rows = cur.fetchall()

        changes = []
        for job_id, title, description, old in rows:
            new = extract_min_years(description or "")
            if new is None:
                if old is not None and old > _MAX_PLAUSIBLE_YEARS:
                    changes.append((job_id, title, old, None))
                continue
            if new != old:
                changes.append((job_id, title, old, new))

        print(f"Checked {len(rows)} postings, {len(changes)} would change:")
        for job_id, title, old, new in changes:
            print(f"  {old!s:>5} -> {new!s:<5} {title}")

        if apply and changes:
            with conn:
                with conn.cursor() as cur:
                    for job_id, title, old, new in changes:
                        mismatch = looks_entry_level(title) and new is not None and new >= 2
                        cur.execute(
                            "UPDATE jobs SET min_years_required = %s, experience_mismatch = %s WHERE job_id = %s",
                            (new, mismatch, job_id),
                        )
            print("Applied.")
        elif changes:
            print("Dry run only. Add --apply to write these changes.")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write the changes to the database")
    rescore(parser.parse_args().apply)