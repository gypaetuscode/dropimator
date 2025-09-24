"""Database models for the dropimator importer."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Column, DateTime, Double, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base

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
