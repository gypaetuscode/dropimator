"""dropimator importer script.

This module reads product data from a CSV file, persists it to PostgreSQL
and enriches products with OpenAI generated metadata.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import openai
from dotenv import load_dotenv
from sqlalchemy import Column, DateTime, Double, Integer, String, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()

LOGGER = logging.getLogger(__name__)
SYSTEM_MESSAGE = {
    "role": "system",
    "content": "You are a fitness nutrition marketing specialist.",
}
MODEL_NAME = "gpt-3.5-turbo"
CATEGORY_CHOICES = (
    "Proteine",
    "Aminoacizi",
    "Vitamine si Minerale",
    "Batoane si Gustari Fitness",
    "Suplimente pentru slabit",
    "Performanta/Stimulatoare",
    "Pre-Workout",
    "Creatina",
    "Imbracaminte si acesorii pentru sala",
    "Masa musculara",
    "Suplimente",
    "Probiotice",
)

Base = declarative_base()


class Product(Base):
    """SQLAlchemy model mirroring the `products` table."""

    __tablename__ = "products"

    sku = Column(String(), primary_key=True)
    manufacturer_name = Column(String())
    name = Column(String())
    qty = Column(String())
    flavour = Column(String())
    weight = Column(String())
    img_url = Column(String())
    retail_price = Column(Double())
    description = Column(String())
    meta_title = Column(String())
    meta_description = Column(String())
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow)
    openai_response = Column(JSONB)
    total_tokens = Column(Integer)
    category = Column(String())


def configure_logging() -> None:
    """Initialise logging for the script."""

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

    missing = [name for name, value in (
        ("PG_USERNAME", username),
        ("PG_PASSWORD", password),
        ("PG_DATABASE", database),
    ) if not value]
    if missing:
        raise RuntimeError(
            "Missing required PostgreSQL environment variables: " + ", ".join(missing)
        )

    return URL.create(
        drivername="postgresql",
        host=host,
        username=username,
        password=password,
        database=database,
    )


def find_csv_file() -> Path:
    """Locate the CSV file that should be imported."""

    explicit_path = os.getenv("PRODUCT_CSV_PATH")
    if explicit_path:
        csv_path = Path(explicit_path)
        if not csv_path.is_file():
            raise FileNotFoundError(
                f"CSV file configured in PRODUCT_CSV_PATH does not exist: {csv_path}"
            )
        return csv_path

    csv_files = sorted(
        Path.cwd().glob("*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not csv_files:
        raise FileNotFoundError(
            "No CSV files found in the current directory. Set PRODUCT_CSV_PATH to "
            "the desired file or place a CSV next to this script."
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


def clean_json_block(content: str) -> str:
    """Remove Markdown fences that may wrap JSON payloads."""

    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = [line for line in stripped.splitlines() if not line.startswith("```")]
        return "\n".join(lines).strip()
    return stripped


def parse_json_content(content: str) -> Optional[Dict[str, Any]]:
    """Parse JSON content returned by OpenAI."""

    try:
        return json.loads(clean_json_block(content))
    except json.JSONDecodeError:
        LOGGER.error("OpenAI response is not valid JSON: %s", content)
        return None


def extract_message_content(response: Dict[str, Any]) -> Optional[str]:
    """Extract the first message content from a chat completion response."""

    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        LOGGER.error("Unexpected response format from OpenAI: %s", response)
        return None


def serialise_openai_response(response: Any) -> Dict[str, Any]:
    """Convert OpenAI SDK responses to plain dictionaries."""

    if hasattr(response, "to_dict_recursive"):
        return response.to_dict_recursive()
    if isinstance(response, dict):
        return response
    return json.loads(json.dumps(response, default=str))


def request_chat_completion(
    prompt: str,
    *,
    temperature: float,
    frequency_penalty: float,
    max_tokens: int,
    request_timeout: int,
) -> Optional[Dict[str, Any]]:
    """Invoke the OpenAI ChatCompletion API with shared defaults."""

    try:
        LOGGER.debug("Sending prompt to OpenAI: %s", prompt)
        response = openai.ChatCompletion.create(
            model=MODEL_NAME,
            messages=[SYSTEM_MESSAGE, {"role": "user", "content": prompt}],
            temperature=temperature,
            frequency_penalty=frequency_penalty,
            max_tokens=max_tokens,
            request_timeout=request_timeout,
        )
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.error("Error communicating with OpenAI: %s", exc)
        return None

    return serialise_openai_response(response)


def build_category_prompt(product: Product) -> str:
    """Create the prompt used to classify products into categories."""

    manufacturer = product.manufacturer_name or "Unknown"
    name = product.name or product.sku
    choices = ", ".join(CATEGORY_CHOICES)
    return (
        "Strictly generate product category as JSON respecting the given JSON "
        f"structure {{\"category\": <one of the value of [{choices}]>}}\n"
        "Product input:\n"
        f"Manufacturer: {manufacturer}\n"
        f"Name: {name}"
    )


def build_marketing_prompt(product: Product) -> str:
    """Create the prompt used to generate marketing copy for a product."""

    manufacturer = product.manufacturer_name or "Unknown"
    flavour = product.flavour or ""
    name = product.name or product.sku
    return (
        "Generate product details using Romanian language and respecting the "
        "given JSON structure {\"html_description\":<formatted string min 600 "
        "tokens max 900 tokens>, \"meta_title\": <string no more than 25 tokens "
        "length>, \"meta_description\": <string no more than 55 tokens length>, "
        "\"weight\": \"<string>\"}.\n"
        "Product details input:\n"
        f"\"manufacturer\": \"{manufacturer}\",\n"
        f"\"name\": \"{name}\",\n"
        f"\"flavour\": \"{flavour}\"\n"
        "Output:"
    )


def normalise_string(value: Optional[str]) -> Optional[str]:
    """Trim whitespace and normalise empty strings to None."""

    if value is None:
        return None
    result = value.strip()
    return result or None


def parse_price(value: Optional[str]) -> Optional[float]:
    """Parse a string price into a float, handling European decimal separators."""

    if value is None:
        return None
    candidate = value.replace(",", ".").strip()
    if not candidate:
        return None
    try:
        return float(candidate)
    except ValueError:
        LOGGER.warning("Unable to parse retail price: %s", value)
        return None


def generate_product_category(product: Product) -> Optional[str]:
    """Return a category for the product, calling OpenAI if needed."""

    if product.category:
        LOGGER.debug(
            "Product %s already has category %s", product.sku, product.category
        )
        return product.category

    prompt = build_category_prompt(product)
    response = request_chat_completion(
        prompt,
        temperature=0.2,
        frequency_penalty=0.5,
        max_tokens=200,
        request_timeout=5,
    )
    if not response:
        return None

    content = extract_message_content(response)
    if not content:
        return None

    payload = parse_json_content(content)
    if not payload:
        return None

    product.openai_response = response
    product.total_tokens = response.get("usage", {}).get("total_tokens")
    return payload.get("category")


def get_first_present(data: Dict[str, Any], *keys: str) -> Optional[str]:
    """Return the first non-empty value from `data` for the given keys."""

    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def enrich_product_marketing(product: Product) -> bool:
    """Populate marketing fields using OpenAI generated content."""

    if product.description and product.meta_title and product.meta_description:
        return False

    prompt = build_marketing_prompt(product)
    response = request_chat_completion(
        prompt,
        temperature=0.7,
        frequency_penalty=0.5,
        max_tokens=750,
        request_timeout=15,
    )
    if not response:
        return False

    content = extract_message_content(response)
    if not content:
        return False

    payload = parse_json_content(content)
    if not payload:
        return False

    description = get_first_present(payload, "html_description", "descriere")
    meta_title = get_first_present(payload, "meta_title", "meta_titlu")
    meta_description = get_first_present(
        payload, "meta_description", "meta_descriere"
    )
    weight = payload.get("weight")

    updated = False
    if description:
        product.description = description
        updated = True
    if meta_title:
        product.meta_title = meta_title
        updated = True
    if meta_description:
        product.meta_description = meta_description
        updated = True
    if isinstance(weight, str) and weight.strip():
        product.weight = weight.strip()
        updated = True

    if updated:
        product.updated_at = dt.datetime.utcnow()
        product.openai_response = response
        product.total_tokens = response.get("usage", {}).get("total_tokens")

    return updated


def process_csv_row(session: Session, row: Dict[str, str]) -> None:
    """Insert or update a product based on the CSV row."""

    sku = normalise_string(row.get("sku"))
    if not sku:
        LOGGER.warning("Encountered a CSV row without SKU. Skipping row: %s", row)
        return

    product = session.get(Product, sku)
    if not product:
        product = Product(sku=sku)
        session.add(product)
        LOGGER.info("Creating new product with SKU %s", sku)
    else:
        LOGGER.info("Updating existing product with SKU %s", sku)

    manufacturer = normalise_string(row.get("manufacturer_name"))
    name = normalise_string(row.get("name"))
    qty = normalise_string(row.get("qty"))
    flavour = normalise_string(row.get("flavour"))
    weight = normalise_string(row.get("weight"))
    img_url = normalise_string(row.get("img_url"))
    retail_price = parse_price(row.get("retail_price"))

    if manufacturer is not None:
        product.manufacturer_name = manufacturer
    if name is not None:
        product.name = name
    if qty is not None:
        product.qty = qty
    if flavour is not None:
        product.flavour = flavour
    if weight is not None:
        product.weight = weight
    if img_url is not None:
        product.img_url = img_url
    if retail_price is not None:
        product.retail_price = retail_price

    product.updated_at = dt.datetime.utcnow()

    category = generate_product_category(product)
    if category:
        product.category = category

    session.commit()


def enrich_products(session: Session) -> None:
    """Fill missing marketing information for products."""

    products = session.query(Product).all()
    LOGGER.info("Enriching %s products with marketing content", len(products))
    for product in products:
        if enrich_product_marketing(product):
            session.commit()


def main() -> None:
    """Entry point for the dropimator importer script."""

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
