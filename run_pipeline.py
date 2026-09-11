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
    jobs = extract()
    print(f"Extracted {len(jobs)} survivor postings.")

    loaded, skipped = load_jobs(jobs)
    print(f"Loaded {loaded} jobs, skipped {skipped}.")