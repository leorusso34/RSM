#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gestione database SQLite e migrazioni per Russo Stock Manager."""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import DB_PATH, STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK
from utils import calculate_profit


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

        # Tabella base
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE,
                size TEXT NOT NULL DEFAULT '',
                quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
                purchased_price REAL NOT NULL CHECK (purchased_price >= 0),
                purchased_place TEXT NOT NULL DEFAULT '',
                selling_place TEXT NOT NULL DEFAULT '',
                selling_price REAL CHECK (selling_price IS NULL OR selling_price >= 0),
                sold_price REAL CHECK (sold_price IS NULL OR sold_price >= 0),
                fees REAL NOT NULL DEFAULT 0.0 CHECK (fees >= 0),
                sold_date TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '{STATUS_STOCK}',
                release_date TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # Controlliamo le colonne esistenti per migrare eventuali database di vecchie versioni
        cursor.execute("PRAGMA table_info(products)")
        existing_columns = {row["name"] for row in cursor.fetchall()}

        # Aggiunta colonne se mancanti
        if "quantity" not in existing_columns:
            cursor.execute("ALTER TABLE products ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1")
        if "sold_price" not in existing_columns:
            cursor.execute("ALTER TABLE products ADD COLUMN sold_price REAL DEFAULT NULL")
        if "fees" not in existing_columns:
            cursor.execute("ALTER TABLE products ADD COLUMN fees REAL NOT NULL DEFAULT 0.0")
        if "sold_date" not in existing_columns:
            cursor.execute("ALTER TABLE products ADD COLUMN sold_date TEXT NOT NULL DEFAULT ''")

        # Indici per velocizzare le query
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_status ON products(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_purchased_place ON products(purchased_place)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_selling_place ON products(selling_place)")

        self.connection.commit()

    def list_products(
        self,
        status: Optional[str] = None,
        search: str = "",
        purchased_place: str = "",
        selling_place: str = "",
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
    ) -> List[sqlite3.Row]:
        """Restituisce i prodotti filtrati per stato e parametri di ricerca."""
        query = "SELECT * FROM products WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status)

        search_clean = search.strip()
        if search_clean:
            needle = f"%{search_clean}%"
            query += """ AND (
                name LIKE ? OR size LIKE ? OR purchased_place LIKE ? OR
                selling_place LIKE ? OR release_date LIKE ? OR notes LIKE ? OR sold_date LIKE ?
            )"""
            params.extend([needle] * 7)

        if purchased_place.strip():
            query += " AND purchased_place = ?"
            params.append(purchased_place.strip())

        if selling_place.strip():
            query += " AND selling_place = ?"
            params.append(selling_place.strip())

        if min_price is not None:
            query += " AND purchased_price >= ?"
            params.append(min_price)

        if max_price is not None:
            query += " AND purchased_price <= ?"
            params.append(max_price)

        query += " ORDER BY name COLLATE NOCASE, id DESC"

        return self.connection.execute(query, params).fetchall()

    def get(self, product_id: int) -> Optional[sqlite3.Row]:
        """Ottiene un singolo prodotto per ID."""
        return self.connection.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()

    def save(self, data: Dict[str, Any], product_id: Optional[int] = None) -> int:
        """Salva (inserisce o aggiorna) un prodotto nel database."""
        fields = (
            "name", "size", "quantity", "purchased_price", "purchased_place",
            "selling_place", "selling_price", "sold_price", "fees", "sold_date",
            "status", "release_date", "notes"
        )
        values = tuple(data.get(field) for field in fields)

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

        placeholders = ", ".join("?" for _ in product_ids)
        params: List[Any] = [new_status]
        extra_sql = ""

        if extra_data:
            if "sold_price" in extra_data:
                extra_sql += ", sold_price = ?"
                params.append(extra_data["sold_price"])
            if "sold_date" in extra_data:
                extra_sql += ", sold_date = ?"
                params.append(extra_data["sold_date"])
            if "fees" in extra_data:
                extra_sql += ", fees = ?"
                params.append(extra_data["fees"])

        if new_status == STATUS_STOCK:
            extra_sql += ", release_date = ''"

        query = f"UPDATE products SET status = ?, updated_at = CURRENT_TIMESTAMP {extra_sql} WHERE id IN ({placeholders})"
        params.extend(product_ids)

        with self.connection:
            cursor = self.connection.execute(query, params)
            return cursor.rowcount

    def get_distinct_places(self) -> Tuple[List[str], List[str]]:
        """Restituisce i luoghi di acquisto e vendita unici già usati nel DB."""
        purchased = [
            row[0] for row in self.connection.execute(
                "SELECT DISTINCT purchased_place FROM products WHERE purchased_place != '' ORDER BY purchased_place"
            ).fetchall()
        ]
        selling = [
            row[0] for row in self.connection.execute(
                "SELECT DISTINCT selling_place FROM products WHERE selling_place != '' ORDER BY selling_place"
            ).fetchall()
        ]
        return purchased, selling

    def totals(self) -> Dict[str, Any]:
        """Calcola i totali KPI di magazzino, pre-ordini e vendite."""
        rows = self.connection.execute("SELECT * FROM products").fetchall()

        stock_total_val = 0.0
        stock_count_val = 0
        preorder_count_val = 0
        preorder_total_val = 0.0
        sold_count_val = 0
        sold_revenue_val = 0.0
        sold_cost_val = 0.0
        sold_fees_val = 0.0
        sold_profit_val = 0.0

        for row in rows:
            qty = row["quantity"] or 1
            cost = (row["purchased_price"] or 0.0) * qty
            st = row["status"]

            if st == STATUS_STOCK:
                stock_count_val += qty
                stock_total_val += cost
            elif st == STATUS_PREORDER:
                preorder_count_val += qty
                preorder_total_val += cost
            elif st == STATUS_SOLD:
                sold_count_val += qty
                sp = (row["sold_price"] or row["selling_price"] or 0.0) * qty
                fees = (row["fees"] or 0.0) * qty
                sold_revenue_val += sp
                sold_cost_val += cost
                sold_fees_val += fees
                profit, _ = calculate_profit(row["purchased_price"], row["sold_price"] or row["selling_price"], row["fees"] or 0.0, qty)
                sold_profit_val += profit

        total_items = stock_count_val + preorder_count_val + sold_count_val
        overall_roi = (sold_profit_val / sold_cost_val * 100) if sold_cost_val > 0 else 0.0

        return {
            "stock_total": stock_total_val,
            "stock_count": stock_count_val,
            "preorder_count": preorder_count_val,
            "preorder_total": preorder_total_val,
            "sold_count": sold_count_val,
            "sold_revenue": sold_revenue_val,
            "sold_profit": sold_profit_val,
            "sold_roi": overall_roi,
            "all_count": total_items,
            "committed_total": stock_total_val + preorder_total_val,
        }

    def get_monthly_sales(self) -> List[Dict[str, Any]]:
        """Restituisce i dati delle vendite raggruppati per mese."""
        rows = self.connection.execute(
            """
            SELECT sold_date, purchased_price, sold_price, selling_price, fees, quantity
            FROM products
            WHERE status = ? AND sold_date != ''
            ORDER BY sold_date ASC
            """,
            (STATUS_SOLD,),
        ).fetchall()

        months_map: Dict[str, Dict[str, float]] = {}

        for row in rows:
            date_str = row["sold_date"]
            month_key = date_str[:7] if len(date_str) >= 7 else "Non specificato"
            qty = row["quantity"] or 1
            sp = row["sold_price"] or row["selling_price"] or 0.0
            profit, _ = calculate_profit(row["purchased_price"], sp, row["fees"] or 0.0, qty)

            if month_key not in months_map:
                months_map[month_key] = {"revenue": 0.0, "profit": 0.0, "count": 0}

            months_map[month_key]["revenue"] += sp * qty
            months_map[month_key]["profit"] += profit
            months_map[month_key]["count"] += qty

        result = []
        for month, data in sorted(months_map.items()):
            result.append({
                "month": month,
                "revenue": data["revenue"],
                "profit": data["profit"],
                "count": int(data["count"]),
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
        dest_conn = sqlite3.connect(target_path)
        try:
            with dest_conn:
                self.connection.backup(dest_conn)
        finally:
            dest_conn.close()

    def close(self) -> None:
        """Chiude la connessione al database."""
        self.connection.close()
