CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_chunks (
    id bigserial PRIMARY KEY,
    text text NOT NULL,
    metadata jsonb NOT NULL,
    embedding vector(768) NOT NULL
);
