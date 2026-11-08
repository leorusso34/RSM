"""Livello 6: Undo Vendita Parziale (Ctrl+Z) & Pulizia Record Duplicati.

Verifiche:
1. Creazione di un prodotto con quantità multipla in magazzino (Stock: 5 pz, € 180,00 cad., Nike SNKRS).
2. Messa in vendita parziale (2 pz su 5 a € 260,00 su StockX) tramite menu contestuale (#ctxItemSell) e modale (#bulkSaleModal).
3. Verifica dello split di quantità tra le viste:
   - Scheda 'Vendite Attive': nuovo record generato con quantità 2 pz e canale StockX.
   - Scheda 'Magazzino': il record originale conserva la rimanenza di 3 pz (5 - 2 = 3).
4. Esecuzione del comando Annulla da tastiera tramite combinazione Ctrl+Z.
5. Asserzione di ripristino e pulizia record generati:
   - Notifica toast di conferma annullamento ('Annullato: Messa in vendita').
   - Scheda 'Magazzino': il record originale è ripristinato alla quantità piena originaria (5 pz).
   - Scheda 'Vendite Attive': il record generato per la vendita parziale è stato completamente eliminato (zero duplicati orfani).
   - La tabella vendite attive ritorna allo stato vuoto ('Nessun prodotto trovato').
6. Audit console (0 errori JavaScript).
7. Checkpoint visivo: screenshot level6_undo_partial_sale.png e registrazione video level6_undo_partial_sale.webm.
"""

from typing import Any

from playwright.sync_api import Page, expect

from tests.e2e.conftest import SANDBOX_BASE_URL, SCREENSHOTS_DIR


def run_level6_undo_partial_sale_checks(page: Page, console_errors: list[str]) -> dict[str, Any]:
    """Esegue tutte le asserzioni e i controlli del Livello 6 (Undo Vendita Parziale)."""
    details = []

    # 1. Navigazione e pulizia contesto
    page.goto(SANDBOX_BASE_URL, wait_until="networkidle")
    page.wait_for_selector(".table-card", timeout=5000)
    page.click('button.table-tab-pill[data-filter="stock"]')
    page.wait_for_timeout(400)

    # 2. Creazione prodotto con quantità multipla (5 pezzi) in magazzino
    page.click(".btn-sidebar-add")
    page.wait_for_selector("#productModal.open", timeout=5000)
    page.locator("#prod-name").press_sequentially("Air Jordan 1 Lost and Found", delay=25)
    page.locator("#prod-size").press_sequentially("43", delay=25)
    page.fill("#prod-qty", "5")
    page.locator("#prod-buy-price").press_sequentially("180.00", delay=25)
    page.locator("#prod-buy-place").press_sequentially("Nike SNKRS", delay=25)
    page.click("#productForm button.btn-primary")
    page.wait_for_selector("#productModal", state="hidden", timeout=5000)
    page.wait_for_selector("#inventory-table-body tr", timeout=5000)
    page.wait_for_timeout(600)

    # Verifica comparsa in magazzino con 5 pz
    stock_row = page.locator("#inventory-table-body tr:has-text('Air Jordan 1 Lost and Found')")
    expect(stock_row).to_be_visible(timeout=5000)
    expect(stock_row).to_contain_text("5 pz")
    details.append("Prodotto creato in magazzino con 5 pezzi ('Air Jordan 1 Lost and Found', € 180,00 cad.)")

    # 3. Messa in vendita parziale di 2 pezzi su 5
    stock_row.click(button="right")
    page.wait_for_selector("#tableContextMenu", state="visible", timeout=5000)
    page.click("#ctxItemSell")
    page.wait_for_selector("#bulkSaleModal.open", timeout=5000)
    page.wait_for_timeout(500)

    # Verifica e selezione della quantità parziale nel menu a tendina
    expect(page.locator("#bulk-sale-qty-group")).to_be_visible(timeout=3000)
    page.select_option("#bulk-sale-qty-select", "2")
    page.fill("#bulk-sale-total-price", "260.00")
    page.fill("#bulk-sale-place", "StockX")
    page.wait_for_timeout(400)

    # Invio del form di vendita
    page.click('#bulkSaleForm button[type="submit"]')
    page.wait_for_selector("#bulkSaleModal", state="hidden", timeout=5000)
    page.wait_for_timeout(800)
    details.append("Vendita parziale confermata: 2 pz su 5 messi in vendita a € 260,00 su StockX")

    # 4. Verifica dello split di quantità tra le viste prima di eseguire l'Undo
    # A) Vendite Attive: presenza del nuovo record generato per i 2 pezzi
    page.click('button.table-tab-pill[data-filter="active-sale"]')
    page.wait_for_timeout(500)
    active_row = page.locator("#inventory-table-body tr:has-text('Air Jordan 1 Lost and Found')")
    expect(active_row).to_be_visible(timeout=5000)
    expect(active_row).to_contain_text("2 pz")
    expect(active_row).to_contain_text("StockX")
    details.append("Scheda 'Vendite Attive': nuovo record generato presente con quantità 2 pz su StockX")

    # B) Magazzino: il record originale conserva i 3 pezzi rimanenti (5 - 2 = 3)
    page.click('button.table-tab-pill[data-filter="stock"]')
    page.wait_for_timeout(500)
    stock_remaining_row = page.locator("#inventory-table-body tr:has-text('Air Jordan 1 Lost and Found')")
    expect(stock_remaining_row).to_be_visible(timeout=5000)
    expect(stock_remaining_row).to_contain_text("3 pz")
    details.append("Scheda 'Magazzino': record originale aggiornato correttamente a 3 pz rimanenti")

    # 5. Esecuzione del comando Annulla (Ctrl+Z) da tastiera
    page.keyboard.press("Control+z")

    # Verifica toast notifica di annullamento
    toast = page.locator("#toastNotification")
    expect(toast).to_contain_text("Annullato", timeout=6000)
    page.wait_for_timeout(600)
    details.append("Scorciatoia Ctrl+Z premuta: toast di annullamento confermato")

    # 6. Asserzione post-Undo: ripristino quantità e cancellazione record vendita
    # A) In Magazzino la quantità deve essere tornata a 5 pz pieni
    page.click('button.table-tab-pill[data-filter="stock"]')
    page.wait_for_timeout(500)
    restored_stock_row = page.locator("#inventory-table-body tr:has-text('Air Jordan 1 Lost and Found')")
    expect(restored_stock_row).to_be_visible(timeout=5000)
    expect(restored_stock_row).to_contain_text("5 pz")
    details.append("Scheda 'Magazzino': quantità originale ripristinata a 5 pz pieni")

    # B) In Vendite Attive il record generato per la vendita deve essere stato eliminato (zero duplicati orfani)
    page.click('button.table-tab-pill[data-filter="active-sale"]')
    page.wait_for_timeout(500)
    empty_state = page.locator("#inventory-table-body")
    expect(empty_state).to_contain_text("Nessun prodotto trovato", timeout=5000)
    orphan_rows = page.locator("#inventory-table-body tr:has-text('Air Jordan 1 Lost and Found')")
    assert orphan_rows.count() == 0, f"Rilevati record vendita orfani in Vendite Attive: count={orphan_rows.count()}"
    details.append("Scheda 'Vendite Attive': record di vendita parziale completamente rimosso (zero duplicati orfani)")

    # 7. Audit errori console JavaScript
    assert len(console_errors) == 0, f"Rilevati errori JavaScript in console: {console_errors}"
    details.append("Audit console superato: 0 errori JavaScript rilevati")

    # 8. Checkpoint visivo screenshot
    screenshot_path = SCREENSHOTS_DIR / "level6_undo_partial_sale.png"
    page.screenshot(path=str(screenshot_path), full_page=False)
    details.append(f"Screenshot salvato: {screenshot_path.name}")

    return {
        "passed": True,
        "details": details,
        "screenshot_path": screenshot_path,
    }


def test_level6_undo_partial_sale_pytest(sandbox_server: Any) -> None:
    """Entry point compatibile con pytest."""
    from playwright.sync_api import sync_playwright

    from tests.e2e.conftest import E2EContextManager

    with sync_playwright() as p, E2EContextManager(p, "level6_undo_partial_sale") as (page, console_errors):
        res = run_level6_undo_partial_sale_checks(page, console_errors)
        assert res["passed"] is True
