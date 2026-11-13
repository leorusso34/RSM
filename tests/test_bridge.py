import json
import threading
from decimal import Decimal
from http.server import ThreadingHTTPServer
from unittest.mock import MagicMock, patch
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
    completed_id = db.save(
        {
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
        }
    )

    # Prodotto normale in stock
    stock_id = db.save(
        {
            "name": "Jordan 4 In Stock",
            "size": "43",
            "quantity": 1,
            "purchased_price": Decimal("200.00"),
            "purchased_place": "Nike",
            "status": STATUS_STOCK,
            "is_completed": 0,
        }
    )

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
        put_payload = json.dumps(
            {
                "name": "Tentativo Modifica Non Consentita",
                "purchasedPrice": 120.00,
            }
        ).encode("utf-8")
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
        put_allowed = json.dumps(
            {
                "name": "Jordan 4 Aggiornata",
                "purchasedPrice": 210.00,
                "purchasedPlace": "Nike Store Milano",
            }
        ).encode("utf-8")
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
        excel_payload = json.dumps(
            {
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
            }
        ).encode("utf-8")

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

    id1 = db.save(
        {
            "name": "Jordan 1 High Chicago",
            "size": "42",
            "quantity": 1,
            "purchased_price": Decimal("180.00"),
            "purchased_place": "Nike SNKRS",
            "status": STATUS_STOCK,
        }
    )
    id2 = db.save(
        {
            "name": "Jordan 1 Low Travis",
            "size": "43",
            "quantity": 1,
            "purchased_price": Decimal("150.00"),
            "purchased_place": "Nike SNKRS",
            "status": STATUS_STOCK,
        }
    )

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
            data=json.dumps(
                {
                    "ids": [id1, id2],
                    "status": "active-sale",
                    "sold_price_total": 400.0,
                    "fees_total": 30.0,
                    "selling_place": "Vinted",
                }
            ).encode("utf-8"),
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
        # Prezzo e spese sono unici: registrati per intero sul primo prodotto, non divisi
        assert prod1["sold_price"] == Decimal("400.00")
        assert prod2["sold_price"] == Decimal("0.00")
        assert prod1["sold_price"] + prod2["sold_price"] == Decimal("400.00")
        assert prod1["fees"] == Decimal("30.00")
        assert prod2["fees"] == Decimal("0.00")
        assert prod1["fees"] + prod2["fees"] == Decimal("30.00")
        assert prod1["selling_place"] == "Vinted"
        assert prod1["bundle_id"] != ""
        assert prod1["bundle_id"] == prod2["bundle_id"]

        # 2. Bulk Status: Completa vendita
        complete_req = request.Request(
            f"http://127.0.0.1:{port}/api/products/bulk-status",
            data=json.dumps(
                {
                    "ids": [id1, id2],
                    "status": "completed",
                }
            ).encode("utf-8"),
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
        multi_qty_id = db.save(
            {
                "name": "Yeezy 350 Onyx",
                "size": "44",
                "quantity": 3,
                "purchased_price": Decimal("220.00"),
                "purchased_place": "Confirmed",
                "status": STATUS_STOCK,
            }
        )

        partial_sale_req = request.Request(
            f"http://127.0.0.1:{port}/api/products/bulk-status",
            data=json.dumps(
                {
                    "ids": [multi_qty_id],
                    "status": "active-sale",
                    "sold_price_total": 280.0,
                    "fees_total": 15.0,
                    "selling_place": "Vinted",
                    "quantity_to_sell": 1,
                }
            ).encode("utf-8"),
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
            data=json.dumps(
                {
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
                }
            ).encode("utf-8"),
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

        # 7. Test Places endpoints (/api/places - GET, POST, DELETE)
        req_places_get = request.Request(f"http://127.0.0.1:{port}/api/places")
        with request.urlopen(req_places_get) as resp:
            places_data = json.loads(resp.read().decode("utf-8"))
            assert places_data["success"] is True
            assert "purchased" in places_data
            assert "selling" in places_data
            assert "StockX" in places_data["selling"] or "stockx" in [s.lower() for s in places_data["selling"]]

        # Add custom place
        req_places_add = request.Request(
            f"http://127.0.0.1:{port}/api/places",
            data=json.dumps({"name": "Wallapop"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req_places_add) as resp:
            add_data = json.loads(resp.read().decode("utf-8"))
            assert add_data["success"] is True
            assert "Wallapop" in add_data["selling"]

        # Delete custom place via DELETE
        req_places_del = request.Request(
            f"http://127.0.0.1:{port}/api/places",
            data=json.dumps({"name": "Wallapop"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="DELETE",
        )
        with request.urlopen(req_places_del) as resp:
            del_data = json.loads(resp.read().decode("utf-8"))
            assert del_data["success"] is True
            assert "Wallapop" not in del_data["selling"]

        # Delete default place via POST /api/places/delete
        req_places_del_post = request.Request(
            f"http://127.0.0.1:{port}/api/places/delete",
            data=json.dumps({"name": "wethenew"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req_places_del_post) as resp:
            del_post_data = json.loads(resp.read().decode("utf-8"))
            assert del_post_data["success"] is True
            assert "wethenew" not in del_post_data["selling"]

        # 16. Step 8: Update endpoints
        # Check updates when no update exists
        with (
            patch("src.services.bridge_server.check_for_updates", return_value=None),
            request.urlopen(f"http://127.0.0.1:{port}/api/updates/check") as resp,
        ):
            upd_check = json.loads(resp.read().decode("utf-8"))
            assert upd_check["success"] is True
            assert upd_check["has_update"] is False

        # Check updates when update is found
        fake_update = {
            "version": "v2.1.0",
            "title": "RSM v2.1.0",
            "changelog": "New features",
            "download_url": "https://rsm-proxy.test/download/123",
            "asset_name": "RSM.zip",
            "size_bytes": 1000,
        }
        with (
            patch("src.services.bridge_server.check_for_updates", return_value=fake_update),
            request.urlopen(f"http://127.0.0.1:{port}/api/updates/check") as resp,
        ):
            upd_check2 = json.loads(resp.read().decode("utf-8"))
            assert upd_check2["success"] is True
            assert upd_check2["has_update"] is True
            assert upd_check2["update"]["version"] == "v2.1.0"

        # Check progress endpoint
        with request.urlopen(f"http://127.0.0.1:{port}/api/updates/progress") as resp:
            prog = json.loads(resp.read().decode("utf-8"))
            assert prog["success"] is True
            assert "status" in prog
            assert "progress" in prog

        # Trigger apply update with mock worker
        req_apply = request.Request(
            f"http://127.0.0.1:{port}/api/updates/apply",
            data=json.dumps({"download_url": "https://rsm-proxy.test/download/123"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with (
            patch("src.services.bridge_server._run_update_worker"),
            request.urlopen(req_apply) as resp,
        ):
            apply_res = json.loads(resp.read().decode("utf-8"))
            assert apply_res["success"] is True

    finally:
        server.shutdown()
        server.server_close()


def test_bridge_multi_quantity_profit_and_roi(tmp_path):
    """Verifica che /api/products calcoli correttamente profitto e ROI moltiplicando il prezzo unitario di acquisto per la quantità."""
    test_db = tmp_path / "test_inventory_multi_qty.db"
    db = InventoryDatabase(test_db)

    # 2 pezzi comprati a 50€ ciascuno (costo totale = 100€)
    # Venduti a 160€ totali con 10€ di commissioni totali
    # Profitto atteso = 160 - (50 * 2) - 10 = 50€
    # ROI atteso = (50 / 100) * 100 = 50.0%
    db.save(
        {
            "name": "Maglie Nike (2 pz)",
            "size": "L",
            "quantity": 2,
            "purchased_price": Decimal("50.00"),
            "purchased_place": "Nike Store",
            "selling_place": "eBay",
            "selling_price": Decimal("160.00"),
            "sold_price": Decimal("160.00"),
            "fees": Decimal("10.00"),
            "sold_date": "2026-10-18",
            "status": STATUS_SOLD,
            "is_completed": 1,
        }
    )

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
        req_get = request.Request(f"http://127.0.0.1:{port}/api/products")
        with request.urlopen(req_get) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            items = data["data"]
            assert len(items) == 1
            prod = items[0]
            assert prod["quantity"] == 2
            assert prod["purchasedPrice"] == 50.0
            assert prod["salePrice"] == 160.0
            assert prod["fees"] == 10.0
            assert prod["profit"] == 50.0
            assert prod["roi"] == 50.0
    finally:
        server.shutdown()
        server.server_close()


def test_bridge_settings_email_sync(tmp_path, monkeypatch):
    """Verifica che /api/settings salvi e restituisca correttamente email_sync_address e email_sync_app_password."""
    test_config = tmp_path / "test_config.json"
    monkeypatch.setattr("src.database.CONFIG_JSON_PATH", test_config)
    test_db = tmp_path / "test_inventory_settings.db"
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
        # 1. Inizialmente le credenziali non sono presenti
        req_get_initial = request.Request(f"http://127.0.0.1:{port}/api/settings")
        with request.urlopen(req_get_initial) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["email_sync_address"] == ""
            assert data["email_sync_app_password"] == ""
            assert data["has_app_password"] is False

        # 2. Salvataggio impostazioni via POST /api/settings
        post_payload = json.dumps(
            {
                "email_sync_address": "utente@gmail.com",
                "email_sync_app_password": "abcd efgh ijkl mnop",
            }
        ).encode("utf-8")
        req_post = request.Request(
            f"http://127.0.0.1:{port}/api/settings",
            data=post_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req_post) as resp:
            post_res = json.loads(resp.read().decode("utf-8"))
            assert post_res["success"] is True

        # 3. Lettura impostazioni via GET /api/settings: password ed email devono essere restituite
        req_get_after = request.Request(f"http://127.0.0.1:{port}/api/settings")
        with request.urlopen(req_get_after) as resp:
            data_after = json.loads(resp.read().decode("utf-8"))
            assert data_after["success"] is True
            assert data_after["email_sync_address"] == "utente@gmail.com"
            assert data_after["email_sync_app_password"] == "abcd efgh ijkl mnop"
            assert data_after["has_app_password"] is True

        assert db.get_setting("email_sync_address") == "utente@gmail.com"
        assert db.get_setting("email_sync_app_password") == "abcd efgh ijkl mnop"
    finally:
        server.shutdown()
        server.server_close()


def test_bridge_bundle_fees_and_price_are_single_not_split(tmp_path):
    """Con un bundle dispari (3 prodotti) e importi decimali dispari (es. 389.99€) prezzo e spese restano unici senza arrotondamenti."""
    test_db = tmp_path / "test_bundle_fees.db"
    db = InventoryDatabase(test_db)
    ids = [
        db.save(
            {
                "name": f"Prodotto {n}",
                "size": "42",
                "quantity": 1,
                "purchased_price": Decimal("50.00"),
                "purchased_place": "Nike",
                "status": STATUS_STOCK,
            }
        )
        for n in range(3)
    ]

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
        req = request.Request(
            f"http://127.0.0.1:{port}/api/products/bulk-status",
            data=json.dumps(
                {
                    "ids": ids,
                    "status": "active-sale",
                    "sold_price_total": 389.99,
                    "fees_total": 10.0,
                    "selling_place": "Vinted",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req) as resp:
            assert json.loads(resp.read().decode("utf-8"))["success"] is True

        prices = [db.get(i)["sold_price"] for i in ids]
        assert prices == [Decimal("389.99"), Decimal("0.00"), Decimal("0.00")]
        assert sum(prices) == Decimal("389.99")

        fees = [db.get(i)["fees"] for i in ids]
        assert fees == [Decimal("10.00"), Decimal("0.00"), Decimal("0.00")]
        assert sum(fees) == Decimal("10.00")
        assert len({db.get(i)["bundle_id"] for i in ids}) == 1

        # Vendita singola: le spese restano sul prodotto
        single_id = db.save(
            {
                "name": "Singolo",
                "size": "43",
                "quantity": 1,
                "purchased_price": Decimal("80.00"),
                "purchased_place": "Nike",
                "status": STATUS_STOCK,
            }
        )
        req_single = request.Request(
            f"http://127.0.0.1:{port}/api/products/bulk-status",
            data=json.dumps(
                {"ids": [single_id], "status": "active-sale", "sold_price_total": 120.0, "fees_total": 7.5}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req_single) as resp:
            assert json.loads(resp.read().decode("utf-8"))["success"] is True
        assert db.get(single_id)["fees"] == Decimal("7.50")
    finally:
        server.shutdown()
        server.server_close()


def test_products_api_returns_created_at_for_dead_stock(tmp_path):
    """Verifica che /api/products restituisca esplicitamente createdAt per il calcolo del dead stock."""
    test_db = tmp_path / "test_inventory_dead_stock.db"
    db = InventoryDatabase(test_db)

    pid = db.save(
        {
            "name": "Jordan 4 Retro",
            "size": "42.5",
            "quantity": 1,
            "purchased_price": Decimal("210.00"),
            "purchased_place": "SNKRS",
            "status": STATUS_STOCK,
        }
    )

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
        req_get = request.Request(f"http://127.0.0.1:{port}/api/products")
        with request.urlopen(req_get) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            items = data["data"]
            assert len(items) == 1
            item = items[0]
            assert item["id"] == pid
            assert "createdAt" in item
            assert item["createdAt"] != ""
            assert len(item["createdAt"]) >= 10
    finally:
        server.shutdown()
        server.server_close()


def test_bridge_partial_stock_move_from_preorder(tmp_path):
    """Verifica lo split parziale di quantità nello spostamento da preordine a magazzino."""
    test_db = tmp_path / "test_partial_stock.db"
    db = InventoryDatabase(test_db)

    # Prodotto iniziale: 10 pezzi in pre-ordine
    pid = db.save(
        {
            "name": "Yeezy Boost 350",
            "size": "44",
            "quantity": 10,
            "purchased_price": Decimal("220.00"),
            "purchased_place": "Confirmed",
            "status": STATUS_PREORDER,
        }
    )

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
        # Sposta 4 pezzi su 10 in Magazzino
        req = request.Request(
            f"http://127.0.0.1:{port}/api/products/bulk-status",
            data=json.dumps(
                {
                    "ids": [pid],
                    "status": "stock",
                    "quantity_to_stock": 4,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["split"] is True
            new_id = data["new_stock_id"]

        # 1. Il record originale rimane in pre-ordine con 6 pezzi
        orig_row = db.get(pid)
        assert orig_row["status"] == STATUS_PREORDER
        assert orig_row["quantity"] == 6

        # 2. Il nuovo record è in magazzino con 4 pezzi
        new_row = db.get(new_id)
        assert new_row["status"] == STATUS_STOCK
        assert new_row["quantity"] == 4
        assert new_row["purchased_price"] == Decimal("220.00")
        assert new_row["size"] == "44"
    finally:
        server.shutdown()
        server.server_close()


def test_bridge_packlink_endpoints(tmp_path, monkeypatch):
    """Verifica gli endpoint bridge dedicati a Packlink PRO (/status, /config, /parse-address, /create-draft)."""
    test_config = tmp_path / "test_config.json"
    monkeypatch.setattr("src.database.CONFIG_JSON_PATH", test_config)
    test_db = tmp_path / "test_bridge_packlink.db"
    InventoryDatabase(test_db)

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
        # 1. GET /api/packlink/status inizialmente non configurata
        req = request.Request(f"http://127.0.0.1:{port}/api/packlink/status")
        with request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["configured"] is False

        # 2. POST /api/packlink/config salva la chiave
        dummy_token = "mock_test_token"
        req_cfg = request.Request(
            f"http://127.0.0.1:{port}/api/packlink/config",
            data=json.dumps({"api_key": dummy_token}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req_cfg) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True

        # Verifica stato aggiornato
        req_status2 = request.Request(f"http://127.0.0.1:{port}/api/packlink/status")
        with request.urlopen(req_status2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["configured"] is True
            assert "mock" in data["masked_key"]

        # 3. POST /api/packlink/parse-address
        req_parse = request.Request(
            f"http://127.0.0.1:{port}/api/packlink/parse-address",
            data=json.dumps({"text": "Mario Rossi via roma 1 20121 milano tel 3331234567"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req_parse) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["data"]["zip"] == "20121"

        # 4. POST /api/packlink/create-draft con mock
        with patch("src.packlink.create_packlink_draft") as mock_create:
            mock_create.return_value = {
                "success": True,
                "draft_id": "draft_mock_99",
                "reference": "IT2026MOCK99",
                "web_url": "https://pro.packlink.it/private/shipments/drafts",
            }
            req_draft = request.Request(
                f"http://127.0.0.1:{port}/api/packlink/create-draft",
                data=json.dumps(
                    {
                        "recipient": {
                            "name": "Mario Rossi",
                            "street1": "Via Roma 1",
                            "zip": "20121",
                            "city": "Milano",
                            "phone": "+393331234567",
                        },
                        "package": {"weight": 1.2},
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req_draft) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                assert data["success"] is True
                assert data["draft_id"] == "draft_mock_99"
                assert data["reference"] == "IT2026MOCK99"
    finally:
        server.shutdown()
        server.server_close()


def test_bridge_tracking_endpoints(tmp_path, monkeypatch):
    """Verifica gli endpoint bridge dedicati a 17TRACK (/api/tracking, /api/products/<id>/tracking)."""
    test_db = tmp_path / "test_bridge_tracking.db"
    db = InventoryDatabase(test_db)

    # Crea un prodotto venduto
    prod_id = db.save(
        {
            "name": "Jordan 4 Retro Military Black",
            "purchased_price": Decimal("210.00"),
            "status": "Venduto",
            "sold_price": Decimal("320.00"),
            "fees": Decimal("25.00"),
        }
    )

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
        mock_tracking_data = {
            "success": True,
            "tracking_number": "179090188502104",
            "carrier": "brt",
            "carrier_name": "BRT Bartolini",
            "status": "Delivered",
            "status_label": "Consegnato",
            "events_count": 2,
            "events": [
                {
                    "time_iso": "2026-11-03T15:27:00+01:00",
                    "formatted_date": "03/11/2026 15:27",
                    "description": "DELIVERED",
                    "location": "LUCCA (090)",
                }
            ],
        }

        # 1. POST /api/products/<id>/tracking con mock di fetch_tracking_info
        with patch("src.services.bridge_server.fetch_tracking_info", return_value=mock_tracking_data):
            req_post = request.Request(
                f"http://127.0.0.1:{port}/api/products/{prod_id}/tracking",
                data=json.dumps({"tracking_number": "179090188502104", "carrier": "brt"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req_post) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                assert data["success"] is True
                assert data["tracking_number"] == "179090188502104"
                assert data["carrier"] == "brt"
                assert data["data"]["status"] == "Delivered"

        # 2. GET /api/products/<id>/tracking da cache
        req_get = request.Request(f"http://127.0.0.1:{port}/api/products/{prod_id}/tracking")
        with request.urlopen(req_get) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["has_tracking"] is True
            assert data["cached"] is True
            assert data["tracking_number"] == "179090188502104"
            assert data["data"]["status"] == "Delivered"

        # 3. GET /api/products include i campi di tracking
        req_list = request.Request(f"http://127.0.0.1:{port}/api/products")
        with request.urlopen(req_list) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            item = next(p for p in data["data"] if p["id"] == prod_id)
            assert item["tracking_number"] == "179090188502104"
            assert item["carrier"] == "brt"
            assert "Delivered" in item["tracking_cache"]

        # 4. DELETE /api/products/<id>/tracking
        req_del = request.Request(
            f"http://127.0.0.1:{port}/api/products/{prod_id}/tracking",
            method="DELETE",
        )
        with request.urlopen(req_del) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True

        # Verifica che il tracking sia stato azzerato
        req_get_empty = request.Request(f"http://127.0.0.1:{port}/api/products/{prod_id}/tracking")
        with request.urlopen(req_get_empty) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["has_tracking"] is False
    finally:
        server.shutdown()
        server.server_close()


def test_bridge_notifications_endpoints(tmp_path):
    """Verifica la generazione automatica notifiche da tracking 17TRACK 'Delivered', dismiss singolo e 'Pulisci tutto'."""
    test_db = tmp_path / "test_bridge_notifications.db"
    db = InventoryDatabase(test_db)

    prod_id_1 = db.save(
        {
            "name": "Jordan 4 Retro Military Blue",
            "size": "42.5",
            "purchased_price": Decimal("210.00"),
            "status": "Venduto",
            "sold_price": Decimal("290.00"),
            "fees": Decimal("15.00"),
        }
    )
    prod_id_2 = db.save(
        {
            "name": "Pokemon Evoluzioni Prismatiche ETB",
            "size": "UNI",
            "purchased_price": Decimal("55.00"),
            "status": "Venduto",
            "sold_price": Decimal("95.00"),
            "fees": Decimal("5.00"),
        }
    )

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
        mock_delivered_1 = {
            "success": True,
            "tracking_number": "BRT111222333",
            "carrier": "brt",
            "carrier_name": "BRT Bartolini",
            "status": "Delivered",
            "status_label": "Consegnato",
            "latest_event": {"formatted_date": "13/11/2026 09:00"},
            "events": [],
        }
        mock_delivered_2 = {
            "success": True,
            "tracking_number": "SDA444555666",
            "carrier": "poste",
            "carrier_name": "Poste Italiane",
            "status": "Delivered",
            "status_label": "Consegnato",
            "latest_event": {"formatted_date": "13/11/2026 09:10"},
            "events": [],
        }

        # 1. Salva due tracking con stato Delivered
        with patch("src.services.bridge_server.fetch_tracking_info", side_effect=[mock_delivered_1, mock_delivered_2]):
            for pid, num, car in [
                (prod_id_1, "BRT111222333", "brt"),
                (prod_id_2, "SDA444555666", "poste"),
            ]:
                req = request.Request(
                    f"http://127.0.0.1:{port}/api/products/{pid}/tracking",
                    data=json.dumps({"tracking_number": num, "carrier": car}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with request.urlopen(req) as resp:
                    assert json.loads(resp.read().decode("utf-8"))["success"] is True

        # 2. GET /api/notifications deve contenere entrambe le notifiche
        with request.urlopen(f"http://127.0.0.1:{port}/api/notifications") as resp:
            notif_res = json.loads(resp.read().decode("utf-8"))
            assert notif_res["success"] is True
            assert len(notif_res["data"]) == 2
            first_id = notif_res["data"][0]["id"]

        # 3. Rimozione singola con DELETE /api/notifications/<id>
        req_del = request.Request(f"http://127.0.0.1:{port}/api/notifications/{first_id}", method="DELETE")
        with request.urlopen(req_del) as resp:
            assert json.loads(resp.read().decode("utf-8"))["success"] is True

        # Verifica che la notifica rimossa non venga ricreata con un refresh 17TRACK dello stesso tracking
        with (
            patch("src.services.bridge_server.fetch_tracking_info", return_value=mock_delivered_2),
            request.urlopen(f"http://127.0.0.1:{port}/api/products/{prod_id_2}/tracking?refresh=1") as resp,
        ):
            assert json.loads(resp.read().decode("utf-8"))["success"] is True

        with request.urlopen(f"http://127.0.0.1:{port}/api/notifications") as resp:
            notif_res = json.loads(resp.read().decode("utf-8"))
            assert len(notif_res["data"]) == 1
            assert notif_res["data"][0]["id"] != first_id

        # 4. Pulisci tutto (POST /api/notifications/clear)
        req_clear = request.Request(
            f"http://127.0.0.1:{port}/api/notifications/clear",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req_clear) as resp:
            clear_res = json.loads(resp.read().decode("utf-8"))
            assert clear_res["success"] is True
            assert clear_res["cleared_count"] == 1

        with request.urlopen(f"http://127.0.0.1:{port}/api/notifications") as resp:
            notif_res = json.loads(resp.read().decode("utf-8"))
            assert notif_res["data"] == []

        # 5. Auto-rimozione notifica quando una vendita passa a Completata (bulk-status & PUT)
        prod_id_3 = db.save(
            {
                "name": "Asics Gel-Kayano 14",
                "size": "43",
                "purchased_price": Decimal("130.00"),
                "status": "Venduto",
                "sold_price": Decimal("195.00"),
                "fees": Decimal("10.00"),
            }
        )
        prod_id_4 = db.save(
            {
                "name": "New Balance 1906R",
                "size": "42",
                "purchased_price": Decimal("120.00"),
                "status": "Venduto",
                "sold_price": Decimal("175.00"),
                "fees": Decimal("10.00"),
            }
        )
        mock_delivered_3 = {**mock_delivered_1, "tracking_number": "GLS777888999"}
        mock_delivered_4 = {**mock_delivered_2, "tracking_number": "UPS000111222"}
        with patch("src.services.bridge_server.fetch_tracking_info", side_effect=[mock_delivered_3, mock_delivered_4]):
            for pid, num, car in [
                (prod_id_3, "GLS777888999", "gls"),
                (prod_id_4, "UPS000111222", "ups"),
            ]:
                req = request.Request(
                    f"http://127.0.0.1:{port}/api/products/{pid}/tracking",
                    data=json.dumps({"tracking_number": num, "carrier": car}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with request.urlopen(req) as resp:
                    assert json.loads(resp.read().decode("utf-8"))["success"] is True

        with request.urlopen(f"http://127.0.0.1:{port}/api/notifications") as resp:
            notif_res = json.loads(resp.read().decode("utf-8"))
            assert len(notif_res["data"]) == 2

        # Completa prod_id_3 tramite bulk-status
        req_bulk = request.Request(
            f"http://127.0.0.1:{port}/api/products/bulk-status",
            data=json.dumps({"ids": [prod_id_3], "status": "completed"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req_bulk) as resp:
            assert json.loads(resp.read().decode("utf-8"))["success"] is True

        with request.urlopen(f"http://127.0.0.1:{port}/api/notifications") as resp:
            notif_res = json.loads(resp.read().decode("utf-8"))
            assert len(notif_res["data"]) == 1
            assert notif_res["data"][0]["product_id"] == prod_id_4

        # Completa prod_id_4 tramite PUT /api/products/<id>
        req_put = request.Request(
            f"http://127.0.0.1:{port}/api/products/{prod_id_4}",
            data=json.dumps({"name": "New Balance 1906R", "status": "completed"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        with request.urlopen(req_put) as resp:
            assert json.loads(resp.read().decode("utf-8"))["success"] is True

        with request.urlopen(f"http://127.0.0.1:{port}/api/notifications") as resp:
            notif_res = json.loads(resp.read().decode("utf-8"))
            assert notif_res["data"] == []
    finally:
        server.shutdown()
        server.server_close()


def test_bridge_speech_start_language_support(tmp_path):
    """Verifica il supporto al parametro di lingua nell'endpoint POST /api/speech/start e fallback it-IT."""
    test_db = tmp_path / "test_bridge_speech.db"

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

        def _get_passed_lang(mock_obj):
            call_kwargs = mock_obj.call_args.kwargs
            if "language" in call_kwargs:
                return call_kwargs["language"]
            return mock_obj.call_args.args[0] if mock_obj.call_args.args else "it-IT"

        # 1. POST /api/speech/start con body {"language": "en-US"} -> inoltra "en-US"
        with patch("src.services.bridge_server._start_voice_recording", return_value=(True, "started")) as mock_start:
            req_en = request.Request(
                f"http://127.0.0.1:{port}/api/speech/start",
                data=json.dumps({"language": "en-US"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req_en) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                assert data["success"] is True
                assert data["status"] == "started"

            mock_start.assert_called_once()
            assert _get_passed_lang(mock_start) == "en-US"

        # 2. POST /api/speech/start con body {"language": "it-IT"} -> inoltra "it-IT"
        with patch("src.services.bridge_server._start_voice_recording", return_value=(True, "started")) as mock_start:
            req_it = request.Request(
                f"http://127.0.0.1:{port}/api/speech/start",
                data=json.dumps({"language": "it-IT"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req_it) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                assert data["success"] is True
                assert data["status"] == "started"

            mock_start.assert_called_once()
            assert _get_passed_lang(mock_start) == "it-IT"

        # 3. POST /api/speech/start con body vuoto JSON -> fallback deterministico "it-IT"
        with patch("src.services.bridge_server._start_voice_recording", return_value=(True, "started")) as mock_start:
            req_empty = request.Request(
                f"http://127.0.0.1:{port}/api/speech/start",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req_empty) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                assert data["success"] is True
                assert data["status"] == "started"

            mock_start.assert_called_once()
            assert _get_passed_lang(mock_start) == "it-IT"

        # 4. POST /api/speech/start senza body (compatibilita retroattiva) -> fallback "it-IT"
        with patch("src.services.bridge_server._start_voice_recording", return_value=(True, "started")) as mock_start:
            req_nobody = request.Request(
                f"http://127.0.0.1:{port}/api/speech/start",
                data=b"",
                method="POST",
            )
            with request.urlopen(req_nobody) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                assert data["success"] is True

            mock_start.assert_called_once()
            assert _get_passed_lang(mock_start) == "it-IT"

        # 5. POST /api/speech/start con query parameter ?language=en-US -> inoltra "en-US"
        with patch("src.services.bridge_server._start_voice_recording", return_value=(True, "started")) as mock_start:
            req_query = request.Request(
                f"http://127.0.0.1:{port}/api/speech/start?language=en-US",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req_query) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                assert data["success"] is True

            mock_start.assert_called_once()
            assert _get_passed_lang(mock_start) == "en-US"

        # 6. POST /api/speech/start con chiave 'lang' nel JSON -> inoltra "en-US"
        with patch("src.services.bridge_server._start_voice_recording", return_value=(True, "started")) as mock_start:
            req_lang = request.Request(
                f"http://127.0.0.1:{port}/api/speech/start",
                data=json.dumps({"lang": "en-US"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req_lang) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                assert data["success"] is True

            mock_start.assert_called_once()
            assert _get_passed_lang(mock_start) == "en-US"

        # 7. POST /api/speech/start con errore registrazione -> solleva HTTPError 400
        with patch(
            "src.services.bridge_server._start_voice_recording",
            return_value=(False, "Dispositivo audio non disponibile"),
        ):
            req_err = request.Request(
                f"http://127.0.0.1:{port}/api/speech/start",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                request.urlopen(req_err)
                raise AssertionError("Doveva sollevare HTTPError 400")
            except HTTPError as err:
                assert err.code == 400
                err_body = json.loads(err.read().decode("utf-8"))
                assert err_body["success"] is False
                assert "Dispositivo audio non disponibile" in err_body["error"]

    finally:
        server.shutdown()
        server.server_close()


def test_bridge_speech_status_endpoint(tmp_path, monkeypatch):
    """Verifica l'endpoint GET /api/speech/status per monitorare lo stato di registrazione e processing."""
    test_db = tmp_path / "test_bridge_speech_status.db"

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
        # 1. Stato iniziale a riposo (idle)
        monkeypatch.setattr(
            "src.services.bridge_server._transcription_status",
            {"is_recording": False, "is_processing": False, "text": "", "error": ""},
        )
        req_idle = request.Request(f"http://127.0.0.1:{port}/api/speech/status")
        with request.urlopen(req_idle) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["is_recording"] is False
            assert data["is_processing"] is False

        # 2. Stato in registrazione attiva
        monkeypatch.setattr(
            "src.services.bridge_server._transcription_status",
            {"is_recording": True, "is_processing": False, "text": "", "error": ""},
        )
        req_rec = request.Request(f"http://127.0.0.1:{port}/api/speech/status")
        with request.urlopen(req_rec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["is_recording"] is True
            assert data["is_processing"] is False

        # 3. Stato in elaborazione trascrizione (processing)
        monkeypatch.setattr(
            "src.services.bridge_server._transcription_status",
            {"is_recording": False, "is_processing": True, "text": "", "error": ""},
        )
        req_proc = request.Request(f"http://127.0.0.1:{port}/api/speech/status")
        with request.urlopen(req_proc) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["is_recording"] is False
            assert data["is_processing"] is True

    finally:
        server.shutdown()
        server.server_close()


def test_bridge_start_voice_recording_normalization(monkeypatch):
    """Verifica che _start_voice_recording normalizzi correttamente le lingue e le passi a SpeechTranscriber."""
    import src.services.bridge_server as bs

    monkeypatch.setattr("src.services.bridge_server._active_transcriber", None)
    monkeypatch.setattr(
        "src.services.bridge_server._transcription_status",
        {"is_recording": False, "is_processing": False, "text": "", "error": ""},
    )

    mock_transcriber = MagicMock()
    mock_transcriber.is_recording = False

    # 1. Inoltro lingua inglese esplicita "en-US"
    with patch("src.speech_helper.SpeechTranscriber", return_value=mock_transcriber):
        ok, msg = bs._start_voice_recording(language="en-US")
        assert ok is True
        assert msg == "started"
        assert mock_transcriber.start.call_args.kwargs.get("language") == "en-US"

    bs._active_transcriber = None

    # 2. Normalizzazione prefisso "en" -> "en-US"
    with patch("src.speech_helper.SpeechTranscriber", return_value=mock_transcriber):
        ok, msg = bs._start_voice_recording(language="en")
        assert ok is True
        assert msg == "started"
        assert mock_transcriber.start.call_args.kwargs.get("language") == "en-US"

    bs._active_transcriber = None

    # 3. Inoltro lingua italiana "it-IT"
    with patch("src.speech_helper.SpeechTranscriber", return_value=mock_transcriber):
        ok, msg = bs._start_voice_recording(language="it-IT")
        assert ok is True
        assert msg == "started"
        assert mock_transcriber.start.call_args.kwargs.get("language") == "it-IT"

    bs._active_transcriber = None

    # 4. Fallback deterministico per valori nulli, vuoti o non supportati -> "it-IT"
    with patch("src.speech_helper.SpeechTranscriber", return_value=mock_transcriber):
        ok, msg = bs._start_voice_recording(language="")
        assert ok is True
        assert msg == "started"
        assert mock_transcriber.start.call_args.kwargs.get("language") == "it-IT"


def test_gemini_transcription_empty_and_malformed_payload_resilience():
    """Verifica la resilienza di _transcribe_with_gemini a payload vuoti o malformati (IndexError/AttributeError)."""
    from src.speech_helper import _transcribe_with_gemini

    def _mock_http_with_payload(payload_dict):
        mock_conn = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload_dict).encode("utf-8")
        mock_conn.getresponse.return_value = mock_resp
        return patch("http.client.HTTPSConnection", return_value=mock_conn)

    # 1. Payload con lista parts vuota (es. finishReason: SAFETY) -> non deve sollevare IndexError
    with _mock_http_with_payload({"candidates": [{"content": {"parts": []}, "finishReason": "SAFETY"}]}):
        res = _transcribe_with_gemini(b"RIFF...", "TEST_KEY", language="it-IT")
        assert res is None, f"Atteso None per parts vuote, ottenuto {res!r}"

    # 2. Payload con campo text nullo (None) -> non deve sollevare AttributeError
    with _mock_http_with_payload({"candidates": [{"content": {"parts": [{"text": None}]}}]}):
        res = _transcribe_with_gemini(b"RIFF...", "TEST_KEY", language="it-IT")
        assert res is None, f"Atteso None per text None, ottenuto {res!r}"

    # 3. Payload con campo text non stringa (es. numero intero) -> non deve sollevare AttributeError
    with _mock_http_with_payload({"candidates": [{"content": {"parts": [{"text": 12345}]}}]}):
        res = _transcribe_with_gemini(b"RIFF...", "TEST_KEY", language="it-IT")
        assert res is None, f"Atteso None per text non stringa, ottenuto {res!r}"

    # 4. Payload con dizionario part vuoto (senza chiave text) -> non deve sollevare eccezioni
    with _mock_http_with_payload({"candidates": [{"content": {"parts": [{}]}}]}):
        res = _transcribe_with_gemini(b"RIFF...", "TEST_KEY", language="it-IT")
        assert res is None, f"Atteso None per part senza text, ottenuto {res!r}"

    # 5. Payload con text contenente solo spazi vuoti -> restituisce None
    with _mock_http_with_payload({"candidates": [{"content": {"parts": [{"text": "   \n\t  "}]}}]}):
        res = _transcribe_with_gemini(b"RIFF...", "TEST_KEY", language="it-IT")
        assert res is None, f"Atteso None per text con soli spazi, ottenuto {res!r}"

    # 6. Payload con candidati vuoti o assenza di content -> restituisce None senza errori
    with _mock_http_with_payload({"candidates": []}):
        assert _transcribe_with_gemini(b"RIFF...", "TEST_KEY", language="it-IT") is None
    with _mock_http_with_payload({"candidates": [{"finishReason": "SAFETY"}]}):
        assert _transcribe_with_gemini(b"RIFF...", "TEST_KEY", language="it-IT") is None

    # 7. Payload con struttura non dizionario o None
    with _mock_http_with_payload([{"candidates": []}]):
        assert _transcribe_with_gemini(b"RIFF...", "TEST_KEY", language="it-IT") is None
    with _mock_http_with_payload(None):
        assert _transcribe_with_gemini(b"RIFF...", "TEST_KEY", language="it-IT") is None

    # 8. Payload multipart con blocco di ragionamento (thought) e trascrizione finale
    payload_thinking = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"thought": True, "text": "Ragionamento interno"},
                        {"text": "Trascrizione effettiva"},
                    ]
                }
            }
        ]
    }
    with _mock_http_with_payload(payload_thinking):
        res = _transcribe_with_gemini(b"RIFF...", "TEST_KEY", language="it-IT")
        assert res == "Trascrizione effettiva"

    # 9. Payload valido standard -> estrae correttamente il testo ripulito da spazi
    with _mock_http_with_payload({"candidates": [{"content": {"parts": [{"text": "  Scarpa Nike Air  "}]}}]}):
        res = _transcribe_with_gemini(b"RIFF...", "TEST_KEY", language="it-IT")
        assert res == "Scarpa Nike Air", f"Atteso 'Scarpa Nike Air', ottenuto {res!r}"


def test_speech_transcriber_fallback_preservation_on_gemini_none():
    """Verifica che il fallback a Google Speech Recognition venga preservato ed eseguito quando Gemini restituisce None."""
    import numpy as np
    import sounddevice as sd
    import speech_recognition as sr

    from src.speech_helper import SpeechTranscriber

    def _create_mock_stream(transcriber):
        def fake_stream(*args, **kwargs):
            cb = kwargs.get("callback")
            mock = MagicMock()

            def _enter():
                if cb:
                    fake_audio = np.zeros((1600, 1), dtype=np.int16)
                    fake_audio[100:200] = 1000
                    cb(fake_audio, 1600, None, 0)
                transcriber._stop_event.set()
                return mock

            mock.__enter__.side_effect = _enter
            mock.__exit__.return_value = None
            return mock

        return fake_stream

    # Sub-caso 1: Gemini restituisce None -> il fallback a Google Speech Recognition viene eseguito
    transcriber = SpeechTranscriber()
    results = []
    errors = []

    with (
        patch.object(sd, "InputStream", side_effect=_create_mock_stream(transcriber)),
        patch.object(sr, "Recognizer") as mock_sr,
        patch.object(sr, "AudioData"),
        patch("src.speech_helper._transcribe_with_gemini", return_value=None) as mock_gemini,
    ):
        mock_rec = MagicMock()
        mock_rec.recognize_google.return_value = "scarpa jordan 4"
        mock_sr.return_value = mock_rec

        transcriber.start(
            on_result=lambda t: results.append(t),
            on_error=lambda e: errors.append(e),
            on_listening=lambda: None,
            api_key="TEST_API_KEY",
            language="en-US",
        )
        transcriber._thread.join(timeout=1.0)

        assert results == ["scarpa jordan 4"]
        assert errors == []
        mock_gemini.assert_called_once()
        mock_rec.recognize_google.assert_called_once()
        assert mock_rec.recognize_google.call_args.kwargs.get("language") == "en-US"

    # Sub-caso 2: Gemini restituisce un testo valido -> il fallback Google non viene invocato
    transcriber2 = SpeechTranscriber()
    results2 = []
    errors2 = []

    with (
        patch.object(sd, "InputStream", side_effect=_create_mock_stream(transcriber2)),
        patch.object(sr, "Recognizer") as mock_sr2,
        patch.object(sr, "AudioData"),
        patch("src.speech_helper._transcribe_with_gemini", return_value="scarpa gemini diretta") as mock_gemini2,
    ):
        mock_rec2 = MagicMock()
        mock_rec2.recognize_google.return_value = "non deve essere chiamato"
        mock_sr2.return_value = mock_rec2

        transcriber2.start(
            on_result=lambda t: results2.append(t),
            on_error=lambda e: errors2.append(e),
            on_listening=lambda: None,
            api_key="TEST_API_KEY",
            language="it-IT",
        )
        transcriber2._thread.join(timeout=1.0)

        assert results2 == ["scarpa gemini diretta"]
        assert errors2 == []
        mock_gemini2.assert_called_once()
        mock_rec2.recognize_google.assert_not_called()


def test_speech_transcriber_empty_parts_regression_end_to_end():
    """Test di regressione end-to-end: un payload Gemini con parts: [] non deve bloccare il fallback Google."""
    import numpy as np
    import sounddevice as sd
    import speech_recognition as sr

    from src.speech_helper import SpeechTranscriber

    def _create_mock_stream(transcriber):
        def fake_stream(*args, **kwargs):
            cb = kwargs.get("callback")
            mock = MagicMock()

            def _enter():
                if cb:
                    fake_audio = np.zeros((1600, 1), dtype=np.int16)
                    fake_audio[100:200] = 1000
                    cb(fake_audio, 1600, None, 0)
                transcriber._stop_event.set()
                return mock

            mock.__enter__.side_effect = _enter
            mock.__exit__.return_value = None
            return mock

        return fake_stream

    transcriber = SpeechTranscriber()
    results = []
    errors = []

    # Mock risposta HTTP Gemini con blocco di sicurezza (parts vuoto come nel caso Challenger 1)
    mock_conn = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(
        {"candidates": [{"content": {"parts": []}, "finishReason": "SAFETY"}]}
    ).encode("utf-8")
    mock_conn.getresponse.return_value = mock_resp

    with (
        patch.object(sd, "InputStream", side_effect=_create_mock_stream(transcriber)),
        patch.object(sr, "Recognizer") as mock_sr,
        patch.object(sr, "AudioData"),
        patch("http.client.HTTPSConnection", return_value=mock_conn),
    ):
        mock_rec = MagicMock()
        mock_rec.recognize_google.return_value = "fallback vocale riuscito"
        mock_sr.return_value = mock_rec

        transcriber.start(
            on_result=lambda t: results.append(t),
            on_error=lambda e: errors.append(e),
            on_listening=lambda: None,
            api_key="TEST_KEY",
            language="it-IT",
        )
        transcriber._thread.join(timeout=1.0)

        # Il fallback a Google deve essere chiamato e on_error non deve essere invocato
        assert results == ["fallback vocale riuscito"]
        assert errors == []
        mock_rec.recognize_google.assert_called_once()


def test_bridge_speech_adversarial_guards(tmp_path):
    """Verifica che body non-dict, liste vuote nei parametri query e valori nulli siano gestiti in sicurezza."""
    test_db = tmp_path / "test_bridge_adversarial.db"

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
        # 1. Body non-dict (array JSON [1, 2, 3]) su POST /api/speech/start
        with patch("src.services.bridge_server._start_voice_recording", return_value=(True, "started")) as mock_rec:
            req_array = request.Request(
                f"http://127.0.0.1:{port}/api/speech/start",
                data=b"[1, 2, 3]",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req_array) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                assert data["success"] is True
                # Con body non dizionario, la lingua deve ripiegare su "it-IT"
                mock_rec.assert_called_once()
                call_lang = mock_rec.call_args.kwargs.get("language")
                if not call_lang and mock_rec.call_args.args:
                    call_lang = mock_rec.call_args.args[0]
                assert call_lang == "it-IT"

        # 2. Body con language array ["en-US"] su POST /api/speech/start
        with patch("src.services.bridge_server._start_voice_recording", return_value=(True, "started")) as mock_rec:
            req_arr_lang = request.Request(
                f"http://127.0.0.1:{port}/api/speech/start",
                data=json.dumps({"language": ["en-US"]}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req_arr_lang) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                assert data["success"] is True
                call_lang = mock_rec.call_args.kwargs.get("language")
                if not call_lang and mock_rec.call_args.args:
                    call_lang = mock_rec.call_args.args[0]
                assert call_lang == "en-US"

        # 3. Parametri query vuoti (es. ?language=) su POST /api/speech/start
        with patch("src.services.bridge_server._start_voice_recording", return_value=(True, "started")) as mock_rec:
            req_empty_q = request.Request(
                f"http://127.0.0.1:{port}/api/speech/start?language=",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req_empty_q) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                assert data["success"] is True
                call_lang = mock_rec.call_args.kwargs.get("language")
                if not call_lang and mock_rec.call_args.args:
                    call_lang = mock_rec.call_args.args[0]
                assert call_lang == "it-IT"

        # 4. POST /api/settings con valori nulli non deve sollevare AttributeError
        req_settings = request.Request(
            f"http://127.0.0.1:{port}/api/settings",
            data=json.dumps({"email_sync_address": None, "packlink_api_key": None}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req_settings) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True

        # 5. POST /api/products/bulk-status con ids scalare (non-list) non deve sollevare TypeError
        req_bulk = request.Request(
            f"http://127.0.0.1:{port}/api/products/bulk-status",
            data=json.dumps({"ids": 12345, "status": "completed"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            request.urlopen(req_bulk)
            raise AssertionError("Doveva restituire errore 400 per assenza di ID validi")
        except HTTPError as err:
            assert err.code == 400
            err_body = json.loads(err.read().decode("utf-8"))
            assert err_body["success"] is False
            assert "Nessun ID prodotto fornito" in err_body["error"]

    finally:
        server.shutdown()
        server.server_close()



