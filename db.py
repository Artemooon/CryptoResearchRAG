import json
import os

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "RAG_DATABASE_URL",
    "postgresql://localhost:5432/cryptoresearchrag",
)
EMBEDDING_DIMENSION = 768


def get_connection(*, register_pgvector: bool = True):
    conn = psycopg.connect(DATABASE_URL)
    if register_pgvector:
        register_vector(conn)
    return conn


def init_db():
    with get_connection(register_pgvector=False) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id bigserial PRIMARY KEY,
                    text text NOT NULL,
                    metadata jsonb NOT NULL,
                    embedding vector({EMBEDDING_DIMENSION}) NOT NULL
                )
                """
            )
            conn.commit()


def replace_document_chunks(rows):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE document_chunks RESTART IDENTITY")
            cur.executemany(
                """
                INSERT INTO document_chunks (text, metadata, embedding)
                VALUES (%s, %s::jsonb, %s)
                """,
                [
                    (
                        row["text"],
                        json.dumps(row["metadata"]),
                        Vector(row["embedding"]),
                    )
                    for row in rows
                ],
            )
            conn.commit()


def search_document_chunks(query_embedding, limit):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    text,
                    metadata,
                    1 - (embedding <=> %s) AS vector_score
                FROM document_chunks
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (Vector(query_embedding), Vector(query_embedding), limit),
            )
            return [
                {
                    "text": text,
                    "metadata": metadata,
                    "vector_score": float(vector_score),
                }
                for text, metadata, vector_score in cur.fetchall()
            ]
