import csv
import sqlite3
from decimal import Decimal

from src.config import STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK
from src.database import InventoryDatabase
from src.utils import (
    calculate_profit,
    export_to_csv,
    format_month_label,
    parse_int,
    parse_money,
    read_spreadsheet_raw,
)


def product(name="Test", status=STATUS_STOCK):
    return {
        "name": name, "size": "42", "quantity": 2,
        "purchased_price": Decimal("100.00"), "purchased_place": "Shop",
        "selling_place": "Market", "selling_price": Decimal("150.00"),
        "sold_price": Decimal("145.00") if status == STATUS_SOLD else None,
        "fees": Decimal("5.00"), "sold_date": "2026-08-26" if status == STATUS_SOLD else "",
        "status": status, "release_date": "2026-09-01" if status == STATUS_PREORDER else "",
        "notes": "",
    }


def test_money_and_profit_are_strict():
    assert parse_money("€ 12,50") == Decimal("12.50")
    assert parse_money("1.234") == Decimal("1234.00")
    assert calculate_profit(Decimal(100), Decimal(0), Decimal(5), 2)[0] == Decimal("-205.00")
    # Prodotto a costo zero (es. regalo/omaggio venduto a 50€ con 2€ fees)
    profit_zero_cost, roi_zero_cost = calculate_profit(Decimal("0.00"), Decimal("50.00"), Decimal("2.00"), 1)
    assert profit_zero_cost == Decimal("48.00")
    assert roi_zero_cost == Decimal("0.00")
    try:
        parse_money("abc100")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid money accepted")
    try:
        parse_int("0")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid quantity accepted")


def test_status_transition_clears_inapplicable_fields(tmp_path):
    db = InventoryDatabase(tmp_path / "inventory.db")
    product_id = db.save(product(status=STATUS_SOLD))
    db.update_status_many([product_id], STATUS_PREORDER)
    row = db.get(product_id)
    assert row["sold_price"] is None
    assert row["sold_date"] == ""
    assert row["fees"] == Decimal("0.00")
    db.close()


def test_backup_and_export(tmp_path):
    db = InventoryDatabase(tmp_path / "inventory.db")
    db.save(product())
    backup = tmp_path / "backup.db"
    db.backup_database_safe(backup)
    db.close()
    backup_db = sqlite3.connect(backup)
    assert backup_db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 1
    backup_db.close()
    csv_path = tmp_path / "export.csv"
    export_to_csv(str(csv_path), [product()])
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        assert next(csv.reader(handle, delimiter=";"))[0] == "ID"


def test_read_spreadsheet_raw_xlsx(tmp_path):
    """Verifica che read_spreadsheet_raw legga qualsiasi .xlsx restituendo testo grezzo."""
    openpyxl = __import__("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Inventario"
    sheet.append(["Nome Prodotto", "Prezzo", "Quantita", "Stato"])
    sheet.append(["Nike Air Max", 120.00, 2, "Magazzino"])
    sheet.append(["Adidas Yeezy", 250.00, 1, "Pre-ordine"])
    path = tmp_path / "test_import.xlsx"
    workbook.save(path)

    raw = read_spreadsheet_raw(str(path))
    assert "Nike Air Max" in raw
    assert "Adidas Yeezy" in raw
    assert "Inventario" in raw  # Il nome del foglio è incluso
    assert "120" in raw
    assert "250" in raw


def test_read_spreadsheet_raw_csv(tmp_path):
    """Verifica che read_spreadsheet_raw legga anche file .csv."""
    csv_path = tmp_path / "test_import.csv"
    csv_path.write_text("Nome,Prezzo,Quantita\nNike Dunk,90.00,1\nJordan 1,180.00,3\n", encoding="utf-8")

    raw = read_spreadsheet_raw(str(csv_path))
    assert "Nike Dunk" in raw
    assert "Jordan 1" in raw
    assert "90" in raw




def test_email_sync_html_stripper():
    from src.email_sync import _strip_html
    raw_html = "<html><body><h1>Conferma Ordine Nike</h1><p>Hai acquistato <b>Dunk Low</b> a &euro; 120,00.</p></body></html>"
    clean = _strip_html(raw_html)
    assert "Conferma Ordine Nike" in clean
    assert "Dunk Low" in clean
    assert "120,00" in clean
    assert "<" not in clean




def test_external_config_json_priority(tmp_path, monkeypatch):
    import json

    from src import database
    fake_config = tmp_path / "config.json"
    fake_config.write_text(json.dumps({"gemini_api_key": "KEY_FROM_JSON"}), encoding="utf-8")
    monkeypatch.setattr(database, "CONFIG_JSON_PATH", fake_config)
    
    db = InventoryDatabase(tmp_path / "test.db")
    # DB has another value
    with db.connection:
        db.connection.execute("INSERT INTO settings (key, value) VALUES ('gemini_api_key', 'KEY_FROM_DB')")
    
    # JSON has priority!
    assert db.get_setting("gemini_api_key") == "KEY_FROM_JSON"
    db.close()


def test_search_by_price(tmp_path):
    """Verifica che la ricerca trovi prodotti anche cercando per prezzo o frazioni di prezzo."""
    db = InventoryDatabase(tmp_path / "test_search.db")
    db.save({
        "name": "Jordan 4 Retro", "size": "43", "quantity": 1,
        "purchased_price": Decimal("210.50"), "purchased_place": "SNKRS",
        "selling_place": "", "selling_price": Decimal("350.00"),
        "sold_price": None, "fees": Decimal(0), "sold_date": "",
        "status": STATUS_STOCK, "release_date": "", "notes": ""
    })
    db.save({
        "name": "Yeezy Slide", "size": "42", "quantity": 1,
        "purchased_price": Decimal("70.00"), "purchased_place": "Confirmed",
        "selling_place": "", "selling_price": Decimal("110.00"),
        "sold_price": None, "fees": Decimal(0), "sold_date": "",
        "status": STATUS_STOCK, "release_date": "", "notes": ""
    })

    # Ricerca per prezzo intero
    res_70 = db.list_products(search="70")
    assert len(res_70) == 1
    assert res_70[0]["name"] == "Yeezy Slide"

    # Ricerca per decimale con virgola
    res_comma = db.list_products(search="210,50")
    assert len(res_comma) == 1
    assert res_comma[0]["name"] == "Jordan 4 Retro"

    # Ricerca per decimale con punto
    res_dot = db.list_products(search="210.50")
    assert len(res_dot) == 1
    assert res_dot[0]["name"] == "Jordan 4 Retro"

    # Ricerca con simbolo valuta
    res_curr = db.list_products(search="€ 350")
    assert len(res_curr) == 1
    assert res_curr[0]["name"] == "Jordan 4 Retro"

    # Ricerca per nome continua a funzionare
    res_name = db.list_products(search="Yeezy")
    assert len(res_name) == 1
    assert res_name[0]["name"] == "Yeezy Slide"

    db.close()




def test_safe_parse_json_products_truncated():
    """Verifica che il parser gestisca sia JSON standard sia JSON troncati dall'AI."""
    from src.ai_agent import _safe_parse_json_products

    # 1. JSON integro in blocco markdown
    normal_json = "```json\n{\"products\": [{\"name\": \"Prodotto A\", \"purchased_price\": 50.0}]}\n```"
    res1 = _safe_parse_json_products(normal_json)
    assert len(res1) == 1
    assert res1[0]["name"] == "Prodotto A"

    # 2. JSON troncato a metà stringa (come nel caso di superamento limiti token)
    truncated_json = '{"products": [{"name": "Prodotto 1", "purchased_price": 10.0}, {"name": "Prodotto 2", "purchased_price": 20.0}, {"name": "Prodotto 3", "purchased_'
    res2 = _safe_parse_json_products(truncated_json)
    assert len(res2) == 2
    assert res2[0]["name"] == "Prodotto 1"
    assert res2[1]["name"] == "Prodotto 2"


def test_partial_sale_splits_record(tmp_path):
    """Verifica la logica DB della vendita parziale:
    vendere k pezzi su N deve creare un nuovo record vendita (qty=k)
    e lasciare il record originale con qty=N-k nello stesso status."""
    from decimal import Decimal

    from src.config import STATUS_SOLD, STATUS_STOCK

    db = InventoryDatabase(tmp_path / "inventory.db")

    # Prodotto originale: 5 pezzi in magazzino
    original_qty = 5
    sold_qty = 2
    remaining_qty = original_qty - sold_qty

    prod_id = db.save({
        "name": "Scarpa Test", "size": "42", "quantity": original_qty,
        "purchased_price": Decimal("80.00"), "purchased_place": "Shop",
        "selling_place": "eBay", "selling_price": Decimal("120.00"),
        "sold_price": None, "fees": Decimal("0.00"),
        "sold_date": "", "status": STATUS_STOCK, "release_date": "", "notes": "",
    })

    # Simulazione della logica di move_selected_to_sold (vendita parziale)
    record = dict(db.get(prod_id))
    new_sold_record = dict(record)
    new_sold_record.pop("id", None)
    new_sold_record["quantity"] = sold_qty
    new_sold_record["status"] = STATUS_SOLD
    new_sold_record["sold_price"] = Decimal("115.00")
    new_sold_record["sold_date"] = "2026-09-10"

    new_id = db.save(new_sold_record)

    updated_original = dict(record)
    updated_original["quantity"] = remaining_qty
    db.save(updated_original, prod_id)

    # Verifica: il record originale ha la quantità decrementata
    original_after = db.get(prod_id)
    assert original_after["quantity"] == remaining_qty
    assert original_after["status"] == STATUS_STOCK

    # Verifica: il nuovo record di vendita è corretto
    sold_after = db.get(new_id)
    assert sold_after["quantity"] == sold_qty
    assert sold_after["status"] == STATUS_SOLD
    assert sold_after["name"] == "Scarpa Test"

    db.close()


def test_get_profit_by_platform(tmp_path):
    db = InventoryDatabase(tmp_path / "inventory.db")
    # Prodotto 1: venduto su eBay (2 pz, costo 50x2=100, incasso 160, fees totali 10 -> profitto 50)
    db.save({
        "name": "Prodotto eBay", "size": "M", "quantity": 2,
        "purchased_price": Decimal("50.00"), "purchased_place": "Shop",
        "selling_place": "eBay", "selling_price": Decimal("160.00"),
        "sold_price": Decimal("160.00"), "fees": Decimal("10.00"),
        "sold_date": "2026-09-01", "status": STATUS_SOLD, "release_date": "", "notes": "",
    })
    # Prodotto 2: venduto su Vinted (1 pz, costo 30, incasso 50, fees 0 -> profitto 20)
    db.save({
        "name": "Prodotto Vinted", "size": "L", "quantity": 1,
        "purchased_price": Decimal("30.00"), "purchased_place": "Shop",
        "selling_place": "Vinted", "selling_price": Decimal("50.00"),
        "sold_price": Decimal("50.00"), "fees": Decimal("0.00"),
        "sold_date": "2026-09-02", "status": STATUS_SOLD, "release_date": "", "notes": "",
    })
    # Prodotto 3: In stock (non deve essere incluso nel calcolo vendite)
    db.save({
        "name": "Prodotto Stock", "size": "S", "quantity": 1,
        "purchased_price": Decimal("20.00"), "purchased_place": "Shop",
        "selling_place": "eBay", "selling_price": Decimal("40.00"),
        "sold_price": None, "fees": Decimal("0.00"),
        "sold_date": "", "status": STATUS_STOCK, "release_date": "", "notes": "",
    })

    platforms = db.get_profit_by_platform()
    assert len(platforms) == 2
    ebay_data = next(p for p in platforms if p["platform"] == "eBay")
    vinted_data = next(p for p in platforms if p["platform"] == "Vinted")

    assert ebay_data["profit"] == Decimal("50.00")
    assert ebay_data["count"] == 2
    assert vinted_data["profit"] == Decimal("20.00")
    assert vinted_data["count"] == 1
    db.close()


def test_get_top_profitable_products(tmp_path):
    db = InventoryDatabase(tmp_path / "inventory.db")
    # Prodotto A: profitto 100
    db.save({
        "name": "Nike Jordan 1", "size": "42", "quantity": 1,
        "purchased_price": Decimal("100.00"), "purchased_place": "Shop",
        "selling_place": "eBay", "selling_price": Decimal("200.00"),
        "sold_price": Decimal("200.00"), "fees": Decimal("0.00"),
        "sold_date": "2026-09-01", "status": STATUS_SOLD, "release_date": "", "notes": "",
    })
    # Prodotto B: profitto 150 (2 pz con costo 50x2=100, incasso 260, fees totali 10 -> profitto 150)
    db.save({
        "name": "Rolex Submariner", "size": "UNI", "quantity": 2,
        "purchased_price": Decimal("50.00"), "purchased_place": "Shop",
        "selling_place": "Chrono24", "selling_price": Decimal("260.00"),
        "sold_price": Decimal("260.00"), "fees": Decimal("10.00"),
        "sold_date": "2026-09-02", "status": STATUS_SOLD, "release_date": "", "notes": "",
    })
    # Prodotto C: in stock (non venduto)
    db.save({
        "name": "Moneta Oro", "size": "UNI", "quantity": 1,
        "purchased_price": Decimal("50.00"), "purchased_place": "Shop",
        "selling_place": "Shop", "selling_price": Decimal("300.00"),
        "sold_price": None, "fees": Decimal("0.00"),
        "sold_date": "", "status": STATUS_STOCK, "release_date": "", "notes": "",
    })

    top = db.get_top_profitable_products(limit=5)
    assert len(top) == 2
    assert top[0]["name"] == "Rolex Submariner"
    assert top[0]["profit"] == Decimal("150.00")
    assert top[0]["count"] == 2

    assert top[1]["name"] == "Nike Jordan 1"
    assert top[1]["profit"] == Decimal("100.00")
    assert top[1]["count"] == 1
    db.close()


def test_format_month_label_and_csv_headers(tmp_path):
    assert format_month_label("2026-09") == "SET '26"
    assert format_month_label("2026-06") == "GIU '26"
    assert format_month_label("2026-01") == "GEN '26"
    assert format_month_label("2025-12-15") == "DIC '25"
    assert format_month_label("") == ""

    csv_file = tmp_path / "test_headers.csv"
    export_to_csv(str(csv_file), [product()])
    with csv_file.open(encoding="utf-8-sig", newline="") as handle:
        headers = next(csv.reader(handle, delimiter=";"))
        assert "PREZZO VENDITA TOTALE (PREVISTO)" in headers
        assert "PREZZO VENDITA TOTALE (EFFETTIVO)" in headers


def test_multiple_quantity_single_shipping_fees(tmp_path):
    """Verifica che la spedizione/fees rimanga singola e non venga moltiplicata per la quantita."""
    # 2 pezzi comprati a 100€ ciascuno (costo 200€), venduti a 250€ totali con 10€ di spedizione totale
    profit, roi = calculate_profit(
        purchased_price=Decimal("100.00"),
        sold_price=Decimal("250.00"),
        fees=Decimal("10.00"),
        quantity=2,
    )
    # Profitto atteso = 250 - (100 * 2) - 10 = 40€
    assert profit == Decimal("40.00")
    # ROI atteso = (40 / 200) * 100 = 20%
    assert roi == Decimal("20.00")

    # 3 pezzi comprati a 50€ ciascuno (costo 150€), venduti a 200€ con 15€ di spedizione totale
    profit_3, roi_3 = calculate_profit(
        purchased_price=Decimal("50.00"),
        sold_price=Decimal("200.00"),
        fees=Decimal("15.00"),
        quantity=3,
    )
    # Profitto atteso = 200 - (50 * 3) - 15 = 35€
    assert profit_3 == Decimal("35.00")
    assert roi_3 == Decimal("23.33")

    # Verifica nel DB
    db = InventoryDatabase(tmp_path / "inventory.db")
    db.save({
        "name": "Pacco 2 Prodotti", "size": "L", "quantity": 2,
        "purchased_price": Decimal("100.00"), "purchased_place": "Shop",
        "selling_place": "StockX", "selling_price": Decimal("250.00"),
        "sold_price": Decimal("250.00"), "fees": Decimal("10.00"),
        "sold_date": "2026-09-10", "status": STATUS_SOLD, "release_date": "", "notes": "",
    })

    t = db.totals()
    assert t["sold_profit"] == Decimal("40.00")
    assert t["sold_roi"] == Decimal("20.00")
    db.close()


def test_bulk_status_move_with_selling_place(tmp_path):
    """Verifica che lo spostamento di massa a STATUS_SOLD aggiorni correttamente il luogo di vendita."""
    db = InventoryDatabase(tmp_path / "inventory.db")
    d1 = product(name="P1", status=STATUS_STOCK)
    d1["selling_place"] = ""
    p1 = db.save(d1)

    d2 = product(name="P2", status=STATUS_STOCK)
    d2["selling_place"] = ""
    p2 = db.save(d2)

    extra_data = {
        "sold_price": Decimal("25.00"),
        "fees": Decimal("2.50"),
        "sold_date": "2026-09-26",
        "selling_place": "Vinted",
        "bundle_id": "bundle-1234",
    }
    db.update_status_many([p1, p2], STATUS_SOLD, extra_data=extra_data)

    r1 = db.get(p1)
    r2 = db.get(p2)
    assert r1["status"] == STATUS_SOLD
    assert r1["selling_place"] == "Vinted"
    assert r1["sold_date"] == "2026-09-26"
    assert r1["sold_price"] == Decimal("25.00")
    assert r1["bundle_id"] == "bundle-1234"

    assert r2["status"] == STATUS_SOLD
    assert r2["selling_place"] == "Vinted"
    assert r2["sold_date"] == "2026-09-26"
    assert r2["sold_price"] == Decimal("25.00")
    assert r2["bundle_id"] == "bundle-1234"
    db.close()





def test_cross_platform_config_app_directory(monkeypatch):
    """Verifica che app_directory gestisca correttamente bundle macOS .app e modalità standard."""
    import sys

    from src.config import app_directory

    # Simula eseguibile dentro un bundle macOS .app
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    fake_exe = "/Applications/RSM.app/Contents/MacOS/RSM"
    monkeypatch.setattr(sys, "executable", fake_exe)
    monkeypatch.setattr(sys, "platform", "darwin")

    dir_found = app_directory()
    assert dir_found.as_posix().endswith("/Applications")

    # Simula eseguibile Windows standard
    fake_win_exe = "C:/Program Files/RSM/RSM.exe"
    monkeypatch.setattr(sys, "executable", fake_win_exe)
    monkeypatch.setattr(sys, "platform", "win32")

    win_dir = app_directory()
    assert win_dir.as_posix().endswith("Program Files/RSM")





