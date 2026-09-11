import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """
    Connect to the Dockerized Postgres from Step 1. Host/port/dbname/user
    match docker-compose.yml exactly - only the password is a secret, so
    only the password comes from .env (the same gitignored file Docker
    Compose itself already reads for ${DB_PASSWORD}).
    """
    return psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="jobmarket",
        user="postgres",
        password=os.environ["DB_PASSWORD"],
    )