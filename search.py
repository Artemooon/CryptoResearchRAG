import os

from dotenv import load_dotenv
import requests

from rag_engine import RAGEngine

load_dotenv()

OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-5.4"


def generate_answer(*, context: str, query: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required to generate RAG answers")

    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a crypto education assistant. "
                "Use only the provided local knowledge-base context. "
                "If the context has no relevant information, say exactly: "
                "I don't have enough information in the local knowledge base to answer that. "
                "If the context is relevant but incomplete, answer what the context supports and clearly say what cannot be determined. "
                "Write a helpful, accurate answer in 2 to 4 sentences. "
                "Mention concrete wallet, protocol, or source article names from the context when useful. "
                "Do not give financial advice."
            ),
        },
        {
            "role": "user",
            "content": (
                "Context:\n"
                f"{context}\n\n"
                "Question:\n"
                f"{query}"
            ),
        },
    ]

    response = requests.post(
        OPENAI_CHAT_COMPLETIONS_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
        },
        timeout=90,
    )
    response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"]


def answer_question(query: str, top_k: int = 3) -> str:
    rag_engine = RAGEngine()

    docs = rag_engine.search(query, top_k=top_k, candidate_k=20)

    if not docs:
        return "I don't have enough information in the local knowledge base to answer that."

    context = "\n\n---\n\n".join(
        f"Title: {doc['metadata'].get('title')}\n"
        f"Content:\n{doc['text']}"
        for doc in docs
    )

    # 3. GENERATE
    answer = generate_answer(context=context, query=query)

    return answer

query = input("Type a query related to crypto: ")
top_k = 2

answer = answer_question(query, top_k)

print(f"\nAnswer: {answer}")
