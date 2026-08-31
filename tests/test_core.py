import csv
import sqlite3
from decimal import Decimal
from pathlib import Path

from src.config import STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK
from src.database import InventoryDatabase
from src.ui.main_window import InventoryApp
from src.utils import calculate_profit, export_to_csv, parse_excel_file, parse_int, parse_money


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


def test_excel_import_validates_dates(tmp_path):
    openpyxl = __import__("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["NOME", "PREZZO ACQUISTO", "DATA VENDITA", "STATO"])
    sheet.append(["Valid", 10, "2026-08-26", "Venduto"])
    sheet.append(["Valid2", 10, "26/08/2026", "Venduto"])
    sheet.append(["Invalid", 10, "NotADate", "Venduto"])
    path = tmp_path / "import.xlsx"
    workbook.save(path)
    records, skipped = parse_excel_file(path)
    assert len(records) == 2
    assert skipped == 1
    assert records[1]["sold_date"] == "2026-08-26"


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