# Job Market Radar

**A RAG-powered career copilot built on a production-style data pipeline for the German tech job market.**

Live postings go in one end; a citation-grounded CV gap analysis, a genuine entry-level detector, and a
filterable job browser come out the other. Built to demonstrate the full stack underneath a real AI
product. It is not just a model call, but the data engineering, retrieval, and judgment calls that make the
model call trustworthy.

[![CI](https://github.com/kiranraj2005/job-market-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/kiranraj2005/job-market-radar/actions/workflows/ci.yml)

## Why this project

German IT hiring data (Bitkom, Hays, Bundesagentur für Arbeit — Sep 2026) shows entry-level demand
shifting away from generalist software development and toward the roles that keep AI systems fed,
secure, and running. Data engineering is one of the only specialisms where entry-level demand is
*rising*, for a simple reason: AI can't be built on bad data structures. This project is a working
demonstration of that pipeline, end to end — not a toy example, a real one, against real live data,
with the messiness that implies.

The entry-level detector (below) came directly out of my own job search: postings labeled "Junior" or
"Entry Level" that, read closely, actually demand 2-4 years of experience. Instead of just complaining
about it, I built the thing that checks for it automatically.

## What it does

### Data pipeline (extract → transform → load)

1. **Extract** — Pulls live postings from a public job-board API (~600 postings per run), paginating
   through the full result set.
2. **Filter & classify** — Restricts to genuinely German-based postings (location data is inconsistent
   in the wild: plain city names, multi-city strings, blank fields. All handled explicitly) and tags
   each posting's role type against a documented, evidence-grown keyword list, including handling for
   German job-title conventions like parenthetical qualifiers (`"AI (Senior) Developer (m/w/d)"`).
3. **Transform** — Strips raw (and inconsistently double-encoded) HTML from job descriptions, decodes
   entities, and extracts specific skill mentions (a 16-entry vocabulary grown from real posting data,
   not guessed in advance).
4. **Load** — Idempotent upserts into a normalized PostgreSQL schema, with foreign-key integrity and
   per-row error handling so one malformed record can't break a run. The `jobs` table is a genuinely
   accumulating, living dataset — every run adds whatever's newly live, rather than replacing the table.

### RAG career-advice copilot

- Every posting's cleaned description is embedded (`gemini-embedding-001`, 3072-dim) into pgvector.
- Paste a CV, and the app retrieves the *k* closest real postings by cosine distance, then asks Gemini
  (`gemini-3.8-flash`) to name specific, concrete skill gaps — each one cited against the exact posting
  number(s) that support it, with a concrete suggestion for how to reword the CV to match the real
  language the market is actually using. No claim the postings don't actually support.

### Genuine entry-level detector (EL-1)

A three-layer pipeline that checks whether a posting that *reads* as entry-level actually is one:

1. **Regex layer** — extracts explicit experience requirements ("3+ years," "mindestens 2 Jahre
   Berufserfahrung") directly from the description, in both English and German.
2. **LLM judgment layer** — for postings regex can't resolve, Gemini reads the description for *implied*
   seniority ("proven track record," "independently led," "mentored other engineers") that doesn't state
   a number but still signals real experience is expected. Runs only on genuinely ambiguous cases, not
   every posting, so the free-tier Gemini quota is spent where it's actually needed.
3. **Resolution layer** — combines both signals into `min_years_required` and `experience_mismatch`,
   persisted per posting and surfaced as a real filter in the web app.

### Web app

A two-page Streamlit interface on top of all of the above: a filterable job browser (entry-level-only,
remote-only, role-type filters) and the CV gap-analysis tool, both backed by the real pipeline — not a
mockup.

### Infrastructure

5. **Run reproducibly, anywhere** — the data pipeline and database are containerized via Docker Compose,
   with a healthcheck-gated startup and automatic schema initialization, so a fresh clone with zero
   manual setup produces a fully working system in one command.
6. **Prove it, automatically** — every push runs the full pytest suite (20+ tests) and a real integration
   smoke test (build the containers, wipe the database, run the full pipeline — including live Gemini
   calls — against a genuinely empty Postgres) via GitHub Actions, so the badge above reflects the
   pipeline actually working end to end, not just code existing.

## Quickstart

**Data pipeline (Docker, no local Python needed):**

```bash
git clone https://github.com/kiranraj2005/job-market-radar.git
cd job-market-radar
echo "DB_PASSWORD=your_password_here" >> .env
echo "GEMINI_API_KEY=your_gemini_key_here" >> .env
docker compose up --build
```

Postgres initializes its schema automatically, the pipeline builds, waits for the database to be
genuinely ready (not just "container started"), and runs against live data — extracting, embedding, and
running the entry-level detector on everything it finds.

**Web app (local Python, against the same database):**

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_gemini_key_here
streamlit run app.py
```

Opens at `localhost:8501` with the job browser and CV analysis tool. The web app isn't deployed anywhere
public yet — it runs against the Postgres instance from the Docker Compose step above.

## Architecture

```
 arbeitnow.com API
        │
        ▼
  extract.py ──► filter (German location) ──► classify (role type)
        │
        ▼
 transform.py ──► strip HTML / decode entities ──► extract skills
        │                                      └──► extract_min_years (EL-1, Layer 1)
        ▼
 entry_level.py ──► judge_seniority via Gemini (EL-1, Layer 2, ambiguous cases only)
        │
        ▼
   load.py ──► resolve_experience (EL-1, Layer 3) ──► idempotent upsert
        │
        ▼
  PostgreSQL + pgvector  (jobs / skills / job_skills)
        │
        ├──► embed.py ──► gemini-embedding-001 ──► embedding column
        │
        └──► app.py (Streamlit)
                ├─ Browse Jobs ──► browse.py ──► filtered SQL (incl. EL-1 filter)
                └─ CV Gap Analysis ──► retrieve.py (vector search) ──► analyze.py (gemini-3.8-flash,
                                        citation-grounded generation)
```

The pipeline and database run as separate Docker Compose services (`pipeline`, `db`), with the pipeline
service waiting on the database's healthcheck before connecting. The Streamlit app runs locally against
the same database.

## Tech stack

Python 3.13 · PostgreSQL 16 + pgvector · Google Gemini (`gemini-embedding-001`, `gemini-3.8-flash`) ·
Streamlit · Docker & Docker Compose · pytest · GitHub Actions

## Real engineering problems found and fixed (not just checkboxes)

This project's data-quality instrumentation (an extraction funnel — raw → German-filtered → classified →
survivors) surfaced two genuine classifier bugs against live data: missing role-title phrasings and a
more general bug where German job titles commonly insert parenthetical qualifiers (`(Senior)`, `(m/w/d)`)
between the words of a phrase, breaking naive substring matching — fixed by stripping parenthetical
content before matching, a fix that protects against the whole pattern, not just the one example found.

Dockerizing the stack surfaced two more: a race condition where `depends_on` only waited for the database
*container* to start, not for Postgres to actually accept connections (fixed with a proper healthcheck);
and a missing schema-initialization step that only "worked" because of a manual, undocumented setup step
weeks earlier (fixed by wiring `schema.sql` into Postgres's own first-boot initialization mechanism).

**Telling a vendor outage apart from a personal quota cap.** The Gemini generation model started failing
with `503 UNAVAILABLE` on effectively every call. Rather than reflexively widening the retry/backoff
settings (the obvious-looking fix), I read the exact error payload, cross-referenced it against Google's
own developer forum, and confirmed it was a known issue specific to that model, not a transient blip.
Widening retries anyway, on a free-tier key, cost me real request quota and produced a genuine
`429 RESOURCE_EXHAUSTED` — a mistake I caught and owned. After three separate days of 100% failure on the
same model, I migrated to a different model with its own separate quota bucket, verified the new model's
output quality on real data before trusting it, and consolidated both Gemini-calling code paths onto the
one proven model.

**Diagnosing a CI failure by reading the actual infrastructure, not guessing.** The first time CI
exercised the full Docker Compose integration step, it failed in under a minute with no visible log text.
Rather than guess, I read `requirements.txt`, `Dockerfile`, and `docker-compose.yml` against what the code
actually imports, and found two real, specific bugs: a dependency (`google-genai`) that was installed
locally but never added to `requirements.txt`, masked because the local virtual environment had it by
hand; and `GEMINI_API_KEY` never being plumbed from GitHub Secrets into the containerized pipeline, the
same class of bug as a fresh terminal not inheriting an exported environment variable, just one layer
further out. Both fixed, CI verified green afterward.

**Catching my own filter logic bug with real output, not code review.** The web app's "genuinely
entry-level only" filter initially used a single boolean column as a shortcut — which turned out to
conflate "verified genuinely entry-level" with "never claimed to be entry-level in the first place,"
letting senior roles leak into the filtered results. Caught by actually looking at what the filter
returned against real data (not by reading the code and assuming it was right), and fixed by requiring
both the original entry-level-title check *and* the absence of a flagged mismatch, reusing the exact same
function the data pipeline uses at write time so the two can never drift apart.

Every fix above is backed by an automated pytest suite and the full Docker Compose integration test, both
of which run automatically on every push.

## Roadmap

- Deploy the web app publicly (Streamlit Community Cloud), which requires migrating the database to a
  free-tier hosted Postgres with pgvector support, since the current database only runs locally
- Trend tracking on the accumulating dataset (e.g. how in-demand skills and the entry-level mismatch rate
  shift over time)
- AWS deployment (App Runner/ECS + RDS), building directly on the containerization work already done

## Data source

[arbeitnow.com](https://www.arbeitnow.com) public job-board API.
