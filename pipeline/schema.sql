CREATE TABLE jobs (
  job_id      TEXT PRIMARY KEY,
  title       TEXT,
  company     TEXT,
  city        TEXT,
  remote      BOOLEAN,
  role_type   TEXT,
  posted_at   DATE,
  fetched_at  TIMESTAMP DEFAULT now()
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
