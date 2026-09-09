import csv
import sqlite3
from decimal import Decimal
from pathlib import Path

from src.config import STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK
from src.database import InventoryDatabase
from src.ui.main_window import InventoryApp
from src.utils import calculate_profit, export_to_csv, read_spreadsheet_raw, parse_int, parse_money


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
    assert calculate_profit(Decimal("100"), Decimal("0"), Decimal("5"), 2)[0] == Decimal("-210.00")
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


def test_sort_tree_is_defined():
    class FakeTree:
        def __init__(self):
            self.rows = {"a": {"name": "Zeta"}, "b": {"name": "Alpha"}}
            self.moves = []

        def set(self, item, column):
            return self.rows[item][column]

        def get_children(self, _root):
            return tuple(self.rows)

        def move(self, item, _parent, _index):
            self.moves.append(item)

    fake_tree = FakeTree()
    controller = type("Controller", (), {"trees": {STATUS_STOCK: fake_tree}, "current_sort": {}})()
    InventoryApp.sort_tree(controller, STATUS_STOCK, "name")
    assert fake_tree.moves == ["b", "a"]


def test_table_shows_only_compact_columns():
    assert "id" not in InventoryApp.COLUMNS
    assert "selling_price" not in InventoryApp.COLUMNS
    assert "release_date" not in InventoryApp.COLUMNS
    assert "sale_price" in InventoryApp.COLUMNS
    assert len(InventoryApp.COLUMNS) == 11


def test_email_sync_html_stripper():
    from src.email_sync import _strip_html
    raw_html = "<html><body><h1>Conferma Ordine Nike</h1><p>Hai acquistato <b>Dunk Low</b> a &euro; 120,00.</p></body></html>"
    clean = _strip_html(raw_html)
    assert "Conferma Ordine Nike" in clean
    assert "Dunk Low" in clean
    assert "120,00" in clean
    assert "<" not in clean


def test_email_sync_dialog_initialization(tmp_path):
    from src.ui.email_sync_dialog import EmailSyncDialog
    db = InventoryDatabase(tmp_path / "test_email.db")
    db.set_setting("email_sync_address", "test@gmail.com")
    db.set_setting("email_sync_app_password", "abcdefghijklmnop")
    
    app = InventoryApp()
    app.update_idletasks()
    
    dialog = EmailSyncDialog(app, db, lambda: None)
    dialog.update_idletasks()
    assert dialog.var_email.get() == "test@gmail.com"
    assert dialog.var_password.get() == "abcdefghijklmnop"
    
    dialog.destroy()
    app.destroy()
    db.close()


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
        "sold_price": None, "fees": Decimal("0"), "sold_date": "",
        "status": STATUS_STOCK, "release_date": "", "notes": ""
    })
    db.save({
        "name": "Yeezy Slide", "size": "42", "quantity": 1,
        "purchased_price": Decimal("70.00"), "purchased_place": "Confirmed",
        "selling_place": "", "selling_price": Decimal("110.00"),
        "sold_price": None, "fees": Decimal("0"), "sold_date": "",
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


def test_undo_stack_limit_and_actions(tmp_path):
    """Verifica che l'undo stack rispetti il limite massimo di 10 azioni e ripristini correttamente i record."""
    db = InventoryDatabase(tmp_path / "test_undo.db")
    status_var = type("Var", (), {"set": lambda self, v: None})()
    
    app_stub = type("AppStub", (), {
        "_undo_stack": [],
        "db": db,
        "status_bar_var": status_var,
        "refresh": lambda self: None,
        "_push_undo": InventoryApp._push_undo,
        "undo": InventoryApp.undo,
        "_undo_insert": InventoryApp._undo_insert,
        "_undo_update": InventoryApp._undo_update,
        "_undo_delete": InventoryApp._undo_delete,
    })()

    # Inseriamo un prodotto
    pid = db.save({
        "name": "Articolo Originale", "size": "42", "quantity": 1,
        "purchased_price": Decimal("100.00"), "purchased_place": "Store",
        "selling_place": "", "selling_price": None, "sold_price": None,
        "fees": Decimal("0"), "sold_date": "", "status": STATUS_STOCK,
        "release_date": "", "notes": ""
    })
    app_stub._push_undo("Aggiunto articolo", lambda nids=[pid]: app_stub._undo_insert(nids))
    assert len(app_stub._undo_stack) == 1

    # Verifichiamo il limite massimo di 10 elementi
    for i in range(15):
        app_stub._push_undo(f"Azione {i}", lambda: None)
    assert len(app_stub._undo_stack) == 10

    # Test eliminazione e ripristino con undo
    app_stub._undo_stack.clear()
    old_rec = dict(db.get(pid))
    db.delete_many([pid])
    assert db.get(pid) is None

    app_stub._push_undo("Eliminato", lambda recs=[old_rec]: app_stub._undo_delete(recs))
    app_stub.undo()
    
    # Il prodotto è stato ripristinato
    prods = db.list_products()
    assert len(prods) == 1
    assert prods[0]["name"] == "Articolo Originale"

    db.close()

