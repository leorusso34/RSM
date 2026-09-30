#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gestione database SQLite e migrazioni per RSM."""

import json
import os
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import DB_PATH, CONFIG_JSON_PATH, STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK, DEFAULT_SELLING_PLACES
from .types import ProductRecord
from .utils import calculate_profit, cents_to_money, money_to_cents


class InventoryDatabase:
    """Classe per l'interazione con il database SQLite dei prodotti."""

    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self._create_schema_and_migrate()

    def _create_schema_and_migrate(self) -> None:
        """Crea la tabella iniziale se non esiste ed effettua le migrazioni per il nuovo schema."""
        cursor = self.connection.cursor()
        cursor.execute("PRAGMA table_info(products)")
        existing_columns = {row["name"] for row in cursor.fetchall()}
        if existing_columns and "purchased_price_cents" not in existing_columns:
            cursor.execute("ALTER TABLE products RENAME TO products_legacy")
            existing_columns = set()

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE,
                size TEXT NOT NULL DEFAULT '',
                quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
                purchased_price_cents INTEGER NOT NULL CHECK (purchased_price_cents >= 0),
                purchased_place TEXT NOT NULL DEFAULT '',
                selling_place TEXT NOT NULL DEFAULT '',
                selling_price_cents INTEGER CHECK (selling_price_cents IS NULL OR selling_price_cents >= 0),
                sold_price_cents INTEGER CHECK (sold_price_cents IS NULL OR sold_price_cents >= 0),
                fees_cents INTEGER NOT NULL DEFAULT 0 CHECK (fees_cents >= 0),
                sold_date TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '{STATUS_STOCK}' CHECK (status IN ('{STATUS_STOCK}', '{STATUS_PREORDER}', '{STATUS_SOLD}')),
                release_date TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                bundle_id TEXT NOT NULL DEFAULT '',
                is_completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

        if existing_columns and "bundle_id" not in existing_columns:
            cursor.execute("ALTER TABLE products ADD COLUMN bundle_id TEXT NOT NULL DEFAULT ''")
            
        if existing_columns and "is_completed" not in existing_columns:
            cursor.execute("ALTER TABLE products ADD COLUMN is_completed INTEGER NOT NULL DEFAULT 0")

        # Fix constraint if older version of STATUS_PREORDER is in schema
        if existing_columns:
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='products'")
            schema = cursor.fetchone()[0]
            if "'Pre-order'" in schema and STATUS_PREORDER == "Pre-ordine":
                cursor.execute("UPDATE products SET status = 'Pre-ordine' WHERE status = 'Pre-order'")
                cursor.execute("ALTER TABLE products RENAME TO products_temp_mig")
                cursor.execute(
                    f"""
                    CREATE TABLE products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL COLLATE NOCASE,
                        size TEXT NOT NULL DEFAULT '',
                        quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
                        purchased_price_cents INTEGER NOT NULL CHECK (purchased_price_cents >= 0),
                        purchased_place TEXT NOT NULL DEFAULT '',
                        selling_place TEXT NOT NULL DEFAULT '',
                        selling_price_cents INTEGER CHECK (selling_price_cents IS NULL OR selling_price_cents >= 0),
                        sold_price_cents INTEGER CHECK (sold_price_cents IS NULL OR sold_price_cents >= 0),
                        fees_cents INTEGER NOT NULL DEFAULT 0 CHECK (fees_cents >= 0),
                        sold_date TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT '{STATUS_STOCK}' CHECK (status IN ('{STATUS_STOCK}', '{STATUS_PREORDER}', '{STATUS_SOLD}')),
                        release_date TEXT NOT NULL DEFAULT '',
                        notes TEXT NOT NULL DEFAULT '',
                        bundle_id TEXT NOT NULL DEFAULT '',
                        is_completed INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
                cursor.execute(
                    """
                    INSERT INTO products (
                        id, name, size, quantity, purchased_price_cents, purchased_place,
                        selling_place, selling_price_cents, sold_price_cents, fees_cents,
                        sold_date, status, release_date, notes, bundle_id, is_completed,
                        created_at, updated_at
                    )
                    SELECT 
                        id, name, size, quantity, purchased_price_cents, purchased_place,
                        selling_place, selling_price_cents, sold_price_cents, fees_cents,
                        sold_date, status, release_date, notes, bundle_id, is_completed,
                        created_at, updated_at
                    FROM products_temp_mig
                    """
                )
                cursor.execute("DROP TABLE products_temp_mig")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_places (
                name TEXT PRIMARY KEY,
                is_deleted INTEGER NOT NULL DEFAULT 0
            );
            """
        )

        if self.connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products_legacy'").fetchone():
            legacy_rows = self.connection.execute("SELECT * FROM products_legacy").fetchall()
            for row in legacy_rows:
                data = dict(row)
                self.connection.execute(
                    """INSERT INTO products
                    (id, name, size, quantity, purchased_price_cents, purchased_place,
                     selling_place, selling_price_cents, sold_price_cents, fees_cents,
                     sold_date, status, release_date, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        data["id"], data.get("name", ""), data.get("size", ""), max(1, int(data.get("quantity", 1) or 1)),
                        money_to_cents(Decimal(str(data.get("purchased_price", 0) or 0))),
                        data.get("purchased_place", ""), data.get("selling_place", ""),
                        money_to_cents(Decimal(str(data["selling_price"]))) if data.get("selling_price") is not None else None,
                        money_to_cents(Decimal(str(data["sold_price"]))) if data.get("sold_price") is not None else None,
                        money_to_cents(Decimal(str(data.get("fees", 0) or 0))), data.get("sold_date", ""),
                        data.get("status", STATUS_STOCK) if data.get("status") in {STATUS_STOCK, STATUS_PREORDER, STATUS_SOLD} else STATUS_STOCK,
                        data.get("release_date", ""), data.get("notes", ""),
                        data.get("created_at"), data.get("updated_at"),
                    ),
                )
            cursor.execute("DROP TABLE products_legacy")

        # Indici per velocizzare le query
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_status ON products(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_purchased_place ON products(purchased_place)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_selling_place ON products(selling_place)")

        self.connection.commit()

    @staticmethod
    def _row_to_product(row: sqlite3.Row) -> Dict[str, Any]:
        product = dict(row)
        product["purchased_price"] = cents_to_money(product.pop("purchased_price_cents"))
        product["selling_price"] = cents_to_money(product.pop("selling_price_cents"))
        product["sold_price"] = cents_to_money(product.pop("sold_price_cents"))
        product["fees"] = cents_to_money(product.pop("fees_cents")) or Decimal("0.00")
        return product

    def list_products(
        self,
        status: Optional[str] = None,
        search: str = "",
        purchased_place: str = "",
        selling_place: str = "",
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Restituisce i prodotti filtrati per stato e parametri di ricerca."""
        query = "SELECT * FROM products WHERE 1=1"
        params: List[Any] = []

        if status:
            from .config import STATUS_COMPLETED, STATUS_SOLD
            if status == STATUS_COMPLETED:
                query += " AND status = ? AND is_completed = 1"
                params.append(STATUS_SOLD)
            elif status == STATUS_SOLD:
                query += " AND status = ? AND is_completed = 0"
                params.append(STATUS_SOLD)
            else:
                query += " AND status = ?"
                params.append(status)

        search_clean = search.strip()
        if search_clean:
            needle = f"%{search_clean}%"
            price_clean = search_clean.replace("€", "").replace("$", "").replace("£", "").strip()
            price_needle = f"%{price_clean}%" if price_clean else needle

            query += """ AND (
                name LIKE ? OR size LIKE ? OR purchased_place LIKE ? OR
                selling_place LIKE ? OR release_date LIKE ? OR notes LIKE ? OR sold_date LIKE ? OR
                CAST(purchased_price_cents / 100 AS TEXT) LIKE ? OR
                printf('%.2f', purchased_price_cents / 100.0) LIKE ? OR
                replace(printf('%.2f', purchased_price_cents / 100.0), '.', ',') LIKE ? OR
                CAST(selling_price_cents / 100 AS TEXT) LIKE ? OR
                printf('%.2f', selling_price_cents / 100.0) LIKE ? OR
                replace(printf('%.2f', selling_price_cents / 100.0), '.', ',') LIKE ? OR
                CAST(sold_price_cents / 100 AS TEXT) LIKE ? OR
                printf('%.2f', sold_price_cents / 100.0) LIKE ? OR
                replace(printf('%.2f', sold_price_cents / 100.0), '.', ',') LIKE ? OR
                CAST(fees_cents / 100 AS TEXT) LIKE ? OR
                printf('%.2f', fees_cents / 100.0) LIKE ? OR
                replace(printf('%.2f', fees_cents / 100.0), '.', ',') LIKE ?
            )"""
            params.extend([needle] * 7 + [price_needle] * 12)

        if purchased_place.strip():
            query += " AND purchased_place = ?"
            params.append(purchased_place.strip())

        if selling_place.strip():
            query += " AND selling_place = ?"
            params.append(selling_place.strip())

        if min_price is not None:
            query += " AND purchased_price_cents >= ?"
            params.append(money_to_cents(min_price))

        if max_price is not None:
            query += " AND purchased_price_cents <= ?"
            params.append(money_to_cents(max_price))

        query += " ORDER BY name COLLATE NOCASE, id DESC"

        return [self._row_to_product(row) for row in self.connection.execute(query, params).fetchall()]

    def all_products(self) -> List[Dict[str, Any]]:
        """Restituisce tutti i prodotti nel formato pubblico dell'applicazione."""
        rows = self.connection.execute("SELECT * FROM products ORDER BY status, name").fetchall()
        return [self._row_to_product(row) for row in rows]

    def get(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Ottiene un singolo prodotto per ID."""
        row = self.connection.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        return self._row_to_product(row) if row else None

    def save(self, data: Dict[str, Any], product_id: Optional[int] = None) -> int:
        """Salva (inserisce o aggiorna) un prodotto nel database."""
        bundle_id = str(data.get("bundle_id", "") or "")
        is_completed = int(data.get("is_completed", 0) or 0)
        fields = (
            "name", "size", "quantity", "purchased_price_cents", "purchased_place",
            "selling_place", "selling_price_cents", "sold_price_cents", "fees_cents", "sold_date",
            "status", "release_date", "notes", "bundle_id", "is_completed"
        )
        status = data.get("status", STATUS_STOCK)
        if status not in {STATUS_STOCK, STATUS_PREORDER, STATUS_SOLD}:
            raise ValueError("Stato prodotto non valido.")
        sold_price = data.get("sold_price") if status == STATUS_SOLD else None
        fees = data.get("fees", Decimal("0")) if status == STATUS_SOLD else Decimal("0")
        sold_date = data.get("sold_date", "") if status == STATUS_SOLD else ""
        release_date = data.get("release_date", "") if status == STATUS_PREORDER else ""
        values = (
            data.get("name", ""), data.get("size", ""), data.get("quantity", 1),
            money_to_cents(data.get("purchased_price")), data.get("purchased_place", ""),
            data.get("selling_place", ""), money_to_cents(data.get("selling_price")),
            money_to_cents(sold_price), money_to_cents(fees), sold_date, status,
            release_date, data.get("notes", ""), bundle_id, is_completed,
        )

        with self.connection:
            if product_id is None:
                placeholders = ", ".join("?" for _ in fields)
                cursor = self.connection.execute(
                    f"INSERT INTO products ({', '.join(fields)}) VALUES ({placeholders})",
                    values,
                )
                return int(cursor.lastrowid)

            assignments = ", ".join(f"{field} = ?" for field in fields)
            self.connection.execute(
                f"UPDATE products SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values + (product_id,),
            )
            return product_id
        
    def _read_config_json(self) -> Dict[str, str]:
        """Legge il file config.json esterno se presente."""
        if not CONFIG_JSON_PATH.exists():
            return {}
        try:
            with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
        except Exception:
            pass
        return {}

    def _write_config_json(self, key: str, value: str) -> None:
        """Aggiorna il file config.json mantenendo sincronizzate le impostazioni."""
        try:
            current_data = {
                "gemini_api_key": "",
                "email_sync_address": "",
                "email_sync_app_password": ""
            }
            if CONFIG_JSON_PATH.exists():
                try:
                    with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, dict):
                            current_data.update(loaded)
                except Exception:
                    pass
            current_data[key] = value
            with open(CONFIG_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(current_data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get_setting(self, key: str, default_value: str = "") -> str:
        """
        Recupera un'impostazione dando precedenza assoluta al file config.json esterno.
        Se non presente o vuoto nel JSON, fa fallback sul database SQLite locale.
        """
        json_cfg = self._read_config_json()
        if key in json_cfg and json_cfg[key].strip() != "":
            return json_cfg[key].strip()

        cursor = self.connection.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default_value
        
    def set_setting(self, key: str, value: str) -> None:
        """Salva un'impostazione nel database SQLite e la sincronizza nel file config.json."""
        with self.connection:
            self.connection.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value)
            )
        self._write_config_json(key, value)

    def delete(self, product_id: int) -> None:
        """Elimina un singolo prodotto."""
        with self.connection:
            self.connection.execute("DELETE FROM products WHERE id = ?", (product_id,))

    def delete_many(self, product_ids: List[int]) -> int:
        """Elimina più prodotti in una sola transazione."""
        if not product_ids:
            return 0
        placeholders = ", ".join("?" for _ in product_ids)
        with self.connection:
            cursor = self.connection.execute(
                f"DELETE FROM products WHERE id IN ({placeholders})", tuple(product_ids)
            )
            return cursor.rowcount

    def update_status_many(
        self,
        product_ids: List[int],
        new_status: str,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> int:
        """Aggiorna lo stato di più prodotti in una sola transazione."""
        if not product_ids:
            return 0
        if new_status not in {STATUS_STOCK, STATUS_PREORDER, STATUS_SOLD}:
            raise ValueError("Stato prodotto non valido.")

        placeholders = ", ".join("?" for _ in product_ids)
        params: List[Any] = [new_status]
        extra_sql = ""

        if extra_data:
            if "sold_price" in extra_data:
                extra_sql += ", sold_price_cents = ?"
                params.append(money_to_cents(extra_data["sold_price"]))
            if "sold_date" in extra_data:
                extra_sql += ", sold_date = ?"
                params.append(extra_data["sold_date"])
            if "fees" in extra_data:
                extra_sql += ", fees_cents = ?"
                params.append(money_to_cents(extra_data["fees"]))
            if "bundle_id" in extra_data:
                extra_sql += ", bundle_id = ?"
                params.append(extra_data["bundle_id"])
            if "selling_place" in extra_data:
                extra_sql += ", selling_place = ?"
                params.append(str(extra_data["selling_place"]).strip())

        if new_status == STATUS_STOCK:
            extra_sql += ", release_date = '', sold_price_cents = NULL, sold_date = '', fees_cents = 0, bundle_id = '', is_completed = 0"
        elif new_status == STATUS_PREORDER:
            extra_sql += ", sold_price_cents = NULL, sold_date = '', fees_cents = 0, is_completed = 0"

        query = f"UPDATE products SET status = ?, updated_at = CURRENT_TIMESTAMP {extra_sql} WHERE id IN ({placeholders})"
        params.extend(product_ids)

        with self.connection:
            cursor = self.connection.execute(query, params)
            return cursor.rowcount

    def find_matching_stock_record(
        self,
        source: Dict[str, Any],
        exclude_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Cerca in magazzino un record già esistente compatibile con *source*.

        Un record è considerato compatibile se coincidono:
          - name (case-insensitive, trim)
          - size
          - purchased_price_cents
          - purchased_place
          - bundle_id = '' (non fa parte di una Vendita Multipla)

        Restituisce il record trovato (come dizionario pubblico) oppure None.
        """
        pp_cents = money_to_cents(source.get("purchased_price"))
        exclude_clause = f"AND id != {int(exclude_id)}" if exclude_id is not None else ""

        params: List[Any] = [
            str(source.get("name", "")).strip(),
            str(source.get("size", "")),
            pp_cents,
            str(source.get("purchased_place", "")),
            STATUS_STOCK,
        ]

        query = f"""
            SELECT * FROM products
            WHERE TRIM(name) = TRIM(?) COLLATE NOCASE
              AND size = ?
              AND purchased_price_cents = ?
              AND purchased_place = ?
              AND status = ?
              AND bundle_id = ''
              {exclude_clause}
            ORDER BY id ASC
            LIMIT 1
        """
        row = self.connection.execute(query, params).fetchone()
        return self._row_to_product(row) if row else None


    def merge_into_stock_record(self, target_id: int, add_qty: int) -> None:
        """Incrementa la quantità di un record in magazzino esistente."""
        with self.connection:
            self.connection.execute(
                "UPDATE products SET quantity = quantity + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (add_qty, target_id),
            )

    def get_distinct_places(self) -> Tuple[List[str], List[str]]:
        """Restituisce i luoghi di acquisto e vendita unici, combinando default, DB e custom_places."""
        purchased_db = [
            row[0] for row in self.connection.execute(
                "SELECT DISTINCT purchased_place FROM products WHERE purchased_place != ''"
            ).fetchall()
        ]
        
        selling_db = [
            row[0] for row in self.connection.execute(
                "SELECT DISTINCT selling_place FROM products WHERE selling_place != ''"
            ).fetchall()
        ]

        custom_added = [
            row[0] for row in self.connection.execute(
                "SELECT name FROM custom_places WHERE is_deleted = 0"
            ).fetchall()
        ]

        custom_deleted = {
            row[0] for row in self.connection.execute(
                "SELECT name FROM custom_places WHERE is_deleted = 1"
            ).fetchall()
        }
        
        purchased = sorted(list(set(purchased_db)))
        
        # Combine DB places, default places, and custom added places.
        # Then remove any that were explicitly deleted by the user.
        all_selling = set(selling_db + DEFAULT_SELLING_PLACES + custom_added)
        all_selling = {p for p in all_selling if p not in custom_deleted}
        
        selling = sorted(list(all_selling), key=lambda s: s.casefold())
        
        return purchased, selling

    def add_custom_place(self, name: str) -> None:
        """Aggiunge un nuovo luogo (o lo ripristina se era eliminato)."""
        with self.connection:
            self.connection.execute(
                "INSERT INTO custom_places (name, is_deleted) VALUES (?, 0) "
                "ON CONFLICT(name) DO UPDATE SET is_deleted = 0", (name,)
            )

    def delete_custom_place(self, name: str) -> None:
        """Segna un luogo come eliminato."""
        with self.connection:
            self.connection.execute(
                "INSERT INTO custom_places (name, is_deleted) VALUES (?, 1) "
                "ON CONFLICT(name) DO UPDATE SET is_deleted = 1", (name,)
            )

    def totals(self) -> Dict[str, Any]:
        """Calcola i totali KPI di magazzino, pre-ordini e vendite."""
        query = """
            SELECT
                status,
                is_completed,
                SUM(quantity) as total_qty,
                SUM(quantity * purchased_price_cents) as total_cost,
                SUM(COALESCE(sold_price_cents, selling_price_cents, 0)) as total_revenue,
                SUM(fees_cents) as total_fees
            FROM products
            GROUP BY status, is_completed
        """
        rows = self.connection.execute(query).fetchall()

        stock_count_val = 0
        stock_total_val = Decimal("0")
        preorder_count_val = 0
        preorder_total_val = Decimal("0")
        sold_count_val = 0
        
        sold_count_active_val = 0
        sold_count_completed_val = 0
        sold_profit_active_val = Decimal("0")
        sold_profit_completed_val = Decimal("0")
        sold_cost_val = Decimal("0")
        sold_revenue_val = Decimal("0")
        sold_fees_val = Decimal("0")

        for row in rows:
            st = row["status"]
            comp = row["is_completed"]
            qty = row["total_qty"] or 0
            cost = cents_to_money(row["total_cost"]) or Decimal("0")
            revenue = cents_to_money(row["total_revenue"]) or Decimal("0")
            fees = cents_to_money(row["total_fees"]) or Decimal("0")

            if st == STATUS_STOCK:
                stock_count_val += qty
                stock_total_val += cost
            elif st == STATUS_PREORDER:
                preorder_count_val += qty
                preorder_total_val += cost
            elif st == STATUS_SOLD:
                sold_cost_val += cost
                sold_revenue_val += revenue
                sold_fees_val += fees
                profit = revenue - cost - fees
                if comp == 1:
                    sold_profit_completed_val += profit
                    sold_count_completed_val += qty
                else:
                    sold_profit_active_val += profit
                    sold_count_active_val += qty

        sold_count_val = sold_count_active_val + sold_count_completed_val

        total_items = stock_count_val + preorder_count_val + sold_count_val
        overall_roi = ((sold_profit_active_val + sold_profit_completed_val) / sold_cost_val * 100) if sold_cost_val > 0 else Decimal("0")

        return {
            "stock_total": stock_total_val.quantize(Decimal("0.01")),
            "stock_count": stock_count_val,
            "preorder_count": preorder_count_val,
            "preorder_total": preorder_total_val.quantize(Decimal("0.01")),
            "sold_count": sold_count_val,
            "sold_count_active": sold_count_active_val,
            "sold_count_completed": sold_count_completed_val,
            "sold_profit_active": sold_profit_active_val.quantize(Decimal("0.01")),
            "sold_profit_completed": sold_profit_completed_val.quantize(Decimal("0.01")),
            "sold_profit": (sold_profit_active_val + sold_profit_completed_val).quantize(Decimal("0.01")),
            "sold_roi": overall_roi.quantize(Decimal("0.01")),
            "all_count": total_items,
            "committed_total": (stock_total_val + preorder_total_val).quantize(Decimal("0.01")),
        }

    def get_monthly_sales(self) -> List[Dict[str, Any]]:
        """Restituisce i dati delle vendite completate raggruppati per mese."""
        query = """
            SELECT
                SUBSTR(sold_date, 1, 7) as month_key,
                SUM(quantity) as total_qty,
                SUM(quantity * purchased_price_cents) as total_cost,
                SUM(COALESCE(sold_price_cents, selling_price_cents, 0)) as total_revenue,
                SUM(fees_cents) as total_fees
            FROM products
            WHERE status = ? AND is_completed = 1 AND sold_date != ''
            GROUP BY month_key
            ORDER BY month_key ASC
        """
        rows = self.connection.execute(query, (STATUS_SOLD,)).fetchall()

        result = []
        for row in rows:
            month = row["month_key"] or "Non specificato"
            qty = row["total_qty"] or 0
            cost = cents_to_money(row["total_cost"]) or Decimal("0")
            revenue = cents_to_money(row["total_revenue"]) or Decimal("0")
            fees = cents_to_money(row["total_fees"]) or Decimal("0")
            profit = revenue - cost - fees

            result.append({
                "month": month,
                "revenue": revenue.quantize(Decimal("0.01")),
                "profit": profit.quantize(Decimal("0.01")),
                "count": int(qty),
            })
        return result

    def get_profit_by_platform(self) -> List[Dict[str, Any]]:
        """Restituisce la ripartizione del profitto netto e volumi raggruppati per piattaforma di vendita."""
        query = """
            SELECT
                CASE 
                    WHEN TRIM(COALESCE(selling_place, '')) = '' THEN 'N.S.'
                    ELSE TRIM(selling_place)
                END as platform,
                SUM(quantity) as total_qty,
                SUM(quantity * purchased_price_cents) as total_cost,
                SUM(COALESCE(sold_price_cents, selling_price_cents, 0)) as total_revenue,
                SUM(fees_cents) as total_fees
            FROM products
            WHERE status = ?
            GROUP BY platform
            ORDER BY (SUM(COALESCE(sold_price_cents, selling_price_cents, 0)) - SUM(quantity * purchased_price_cents) - SUM(fees_cents)) DESC
        """
        rows = self.connection.execute(query, (STATUS_SOLD,)).fetchall()
        result = []
        for row in rows:
            platform = row["platform"]
            qty = row["total_qty"] or 0
            cost = cents_to_money(row["total_cost"]) or Decimal("0")
            revenue = cents_to_money(row["total_revenue"]) or Decimal("0")
            fees = cents_to_money(row["total_fees"]) or Decimal("0")
            profit = revenue - cost - fees

            result.append({
                "platform": platform,
                "revenue": revenue.quantize(Decimal("0.01")),
                "cost": cost.quantize(Decimal("0.01")),
                "fees": fees.quantize(Decimal("0.01")),
                "profit": profit.quantize(Decimal("0.01")),
                "count": int(qty),
            })
        return result

    def get_top_profitable_products(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Restituisce i top prodotti che hanno generato maggior profitto netto totale."""
        query = """
            SELECT
                TRIM(name) as prod_name,
                SUM(quantity) as total_qty,
                SUM(quantity * purchased_price_cents) as total_cost,
                SUM(COALESCE(sold_price_cents, selling_price_cents, 0)) as total_revenue,
                SUM(fees_cents) as total_fees
            FROM products
            WHERE status = ? AND TRIM(name) != ''
            GROUP BY prod_name
            HAVING (SUM(COALESCE(sold_price_cents, selling_price_cents, 0)) - SUM(quantity * purchased_price_cents) - SUM(fees_cents)) > 0
            ORDER BY (SUM(COALESCE(sold_price_cents, selling_price_cents, 0)) - SUM(quantity * purchased_price_cents) - SUM(fees_cents)) DESC
            LIMIT ?
        """
        rows = self.connection.execute(query, (STATUS_SOLD, limit)).fetchall()
        result = []
        for row in rows:
            name = row["prod_name"]
            qty = row["total_qty"] or 0
            cost = cents_to_money(row["total_cost"]) or Decimal("0")
            revenue = cents_to_money(row["total_revenue"]) or Decimal("0")
            fees = cents_to_money(row["total_fees"]) or Decimal("0")
            profit = revenue - cost - fees

            result.append({
                "name": name,
                "profit": profit.quantize(Decimal("0.01")),
                "count": int(qty),
            })
        return result

    def insert_many(self, records: List[Dict[str, Any]]) -> int:
        """Inserisce una lista di record in una singola transazione."""
        count = 0
        with self.connection:
            for record in records:
                self.save(record)
                count += 1
        return count

    def backup_database_safe(self, target_path: Path) -> None:
        """Esegue un backup atomico, sicuro e coerente del database usando l'API SQLite nativa."""
        self.connection.commit()
        target_path = Path(target_path)
        if target_path.resolve() == self.path.resolve():
            raise ValueError("Il file di backup deve essere diverso dal database corrente.")
        temporary_path = target_path.with_suffix(target_path.suffix + ".tmp")
        if temporary_path.exists():
            temporary_path.unlink()
        dest_conn = sqlite3.connect(temporary_path)
        try:
            with dest_conn:
                self.connection.backup(dest_conn)
        finally:
            dest_conn.close()
        os.replace(temporary_path, target_path)

    def close(self) -> None:
        """Chiude la connessione al database."""
        self.connection.close()
