"""Micro-server bridge locale ad altissime prestazioni per collegare il database SQLite di RSM e i servizi Python all'interfaccia Tauri / Web.

Zero dipendenze esterne: utilizza esclusivamente la libreria standard di Python (http.server).
Latenza su localhost: <1ms.
"""

import json
import re
import sys
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

# Assicura che la root del progetto sia nel path di importazione
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import (
    APP_NAME,
    APP_VERSION,
    STATUS_COMPLETED,
    STATUS_PREORDER,
    STATUS_SOLD,
    STATUS_STOCK,
)
from src.database import InventoryDatabase

PORT = 28472
HOST = "127.0.0.1"


class DecimalEncoder(json.JSONEncoder):
    """Encoder JSON personalizzato per gestire oggetti Decimal di Python."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


import threading

_thread_local = threading.local()

def get_thread_db() -> InventoryDatabase:
    """Restituisce un'istanza thread-safe di InventoryDatabase per il thread corrente."""
    if not hasattr(_thread_local, "db"):
        _thread_local.db = InventoryDatabase()
    return _thread_local.db


class RSMBridgeHandler(BaseHTTPRequestHandler):
    """Gestore richieste HTTP per le API REST locali di RSM."""

    @property
    def db(self) -> InventoryDatabase:
        return get_thread_db()

    def _set_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self) -> None:
        """Risponde alle chiamate pre-flight CORS dei browser / webview."""
        self.send_response(HTTPStatus.NO_CONTENT)
        self._set_cors_headers()
        self.end_headers()

    def _send_json(self, data: Any, status: int = HTTPStatus.OK) -> None:
        payload = json.dumps(data, cls=DecimalEncoder, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _send_error(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        self._send_json({"success": False, "error": message}, status=status)

    def _read_body_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            return {}
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(body)
        except Exception:
            return {}

    # --------------------------------------------------------------------------
    # GESTIONE METODI GET
    # --------------------------------------------------------------------------
    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        params = parse_qs(parsed_url.query)

        # Health Check
        if path == "/api/health":
            products = self.db.all_products()
            self._send_json({
                "status": "online",
                "app": APP_NAME,
                "version": APP_VERSION,
                "database_products_count": len(products),
            })
            return

        # Lista Prodotti
        if path == "/api/products":
            raw_products = self.db.all_products()
            formatted = []
            for p in raw_products:
                cost = float(p.get("purchased_price") or 0)
                qty = int(p.get("quantity") or 1)
                sale_price = float(p.get("sold_price") or p.get("selling_price") or 0)
                fees = float(p.get("fees") or 0)
                st = p.get("status") or STATUS_STOCK
                is_completed = (p.get("is_completed") == 1)
                is_active_sale = (st == STATUS_SOLD and not is_completed)

                if is_completed:
                    status_key = "completed"
                    status_label = "Completato"
                elif is_active_sale:
                    status_key = "active-sale"
                    status_label = "Venduto"
                elif st == STATUS_PREORDER:
                    status_key = "preorder"
                    status_label = "Pre-ordine"
                else:
                    status_key = "stock"
                    status_label = "In Stock"

                has_sale_data = (is_completed or is_active_sale)
                profit = (sale_price - cost - fees) * qty if has_sale_data else 0.0
                roi = (profit / (cost * qty) * 100) if (cost > 0 and has_sale_data) else 0.0

                formatted.append({
                    "id": p.get("id"),
                    "name": p.get("name") or "",
                    "brand": "Brand",  # Estratto o fallback
                    "size": p.get("size") or "-",
                    "quantity": qty,
                    "purchasedPrice": cost,
                    "purchasedPlace": p.get("purchased_place") or "",
                    "sellingPlace": p.get("selling_place") or "",
                    "salePrice": sale_price if (sale_price > 0) else None,
                    "fees": fees,
                    "profit": round(profit, 2) if has_sale_data else None,
                    "roi": round(roi, 1) if has_sale_data else None,
                    "status": status_key,
                    "statusLabel": status_label,
                    "date": p.get("sold_date") or p.get("created_at") or "",
                    "notes": p.get("notes") or "",
                    "bundle_id": p.get("bundle_id") or "",
                })
            self._send_json({"success": True, "count": len(formatted), "data": formatted})
            return

        # KPI & Metriche Dashboard
        if path == "/api/metrics":
            products = self.db.all_products()
            total_invested = 0.0
            total_stock_value = 0.0
            total_profit = 0.0
            total_roi_sum = 0.0
            completed_count = 0
            platforms_count: dict[str, int] = {}

            for p in products:
                cost = float(p.get("purchased_price") or 0) * int(p.get("quantity") or 1)
                total_invested += cost
                st = p.get("status")
                is_completed = (p.get("is_completed") == 1)

                if st == STATUS_STOCK:
                    sell_p = float(p.get("selling_price") or p.get("purchased_price") or 0)
                    total_stock_value += sell_p * int(p.get("quantity") or 1)

                if is_completed:
                    sale = float(p.get("sold_price") or p.get("selling_price") or 0) * int(p.get("quantity") or 1)
                    fees = float(p.get("fees") or 0) * int(p.get("quantity") or 1)
                    profit = sale - cost - fees
                    total_profit += profit
                    completed_count += 1
                    if cost > 0:
                        total_roi_sum += (profit / cost) * 100

                    # Conta piattaforma
                    place = p.get("selling_place") or "Altro"
                    platforms_count[place] = platforms_count.get(place, 0) + 1

            avg_roi = (total_roi_sum / completed_count) if completed_count > 0 else 0.0

            self._send_json({
                "success": True,
                "kpi": {
                    "totalInvested": round(total_invested, 2),
                    "totalStockValue": round(total_stock_value, 2),
                    "totalProfit": round(total_profit, 2),
                    "avgRoi": round(avg_roi, 1),
                    "completedSalesCount": completed_count,
                    "activeSalesCount": sum(1 for p in products if p.get("status") == STATUS_SOLD and p.get("is_completed") != 1),
                    "stockCount": sum(1 for p in products if p.get("status") == STATUS_STOCK),
                    "preorderCount": sum(1 for p in products if p.get("status") == STATUS_PREORDER),
                },
                "platforms": platforms_count,
            })
            return

        # Stima prezzi di mercato eBay
        if path == "/api/ebay-prices":
            name = params.get("name", [""])[0]
            size = params.get("size", [""])[0]
            if not name:
                self._send_error("Parametro 'name' richiesto.")
                return
            try:
                from src.ebay_api import fetch_market_prices
                ebay_res = fetch_market_prices(name, size)
                self._send_json({"success": True, "data": ebay_res})
            except Exception as e:
                self._send_error(f"eBay lookup: {e}")
            return

        # Dettaglio singolo prodotto /api/products/<id>
        match_id = re.match(r"^/api/products/(\d+)$", path)
        if match_id:
            prod_id = int(match_id.group(1))
            product = self.db.get(prod_id)
            if product:
                self._send_json({"success": True, "data": product})
            else:
                self._send_error("Prodotto non trovato", status=HTTPStatus.NOT_FOUND)
            return

        # Impostazioni applicazione
        if path == "/api/settings":
            email_addr = self.db.get_setting("email_sync_address", "")
            has_pwd = bool(self.db.get_setting("email_sync_app_password", ""))
            self._send_json({
                "success": True,
                "email_sync_address": email_addr,
                "has_app_password": has_pwd,
            })
            return

        self._send_error("Endpoint non trovato", status=HTTPStatus.NOT_FOUND)

    # --------------------------------------------------------------------------
    # GESTIONE METODI POST
    # --------------------------------------------------------------------------
    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self._read_body_json()

        # Analisi AI con Gemini
        if path == "/api/ai-parse":
            prompt = body.get("prompt", "").strip()
            if not prompt:
                self._send_error("Prompt richiesto per l'analisi AI.")
                return
            try:
                from src.ai_agent import parse_product_with_ai
                parsed = parse_product_with_ai(prompt)
                self._send_json({"success": True, "data": parsed})
            except Exception as e:
                self._send_error(f"Errore analisi AI: {e}")
            return

        # Sincronizzazione Email Gmail
        if path == "/api/sync-email":
            email_addr = self.db.get_setting("email_sync_address")
            app_pwd = self.db.get_setting("email_sync_app_password")
            if not email_addr or not app_pwd:
                self._send_error("Configura prima l'indirizzo Gmail e l'App Password nelle impostazioni.")
                return
            try:
                from src.email_sync import fetch_unread_order_emails, mark_emails_as_read, parse_order_email_with_gemini
                emails = fetch_unread_order_emails(email_addr, app_pwd, max_emails=10)
                imported = []
                read_uids = []
                for em in emails:
                    extracted = parse_order_email_with_gemini(em)
                    for prod in extracted:
                        new_id = self.db.save({
                            "name": prod.get("name", "Prodotto da Email"),
                            "size": prod.get("size", "UNI"),
                            "quantity": int(prod.get("quantity", 1)),
                            "purchased_price": Decimal(str(prod.get("purchased_price", 0))),
                            "purchased_place": prod.get("purchased_place", "Email"),
                            "status": STATUS_PREORDER,
                            "notes": f"Email: {em.get('subject', '')}",
                        })
                        imported.append({"id": new_id, "name": prod.get("name")})
                    if em.get("uid"):
                        read_uids.append(em.get("uid"))
                if read_uids:
                    mark_emails_as_read(email_addr, app_pwd, read_uids)
                self._send_json({"success": True, "imported_count": len(imported), "products": imported})
            except Exception as e:
                self._send_error(f"Sincronizzazione fallita: {e}")
            return

        # Salvataggio impostazioni
        if path == "/api/settings":
            if "email_sync_address" in body:
                self.db.set_setting("email_sync_address", body["email_sync_address"].strip())
            if "email_sync_app_password" in body and body["email_sync_app_password"].strip():
                self.db.set_setting("email_sync_app_password", body["email_sync_app_password"].strip())
            self._send_json({"success": True, "message": "Impostazioni salvate con successo!"})
            return

        if path == "/api/products":
            name = body.get("name", "").strip()
            if not name:
                self._send_error("Il nome del prodotto è obbligatorio.")
                return

            status_input = body.get("status", "stock")
            is_completed = 1 if status_input == "completed" else 0
            if status_input in ("completed", "active-sale", "Venduto"):
                db_status = STATUS_SOLD
            elif status_input in ("preorder", "Pre-ordine"):
                db_status = STATUS_PREORDER
            else:
                db_status = STATUS_STOCK

            db_payload = {
                "name": name,
                "size": body.get("size", ""),
                "quantity": max(1, int(body.get("quantity", 1))),
                "purchased_price": Decimal(str(body.get("purchasedPrice", 0))),
                "purchased_place": body.get("purchasedPlace", ""),
                "selling_place": body.get("sellingPlace", ""),
                "selling_price": Decimal(str(body.get("salePrice", 0))) if body.get("salePrice") else None,
                "sold_price": Decimal(str(body.get("salePrice", 0))) if (is_completed or status_input == "active-sale") else None,
                "fees": Decimal(str(body.get("fees", 0))),
                "status": db_status,
                "notes": body.get("notes", ""),
                "sold_date": body.get("date", "") if (is_completed or status_input == "active-sale") else "",
                "is_completed": is_completed,
            }

            try:
                new_id = self.db.save(db_payload)
                self._send_json({"success": True, "id": new_id, "message": "Prodotto salvato con successo!"})
            except Exception as e:
                self._send_error(f"Errore durante il salvataggio: {e}")
            return

        self._send_error("Endpoint POST non trovato", status=HTTPStatus.NOT_FOUND)

    # --------------------------------------------------------------------------
    # GESTIONE METODI PUT (Aggiornamento Prodotto)
    # --------------------------------------------------------------------------
    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        match_id = re.match(r"^/api/products/(\d+)$", path)
        if match_id:
            prod_id = int(match_id.group(1))
            existing = self.db.get(prod_id)
            if not existing:
                self._send_error(f"Prodotto #{prod_id} non trovato.", status=HTTPStatus.NOT_FOUND)
                return

            body = self._read_body_json()
            name = body.get("name", existing.get("name", "")).strip()
            if not name:
                self._send_error("Il nome del prodotto non può essere vuoto.")
                return

            status_input = body.get("status", existing.get("status", "stock"))
            is_completed = 1 if status_input == "completed" else existing.get("is_completed", 0)
            if status_input in ("completed", "active-sale", "Venduto"):
                db_status = STATUS_SOLD
            elif status_input in ("preorder", "Pre-ordine"):
                db_status = STATUS_PREORDER
            else:
                db_status = STATUS_STOCK

            db_payload = {
                "name": name,
                "size": body.get("size", existing.get("size", "")),
                "quantity": max(1, int(body.get("quantity", existing.get("quantity", 1)))),
                "purchased_price": Decimal(str(body.get("purchasedPrice", existing.get("purchased_price", 0)))),
                "purchased_place": body.get("purchasedPlace", existing.get("purchased_place", "")),
                "selling_place": body.get("sellingPlace", existing.get("selling_place", "")),
                "selling_price": Decimal(str(body.get("salePrice", existing.get("selling_price", 0)))) if body.get("salePrice") is not None else None,
                "sold_price": Decimal(str(body.get("soldPrice", body.get("salePrice", existing.get("sold_price", 0))))) if (is_completed or status_input == "active-sale") else None,
                "fees": Decimal(str(body.get("fees", existing.get("fees", 0)))),
                "status": db_status,
                "notes": body.get("notes", existing.get("notes", "")),
                "sold_date": body.get("date", existing.get("sold_date", "")),
                "bundle_id": body.get("bundle_id", existing.get("bundle_id", "")),
                "is_completed": is_completed,
            }

            try:
                self.db.save(db_payload, product_id=prod_id)
                self._send_json({"success": True, "id": prod_id, "message": "Prodotto aggiornato con successo!"})
            except Exception as e:
                self._send_error(f"Errore durante l'aggiornamento: {e}")
            return

        self._send_error("Endpoint PUT non trovato", status=HTTPStatus.NOT_FOUND)

    # --------------------------------------------------------------------------
    # GESTIONE METODI DELETE
    # --------------------------------------------------------------------------
    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        match_id = re.match(r"^/api/products/(\d+)$", path)
        if match_id:
            prod_id = int(match_id.group(1))
            try:
                self.db.delete(prod_id)
                self._send_json({"success": True, "message": f"Prodotto #{prod_id} eliminato con successo."})
            except Exception as e:
                self._send_error(f"Errore eliminazione: {e}")
            return

        self._send_error("Endpoint DELETE non trovato", status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        """Silenzia i log HTTP standard della console per mantenere zero overhead."""
        pass


def run_bridge_server() -> None:
    """Avvia il server bridge locale."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    server = ThreadingHTTPServer((HOST, PORT), RSMBridgeHandler)
    print(f"[RSM] Bridge Server attivo su http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArresto del server bridge...")
        server.server_close()


if __name__ == "__main__":
    run_bridge_server()
