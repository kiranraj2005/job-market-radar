# Job Market Radar

**Data foundations for AI-ready hiring intelligence.**

A production-style ETL pipeline that turns messy, real-world German tech job postings into a clean,
queryable, normalized dataset — built to demonstrate the part of the AI pipeline that rarely gets shown:
the data engineering underneath it.

[![CI](https://github.com/kiranraj2005/job-market-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/kiranraj2005/job-market-radar/actions/workflows/ci.yml)

## Why this project

German IT hiring data (Bitkom, Hays, Bundesagentur für Arbeit — Sep 2026) shows entry-level demand
shifting away from generalist software development and toward the roles that keep AI systems fed,
secure, and running. Data engineering is one of the only specialisms where entry-level demand is
*rising*, for a simple reason: AI can't be built on bad data structures. This project is a working
demonstration of that pipeline, end to end — not a toy example, a real one, against real live data,
with the messiness that implies.

## What it does

1. **Extract** — pulls live postings from a public job-board API (~600 postings per run), paginating
   through the full result set.
2. **Filter & classify** — restricts to genuinely German-based postings (location data is inconsistent
   in the wild: plain city names, multi-city strings, blank fields — all handled explicitly) and tags
   each posting's role type against a documented, evidence-grown keyword list, including handling for
   German job-title conventions like parenthetical qualifiers (`"AI (Senior) Developer (m/w/d)"`).
3. **Transform** — strips raw (and inconsistently double-encoded) HTML from job descriptions, decodes
   entities, and extracts specific skill mentions (a 16-entry vocabulary grown from real posting data,
   not guessed in advance).
4. **Load** — idempotent upserts into a normalized 3-table PostgreSQL schema (`jobs`, `skills`,
   `job_skills`), with foreign-key integrity and per-row error handling so one malformed record can't
   break a run.
5. **Run reproducibly, anywhere** — the entire stack (database + pipeline) is containerized via Docker
   Compose, with a healthcheck-gated startup and automatic schema initialization, so a fresh clone with
   zero manual setup produces a fully working system in one command.
6. **Prove it, automatically** — every push runs the full pytest suite and a real integration smoke test
   (build the containers, wipe the database, run the pipeline against a genuinely empty Postgres) via
   GitHub Actions, so the badge above reflects the pipeline actually working, not just code existing.

## Quickstart

```bash
git clone https://github.com/kiranraj2005/job-market-radar.git
cd job-market-radar
echo "DB_PASSWORD=your_password_here" > .env
docker compose up --build
```

That's it — Postgres initializes its schema automatically, the pipeline builds, waits for the database
to be genuinely ready (not just "container started"), and runs against live data. No manual `docker exec`,
no manual schema setup.


## Architecture

```
 arbeitnow.com API
        │
        ▼
  extract.py  ──► filter (German location) ──► classify (role type)
        │
        ▼
 transform.py ──► strip HTML / decode entities ──► extract skills
        │
        ▼
   load.py    ──► idempotent upsert
        │
        ▼
  PostgreSQL  (jobs / skills / job_skills — normalized, FK-enforced)
```

Both the pipeline and the database run as separate Docker Compose services (`pipeline`, `db`), with the
pipeline service waiting on the database's healthcheck before connecting.


## Tech stack

Python 3.13 · PostgreSQL 16 · Docker & Docker Compose · pytest · GitHub Actions

## Real engineering problems found and fixed (not just checkboxes)

This project's data-quality instrumentation (an extraction funnel — raw → German-filtered → classified →
survivors) surfaced two genuine classifier bugs against live data: missing role-title phrasings (e.g.
"Data Platform Engineer," "Agentic AI") and a more general bug where German job titles commonly insert
parenthetical qualifiers (`(Senior)`, `(m/w/d)`) between the words of a phrase, breaking naive substring
matching — fixed by stripping parenthetical content before matching, a fix that protects against the
whole pattern, not just the one example found.

Dockerizing the stack surfaced two more: a race condition where `depends_on` only waited for the database
*container* to start, not for Postgres to actually accept connections (fixed with a proper healthcheck);
and a missing schema-initialization step that only "worked" because of a manual, undocumented setup step
weeks earlier (fixed by wiring `schema.sql` into Postgres's own first-boot initialization mechanism).

Both are backed by an automated pytest suite (25 tests) and now run automatically on every push.

## Roadmap

- RAG-based career-advice copilot on top of the collected data
- AWS deployment (App Runner/ECS + RDS), building directly on the containerization work already done

## Data source

[arbeitnow.com](https://www.arbeitnow.com) public job-board API.
