import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()


def _build_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME")

    if not all([user, password, host, name]):
        raise RuntimeError(
            "Database not configured. Set DATABASE_URL or DB_USER/DB_PASSWORD/DB_HOST/DB_NAME."
        )

    from urllib.parse import quote_plus
    return f"postgresql+psycopg://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{name}"


engine = create_engine(_build_database_url())
SessionLocal = sessionmaker(bind=engine)
