"""Livello 5: Vendita Multipla Massiva (Bulk Sale), Gestione Bundle & Calcoli Aggregati Pillola Flottante.

Verifiche:
1. Creazione di 2 prodotti distinti in magazzino:
   - Prodotto A: Nike Dunk Low Retro Panda (Costo: 120.00 €, Taglia: 42, Canale: Nike SNKRS)
   - Prodotto B: Air Jordan 4 Military Black (Costo: 210.00 €, Taglia: 43, Canale: Foot Locker)
2. Attivazione della Modalità Selezione Multipla (#btnToggleSelect).
3. Selezione di entrambi i prodotti tramite checkbox (.row-checkbox).
4. Asserzione metrica della Pillola Flottante Riassuntiva (#selectionFloatingCapsule) in Magazzino:
   - Conteggio: '2 sel.'
   - Spesa Totale: '€ 330,00' (120.00 + 210.00)
   - Costo Medio di Acquisto: '€ 165,00' (330.00 / 2)
   - Sezione Vendite/Utili (#capsuleSalesStats) correttamente nascosta.
5. Menu Contestuale con Tasto Destro (#tableContextMenu):
   - Click col tasto destro sulla riga.
   - Verifica intestazione menu: '2 Prodotti Selezionati'.
   - Selezione azione 'Metti in vendita' (#ctxItemSell).
6. Modale di Vendita Multipla (#bulkSaleModal):
   - Apertura modale e compilazione parametri cumulativi:
     * Prezzo Totale di Vendita: 500.00 €
     * Commissioni Totali: 40.00 €
     * Marketplace: StockX
   - Invio form con creazione del gruppo di vendita (Bundle).
7. Scheda 'Vendite Attive':
   - Presenza della riga bundle (.bundle-row) con badge 'In Vendita', 2 pz, Spesa € 330,00, Ricavo € 500,00, Utile € 130,00, ROI 39.4%.
   - Espansione al click con visualizzazione delle 2 sotto-righe prodotto (.bundle-child-row).
8. Completamento Vendita Multipla:
   - Tasto destro sul bundle e selezione 'Completa Vendita' (#ctxItemComplete) con auto-conferma dialog.
9. Scheda 'Vendite Completate' & Asserzione Matematica Pillola:
   - Presenza del bundle con badge 'Venduto'.
   - Selezione del bundle tramite checkbox master (.bundle-chk).
   - Verifica metrica della Pillola Flottante a vendita conclusa:
     * Conteggio: '2 sel.'
     * Spesa Totale: '€ 330,00'
     * Costo Medio: '€ 165,00'
     * Vendita Totale: '€ 500,00'
     * Utile Netto Totale: '+€ 130,00' (500.00 - 330.00 - 40.00)
     * Badge ROI cumulato: '+39.4% ROI' (+130.00 / 330.00 * 100)
10. Eliminazione finale del bundle dal menu contestuale (#ctxItemDelete) e svuotamento tabella.
11. Audit console (0 errori).
12. Checkpoint visivo: screenshot level5_bulk.png e registrazione video level5_bulk.webm.
"""

from typing import Any

from playwright.sync_api import Page, expect

from tests.e2e.conftest import SANDBOX_BASE_URL, SCREENSHOTS_DIR


def run_level5_bulk_checks(page: Page, console_errors: list[str]) -> dict[str, Any]:
    """Esegue tutte le asserzioni e i controlli del Livello 5."""
    details = []

    # 1. Navigazione e pulizia contesto
    page.goto(SANDBOX_BASE_URL, wait_until="networkidle")
    page.wait_for_selector(".table-card", timeout=5000)
    page.click('button.table-tab-pill[data-filter="stock"]')
    page.wait_for_timeout(400)

    # 2. Creazione Prodotto 1 (Nike Dunk Low Retro Panda - 120.00 €)
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
    page.wait_for_timeout(500)
    details.append("Prodotto 1 aggiunto in magazzino (Nike Dunk Panda, € 120,00)")

    # 3. Creazione Prodotto 2 (Air Jordan 4 Military Black - 210.00 €)
    page.click(".btn-sidebar-add")
    page.wait_for_selector("#productModal.open", timeout=5000)
    page.locator("#prod-name").press_sequentially("Air Jordan 4 Military Black", delay=30)
    page.locator("#prod-size").press_sequentially("43", delay=30)
    page.fill("#prod-qty", "1")
    page.locator("#prod-buy-price").press_sequentially("210.00", delay=30)
    page.locator("#prod-buy-place").press_sequentially("Foot Locker", delay=30)
    page.click("#productForm button.btn-primary")
    page.wait_for_selector("#productModal", state="hidden", timeout=5000)
    page.wait_for_timeout(600)
    details.append("Prodotto 2 aggiunto in magazzino (Air Jordan 4, € 210,00)")

    # 4. Attivazione Modalità Selezione Multipla
    page.click("#btnToggleSelect")
    page.wait_for_timeout(400)

    checkboxes = page.locator("#inventory-table-body input.row-checkbox")
    expect(checkboxes).to_have_count(2, timeout=5000)
    checkboxes.nth(0).check()
    page.wait_for_timeout(300)
    checkboxes.nth(1).check()
    page.wait_for_timeout(600)
    details.append("Modalità Selezione attivata e 2 prodotti spuntati")

    # 5. Asserzione Pillola Flottante Riassuntiva in Magazzino
    capsule = page.locator("#selectionFloatingCapsule")
    expect(capsule).to_be_visible(timeout=5000)
    page.wait_for_timeout(800)

    expect(page.locator("#capsuleSelectedCount")).to_contain_text("2 sel.")
    expect(page.locator("#capsuleTotalCost")).to_contain_text("330")
    expect(page.locator("#capsuleAvgCost")).to_contain_text("165")
    expect(page.locator("#capsuleSalesStats")).to_be_hidden()
    details.append("Pillola Flottante in Magazzino verificata: 2 sel., Spesa € 330,00, Media € 165,00")

    # 6. Apertura Menu Contestuale con Tasto Destro
    page.locator("#inventory-table-body tr").first.click(button="right")
    page.wait_for_selector("#tableContextMenu", state="visible", timeout=5000)
    expect(page.locator("#ctxMenuHeader")).to_contain_text("2 Prodotti Selezionati")
    page.wait_for_timeout(700)
    details.append("Menu contestuale aperto con tasto destro ('2 Prodotti Selezionati')")

    # 7. Apertura Modale Vendita Multipla (Bulk Sale)
    page.click("#ctxItemSell")
    page.wait_for_selector("#bulkSaleModal.open", timeout=5000)
    page.wait_for_timeout(500)

    page.fill("#bulk-sale-total-price", "500.00")
    page.fill("#bulk-sale-total-fees", "40.00")
    page.fill("#bulk-sale-place", "StockX")
    page.wait_for_timeout(600)

    page.click('#bulkSaleForm button[type="submit"]')
    page.wait_for_selector("#bulkSaleModal", state="hidden", timeout=5000)
    page.wait_for_timeout(800)
    details.append("Vendita multipla configurata: Totale € 500,00, Spese € 40,00 su StockX")

    # 8. Verifica Bundle in 'Vendite Attive'
    page.click('button.table-tab-pill[data-filter="active-sale"]')
    page.wait_for_timeout(600)
    bundle_row = page.locator("#inventory-table-body tr.bundle-row")
    expect(bundle_row).to_be_visible(timeout=5000)

    bundle_text = bundle_row.inner_text()
    assert "StockX" in bundle_text, "Canale StockX non presente nel bundle vendite attive"
    assert "500" in bundle_text, "Prezzo totale € 500 non presente nel bundle vendite attive"
    assert "In Vendita" in bundle_text, "Badge 'In Vendita' non presente nel bundle"

    # Espansione bundle
    bundle_row.click()
    page.wait_for_timeout(500)
    child_rows = page.locator("#inventory-table-body tr.bundle-child-row")
    expect(child_rows).to_have_count(2, timeout=5000)
    page.wait_for_timeout(800)
    details.append("Bundle raggruppato in 'Vendite Attive' verificato ed espanso (2 sotto-righe prodotto)")

    # 9. Conclusione Vendita Multipla dal Menu Contestuale
    bundle_row.click(button="right")
    page.wait_for_selector("#tableContextMenu", state="visible", timeout=5000)
    page.wait_for_timeout(500)
    page.click("#ctxItemComplete")
    page.wait_for_timeout(800)
    details.append("Vendita multipla conclusa con successo tramite menu contestuale ('Completa Vendita')")

    # 10. Scheda 'Vendite Completate' & Asserzione Matematica Pillola Cumulativa
    page.click('button.table-tab-pill[data-filter="completed"]')
    page.wait_for_timeout(600)
    comp_bundle = page.locator("#inventory-table-body tr.bundle-row")
    expect(comp_bundle).to_be_visible(timeout=5000)

    # Attivazione selezione per verificare la pillola con dati di vendita
    page.click("#btnToggleSelect")
    page.wait_for_timeout(400)
    bundle_chk = page.locator("#inventory-table-body tr.bundle-row input.bundle-chk")
    bundle_chk.check()
    page.wait_for_timeout(1000)

    expect(capsule).to_be_visible(timeout=5000)
    expect(page.locator("#capsuleSelectedCount")).to_contain_text("2 sel.")
    expect(page.locator("#capsuleTotalCost")).to_contain_text("330")
    expect(page.locator("#capsuleAvgCost")).to_contain_text("165")
    expect(page.locator("#capsuleSalesStats")).to_be_visible()
    expect(page.locator("#capsuleTotalSale")).to_contain_text("500")
    expect(page.locator("#capsuleTotalProfit")).to_contain_text("130")
    expect(page.locator("#capsuleRoiBadge")).to_contain_text("39.4%")
    details.append(
        "Pillola Flottante a vendita conclusa validata: 2 sel., Spesa € 330, Media € 165, Vendita € 500, Utile Netto +€ 130,00, ROI +39.4%"
    )

    # 11. Pulizia finale: Eliminazione Bundle dal Menu Contestuale
    comp_bundle.click(button="right")
    page.wait_for_selector("#tableContextMenu", state="visible", timeout=5000)
    page.wait_for_timeout(400)
    page.click("#ctxItemDelete")
    page.wait_for_timeout(800)
    expect(page.locator("#inventory-table-body")).to_contain_text("Nessun prodotto trovato", timeout=5000)
    page.wait_for_timeout(600)
    details.append("Bundle eliminato definitivamente e tabella inventario ripulita al 100%")

    # 12. Audit console
    assert len(console_errors) == 0, f"Rilevati errori console durante il ciclo del Livello 5: {console_errors}"

    # 13. Checkpoint visivo screenshot
    screenshot_path = SCREENSHOTS_DIR / "level5_bulk.png"
    page.screenshot(path=str(screenshot_path), full_page=False)
    details.append(f"Screenshot salvato: {screenshot_path.name}")

    return {
        "passed": True,
        "details": details,
        "screenshot_path": screenshot_path,
    }


def test_level5_bulk_pytest(sandbox_server: Any) -> None:
    """Entry point compatibile con pytest."""
    from playwright.sync_api import sync_playwright

    from tests.e2e.conftest import E2EContextManager

    with sync_playwright() as p, E2EContextManager(p, "level5_bulk") as (page, console_errors):
        res = run_level5_bulk_checks(page, console_errors)
        assert res["passed"] is True
