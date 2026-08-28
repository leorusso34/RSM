#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Definizioni dei tipi per Russo Stock Manager."""

from typing import TypedDict, Optional
from decimal import Decimal

class ProductRecord(TypedDict, total=False):
    id: int
    name: str
    size: str
    quantity: int
    purchased_price: Decimal
    purchased_price_cents: int
    purchased_place: str
    selling_place: str
    selling_price: Optional[Decimal]
    selling_price_cents: Optional[int]
    sold_price: Optional[Decimal]
    sold_price_cents: Optional[int]
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
