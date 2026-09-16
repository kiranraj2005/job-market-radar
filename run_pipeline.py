"""
run_pipeline.py

The real entry point: pull live postings from the API, run them through
the full extract -> transform -> load pipeline, and report what happened.
Run outside Docker first (as we're doing now) - Dockerizing this comes
last, once we know the plain Python version works correctly.
"""

from pipeline.extract import extract
from pipeline.load import load_jobs

if __name__ == "__main__":
    jobs, stats = extract()
    print(
        f"Extracted {stats['survivors']} survivor postings out of {stats['raw']} raw postings "
        f"({stats['dropped_non_german']} dropped as non-German, "
        f"{stats['dropped_unclassified']} dropped as role-unclassified)."
    )

    loaded, skipped = load_jobs(jobs)
    print(f"Loaded {loaded} jobs, skipped {skipped}.")