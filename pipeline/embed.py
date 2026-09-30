from google import genai
from google.genai import types
from pipeline.db import get_connection

EMBEDDING_MODEL = "gemini-embedding-001"


def embed_text(client, text):
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
    )
    return result.embeddings[0].values


def vector_literal(values):
    """Format a list of floats as a Postgres vector literal, e.g. '[0.1,0.2,...]',
    so it can be cast with ::vector in SQL. No extra pgvector Python package
    needed — Postgres parses this text form natively."""
    return "[" + ",".join(str(v) for v in values) + "]"


def embed_missing_jobs():
    client = genai.Client()
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT job_id, description FROM jobs WHERE embedding IS NULL")
    rows = cur.fetchall()

    embedded = 0
    skipped = 0
    for job_id, description in rows:
        if not description:
            print(f"Skipped {job_id}: no description text")
            skipped += 1
            continue
        try:
            values = embed_text(client, description)
            cur.execute(
                "UPDATE jobs SET embedding = %s::vector WHERE job_id = %s",
                (vector_literal(values), job_id),
            )
            conn.commit()
            embedded += 1
        except Exception as e:
            conn.rollback()
            print(f"Skipped {job_id}: {e}")
            skipped += 1

    conn.close()
    return embedded, skipped


if __name__ == "__main__":
    embedded, skipped = embed_missing_jobs()
    print(f"Embedded {embedded} jobs, skipped {skipped}.")