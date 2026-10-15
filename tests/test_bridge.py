import json
import threading
from decimal import Decimal
from http.server import ThreadingHTTPServer
from urllib import request
from urllib.error import HTTPError

from src.config import STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK
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


def test_bridge_excel_endpoints(tmp_path):
    """Verifica il corretto salvataggio e gestione degli endpoint Excel del bridge server."""
    test_db = tmp_path / "test_excel_bridge.db"
    db = InventoryDatabase(test_db)

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
        # 1. Test /api/save-excel-products con prodotti estratti
        excel_payload = json.dumps({
            "products": [
                {
                    "name": "Nike Dunk Low Retro",
                    "size": "42.5",
                    "quantity": 2,
                    "purchased_price": 110.0,
                    "purchased_place": "SNKRS",
                    "status": "In Stock",
                    "notes": "Taglia popolare",
                },
                {
                    "name": "Jordan 1 High Lost & Found",
                    "size": "44",
                    "quantity": 1,
                    "purchased_price": 180.0,
                    "purchased_place": "Foot Locker",
                    "status": "Pre-ordine",
                    "release_date": "2026-11-01",
                    "notes": "Consegna programmata",
                },
                {
                    "name": "Yeezy Slide Onyx",
                    "size": "43",
                    "quantity": 1,
                    "purchased_price": 70.0,
                    "purchased_place": "Confirmed",
                    "selling_place": "Vinted",
                    "sold_price": 120.0,
                    "fees": 5.0,
                    "status": "Venduto",
                    "notes": "Vendita conclusa",
                },
            ]
        }).encode("utf-8")

        req = request.Request(
            f"http://127.0.0.1:{port}/api/save-excel-products",
            data=excel_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["saved_count"] == 3

        # Verifica nel database
        products = db.all_products()
        assert len(products) == 3
        dunk = next(p for p in products if p["name"] == "Nike Dunk Low Retro")
        assert dunk["size"] == "42.5"
        assert dunk["quantity"] == 2
        assert dunk["purchased_price"] == Decimal("110.00")
        assert dunk["status"] == STATUS_STOCK

        jordan = next(p for p in products if p["name"] == "Jordan 1 High Lost & Found")
        assert jordan["status"] == STATUS_PREORDER
        assert jordan["release_date"] == "2026-11-01"

        yeezy = next(p for p in products if p["name"] == "Yeezy Slide Onyx")
        assert yeezy["status"] == STATUS_SOLD
        assert yeezy["sold_price"] == Decimal("120.00")
        assert yeezy["fees"] == Decimal("5.00")

        # 2. Test salvataggio payload vuoto -> solleva errore
        empty_req = request.Request(
            f"http://127.0.0.1:{port}/api/save-excel-products",
            data=json.dumps({"products": []}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            request.urlopen(empty_req)
            raise AssertionError("Dovrebbe sollevare errore su products vuoti")
        except HTTPError as err:
            assert err.code == 400
            err_json = json.loads(err.read().decode("utf-8"))
            assert "Nessun prodotto da salvare" in err_json["error"]

        # 3. Test /api/parse-excel senza file base64 -> solleva errore 400
        parse_req = request.Request(
            f"http://127.0.0.1:{port}/api/parse-excel",
            data=json.dumps({}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            request.urlopen(parse_req)
            raise AssertionError("Dovrebbe sollevare errore se file_base64 è assente")
        except HTTPError as err:
            assert err.code == 400
            err_json = json.loads(err.read().decode("utf-8"))
            assert "Nessun contenuto file ricevuto" in err_json["error"]

    finally:
        server.shutdown()
        server.server_close()


def test_bridge_bulk_operations(tmp_path):
    """Verifica le operazioni massive: bulk-status, bulk-delete, duplicate."""
    test_db = tmp_path / "test_bulk_ops.db"
    db = InventoryDatabase(test_db)

    id1 = db.save({
        "name": "Jordan 1 High Chicago",
        "size": "42",
        "quantity": 1,
        "purchased_price": Decimal("180.00"),
        "purchased_place": "Nike SNKRS",
        "status": STATUS_STOCK,
    })
    id2 = db.save({
        "name": "Jordan 1 Low Travis",
        "size": "43",
        "quantity": 1,
        "purchased_price": Decimal("150.00"),
        "purchased_place": "Nike SNKRS",
        "status": STATUS_STOCK,
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
        # 1. Bulk Status: Metti in vendita multipla (active-sale con bundle)
        bulk_sale_req = request.Request(
            f"http://127.0.0.1:{port}/api/products/bulk-status",
            data=json.dumps({
                "ids": [id1, id2],
                "status": "active-sale",
                "sold_price_total": 400.0,
                "fees_total": 30.0,
                "selling_place": "Vinted",
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(bulk_sale_req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["updated_count"] == 2

        prod1 = db.get(id1)
        prod2 = db.get(id2)
        assert prod1["status"] == STATUS_SOLD
        assert prod1["is_completed"] == 0
        assert prod1["sold_price"] == Decimal("200.00")
        assert prod1["fees"] == Decimal("15.00")
        assert prod1["selling_place"] == "Vinted"
        assert prod1["bundle_id"] != ""
        assert prod1["bundle_id"] == prod2["bundle_id"]

        # 2. Bulk Status: Completa vendita
        complete_req = request.Request(
            f"http://127.0.0.1:{port}/api/products/bulk-status",
            data=json.dumps({
                "ids": [id1, id2],
                "status": "completed",
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(complete_req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["updated_count"] == 2

        assert db.get(id1)["is_completed"] == 1
        assert db.get(id2)["is_completed"] == 1

        # 3. Duplicate
        dup_req = request.Request(
            f"http://127.0.0.1:{port}/api/products/duplicate",
            data=json.dumps({"ids": [id1]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(dup_req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            dup_ids = data["ids"]
            assert len(dup_ids) == 1
            dup_id = dup_ids[0]

        dup_prod = db.get(dup_id)
        assert "Jordan 1 High Chicago (Copia)" in dup_prod["name"]
        assert dup_prod["bundle_id"] == ""
        assert dup_prod["is_completed"] == 0

        # 4. Bulk Delete
        del_req = request.Request(
            f"http://127.0.0.1:{port}/api/products/bulk-delete",
            data=json.dumps({"ids": [id1, id2, dup_id]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(del_req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["deleted_count"] == 3

        assert db.get(id1) is None
        assert db.get(id2) is None
        assert db.get(dup_id) is None

        # 5. Spostamento Parziale Scorte (Vendita parziale di 1 unità su 3)
        multi_qty_id = db.save({
            "name": "Yeezy 350 Onyx",
            "size": "44",
            "quantity": 3,
            "purchased_price": Decimal("220.00"),
            "purchased_place": "Confirmed",
            "status": STATUS_STOCK,
        })

        partial_sale_req = request.Request(
            f"http://127.0.0.1:{port}/api/products/bulk-status",
            data=json.dumps({
                "ids": [multi_qty_id],
                "status": "active-sale",
                "sold_price_total": 280.0,
                "fees_total": 15.0,
                "selling_place": "Vinted",
                "quantity_to_sell": 1,
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(partial_sale_req) as resp:
            partial_data = json.loads(resp.read().decode("utf-8"))
            assert partial_data["success"] is True
            assert partial_data["partial"] is True
            assert partial_data["remaining"] == 2
            new_sold_id = partial_data["new_id"]

        orig_row = db.get(multi_qty_id)
        assert orig_row["status"] == STATUS_STOCK
        assert orig_row["quantity"] == 2

        sold_row = db.get(new_sold_id)
        assert sold_row["status"] == STATUS_SOLD
        assert sold_row["is_completed"] == 0
        assert sold_row["quantity"] == 1
        assert sold_row["sold_price"] == Decimal("280.00")
        assert sold_row["fees"] == Decimal("15.00")
        # 6. Test Undo Restore endpoint (/api/undo/restore)
        undo_restore_req = request.Request(
            f"http://127.0.0.1:{port}/api/undo/restore",
            data=json.dumps({
                "records": [
                    {
                        "id": multi_qty_id,
                        "name": "Yeezy 350 Onyx",
                        "size": "44",
                        "quantity": 3,
                        "purchased_price": 220.0,
                        "purchased_place": "Confirmed",
                        "status": "stock",
                    }
                ]
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(undo_restore_req) as resp:
            restore_data = json.loads(resp.read().decode("utf-8"))
            assert restore_data["success"] is True
            assert restore_data["restored_count"] == 1

        restored_row = db.get(multi_qty_id)
        assert restored_row["quantity"] == 3
        assert restored_row["status"] == STATUS_STOCK

    finally:
        server.shutdown()
        server.server_close()

