"""
pipeline/explore_api.py

THROWAWAY / EXPLORATORY SCRIPT - not part of the production pipeline.

Used during Step 3 to poke at the real arbeitnow API response shape
before writing extract.py. Not polished, not tested, and not run as
part of run_pipeline.py. Kept in the repo because the 11 findings it
surfaced (see project notes / README) directly shaped extract.py and
transform.py's design - this is the "how I actually explored an
unfamiliar API" receipt, not a script meant to be reused as-is.
"""

import requests

response = requests.get("https://www.arbeitnow.com/api/job-board-api")
data = response.json()["data"]

print(f"Total postings on this page: {len(data)}\n")

print("--- Quick scan of the first 15 ---")
for job in data[:15]:
    print(f"- {job['title']!r} | {job['company_name']} | {job['location']} "
          f"| remote={job['remote']} | tags={job['tags']} | job_types={job['job_types']}")

remote_jobs = [j for j in data if j['remote']]
print(f"\n{len(remote_jobs)} of {len(data)} are marked remote=True")

typed_jobs = [j for j in data if j['job_types']]
print(f"{len(typed_jobs)} of {len(data)} have a non-empty job_types")
if typed_jobs:
    print("Example job_types value:", typed_jobs[0]['job_types'])

data_jobs = [j for j in data if 'data' in j['title'].lower()]
print(f"\n{len(data_jobs)} postings have 'data' in the title:")
for j in data_jobs:
    print(f"- {j['title']} | {j['company_name']} | {j['location']}")

print("\n--- pagination info ---")
payload = requests.get("https://www.arbeitnow.com/api/job-board-api").json()
print("links:", payload["links"])
print("meta:", payload["meta"])
