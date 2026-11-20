"""Apply a SQL migration file to the database configured for this project.

Usage:  python3 -m pipeline.apply_migration pipeline/migrations/001_multi_source.sql
"""
import sys
from pathlib import Path

from pipeline.db import get_connection


def apply(path):
    sql = Path(path).read_text()
    conn = get_connection()
    try:
        host = conn.get_dsn_parameters().get("host")
        print(f"Connected to: {host}")
        with conn:                      # commits if everything succeeds, rolls back on any error
            with conn.cursor() as cur:
                cur.execute(sql)
        print(f"Applied: {path}")
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 -m pipeline.apply_migration <file.sql>")
    apply(sys.argv[1])