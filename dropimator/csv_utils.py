"""Utilities for discovering and reading CSV product feeds."""
from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from typing import Dict, Iterable

LOGGER = logging.getLogger(__name__)


def find_csv_file() -> Path:
    """Locate the CSV file that should be imported."""

    explicit_path = os.getenv("PRODUCT_CSV_PATH")
    if explicit_path:
        csv_path = Path(explicit_path)
        if not csv_path.is_file():
            raise FileNotFoundError(
                "CSV file configured in PRODUCT_CSV_PATH does not exist: "
                f"{csv_path}"
            )
        return csv_path

    csv_files = sorted(
        Path.cwd().glob("*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not csv_files:
        raise FileNotFoundError(
            "No CSV files found in the current directory. Set PRODUCT_CSV_PATH "
            "to the desired file or place a CSV next to this script."
        )

    if len(csv_files) > 1:
        LOGGER.info(
            "Multiple CSV files found. Using the most recent one: %s",
            csv_files[0].name,
        )

    return csv_files[0]


def iter_csv_rows(csv_path: Path) -> Iterable[Dict[str, str]]:
    """Yield rows from the input CSV as dictionaries."""

    LOGGER.info("Reading products from %s", csv_path)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row_number, row in enumerate(reader, start=1):
            if not row:
                LOGGER.debug("Skipping empty row %s", row_number)
                continue
            yield row
