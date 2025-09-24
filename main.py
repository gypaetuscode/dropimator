"""dropimator importer script entry point."""
from __future__ import annotations

import logging

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dropimator import (
    Base,
    configure_logging,
    configure_openai,
    enrich_products,
    find_csv_file,
    get_database_url,
    iter_csv_rows,
    process_csv_row,
)

LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Entry point for the dropimator importer script."""

    load_dotenv()

    configure_logging()
    configure_openai()

    database_url = get_database_url()
    engine = create_engine(database_url)
    # Validate that the database connection is reachable early.
    with engine.connect():
        LOGGER.info("Successfully connected to PostgreSQL at %s", database_url)

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    csv_path = find_csv_file()

    with SessionLocal() as session:
        for row in iter_csv_rows(csv_path):
            process_csv_row(session, row)
        enrich_products(session)


if __name__ == "__main__":
    main()
