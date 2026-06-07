import os

from dotenv import load_dotenv


load_dotenv()

PLATFORM_API_BASE_URL_ENV = "PLATFORM_API_BASE_URL"
PLATFORM_API_BASE_URL = os.environ.get(PLATFORM_API_BASE_URL_ENV, "").rstrip("/")
PLATFORM_AUTH_TOKEN_ENV = "PLATFORM_AUTH_TOKEN"


def get_platform_auth_token(explicit_token: str | None = None) -> str | None:
    return explicit_token or os.environ.get(PLATFORM_AUTH_TOKEN_ENV)


def build_platform_api_url(path: str) -> str:
    if not PLATFORM_API_BASE_URL:
        raise RuntimeError(f"{PLATFORM_API_BASE_URL_ENV} is required")
    return f"{PLATFORM_API_BASE_URL}/{path.lstrip('/')}"
