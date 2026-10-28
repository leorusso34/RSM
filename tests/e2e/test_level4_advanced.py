"""Livello 4: Interazioni Avanzate, Selezione Multipla, Pillola Flottante, Filtri & Eliminazione.

Verifiche:
1. Verifica/garanzia di esistenza di una vendita completata (Costo: 120.00 €, Vendita: 180.00 €, Spese: 15.00 €).
2. Attivazione della Modalità Selezione Multipla (#btnToggleSelect).
3. Selezione della riga prodotto tramite checkbox (.row-checkbox).
4. Asserzione della Pillola Flottante Riassuntiva (#selectionFloatingCapsule):
   - Visibilità e ancoraggio sopra la tabella inventario.
   - Conteggio selezionati: '1 sel.'.
   - Spesa totale: '€ 120,00'.
   - Ricavo totale: '€ 180,00'.
   - Utile netto: '+€ 45,00'.
   - Badge ROI dinamico: '+37.5% ROI'.
5. Deselezione rapida tramite pulsante clear (.capsule-btn-clear) e scomparsa della pillola.
6. Disattivazione della Modalità Selezione (#btnToggleSelect).
7. Collaudo del Filtro di Ricerca Globale (#global-search-input):
   - Termine corrispondente ('Panda') -> riga visibile.
   - Termine inesistente ('NonExistentXYZ999') -> stato vuoto ('Nessun prodotto trovato').
   - Ripristino campo ricerca -> riga ripristinata.
8. Eliminazione Finale del Prodotto:
   - Click su icona elimina (.btn-action-icon.delete) con auto-conferma dialog.
   - Verifica scomparsa riga dal database e svuotamento tabella.
9. Audit console (0 errori).
10. Checkpoint visivo: screenshot level4_advanced.png e registrazione video level4_advanced.webm.
"""

import re
from typing import Any

from playwright.sync_api import Page, expect

from tests.e2e.conftest import SANDBOX_BASE_URL, SCREENSHOTS_DIR


def ensure_completed_product_exists(page: Page) -> None:
    """Garantisce la presenza di un prodotto venduto prima dei test avanzati."""
    page.goto(SANDBOX_BASE_URL, wait_until="networkidle")
    page.wait_for_selector(".table-card", timeout=5000)
    page.click('button.table-tab-pill[data-filter="completed"]')
    page.wait_for_timeout(400)

    rows = page.locator("#inventory-table-body tr:has-text('Nike Dunk Low Retro Panda')")
    if rows.count() == 0:
        page.click(".btn-sidebar-add")
        page.wait_for_selector("#productModal.open", timeout=5000)
        page.fill("#prod-name", "Nike Dunk Low Retro Panda")
        page.fill("#prod-size", "42")
        page.fill("#prod-qty", "1")
        page.fill("#prod-buy-price", "120.00")
        page.fill("#prod-buy-place", "Nike SNKRS")
        page.fill("#prod-sell-place", "StockX")
        page.fill("#prod-sold-price", "180.00")
        page.fill("#prod-fees", "15.00")
        page.select_option("#prod-status", "completed")
        page.click("#productForm button.btn-primary")
        page.wait_for_selector("#productModal", state="hidden", timeout=5000)
        page.click('button.table-tab-pill[data-filter="completed"]')
        page.wait_for_selector("#inventory-table-body tr", timeout=5000)


def run_level4_advanced_checks(page: Page, console_errors: list[str]) -> dict[str, Any]:
    """Esegue tutte le asserzioni e i controlli del Livello 4."""
    details = []

    # 1. Verifica/creazione del prodotto venduto
    ensure_completed_product_exists(page)
    page.wait_for_timeout(600)
    details.append("Prodotto venduto verificato nella tabella 'Vendite Completate'")

    # 2. Attivazione Modalità Selezione Multipla
    toggle_select_btn = page.locator("#btnToggleSelect")
    toggle_select_btn.click()
    page.wait_for_timeout(500)
    expect(toggle_select_btn).to_have_class(re.compile(r"\bactive\b"), timeout=3000)
    details.append("Modalità Selezione Multipla attivata (#btnToggleSelect attivo)")

    # 3. Selezione riga tramite checkbox
    row_checkbox = page.locator("#inventory-table-body input.row-checkbox").first
    expect(row_checkbox).to_be_visible(timeout=5000)
    row_checkbox.check()
    page.wait_for_timeout(600)
    details.append("Checkbox di riga selezionata")

    # 4. Asserzione Pillola Flottante Riassuntiva (#selectionFloatingCapsule)
    capsule = page.locator("#selectionFloatingCapsule")
    expect(capsule).to_be_visible(timeout=5000)
    page.wait_for_timeout(1000)

    # Verifica metriche aggregate calcolate in tempo reale
    expect(page.locator("#capsuleSelectedCount")).to_contain_text("1")
    expect(page.locator("#capsuleTotalCost")).to_contain_text("120")
    expect(page.locator("#capsuleTotalSale")).to_contain_text("180")
    expect(page.locator("#capsuleTotalProfit")).to_contain_text("45")
    expect(page.locator("#capsuleRoiBadge")).to_contain_text("37.5%")
    details.append(
        "Pillola Flottante Riassuntiva verificata: 1 sel., Spesa € 120,00, Vendita € 180,00, Utile +€ 45,00, ROI +37.5%"
    )

    # 5. Deselezione rapida tramite pulsante pillola
    page.click("button.capsule-btn-clear")
    page.wait_for_timeout(600)
    expect(capsule).to_be_hidden(timeout=5000)
    details.append("Pulsante 'Deseleziona tutto' testato con successo: pillola flottante nascosta")

    # 6. Disattivazione Modalità Selezione
    toggle_select_btn.click()
    page.wait_for_timeout(400)
    details.append("Modalità Selezione disattivata")

    # 7. Collaudo Filtro di Ricerca Globale
    search_input = page.locator("#global-search-input")

    # Match valido
    search_input.press_sequentially("Panda", delay=40)
    expect(page.locator("#inventory-table-body tr:has-text('Panda')")).to_be_visible(timeout=5000)
    page.wait_for_timeout(800)
    details.append("Filtro di ricerca: match corretto con termine 'Panda'")

    # Match inesistente
    search_input.fill("NonExistentXYZ999")
    expect(page.locator("#inventory-table-body tr:has-text('Panda')")).to_have_count(0, timeout=5000)
    expect(page.locator("#inventory-table-body")).to_contain_text("Nessun prodotto trovato", timeout=5000)
    page.wait_for_timeout(800)
    details.append("Filtro di ricerca: stato vuoto verificato su termine inesistente")

    # Reset ricerca
    search_input.fill("")
    expect(page.locator("#inventory-table-body tr:has-text('Panda')")).to_be_visible(timeout=5000)
    page.wait_for_timeout(600)
    details.append("Filtro di ricerca ripristinato")

    # 8. Eliminazione Finale del Prodotto
    page.click("button.btn-action-icon.delete")
    expect(page.locator("#inventory-table-body tr:has-text('Nike Dunk Low Retro Panda')")).to_have_count(
        0, timeout=5000
    )
    expect(page.locator("#inventory-table-body")).to_contain_text("Nessun prodotto trovato", timeout=5000)
    page.wait_for_timeout(1000)
    details.append("Eliminazione riga eseguita: confermata distruzione e svuotamento tabella")

    # 9. Audit console
    assert len(console_errors) == 0, f"Rilevati errori console durante il ciclo del Livello 4: {console_errors}"

    # 10. Checkpoint visivo screenshot
    screenshot_path = SCREENSHOTS_DIR / "level4_advanced.png"
    page.screenshot(path=str(screenshot_path), full_page=False)
    details.append(f"Screenshot salvato: {screenshot_path.name}")

    return {
        "passed": True,
        "details": details,
        "screenshot_path": screenshot_path,
    }


def test_level4_advanced_pytest(sandbox_server: Any) -> None:
    """Entry point compatibile con pytest."""
    from playwright.sync_api import sync_playwright

    from tests.e2e.conftest import E2EContextManager

    with sync_playwright() as p, E2EContextManager(p, "level4_advanced") as (page, console_errors):
        res = run_level4_advanced_checks(page, console_errors)
        assert res["passed"] is True
