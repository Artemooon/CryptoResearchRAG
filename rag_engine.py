import numpy as np
from sentence_transformers import CrossEncoder, SentenceTransformer
from db import init_db, search_document_chunks


MODEL_NAME = "BAAI/bge-base-en-v1.5"
RERANKER_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class RAGEngine:
    def __init__(self):
        print("Loading embedding model...")
        self.model = SentenceTransformer(MODEL_NAME)

        print("Loading reranker...")
        self.reranker = CrossEncoder(RERANKER_NAME)
        init_db()

    def search(self, query: str, top_k: int = 5, candidate_k: int = 20):
        query_for_embedding = (
            f"Represent this sentence for searching relevant passages: {query}"
        )

        query_embedding = self.model.encode(
            [query_for_embedding],
            normalize_embeddings=True,
        )

        query_embedding = np.asarray(query_embedding[0], dtype="float32")
        candidates = search_document_chunks(query_embedding.tolist(), candidate_k)

        if not candidates:
            return []

        pairs = [(query, doc["text"]) for doc in candidates]
        rerank_scores = self.reranker.predict(pairs)

        for doc, rerank_score in zip(candidates, rerank_scores):
            doc["rerank_score"] = float(rerank_score)

        reranked_docs = sorted(
            candidates,
            key=lambda doc: doc["rerank_score"],
            reverse=True,
        )[:top_k]

        print("--- RERANKED DOCS ---")
        for i, doc in enumerate(reranked_docs, start=1):
            title = doc["metadata"].get("title")
            print(
                f"{i}. title={title!r} "
                f"vector_score={doc['vector_score']:.4f} "
                f"rerank_score={doc['rerank_score']:.4f}"
            )
        print("--- END RERANKED DOCS ---")

        return reranked_docs
