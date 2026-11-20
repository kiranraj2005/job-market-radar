-- Migration 001: multi-source support (Bundesagentur API) and CV-based ranking.
-- Safe to run more than once: every statement checks whether it is already applied.

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source            TEXT NOT NULL DEFAULT 'arbeitnow';
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS changed_at        TIMESTAMP;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS employment_type   TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS career_changer_ok BOOLEAN;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_temp_agency    BOOLEAN;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS content_hash      TEXT;

CREATE TABLE IF NOT EXISTS cv_profiles (
  profile_name  TEXT PRIMARY KEY,
  content_hash  TEXT,
  embedding     vector(3072),
  skills        TEXT[],
  updated_at    TIMESTAMP DEFAULT now()
);