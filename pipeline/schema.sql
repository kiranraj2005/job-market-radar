CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE jobs (
  job_id      TEXT PRIMARY KEY,
  title       TEXT,
  company     TEXT,
  city        TEXT,
  remote      BOOLEAN,
  role_type   TEXT,
  posting_url TEXT,
  posted_at   DATE,
  fetched_at  TIMESTAMP DEFAULT now(),
  description TEXT,
  embedding   vector(3072),
  min_years_required  INTEGER,
  experience_mismatch BOOLEAN
);

CREATE TABLE skills (
  skill_id    SERIAL PRIMARY KEY,
  skill_name  TEXT UNIQUE
);

CREATE TABLE job_skills (
  job_id      TEXT REFERENCES jobs(job_id),
  skill_id    INT REFERENCES skills(skill_id),
  PRIMARY KEY (job_id, skill_id)
);
CREATE TABLE trend_snapshots (
  snapshot_id                SERIAL PRIMARY KEY,
  captured_at                TIMESTAMP DEFAULT now(),
  total_postings             INTEGER,
  entry_level_mismatch_rate  NUMERIC(5,2),
  avg_min_years_required     NUMERIC(5,2),
  skill_counts                JSONB,
  role_type_counts           JSONB
);
