"""Helpers for interacting with the OpenAI ChatCompletion API."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

import openai

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

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from .models import Product


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


def build_category_prompt(product: "Product") -> str:
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


def build_marketing_prompt(product: "Product") -> str:
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
