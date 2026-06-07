import json
from langchain_text_splitters import RecursiveCharacterTextSplitter


splitter = RecursiveCharacterTextSplitter(
    chunk_size=700,
    chunk_overlap=150,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def load_and_chunk_jsonl(path: str):
    chunks = []

    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            article = json.loads(line)

            text = article["clean_text"]

            docs = splitter.create_documents(
                texts=[text],
                metadatas=[{
                    "slug": article.get("slug"),
                    "title": article.get("title"),
                    "created": article.get("created"),
                    "updated": article.get("updated"),
                }],
            )
            chunks.extend(docs)

    return chunks