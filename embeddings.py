import argparse
import runpy
from pathlib import Path

import numpy as np

from sentence_transformers import SentenceTransformer
from chunker import load_and_chunk_jsonl
from db import init_db, replace_document_chunks

DEFAULT_INPUT_PATH = Path(__file__).resolve().parent / "crypto-school-data.jsonl"
DATA_EXTRACTOR_PATH = Path(__file__).resolve().parent / "data-extractor.py"


def parse_args():
    parser = argparse.ArgumentParser(description="Embed crypto school JSONL data into Postgres.")
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT_PATH),
        help="Path to crypto-school-data.jsonl.",
    )
    parser.add_argument(
        "--no-generate",
        action="store_true",
        help="fail if the input JSONL is missing instead of generating it with data-extractor.py.",
    )
    return parser.parse_args()


def generate_jsonl(output_path: Path) -> None:
    print(f"Input JSONL not found. Generating {output_path} with data-extractor.py...")
    module_globals = runpy.run_path(str(DATA_EXTRACTOR_PATH))
    ingest = module_globals["ingest_crypto_school_posts"]
    ingest(output_path=output_path)


def embedd_data(input_path: str, *, generate_if_missing: bool = True):
    path = Path(input_path).expanduser().resolve()
    if not path.exists():
        if generate_if_missing:
            generate_jsonl(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Input JSONL file not found: {path}\n"
            "Generate it with `python data-extractor.py` or pass the file path with "
            "`python embeddings.py --input /path/to/crypto-school-data.jsonl`."
        )

    docs = load_and_chunk_jsonl(str(path))
    if not docs:
        raise RuntimeError(f"No chunks were loaded from {path}")

    model = SentenceTransformer("BAAI/bge-base-en-v1.5")

    texts = [doc.page_content for doc in docs]
    metadatas = [doc.metadata for doc in docs]

    chunk_embeddings = model.encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    embeddings_np = np.asarray(chunk_embeddings, dtype="float32")

    init_db()
    replace_document_chunks(
        [
            {
                "text": text,
                "metadata": metadata,
                "embedding": embedding.tolist(),
            }
            for text, metadata, embedding in zip(texts, metadatas, embeddings_np)
        ]
    )
    print(f"Inserted {len(texts)} chunks into document_chunks.")


if __name__ == "__main__":
    args = parse_args()
    embedd_data(args.input, generate_if_missing=not args.no_generate)
