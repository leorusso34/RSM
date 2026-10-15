import json
import threading
from decimal import Decimal
from http.server import ThreadingHTTPServer
from urllib import request
from urllib.error import HTTPError

from src.config import STATUS_SOLD, STATUS_STOCK
from src.database import InventoryDatabase
from src.services.bridge_server import RSMBridgeHandler, _thread_local


def test_bridge_completed_sale_cannot_be_modified(tmp_path):
    """Verifica che le vendite completate non possano essere modificate via PUT bridge."""
    test_db = tmp_path / "test_inventory.db"
    db = InventoryDatabase(test_db)

    # Crea un prodotto venduto e completato
    completed_id = db.save({
        "name": "Nike Dunk Low Completata",
        "size": "42",
        "quantity": 1,
        "purchased_price": Decimal("100.00"),
        "purchased_place": "SNKRS",
        "selling_place": "StockX",
        "selling_price": Decimal("180.00"),
        "sold_price": Decimal("180.00"),
        "fees": Decimal("15.00"),
        "sold_date": "2026-10-01",
        "status": STATUS_SOLD,
        "is_completed": 1,
    })

    # Prodotto normale in stock
    stock_id = db.save({
        "name": "Jordan 4 In Stock",
        "size": "43",
        "quantity": 1,
        "purchased_price": Decimal("200.00"),
        "purchased_place": "Nike",
        "status": STATUS_STOCK,
        "is_completed": 0,
    })

    class TestBridgeHandler(RSMBridgeHandler):
        @property
        def db(self) -> InventoryDatabase:
            if not hasattr(_thread_local, "test_db") or _thread_local.test_db.path != test_db:
                _thread_local.test_db = InventoryDatabase(test_db)
            return _thread_local.test_db

    server = ThreadingHTTPServer(("127.0.0.1", 0), TestBridgeHandler)
    port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        # 1. Verifica che /api/products non includa il campo fittizio 'brand'
        req_get = request.Request(f"http://127.0.0.1:{port}/api/products")
        with request.urlopen(req_get) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            items = data["data"]
            assert len(items) == 2
            for item in items:
                assert "brand" not in item
                assert "purchasedPlace" in item

        # 2. Tentativo di modifica su vendita completata -> deve restituire 403 Forbidden
        put_payload = json.dumps({
            "name": "Tentativo Modifica Non Consentita",
            "purchasedPrice": 120.00,
        }).encode("utf-8")
        req_forbidden = request.Request(
            f"http://127.0.0.1:{port}/api/products/{completed_id}",
            data=put_payload,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        try:
            request.urlopen(req_forbidden)
            raise AssertionError("La modifica di una vendita completata doveva sollevare HTTPError 403")
        except HTTPError as err:
            assert err.code == 403
            err_body = json.loads(err.read().decode("utf-8"))
            assert "Le vendite completate non possono essere modificate" in err_body["error"]

        # 3. Modifica consentita su prodotto in stock
        put_allowed = json.dumps({
            "name": "Jordan 4 Aggiornata",
            "purchasedPrice": 210.00,
            "purchasedPlace": "Nike Store Milano",
        }).encode("utf-8")
        req_ok = request.Request(
            f"http://127.0.0.1:{port}/api/products/{stock_id}",
            data=put_allowed,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        try:
            with request.urlopen(req_ok) as resp_ok:
                ok_body = json.loads(resp_ok.read().decode("utf-8"))
                assert ok_body["success"] is True
        except HTTPError as err:
            err_data = err.read().decode("utf-8")
            raise AssertionError(f"req_ok failed with {err.code}: {err_data}") from err

        updated_row = db.get(stock_id)
        assert updated_row["name"] == "Jordan 4 Aggiornata"
        assert updated_row["purchased_price"] == Decimal("210.00")
        assert updated_row["purchased_place"] == "Nike Store Milano"

    finally:
        server.shutdown()
        server.server_close()
