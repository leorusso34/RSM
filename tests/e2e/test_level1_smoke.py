"""Livello 1: Smoke Test & Layout Integrity.

Verifiche:
1. Caricamento pulito della Web UI locale senza timeout.
2. Integrità visiva: presenza della sidebar (#appSidebar), griglia KPI (.kpi-grid), tabella inventario e barra di ricerca.
3. Zero errori JavaScript rossi in console (audit page.on("console")).
4. Checkpoint visivo: cattura screenshot level1_smoke.png e registrazione video.
"""

from typing import Any

from playwright.sync_api import Page, expect

from tests.e2e.conftest import SANDBOX_BASE_URL, SCREENSHOTS_DIR


def run_level1_smoke_checks(page: Page, console_errors: list[str]) -> dict[str, Any]:
    """Esegue tutte le asserzioni e i controlli del Livello 1."""
    details = []

    # 1. Apertura dell'applicazione
    page.goto(SANDBOX_BASE_URL, wait_until="networkidle")
    page.wait_for_timeout(1000)
    details.append("Pagina iniziale caricata con successo (networkidle)")

    # 2. Verifica elementi strutturali principali
    sidebar = page.locator("#appSidebar")
    expect(sidebar).to_be_visible(timeout=5000)
    sidebar.hover()
    page.wait_for_timeout(400)
    details.append("Sidebar (#appSidebar) presente e visibile")

    kpi_grid = page.locator(".kpi-grid")
    expect(kpi_grid).to_be_visible(timeout=5000)
    kpi_grid.hover()
    page.wait_for_timeout(400)
    details.append("Griglia KPI metriche (.kpi-grid) presente e visibile")

    search_input = page.locator("#global-search-input")
    expect(search_input).to_be_visible(timeout=5000)
    details.append("Barra di ricerca globale (#global-search-input) pronta per l'input")

    table_wrap = page.locator(".data-table-wrap")
    expect(table_wrap).to_be_visible(timeout=5000)
    details.append("Contenitore tabella inventario (.data-table-wrap) inizializzato")

    # Pausa di stabilità per consentire una visione chiara e naturale nel video
    page.wait_for_timeout(1200)

    # 3. Verifica zero errori JavaScript in console
    assert len(console_errors) == 0, f"Rilevati {len(console_errors)} errori JavaScript in console: {console_errors}"
    details.append("Audit console JavaScript superato: 0 errori rossi rilevati")

    # 4. Cattura screenshot di checkpoint
    screenshot_path = SCREENSHOTS_DIR / "level1_smoke.png"
    page.screenshot(path=str(screenshot_path), full_page=False)
    details.append(f"Screenshot salvato: {screenshot_path.name}")

    return {
        "passed": True,
        "details": details,
        "screenshot_path": screenshot_path,
    }


def test_level1_smoke_pytest(sandbox_server: Any) -> None:
    """Entry point compatibile con pytest."""
    from playwright.sync_api import sync_playwright

    from tests.e2e.conftest import E2EContextManager

    with sync_playwright() as p, E2EContextManager(p, "level1_smoke") as (page, console_errors):
        res = run_level1_smoke_checks(page, console_errors)
        assert res["passed"] is True
