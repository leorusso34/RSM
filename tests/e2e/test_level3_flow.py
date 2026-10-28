"""Livello 3: Transazione Vendita, Calcolo Profitti, Ricerca & Eliminazione.

Verifiche:
1. Modifica del prodotto e passaggio allo stato 'Venduto' (Completato).
2. Compilazione dei parametri di vendita: Prezzo Vendita (€ 180.00), Commissioni (€ 15.00), Canale (StockX).
3. Asserzione Matematica dei Profitti:
   Profitto Netto = Prezzo Vendita - Prezzo Acquisto - Commissioni = 180 - 120 - 15 = +45.00 €
   ROI % = (+45.00 / 120.00) * 100 = +37.5%
4. Switch alla scheda 'Vendite Completate' e verifica colonne (Ricavo, Spese, Utile, ROI %, Marketplace).
5. Collaudo del Filtro di Ricerca Globale:
   - Inserimento termine presente ("Panda") -> il prodotto resta visibile.
   - Inserimento termine inesistente ("NonExistentXYZ999") -> il prodotto scompare e compare lo stato vuoto.
   - Reset della barra di ricerca -> il prodotto ricompare.
6. Eliminazione Finale:
   - Click sull'icona elimina riga con accettazione del dialogo di conferma.
   - Verifica scomparsa riga dal database e svuotamento tabella.
7. Checkpoint visivo: screenshot level3_flow.png e registrazione video level3_flow.webm.
"""

from typing import Any

from playwright.sync_api import Page, expect

from tests.e2e.conftest import SANDBOX_BASE_URL, SCREENSHOTS_DIR


def ensure_test_product_exists(page: Page) -> None:
    """Garantisce la presenza di un prodotto in stock prima di avviare il flusso di vendita."""
    page.goto(SANDBOX_BASE_URL, wait_until="networkidle")
    page.wait_for_selector(".table-card", timeout=5000)

    # Controlla se la tabella è vuota
    edit_btn = page.locator('button[title="Modifica Prodotto"]')
    if edit_btn.count() == 0:
        page.click(".btn-sidebar-add")
        page.wait_for_selector("#productModal.open", timeout=5000)
        page.fill("#prod-name", "Nike Dunk Low Retro Panda")
        page.fill("#prod-size", "42")
        page.fill("#prod-qty", "1")
        page.fill("#prod-buy-price", "120.00")
        page.fill("#prod-buy-place", "Nike SNKRS")
        page.click("#productForm button.btn-primary")
        page.wait_for_selector("#productModal", state="hidden", timeout=5000)
        page.wait_for_selector("#inventory-table-body tr", timeout=5000)


def run_level3_flow_checks(page: Page, console_errors: list[str]) -> dict[str, Any]:
    """Esegue tutte le asserzioni e i controlli del Livello 3."""
    details = []

    # 1. Assicura che esista il prodotto da vendere
    ensure_test_product_exists(page)
    details.append("Prodotto base verificato in tabella inventario")

    # 2. Apertura modale di modifica
    page.click('button[title="Modifica Prodotto"]')
    page.wait_for_selector("#productModal.open", timeout=5000)
    details.append("Modale di modifica aperta sul prodotto selezionato")

    # 3. Passaggio allo stato 'completed' e compilazione parametri di vendita
    page.select_option("#prod-status", "completed")
    page.fill("#prod-sold-price", "180.00")
    page.fill("#prod-fees", "15.00")
    page.fill("#prod-sell-place", "StockX")
    details.append("Stato impostato su 'Venduto' con Prezzo Vendita € 180,00, Spese € 15,00 e Canale 'StockX'")

    # 4. Salvataggio
    page.click("#productForm button.btn-primary")
    page.wait_for_selector("#productModal", state="hidden", timeout=5000)
    details.append("Vendita salvata e registrata nel database")

    # 5. Navigazione a 'Vendite Completate' e asserzione matematica del profitto
    page.click('button.table-tab-pill[data-filter="completed"]')
    sale_row = page.locator("#inventory-table-body tr:has-text('Nike Dunk Low Retro Panda')")
    expect(sale_row).to_be_visible(timeout=5000)

    sale_row_text = sale_row.inner_text()
    assert "180" in sale_row_text, "Prezzo di vendita (€ 180,00) non trovato nella riga della vendita completata"
    assert "15" in sale_row_text, "Commissioni (€ 15,00) non trovate nella riga della vendita completata"
    assert "45" in sale_row_text, "Profitto netto calcolato (€ 45,00 = 180 - 120 - 15) non presente nella riga"
    assert "37.5" in sale_row_text, "Badge ROI calcolato (+37.5%) non trovato nella riga"
    assert "StockX" in sale_row_text, "Canale di vendita 'StockX' non trovato nella riga"
    details.append("Asserzione matematica superata: Utile Netto = +€ 45,00 e ROI = +37.5% verificati con successo")

    # 6. Test Filtro di Ricerca Globale
    search_input = page.locator("#global-search-input")

    # Ricerca con termine valido
    search_input.fill("Panda")
    expect(page.locator("#inventory-table-body tr:has-text('Panda')")).to_be_visible(timeout=5000)
    details.append("Filtro di ricerca: match positivo su 'Panda' confermato")

    # Ricerca con termine inesistente
    search_input.fill("NonExistentXYZ999")
    expect(page.locator("#inventory-table-body tr:has-text('Panda')")).to_have_count(0, timeout=5000)
    expect(page.locator("#inventory-table-body")).to_contain_text("Nessun prodotto trovato", timeout=5000)
    details.append("Filtro di ricerca: stato vuoto confermato su termine inesistente")

    # Reset ricerca
    search_input.fill("")
    expect(page.locator("#inventory-table-body tr:has-text('Panda')")).to_be_visible(timeout=5000)
    details.append("Filtro di ricerca azzerato correttamente")

    # 7. Test Eliminazione Prodotto
    page.click("button.btn-action-icon.delete")
    expect(page.locator("#inventory-table-body tr:has-text('Nike Dunk Low Retro Panda')")).to_have_count(
        0, timeout=5000
    )
    expect(page.locator("#inventory-table-body")).to_contain_text("Nessun prodotto trovato", timeout=5000)
    details.append("Eliminazione riga eseguita con successo con accettazione automatica del dialogo di conferma")

    # 8. Verifica zero errori console
    assert len(console_errors) == 0, f"Rilevati errori console durante il ciclo del Livello 3: {console_errors}"

    # 9. Screenshot di checkpoint
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
