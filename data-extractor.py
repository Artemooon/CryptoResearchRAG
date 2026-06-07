import json
import time
import random
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from platform_config import build_platform_api_url

REQUEST_DELAY_SECONDS = 0.2
CRYPTO_SCHOOL_PAGE_SIZE = 20
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent / "crypto-school-data.jsonl"


def build_session() -> Session:
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        status=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )

    adapter = HTTPAdapter(max_retries=retry)

    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


def rate_limited_get(session: Session, url: str, **kwargs) -> requests.Response:
    time.sleep(REQUEST_DELAY_SECONDS + random.uniform(0, 0.3))

    response = session.get(url, timeout=30, **kwargs)
    response.raise_for_status()
    return response


def get_post_slugs(session: Session) -> list[str]:
    url = build_platform_api_url(
        f"/posts/?page=1&tags=&search=&page_size={CRYPTO_SCHOOL_PAGE_SIZE}&ordering=-created&language_code=en&post_type=4"
    )

    response = rate_limited_get(session, url)
    data = response.json()

    slugs = [item["slug"] for item in data["results"]]
    return slugs


def get_post_detail(session: Session, slug: str) -> dict:
    url = build_platform_api_url(f"/posts/{slug}")

    response = rate_limited_get(session, url)
    return response.json()


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    for img in soup.find_all("img"):
        alt = img.get("alt")
        if alt:
            img.replace_with(f"\n[Image: {alt}]\n")
        else:
            img.decompose()

    for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
        tag.decompose()

    lines = [
        line.strip()
        for line in soup.get_text(separator="\n").splitlines()
        if line.strip()
    ]

    return "\n".join(lines)


def ingest_crypto_school_posts(output_path: str | Path = DEFAULT_OUTPUT_PATH):
    session = build_session()
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("", encoding="utf-8")

    slugs = get_post_slugs(session)

    for slug in slugs:
        detail = get_post_detail(session, slug)

        html = detail.get("content")
        if html:
            clean_text = html_to_text(html)

        print(f"html: {html}")
        print(f"clean_text: {clean_text}")

        article = {
            "slug": slug,
            "title": detail.get("title"),
            "created": detail.get("created"),
            "updated": detail.get("updated"),
            "raw_html": html,
            "clean_text": clean_text,
        }

        # Save this to DB, file, or pass to chunking pipeline
        print("Parsed article", article)

        with output.open("a", encoding="utf-8") as file:
            file.write(json.dumps(article, ensure_ascii=False) + "\n")



if __name__ == "__main__":
    ingest_crypto_school_posts()
