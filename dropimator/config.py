"""Configuration helpers for the dropimator importer."""
from __future__ import annotations

import logging
import os

import openai
from sqlalchemy.engine import URL

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    """Initialise logging for the importer."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def configure_openai() -> None:
    """Ensure the OpenAI client is ready to use."""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

    openai.api_key = api_key


def get_database_url() -> URL:
    """Build a SQLAlchemy URL from environment configuration."""

    username = os.getenv("PG_USERNAME")
    password = os.getenv("PG_PASSWORD")
    database = os.getenv("PG_DATABASE")
    host = os.getenv("PG_HOST", "localhost")

    missing = [
        name
        for name, value in (
            ("PG_USERNAME", username),
            ("PG_PASSWORD", password),
            ("PG_DATABASE", database),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing required PostgreSQL environment variables: "
            + ", ".join(missing)
        )

    return URL.create(
        drivername="postgresql",
        host=host,
        username=username,
        password=password,
        database=database,
    )
