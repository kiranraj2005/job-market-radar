from google import genai
from google.genai import types
from pipeline.db import get_connection

EMBEDDING_MODEL = "gemini-embedding-001"


def embed_query(client, text):
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    return result.embeddings[0].values


def vector_literal(values):
    return "[" + ",".join(str(v) for v in values) + "]"


def find_matching_jobs(cv_text, k=5):
    client = genai.Client()
    query_vector = embed_query(client, cv_text)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT title, company, posting_url, posted_at, description,
               embedding <=> %s::vector AS distance
        FROM jobs
        ORDER BY distance
        LIMIT %s
        """,
        (vector_literal(query_vector), k),
    )
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "title": r[0], "company": r[1], "posting_url": r[2],
            "posted_at": r[3], "description": r[4], "distance": r[5],
        }
        for r in rows
    ]


if __name__ == "__main__":
    sample_cv = """
    MSc Computer Science graduate. Skilled in Python, SQL, Docker, and building
    ETL pipelines. Experience with PostgreSQL and CI/CD using GitHub Actions.
    Looking for Data Engineer or Data Analyst roles in Germany.
    """
    matches = find_matching_jobs(sample_cv, k=5)
    for title, company, url, posted_at, distance in matches:
        print(f"{distance:.4f}  {title} @ {company}  ({posted_at})")
        print(f"        {url}")