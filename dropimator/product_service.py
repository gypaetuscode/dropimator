"""Domain services for importing and enriching products."""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .models import Product
from .openai_client import (
    build_category_prompt,
    build_marketing_prompt,
    extract_message_content,
    parse_json_content,
    request_chat_completion,
)

LOGGER = logging.getLogger(__name__)


def normalise_string(value: Optional[str]) -> Optional[str]:
    """Trim whitespace and normalise empty strings to ``None``."""

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
    """Return the first non-empty value from ``data`` for the given keys."""

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
