"""Definizioni dei tipi per RSM."""

from decimal import Decimal
from typing import TypedDict


class ProductRecord(TypedDict, total=False):
    id: int
    name: str
    size: str
    quantity: int
    purchased_price: Decimal
    purchased_price_cents: int
    purchased_place: str
    selling_place: str
    selling_price: Decimal | None
    selling_price_cents: int | None
    sold_price: Decimal | None
    sold_price_cents: int | None
    fees: Decimal
    fees_cents: int
    sold_date: str
    status: str
    release_date: str
    notes: str
    bundle_id: str
    is_completed: int
    created_at: str
    updated_at: str
