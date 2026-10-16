"""Micro-server bridge locale ad altissime prestazioni per collegare il database SQLite di RSM e i servizi Python all'interfaccia Tauri / Web.

Zero dipendenze esterne: utilizza esclusivamente la libreria standard di Python (http.server).
Latenza su localhost: <1ms.
"""

import base64
import json
import os
import re
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
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


_thread_local = threading.local()

def get_thread_db() -> InventoryDatabase:
    """Restituisce un'istanza thread-safe di InventoryDatabase per il thread corrente."""
    if not hasattr(_thread_local, "db"):
        _thread_local.db = InventoryDatabase()
    return _thread_local.db


# --------------------------------------------------------------------------
# GESTIONE TRASCRIZIONE VOCALE BACKGROUND (sounddevice + Gemini / Google Speech)
# --------------------------------------------------------------------------
_speech_lock = threading.Lock()
_active_transcriber: Any = None
_transcription_status = {
    "is_recording": False,
    "is_processing": False,
    "text": "",
    "error": "",
}

def _start_voice_recording() -> tuple[bool, str]:
    global _active_transcriber
    with _speech_lock:
        if _active_transcriber and getattr(_active_transcriber, "is_recording", False):
            return True, "already_recording"

        _transcription_status["is_recording"] = True
        _transcription_status["is_processing"] = False
        _transcription_status["text"] = ""
        _transcription_status["error"] = ""

        def _on_result(text: str):
            with _speech_lock:
                _transcription_status["is_recording"] = False
                _transcription_status["is_processing"] = False
                _transcription_status["text"] = text

        def _on_error(err: str):
            with _speech_lock:
                _transcription_status["is_recording"] = False
                _transcription_status["is_processing"] = False
                _transcription_status["error"] = err

        def _on_listening():
            with _speech_lock:
                _transcription_status["is_recording"] = True
                _transcription_status["is_processing"] = False

        try:
            from src.speech_helper import SpeechTranscriber
            api_key = os.environ.get("GEMINI_API_KEY", "")
            _active_transcriber = SpeechTranscriber()
            _active_transcriber.start(
                on_result=_on_result,
                on_error=_on_error,
                on_listening=_on_listening,
                api_key=api_key,
                max_duration=300,  # fino a 5 minuti senza spegnimento automatico
                language="it-IT",
            )
            return True, "started"
        except Exception as exc:  # noqa: BLE001
            _transcription_status["is_recording"] = False
            _transcription_status["is_processing"] = False
            _transcription_status["error"] = str(exc)
            return False, str(exc)

def _stop_voice_recording() -> tuple[bool, str]:
    with _speech_lock:
        if not _active_transcriber or not getattr(_active_transcriber, "is_recording", False):
            if _transcription_status["text"]:
                return True, _transcription_status["text"]
            return False, "Nessuna registrazione attiva."

        _transcription_status["is_recording"] = False
        _transcription_status["is_processing"] = True
        _active_transcriber.stop()

    start_t = time.time()
    while time.time() - start_t < 15:
        with _speech_lock:
            if not _transcription_status["is_processing"]:
                if _transcription_status["text"]:
                    return True, _transcription_status["text"]
                elif _transcription_status["error"]:
                    return False, _transcription_status["error"]
        time.sleep(0.1)

    return False, "Tempo di elaborazione trascrizione scaduto."


# --------------------------------------------------------------------------
# GESTIONE AGGIORNAMENTI BACKGROUND (Cloudflare Worker Proxy + GitHub Releases)
# --------------------------------------------------------------------------
from src.updater import apply_update_and_restart, check_for_updates

_updater_lock = threading.Lock()
_update_state: dict[str, Any] = {
    "status": "idle",  # "idle", "checking", "downloading", "extracting", "applying", "error", "done"
    "progress": 0.0,
    "message": "",
    "error": None,
    "latest_info": None,
}


def _run_update_worker(download_url: str) -> None:
    try:
        def on_progress(fraction: float) -> None:
            with _updater_lock:
                _update_state["status"] = "downloading"
                _update_state["progress"] = fraction
                _update_state["message"] = f"Download in corso: {int(fraction * 100)}%"

        def on_status(msg: str) -> None:
            with _updater_lock:
                _update_state["message"] = msg
                if "Estrazione" in msg:
                    _update_state["status"] = "extracting"
                elif "Avvio" in msg or "Riavvio" in msg:
                    _update_state["status"] = "applying"

        apply_update_and_restart(
            download_url=download_url,
            progress_callback=on_progress,
            status_callback=on_status,
        )
    except Exception as e:  # noqa: BLE001
        with _updater_lock:
            _update_state["status"] = "error"
            _update_state["error"] = str(e)
            _update_state["message"] = f"Errore aggiornamento: {e}"


class RSMBridgeHandler(BaseHTTPRequestHandler):
    """Gestore richieste HTTP per le API REST locali di RSM."""

    @property
    def db(self) -> InventoryDatabase:
        return get_thread_db()

    def _is_allowed_origin(self, origin: str) -> bool:
        """Verifica che la richiesta provenga da Tauri WebView o da localhost."""
        if not origin:
            return True
        o = origin.lower()
        return o.startswith((
            "https://tauri.localhost",
            "http://tauri.localhost",
            "tauri://localhost",
            "http://localhost",
            "https://localhost",
            "http://127.0.0.1",
            "https://127.0.0.1",
        ))

    def _set_cors_headers(self) -> None:
        origin = self.headers.get("Origin", "")
        if self._is_allowed_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin if origin else "*")
        else:
            self.send_header("Access-Control-Allow-Origin", "null")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "86400")

    def do_OPTIONS(self) -> None:
        """Risponde alle chiamate pre-flight CORS e Private Network Access (PNA) dei browser / webview."""
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
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return {}

    # --------------------------------------------------------------------------
    # GESTIONE METODI GET
    # --------------------------------------------------------------------------
    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path.rstrip("/") or "/"
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

        # Controllo Versione
        if path == "/api/version":
            self._send_json({"success": True, "version": APP_VERSION, "name": APP_NAME})
            return

        # Stato microfono / trascrizione vocale
        if path == "/api/speech/status":
            with _speech_lock:
                self._send_json({
                    "success": True,
                    "is_recording": _transcription_status["is_recording"],
                    "is_processing": _transcription_status["is_processing"],
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
            totals = self.db.totals()
            monthly_sales = self.db.get_monthly_sales()
            platform_profits = self.db.get_profit_by_platform()
            top_products = self.db.get_top_profitable_products(limit=6)

            raw_products = self.db.all_products()
            platforms_count: dict[str, int] = {}
            for p in raw_products:
                if p.get("is_completed") == 1 or p.get("status") == STATUS_SOLD:
                    place = p.get("selling_place") or "Altro"
                    platforms_count[place] = platforms_count.get(place, 0) + 1

            self._send_json({
                "success": True,
                "kpi": {
                    "totalInvested": float(totals["committed_total"]),
                    "totalStockValue": float(totals["stock_total"]),
                    "totalProfit": float(totals["sold_profit"]),
                    "avgRoi": float(totals["sold_roi"]),
                    "completedSalesCount": totals["sold_count_completed"],
                    "activeSalesCount": totals["sold_count_active"],
                    "stockCount": totals["stock_count"],
                    "preorderCount": totals["preorder_count"],
                    "allCount": totals["all_count"],
                },
                "platforms": platforms_count,
                "monthlySales": monthly_sales,
                "platformProfits": platform_profits,
                "topProducts": top_products,
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
            except Exception as e:  # noqa: BLE001
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

        # Luoghi e Marketplace per Autocompletamento (Punto 7)
        if path == "/api/places":
            purchased, selling = self.db.get_distinct_places()
            self._send_json({
                "success": True,
                "purchased": purchased,
                "selling": selling,
            })
            return

        # Verifica disponibilità aggiornamenti (Punto 8)
        if path == "/api/updates/check":
            try:
                import importlib

                import src.config
                importlib.reload(src.config)
                curr_ver = params.get("current_version", [src.config.APP_VERSION])[0]
                update_info = check_for_updates(current_version=curr_ver)
                with _updater_lock:
                    _update_state["latest_info"] = update_info
                self._send_json({
                    "success": True,
                    "has_update": update_info is not None,
                    "current_version": curr_ver,
                    "update": update_info,
                })
            except Exception as e:  # noqa: BLE001
                self._send_error(f"Errore verifica aggiornamenti: {e}")
            return

        # Stato avanzamento download/installazione aggiornamento (Punto 8)
        if path == "/api/updates/progress":
            with _updater_lock:
                self._send_json({
                    "success": True,
                    "status": _update_state["status"],
                    "progress": _update_state["progress"],
                    "message": _update_state["message"],
                    "error": _update_state["error"],
                    "has_update": _update_state["latest_info"] is not None,
                    "update": _update_state["latest_info"],
                })
            return

        self._send_error("Endpoint non trovato", status=HTTPStatus.NOT_FOUND)

    # --------------------------------------------------------------------------
    # GESTIONE METODI POST
    # --------------------------------------------------------------------------
    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        body = self._read_body_json()

        # Avvio registrazione vocale SpeechTranscriber
        if path == "/api/speech/start":
            ok, msg = _start_voice_recording()
            if ok:
                self._send_json({"success": True, "status": msg})
            else:
                self._send_error(msg)
            return

        # Arresto registrazione vocale e trascrizione con Gemini
        if path == "/api/speech/stop":
            ok, result_or_err = _stop_voice_recording()
            if ok:
                self._send_json({"success": True, "text": result_or_err})
            else:
                self._send_error(result_or_err)
            return

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
            except Exception as e:  # noqa: BLE001
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
                from src.email_sync import (
                    fetch_unread_order_emails,
                    mark_emails_as_read,
                    parse_order_email_with_gemini,
                )
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
            except Exception as e:  # noqa: BLE001
                self._send_error(f"Sincronizzazione fallita: {e}")
            return

        # Test connessione Gmail
        if path == "/api/test-email-connection":
            email_addr = (body.get("email_sync_address") or self.db.get_setting("email_sync_address", "")).strip()
            app_pwd = (body.get("email_sync_app_password") or self.db.get_setting("email_sync_app_password", "")).replace(" ", "").strip()
            if not email_addr or not app_pwd:
                self._send_error("Inserisci l'indirizzo Gmail e la Password per le App a 16 caratteri.")
                return
            try:
                from src.email_sync import test_gmail_connection
                ok, msg = test_gmail_connection(email_addr, app_pwd)
                self._send_json({"success": ok, "message": msg})
            except Exception as e:  # noqa: BLE001
                self._send_error(f"Errore connessione: {e}")
            return

        # Apertura ricerca eBay nel browser predefinito
        if path == "/api/ebay-open-browser":
            try:
                from src.ebay_api import open_search_in_browser
                name = str(body.get("name", "")).strip()
                size = str(body.get("size", "")).strip()
                if size.upper() == "UNI":
                    size = ""
                open_search_in_browser(name, size)
                self._send_json({"success": True})
            except Exception as e:  # noqa: BLE001
                self._send_error(f"Errore apertura browser eBay: {e}")
            return

        # Scansione Email Gmail con anteprima
        if path == "/api/scan-emails":
            email_addr = (body.get("email_sync_address") or self.db.get_setting("email_sync_address", "")).strip()
            app_pwd = (body.get("email_sync_app_password") or self.db.get_setting("email_sync_app_password", "")).replace(" ", "").strip()
            if not email_addr or not app_pwd:
                self._send_error("Configura prima l'indirizzo Gmail e la Password per le App.")
                return
            try:
                from src.email_sync import (
                    fetch_unread_order_emails,
                    parse_order_email_with_gemini,
                )
                emails = fetch_unread_order_emails(email_addr, app_pwd, max_emails=15)
                extracted_items = []
                for em in emails:
                    try:
                        parsed = parse_order_email_with_gemini(em)
                        for prod in parsed:
                            extracted_items.append({
                                "name": prod.get("name", "Prodotto da Email"),
                                "size": prod.get("size", "UNI"),
                                "quantity": int(prod.get("quantity", 1)),
                                "price": float(prod.get("purchased_price", 0)),
                                "store": prod.get("purchased_place", "Email"),
                                "date": prod.get("release_date") or em.get("date", ""),
                                "uid": em.get("uid"),
                            })
                    except Exception as err:  # noqa: BLE001
                        print(f"Errore parsing email UID {em.get('uid')}: {err}")
                self._send_json({
                    "success": True,
                    "emails_scanned": len(emails),
                    "items": extracted_items
                })
            except Exception as e:  # noqa: BLE001
                self._send_error(f"Scansione fallita: {e}")
            return

        # Salvataggio ordini email nei Pre-ordini
        if path == "/api/save-scanned-emails":
            items = body.get("items", [])
            uids = body.get("uids", [])
            email_addr = (self.db.get_setting("email_sync_address", "")).strip()
            app_pwd = (self.db.get_setting("email_sync_app_password", "")).replace(" ", "").strip()
            saved_count = 0
            for item in items:
                self.db.save({
                    "name": str(item.get("name", "Prodotto Email")).strip(),
                    "size": str(item.get("size", "UNI")).strip(),
                    "quantity": int(item.get("quantity", 1)),
                    "purchased_price": Decimal(str(item.get("price", 0))),
                    "purchased_place": str(item.get("store", "Email")).strip(),
                    "status": STATUS_PREORDER,
                    "notes": "Importato automaticamente da email di ordine.",
                })
                saved_count += 1
            if uids and email_addr and app_pwd:
                try:
                    from src.email_sync import mark_emails_as_read
                    mark_emails_as_read(email_addr, app_pwd, uids)
                except Exception as e:  # noqa: BLE001
                    print(f"Errore marcatura email lette: {e}")
            self._send_json({"success": True, "saved_count": saved_count})
            return

        # Inserimento batch di prodotti da AI (accetta sia /api/products-batch sia /api/products con products)
        if (path == "/api/products-batch" or path == "/api/products") and "products" in body:
            records = body.get("products", [])
            inserted = 0
            for p in records:
                self.db.save({
                    "name": str(p.get("name", "")).strip(),
                    "size": str(p.get("size", "UNI")).strip(),
                    "quantity": int(p.get("quantity", 1)),
                    "purchased_price": Decimal(str(p.get("purchased_price", 0))),
                    "purchased_place": str(p.get("purchased_place", "")).strip(),
                    "status": p.get("status", STATUS_STOCK),
                    "notes": p.get("notes", "Generato automaticamente tramite AI."),
                })
                inserted += 1
            self._send_json({"success": True, "inserted_count": inserted})
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

            purchased_raw = body.get("purchasedPrice", 0)
            purchased_price = Decimal(str(purchased_raw or 0))
            sale_price_raw = body.get("salePrice")
            selling_price = Decimal(str(sale_price_raw)) if (sale_price_raw is not None and sale_price_raw != "") else None
            sold_price = selling_price if (is_completed or status_input == "active-sale") else None
            fees_raw = body.get("fees", 0)
            fees = Decimal(str(fees_raw or 0))

            db_payload = {
                "name": name,
                "size": body.get("size", ""),
                "quantity": max(1, int(body.get("quantity", 1))),
                "purchased_price": purchased_price,
                "purchased_place": body.get("purchasedPlace", ""),
                "selling_place": body.get("sellingPlace", ""),
                "selling_price": selling_price,
                "sold_price": sold_price,
                "fees": fees,
                "status": db_status,
                "notes": body.get("notes", ""),
                "sold_date": body.get("date", "") if (is_completed or status_input == "active-sale") else "",
                "is_completed": is_completed,
            }

            try:
                new_id = self.db.save(db_payload)
                self._send_json({"success": True, "id": new_id, "message": "Prodotto salvato con successo!"})
            except Exception as e:  # noqa: BLE001
                self._send_error(f"Errore durante il salvataggio: {e}")
            return

        # Analisi file Excel / CSV con AI Gemini
        if path == "/api/parse-excel":
            file_b64 = body.get("file_base64", "")
            filename = str(body.get("filename", "import.xlsx")).strip()
            user_hint = str(body.get("user_hint", "")).strip()

            if not file_b64:
                self._send_error("Nessun contenuto file ricevuto.")
                return

            from src.ai_agent import parse_excel_with_ai
            from src.utils import read_spreadsheet_raw

            suffix = Path(filename).suffix or ".xlsx"
            temp_file = None
            try:
                raw_bytes = base64.b64decode(file_b64)
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
                    tf.write(raw_bytes)
                    temp_file = tf.name

                raw_text = read_spreadsheet_raw(temp_file)
                if not raw_text.strip():
                    self._send_error("Il file selezionato non contiene dati leggibili.")
                    return

                products = parse_excel_with_ai(raw_text, user_hint=user_hint)
                self._send_json({"success": True, "products": products, "count": len(products)})
            except Exception as e:  # noqa: BLE001
                self._send_error(f"Errore durante l'analisi del file: {e}")
            finally:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass
            return

        # Salvataggio prodotti confermati dall'importazione Excel
        if path == "/api/save-excel-products":
            products = body.get("products", [])
            if not products:
                self._send_error("Nessun prodotto da salvare.")
                return

            saved_count = 0
            for p in products:
                try:
                    raw_status = str(p.get("status", "")).strip()
                    if raw_status in ("Venduto", "Vendite Attive", STATUS_SOLD):
                        db_status = STATUS_SOLD
                    elif raw_status in ("Pre-ordine", "Preordine", STATUS_PREORDER):
                        db_status = STATUS_PREORDER
                    else:
                        db_status = STATUS_STOCK

                    purchased_raw = p.get("purchased_price", 0) or 0
                    purchased = Decimal(str(purchased_raw)).quantize(Decimal("0.01"))

                    selling_raw = p.get("selling_price")
                    selling = Decimal(str(selling_raw)).quantize(Decimal("0.01")) if selling_raw is not None else None

                    sold_raw = p.get("sold_price")
                    sold = Decimal(str(sold_raw)).quantize(Decimal("0.01")) if sold_raw is not None else None

                    fees_raw = p.get("fees", 0) or 0
                    fees = Decimal(str(fees_raw)).quantize(Decimal("0.01"))

                    qty = int(p.get("quantity", 1) or 1)
                    if qty <= 0:
                        qty = 1

                    sold_date = str(p.get("sold_date", "") or "").strip()
                    if db_status == STATUS_SOLD and not sold_date:
                        sold_date = datetime.now(tz=timezone.utc).astimezone().date().isoformat()
                    release_date = str(p.get("release_date", "") or "").strip()
                    notes = str(p.get("notes", "") or "").strip()

                    record = {
                        "name": str(p.get("name", "")).strip(),
                        "size": str(p.get("size", "UNI") or "UNI").strip() or "UNI",
                        "quantity": qty,
                        "purchased_price": purchased,
                        "purchased_place": str(p.get("purchased_place", "") or "").strip(),
                        "selling_place": str(p.get("selling_place", "") or "").strip(),
                        "selling_price": selling,
                        "sold_price": sold,
                        "fees": fees,
                        "sold_date": sold_date,
                        "status": db_status,
                        "release_date": release_date if db_status == STATUS_PREORDER else "",
                        "notes": notes,
                    }
                    self.db.save(record)
                    saved_count += 1
                except (ValueError, KeyError, OSError) as e:
                    print(f"Errore salvataggio record Excel: {e}")

            self._send_json({"success": True, "saved_count": saved_count})
            return

        # Operazioni massive: Aggiornamento stato di gruppo
        if path == "/api/products/bulk-status":
            ids = [int(i) for i in body.get("ids", []) if str(i).isdigit()]
            if not ids:
                self._send_error("Nessun ID prodotto fornito.")
                return

            target_status = str(body.get("status", "")).strip().lower()
            if target_status not in ("stock", "preorder", "active-sale", "completed"):
                self._send_error("Stato target non valido.")
                return

            try:
                if target_status == "completed":
                    placeholders = ", ".join("?" for _ in ids)
                    with self.db.connection:
                        self.db.connection.execute(
                            f"UPDATE products SET is_completed = 1, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                            ids,
                        )
                    self._send_json({"success": True, "updated_count": len(ids)})
                    return

                if target_status == "stock":
                    self.db.update_status_many(ids, STATUS_STOCK)
                    self._send_json({"success": True, "updated_count": len(ids)})
                    return

                if target_status == "preorder":
                    self.db.update_status_many(ids, STATUS_PREORDER)
                    self._send_json({"success": True, "updated_count": len(ids)})
                    return

                if target_status == "active-sale":
                    extra: dict[str, Any] = {}
                    sp_total = body.get("sold_price_total")
                    fees_total = body.get("fees_total", 0)
                    count_dec = Decimal(str(len(ids))) if ids else Decimal(1)

                    if sp_total is not None and str(sp_total).strip() != "":
                        sp_dec = Decimal(str(sp_total))
                        extra["sold_price"] = (sp_dec / count_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                    fees_dec = Decimal(str(fees_total or 0))
                    extra["fees"] = (fees_dec / count_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                    if "selling_place" in body:
                        extra["selling_place"] = str(body["selling_place"]).strip()

                    extra["sold_date"] = datetime.now(tz=timezone.utc).astimezone().date().isoformat()

                    # Gestione vendita parziale per singolo prodotto (quantità residua in magazzino)
                    qty_to_sell = body.get("quantity_to_sell")
                    if len(ids) == 1 and qty_to_sell:
                        chosen_qty = int(qty_to_sell)
                        prod_id = ids[0]
                        rec = self.db.get(prod_id)
                        if rec and 0 < chosen_qty < (rec.get("quantity", 1) or 1):
                            original_qty = rec.get("quantity", 1) or 1
                            remaining = original_qty - chosen_qty

                            # Aggiorna record originale lasciando rimanenza nello stato attuale
                            updated_orig = dict(rec)
                            updated_orig["quantity"] = remaining
                            self.db.save(updated_orig, prod_id)

                            # Crea nuovo record per la quota venduta in Vendite Attive
                            new_sold = dict(rec)
                            new_sold.pop("id", None)
                            new_sold["quantity"] = chosen_qty
                            new_sold["status"] = STATUS_SOLD
                            new_sold["is_completed"] = 0
                            new_sold["selling_price"] = extra.get("sold_price")
                            new_sold["sold_price"] = extra.get("sold_price")
                            new_sold["fees"] = extra.get("fees", Decimal(0))
                            new_sold["selling_place"] = extra.get("selling_place", "")
                            new_sold["sold_date"] = extra.get("sold_date", "")
                            new_sold["bundle_id"] = ""
                            new_id = self.db.save(new_sold)
                            self._send_json({
                                "success": True,
                                "updated_count": 1,
                                "partial": True,
                                "new_id": new_id,
                                "remaining": remaining,
                            })
                            return

                    extra["bundle_id"] = str(uuid.uuid4()) if len(ids) > 1 else ""

                    self.db.update_status_many(ids, STATUS_SOLD, extra_data=extra)
                    placeholders = ", ".join("?" for _ in ids)
                    with self.db.connection:
                        self.db.connection.execute(
                            f"UPDATE products SET is_completed = 0 WHERE id IN ({placeholders})",
                            ids,
                        )
                    self._send_json({"success": True, "updated_count": len(ids)})
                    return
            except Exception as e:  # noqa: BLE001
                self._send_error(f"Errore aggiornamento massivo: {e}")
                return

        # Operazioni massive: Eliminazione di gruppo
        if path == "/api/products/bulk-delete":
            ids = [int(i) for i in body.get("ids", []) if str(i).isdigit()]
            if not ids:
                self._send_error("Nessun ID prodotto fornito.")
                return
            try:
                deleted_count = self.db.delete_many(ids)
                self._send_json({"success": True, "deleted_count": deleted_count})
            except Exception as e:  # noqa: BLE001
                self._send_error(f"Errore eliminazione multipla: {e}")
            return

        # Operazioni massive: Duplicazione prodotti
        if path == "/api/products/duplicate":
            ids = [int(i) for i in body.get("ids", []) if str(i).isdigit()]
            if not ids:
                self._send_error("Nessun ID prodotto fornito.")
                return
            try:
                duplicated_ids = []
                for prod_id in ids:
                    rec = self.db.get(prod_id)
                    if rec:
                        copy_rec = dict(rec)
                        copy_rec.pop("id", None)
                        copy_rec["name"] = f"{copy_rec.get('name', 'Prodotto')} (Copia)"
                        copy_rec["bundle_id"] = ""
                        copy_rec["is_completed"] = 0
                        new_id = self.db.save(copy_rec)
                        duplicated_ids.append(new_id)
                self._send_json({"success": True, "ids": duplicated_ids, "count": len(duplicated_ids)})
            except Exception as e:  # noqa: BLE001
                self._send_error(f"Errore duplicazione: {e}")
            return

        # Operazioni massive / Undo Stack: Ripristino record
        if path == "/api/undo/restore":
            records = body.get("records", [])
            restored_count = 0
            for rec in records:
                pid = rec.get("id")
                st = rec.get("status", STATUS_STOCK)
                is_completed = 1 if (st == "completed" or rec.get("is_completed") == 1) else 0
                if st in ("completed", "active-sale", "Venduto"):
                    db_status = STATUS_SOLD
                elif st in ("preorder", "Pre-ordine"):
                    db_status = STATUS_PREORDER
                else:
                    db_status = STATUS_STOCK

                purchased_price = rec.get("purchased_price")
                if purchased_price is None:
                    purchased_price = rec.get("purchasedPrice", 0)

                sold_price = rec.get("sold_price")
                if sold_price is None:
                    sold_price = rec.get("salePrice")

                save_data = {
                    "name": rec.get("name", "").strip(),
                    "size": rec.get("size", "UNI").strip(),
                    "quantity": int(rec.get("quantity", 1) or 1),
                    "purchased_price": Decimal(str(purchased_price or 0)),
                    "purchased_place": str(rec.get("purchased_place") or rec.get("purchasedPlace") or "").strip(),
                    "selling_place": str(rec.get("selling_place") or rec.get("sellingPlace") or "").strip(),
                    "selling_price": Decimal(str(sold_price)) if sold_price is not None else None,
                    "sold_price": Decimal(str(sold_price)) if sold_price is not None else None,
                    "fees": Decimal(str(rec.get("fees") or 0)),
                    "sold_date": str(rec.get("sold_date") or rec.get("date") or "").strip(),
                    "status": db_status,
                    "notes": str(rec.get("notes") or "").strip(),
                    "bundle_id": str(rec.get("bundle_id") or rec.get("bundleId") or "").strip(),
                    "is_completed": is_completed,
                }
                try:
                    target_id = int(pid) if (pid and str(pid).isdigit()) else None
                    if target_id and self.db.get(target_id):
                        self.db.save(save_data, target_id)
                    else:
                        self.db.save(save_data)
                    restored_count += 1
                except Exception as e:  # noqa: BLE001
                    print(f"Errore ripristino record undo: {e}")
            self._send_json({"success": True, "restored_count": restored_count})
            return

        # Aggiunta Luogo/Marketplace Personalizzato (Punto 7)
        if path == "/api/places":
            name = body.get("name", "").strip()
            if not name:
                self._send_error("Il nome del luogo non può essere vuoto.")
                return
            self.db.add_custom_place(name)
            purchased, selling = self.db.get_distinct_places()
            self._send_json({
                "success": True,
                "name": name,
                "purchased": purchased,
                "selling": selling,
            })
            return

        # Eliminazione Luogo/Marketplace Personalizzato (Punto 7)
        if path == "/api/places/delete":
            name = body.get("name", "").strip()
            if not name:
                self._send_error("Il nome del luogo non può essere vuoto.")
                return
            self.db.delete_custom_place(name)
            purchased, selling = self.db.get_distinct_places()
            self._send_json({
                "success": True,
                "name": name,
                "purchased": purchased,
                "selling": selling,
            })
            return

        # Avvio download e applicazione aggiornamento (Punto 8)
        if path == "/api/updates/apply":
            with _updater_lock:
                if _update_state["status"] in ("downloading", "extracting", "applying"):
                    self._send_json({"success": True, "message": "Aggiornamento già in corso", "already_running": True})
                    return

                download_url = (body or {}).get("download_url")
                if not download_url and _update_state.get("latest_info"):
                    download_url = _update_state["latest_info"].get("download_url")

                if not download_url:
                    self._send_error("URL di download non fornito o non valido.")
                    return

                _update_state["status"] = "downloading"
                _update_state["progress"] = 0.0
                _update_state["message"] = "Avvio download dell'aggiornamento..."
                _update_state["error"] = None

                thread = threading.Thread(target=_run_update_worker, args=(download_url,), daemon=True)
                thread.start()

                self._send_json({"success": True, "message": "Aggiornamento avviato con successo."})
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

            if existing.get("is_completed") == 1:
                self._send_error("Le vendite completate non possono essere modificate.", status=HTTPStatus.FORBIDDEN)
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

            purchased_raw = body.get("purchasedPrice")
            if purchased_raw is None:
                purchased_price = existing.get("purchased_price") or Decimal("0.00")
            else:
                purchased_price = Decimal(str(purchased_raw or 0))

            selling_price_raw = body.get("salePrice")
            if selling_price_raw is None:
                selling_price = existing.get("selling_price")
            else:
                selling_price = Decimal(str(selling_price_raw)) if selling_price_raw != "" else None

            sold_price_raw = body.get("soldPrice", body.get("salePrice"))
            if sold_price_raw is None:
                sold_price = existing.get("sold_price") if (is_completed or status_input == "active-sale") else None
            else:
                sold_price = Decimal(str(sold_price_raw)) if (sold_price_raw != "" and (is_completed or status_input == "active-sale")) else None

            fees_raw = body.get("fees")
            if fees_raw is None:
                fees = existing.get("fees") or Decimal("0.00")
            else:
                fees = Decimal(str(fees_raw or 0))

            db_payload = {
                "name": name,
                "size": body.get("size", existing.get("size", "")),
                "quantity": max(1, int(body.get("quantity", existing.get("quantity", 1)))),
                "purchased_price": purchased_price,
                "purchased_place": body.get("purchasedPlace", existing.get("purchased_place", "")),
                "selling_place": body.get("sellingPlace", existing.get("selling_place", "")),
                "selling_price": selling_price,
                "sold_price": sold_price,
                "fees": fees,
                "status": db_status,
                "notes": body.get("notes", existing.get("notes", "")),
                "sold_date": body.get("date", existing.get("sold_date", "")),
                "bundle_id": body.get("bundle_id", existing.get("bundle_id", "")),
                "is_completed": is_completed,
            }

            try:
                self.db.save(db_payload, product_id=prod_id)
                self._send_json({"success": True, "id": prod_id, "message": "Prodotto aggiornato con successo!"})
            except Exception as e:  # noqa: BLE001
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
            except Exception as e:  # noqa: BLE001
                self._send_error(f"Errore eliminazione: {e}")
            return

        # Eliminazione Luogo/Marketplace Personalizzato (Punto 7)
        if path == "/api/places":
            body = self._read_body_json()
            name = body.get("name", "").strip()
            if not name:
                self._send_error("Il nome del luogo non può essere vuoto.")
                return
            self.db.delete_custom_place(name)
            purchased, selling = self.db.get_distinct_places()
            self._send_json({
                "success": True,
                "name": name,
                "purchased": purchased,
                "selling": selling,
            })
            return

        self._send_error("Endpoint DELETE non trovato", status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        """Silenzia i log HTTP standard della console per mantenere zero overhead."""


def run_bridge_server() -> None:
    """Avvia il server bridge locale."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
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
