"""Livello 2: Creazione Prodotto & Consistenza Dati (CRUD).

Verifiche:
1. Apertura della modale di aggiunta prodotto (#productModal).
2. Compilazione dei campi anagrafici ed economici (Nome, Taglia, Quantità, Prezzo Acquisto, Luogo Acquisto).
3. Salvataggio e verifica della chiusura automatica della modale.
4. Asserzione consistenza: comparsa immediata della riga in tabella con dati corretti.
5. Verifica incremento del capitale investito e metriche in stock.
6. Checkpoint visivo: screenshot level2_product_created.png e video level2_crud.webm.
"""

from typing import Any

from playwright.sync_api import Page, expect

from tests.e2e.conftest import SANDBOX_BASE_URL, SCREENSHOTS_DIR


def run_level2_crud_checks(page: Page, console_errors: list[str]) -> dict[str, Any]:
    """Esegue tutte le asserzioni e i controlli del Livello 2."""
    details = []

    # 1. Apertura e attesa layout
    page.goto(SANDBOX_BASE_URL, wait_until="networkidle")
    page.wait_for_selector(".table-card", timeout=5000)

    # 2. Click su pulsante Aggiungi Prodotto
    add_btn = page.locator(".btn-sidebar-add")
    expect(add_btn).to_be_visible(timeout=5000)
    add_btn.click()
    details.append("Click effettuato sul pulsante 'Aggiungi Prodotto'")

    # 3. Attesa apertura modale anagrafica
    page.wait_for_selector("#productModal.open", timeout=5000)
    details.append("Modale anagrafica (#productModal) aperta e attiva")

    # 4. Compilazione campi
    test_product_name = "Nike Dunk Low Retro Panda"
    test_size = "42"
    test_buy_price = "120.00"
    test_buy_place = "Nike SNKRS"

    page.fill("#prod-name", test_product_name)
    page.fill("#prod-size", test_size)
    page.fill("#prod-qty", "1")
    page.fill("#prod-buy-price", test_buy_price)
    page.fill("#prod-buy-place", test_buy_place)
    details.append(
        f"Campi compilati: '{test_product_name}', Taglia {test_size}, Spesa € {test_buy_price}, Luogo '{test_buy_place}'"
    )

    # 5. Invio del modulo
    submit_btn = page.locator("#productForm button.btn-primary")
    submit_btn.click()
    page.wait_for_selector("#productModal", state="hidden", timeout=5000)
    details.append("Modulo inviato e modale chiusa correttamente")

    # 6. Verifica comparsa della riga in tabella (vista Tutti i Prodotti)
    product_row = page.locator(f"#inventory-table-body tr:has-text('{test_product_name}')")
    expect(product_row).to_be_visible(timeout=5000)

    row_text = product_row.inner_text()
    assert "120" in row_text, "Prezzo di acquisto non visualizzato correttamente nella riga"
    assert "1 pz" in row_text, "Quantità non visualizzata correttamente nella riga"
    details.append("Riga inserita visibile nella vista generale 'Tutti i Prodotti' (Nome, Quantità, Spesa)")

    # 7. Verifica nella scheda dedicata 'Magazzino' (con colonna Taglia)
    page.click('button.table-tab-pill[data-filter="stock"]')
    stock_row = page.locator(f"#inventory-table-body tr:has-text('{test_product_name}')")
    expect(stock_row).to_be_visible(timeout=5000)
    stock_row_text = stock_row.inner_text()
    assert test_size in stock_row_text, f"Taglia '{test_size}' non trovata nella vista 'Magazzino': {stock_row_text}"
    details.append(f"Scheda 'Magazzino' verificata: visualizzazione corretta della colonna Taglia ({test_size})")

    # Torna a 'Tutti i Prodotti'
    page.click('button.table-tab-pill[data-filter="all"]')
    page.wait_for_timeout(200)

    # 8. Verifica metriche KPI Capitale Investito
    kpi_invested = page.locator("#kpi-invested")
    kpi_text = kpi_invested.inner_text()
    assert "120" in kpi_text, f"Il KPI Capitale Investito ({kpi_text}) non riflette i 120,00 € del prodotto inserito"
    details.append(f"Card KPI Capitale Investito aggiornata in tempo reale ({kpi_text.strip()})")

    # 8. Verifica assenza di errori console durante il salvataggio
    assert len(console_errors) == 0, f"Errori console durante la creazione del prodotto: {console_errors}"

    # 9. Screenshot di checkpoint
    screenshot_path = SCREENSHOTS_DIR / "level2_product_created.png"
    page.screenshot(path=str(screenshot_path), full_page=False)
    details.append(f"Screenshot salvato: {screenshot_path.name}")

    return {
        "passed": True,
        "details": details,
        "screenshot_path": screenshot_path,
    }


def test_level2_crud_pytest(sandbox_server: Any) -> None:
    """Entry point compatibile con pytest."""
    from playwright.sync_api import sync_playwright

    from tests.e2e.conftest import E2EContextManager

    with sync_playwright() as p, E2EContextManager(p, "level2_crud") as (page, console_errors):
        res = run_level2_crud_checks(page, console_errors)
        assert res["passed"] is True
