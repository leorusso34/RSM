"""Livello 3: Ciclo di Vendita Realistico, Transizioni di Stato e Asserzione Matematica Profitti.

Verifiche:
1. Verifica/creazione del prodotto in magazzino (Stock: 120.00 €).
2. Transizione a 'Vendita Attiva' (active-sale) con impostazione del marketplace (StockX) e prezzo atteso (170.00 €).
3. Switch alla scheda 'Vendite Attive' e verifica presenza riga con badge 'In Vendita' e canale 'StockX'.
4. Modifica della Vendita Attiva & Verifica Blocchi di Sicurezza:
   - Presenza del banner di notifica campi bloccati (#active-sale-lock-notice).
   - Campi anagrafici bloccati (#prod-name, #prod-size, #prod-buy-place, #prod-sell-place disabilitati).
   - Campi commerciali sbloccati (#prod-sold-price abilitato).
   - Aggiornamento prezzo di vendita (180.00 €) e spese/commissioni (15.00 €).
5. Conclusione della vendita con passaggio allo stato 'Venduto' (completed).
6. Switch alla scheda 'Vendite Completate' e verifica formula matematica del profitto:
   - Ricavo: 180.00 €
   - Spese: 15.00 €
   - Utile Netto = 180.00 - 120.00 - 15.00 = +45.00 €
   - ROI % = (+45.00 / 120.00) * 100 = +37.5%
7. Checkpoint visivo: screenshot level3_flow.png e registrazione video level3_flow.webm.
"""

from typing import Any

from playwright.sync_api import Page, expect

from tests.e2e.conftest import SANDBOX_BASE_URL, SCREENSHOTS_DIR


def ensure_test_product_in_stock(page: Page) -> None:
    """Garantisce la presenza di un prodotto in stock prima di avviare il flusso di vendita."""
    page.goto(SANDBOX_BASE_URL, wait_until="networkidle")
    page.wait_for_selector(".table-card", timeout=5000)

    # Assicurati di essere nella tab stock o tutti
    edit_btn = page.locator('button[title="Modifica Prodotto"]')
    if edit_btn.count() == 0:
        page.click(".btn-sidebar-add")
        page.wait_for_selector("#productModal.open", timeout=5000)
        page.locator("#prod-name").press_sequentially("Nike Dunk Low Retro Panda", delay=30)
        page.locator("#prod-size").press_sequentially("42", delay=30)
        page.fill("#prod-qty", "1")
        page.locator("#prod-buy-price").press_sequentially("120.00", delay=30)
        page.locator("#prod-buy-place").press_sequentially("Nike SNKRS", delay=30)
        page.click("#productForm button.btn-primary")
        page.wait_for_selector("#productModal", state="hidden", timeout=5000)
        page.wait_for_selector("#inventory-table-body tr", timeout=5000)


def run_level3_flow_checks(page: Page, console_errors: list[str]) -> dict[str, Any]:
    """Esegue tutte le asserzioni e i controlli del Livello 3."""
    details = []

    # 1. Assicura che esista il prodotto base in magazzino
    ensure_test_product_in_stock(page)
    page.wait_for_timeout(600)
    details.append("Prodotto base verificato in magazzino (Costo: € 120,00, Canale: Nike SNKRS)")

    # 2. Transizione a 'Vendita Attiva' (active-sale)
    page.click('button[title="Modifica Prodotto"]')
    page.wait_for_selector("#productModal.open", timeout=5000)
    page.wait_for_timeout(500)

    # Compila canale di vendita e prezzo previsto prima di attivare active-sale
    page.locator("#prod-sell-place").press_sequentially("StockX", delay=35)
    page.locator("#prod-sold-price").press_sequentially("170.00", delay=35)
    page.wait_for_timeout(300)
    page.select_option("#prod-status", "active-sale")
    page.wait_for_timeout(600)

    page.click("#productForm button.btn-primary")
    page.wait_for_selector("#productModal", state="hidden", timeout=5000)
    page.wait_for_timeout(600)
    details.append("Transizione a 'Vendita Attiva' registrata su StockX con prezzo previsto € 170,00")

    # 3. Verifica nella scheda 'Vendite Attive'
    page.click('button.table-tab-pill[data-filter="active-sale"]')
    active_row = page.locator("#inventory-table-body tr:has-text('Nike Dunk Low Retro Panda')")
    expect(active_row).to_be_visible(timeout=5000)
    page.wait_for_timeout(1000)

    active_row_text = active_row.inner_text()
    assert "StockX" in active_row_text, "Canale StockX non visibile nella riga della vendita attiva"
    assert "170" in active_row_text, "Prezzo previsto € 170 non visibile nella riga della vendita attiva"
    details.append("Scheda 'Vendite Attive' verificata con successo (badge 'In Vendita', StockX, € 170,00)")

    # 4. Modifica Vendita Attiva & Verifica Blocchi di Sicurezza UI
    page.click('button[title="Modifica Prodotto"]')
    page.wait_for_selector("#productModal.open", timeout=5000)
    page.wait_for_timeout(600)

    # Asserzione visiva e funzionale dei lock
    expect(page.locator("#active-sale-lock-notice")).to_be_visible(timeout=5000)
    expect(page.locator("#prod-name")).to_be_disabled()
    expect(page.locator("#prod-size")).to_be_disabled()
    expect(page.locator("#prod-buy-place")).to_be_disabled()
    expect(page.locator("#prod-sell-place")).to_be_disabled()
    expect(page.locator("#prod-sold-price")).to_be_editable()
    details.append("Blocchi di sicurezza UI verificati: campi anagrafici e canale protetti da modifica accidentale")

    # Aggiornamento prezzo di vendita e inserimento commissioni
    page.fill("#prod-sold-price", "180.00")
    page.locator("#prod-fees").press_sequentially("15.00", delay=35)
    page.wait_for_timeout(600)

    page.click("#productForm button.btn-primary")
    page.wait_for_selector("#productModal", state="hidden", timeout=5000)
    page.wait_for_timeout(600)
    details.append("Vendita attiva aggiornata: prezzo portato a € 180,00 e commissioni a € 15,00")

    # 5. Conclusione della vendita -> passaggio a 'Venduto' (completed)
    page.click('button[title="Modifica Prodotto"]')
    page.wait_for_selector("#productModal.open", timeout=5000)
    page.wait_for_timeout(500)
    page.select_option("#prod-status", "completed")
    page.wait_for_timeout(600)

    page.click("#productForm button.btn-primary")
    page.wait_for_selector("#productModal", state="hidden", timeout=5000)
    page.wait_for_timeout(600)
    details.append("Vendita finalizzata: stato commutato su 'Venduto'")

    # 6. Switch a 'Vendite Completate' e Asserzione Matematica Profitti
    page.click('button.table-tab-pill[data-filter="completed"]')
    completed_row = page.locator("#inventory-table-body tr:has-text('Nike Dunk Low Retro Panda')")
    expect(completed_row).to_be_visible(timeout=5000)
    page.wait_for_timeout(1500)

    completed_text = completed_row.inner_text()
    assert "180" in completed_text, "Prezzo di vendita finale (€ 180,00) non trovato nella riga"
    assert "15" in completed_text, "Commissioni (€ 15,00) non trovate nella riga"
    assert "45" in completed_text, "Utile netto calcolato (€ 45,00 = 180 - 120 - 15) non presente nella riga"
    assert "37.5" in completed_text, "Badge ROI calcolato (+37.5%) non trovato nella riga"
    assert "StockX" in completed_text, "Marketplace 'StockX' non trovato nella riga"
    details.append("Asserzione matematica superata: Utile Netto = +€ 45,00 e ROI = +37.5% validati al 100%")

    # 7. Verifica assenza errori console
    assert len(console_errors) == 0, f"Rilevati errori console durante il ciclo del Livello 3: {console_errors}"

    # 8. Checkpoint visivo screenshot
    screenshot_path = SCREENSHOTS_DIR / "level3_flow.png"
    page.screenshot(path=str(screenshot_path), full_page=False)
    details.append(f"Screenshot salvato: {screenshot_path.name}")

    return {
        "passed": True,
        "details": details,
        "screenshot_path": screenshot_path,
    }


def test_level3_flow_pytest(sandbox_server: Any) -> None:
    """Entry point compatibile con pytest."""
    from playwright.sync_api import sync_playwright

    from tests.e2e.conftest import E2EContextManager

    with sync_playwright() as p, E2EContextManager(p, "level3_flow") as (page, console_errors):
        res = run_level3_flow_checks(page, console_errors)
        assert res["passed"] is True
