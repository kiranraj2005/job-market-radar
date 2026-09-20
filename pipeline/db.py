import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Connect to Postgres. Host is configurable via DB_HOST so this same
    code works both ways: locally (DB_HOST unset, defaults to localhost,
    since Postgres's port is exposed to the host machine) and inside
    Docker Compose (DB_HOST=db, Compose's internal DNS resolving the
    service name "db" to the database container)."""
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=5432, dbname="jobmarket", user="postgres",
        password=os.environ["DB_PASSWORD"],
    )