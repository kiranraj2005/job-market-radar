import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Connect to Postgres.

    Two modes, chosen automatically:
      - DATABASE_URL set (a full connection string, e.g. from Neon) -> connect
        with it directly. This is the standard pattern hosted Postgres
        providers expect (Heroku, Render, Railway, Neon all default to it),
        since a hosted DB has its own dbname/user that won't match our local
        hardcoded "jobmarket"/"postgres", and typically requires SSL
        (sslmode=require), which the connection string already encodes.
      - DATABASE_URL unset -> fall back to the original host/port/dbname/user
        construction, unchanged from before. DB_HOST defaults to "localhost"
        for a bare local run, or is set to "db" inside Docker Compose (its
        internal DNS resolving the service name "db" to the database
        container). This path is untouched so local Docker Compose keeps
        working exactly as it did before Neon existed.
    """
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)

    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=5432, dbname="jobmarket", user="postgres",
        password=os.environ["DB_PASSWORD"],
    )
