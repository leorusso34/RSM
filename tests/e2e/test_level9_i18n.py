"""Livello 9: Supporto Bilingue Italiano / Inglese (i18n), Rilevamento Automatico e Persistenza.

Verifiche E2E:
1. Scenario A: Rilevamento automatico della lingua al primo avvio:
   - Contesto Chromium avviato con locale="en-US" e memoria locale (localStorage) vuota.
   - Apertura interfaccia Web su SANDBOX_BASE_URL.
   - Verifica caricamento automatico in lingua inglese:
     * Pulsante sidebar Nuovo Prodotto (.btn-sidebar-add span) reca il testo "New Product".
     * Intestazione prima card metrica (.kpi-title) reca il testo "Invested Capital".
     * Pulsante selettore lingua inglese (.lang-btn[data-lang="en"]) presenta la classe .active.
     * Pulsante selettore lingua italiana (.lang-btn[data-lang="it"]) non presenta la classe .active.
2. Scenario B: Cambio lingua dinamico e istantaneo in tempo reale (Live Switching senza reload):
   - Click su .lang-btn[data-lang="it"] per passare all'italiano.
   - Verifica immediata nel DOM senza ricaricare la pagina:
     * .btn-sidebar-add span transita a "Nuovo Prodotto".
     * .kpi-title transita a "Capitale Investito".
     * .lang-btn[data-lang="it"] acquisisce la classe .active.
     * .lang-btn[data-lang="en"] non presenta la classe .active.
     * localStorage.getItem("rsm_app_lang") e' pari a "it".
   - Click su .lang-btn[data-lang="en"] per tornare all'inglese:
     * .btn-sidebar-add span ritorna a "New Product".
     * .kpi-title ritorna a "Invested Capital".
     * .lang-btn[data-lang="en"] acquisisce la classe .active.
     * localStorage.getItem("rsm_app_lang") e' pari a "en".
3. Scenario C: Persistenza della lingua scelta attraverso il ricaricamento di pagina:
   - Ricaricamento con page.reload(wait_until="networkidle") mantenendo l'inglese:
     * .btn-sidebar-add span rimane "New Product".
     * .kpi-title rimane "Invested Capital".
     * .lang-btn[data-lang="en"] rimane .active.
   - Selezione dell'italiano via click su .lang-btn[data-lang="it"].
   - Nuovo ricaricamento con page.reload(wait_until="networkidle"):
     * .btn-sidebar-add span rimane "Nuovo Prodotto".
     * .kpi-title rimane "Capitale Investito".
     * .lang-btn[data-lang="it"] rimane .active.
     * localStorage.getItem("rsm_app_lang") persiste con valore "it".
4. Scenario D: Audit console JavaScript (0 errori rossi rilevati).
5. Scenario E: Checkpoint visivo con salvataggio screenshot (level9_i18n.png) e restituzione dizionario LevelResult.
"""

import re
from typing import Any

from playwright.sync_api import Page, expect

from tests.e2e.conftest import SANDBOX_BASE_URL, SCREENSHOTS_DIR


def run_level9_i18n_checks(page: Page, console_errors: list[str]) -> dict[str, Any]:
    """Esegue tutte le asserzioni e i controlli del Livello 9 (i18n)."""
    details: list[str] = []

    # =========================================================================
    # SCENARIO A: Rilevamento automatico della lingua al primo avvio (locale="en-US")
    # =========================================================================
    # 1. Navigazione iniziale con contesto en-US e localStorage pulito
    page.goto(SANDBOX_BASE_URL, wait_until="networkidle")
    page.wait_for_selector(".table-card", timeout=5000)
    page.wait_for_timeout(400)
    details.append("Interfaccia iniziale caricata con contesto locale en-US")

    # 2. Localizzatori chiave per le verifiche bilingue
    add_btn_span = page.locator(".btn-sidebar-add span")
    kpi_title_invested = page.locator(".kpi-title").first
    lang_btn_en = page.locator('.lang-btn[data-lang="en"]')
    lang_btn_it = page.locator('.lang-btn[data-lang="it"]')

    # 3. Asserzioni Scenario A: interfaccia caricata nativamente in lingua inglese
    expect(add_btn_span).to_have_text("New Product", timeout=5000)
    expect(kpi_title_invested).to_have_text("Invested Capital", timeout=5000)
    expect(lang_btn_en).to_have_class(re.compile(r"\bactive\b"), timeout=5000)
    expect(lang_btn_it).not_to_have_class(re.compile(r"\bactive\b"), timeout=5000)
    details.append(
        "Scenario A superato: auto-rilevamento inglese attivo al primo avvio "
        "('New Product', 'Invested Capital', .lang-btn[data-lang='en'].active)"
    )

    # =========================================================================
    # SCENARIO B: Cambio dinamico istantaneo senza reload (Live Switching IT <-> EN)
    # =========================================================================
    # 1. Transizione a italiano al click sul pulsante IT
    lang_btn_it.click()
    page.wait_for_timeout(400)

    # Asserzioni transizione a italiano
    expect(add_btn_span).to_have_text("Nuovo Prodotto", timeout=5000)
    expect(kpi_title_invested).to_have_text("Capitale Investito", timeout=5000)
    expect(lang_btn_it).to_have_class(re.compile(r"\bactive\b"), timeout=5000)
    expect(lang_btn_en).not_to_have_class(re.compile(r"\bactive\b"), timeout=5000)

    # Verifica memorizzazione della preferenza in localStorage
    stored_lang_it = page.evaluate("() => localStorage.getItem('rsm_app_lang')")
    assert stored_lang_it == "it", f"Atteso localStorage 'rsm_app_lang' == 'it', ottenuto: {stored_lang_it}"
    details.append(
        "Scenario B1 superato: switch dinamico a italiano senza reload "
        "('Nuovo Prodotto', 'Capitale Investito', .lang-btn[data-lang='it'].active, localStorage='it')"
    )

    # 2. Transizione di ritorno a inglese al click sul pulsante EN
    lang_btn_en.click()
    page.wait_for_timeout(400)

    # Asserzioni ripristino inglese
    expect(add_btn_span).to_have_text("New Product", timeout=5000)
    expect(kpi_title_invested).to_have_text("Invested Capital", timeout=5000)
    expect(lang_btn_en).to_have_class(re.compile(r"\bactive\b"), timeout=5000)
    expect(lang_btn_it).not_to_have_class(re.compile(r"\bactive\b"), timeout=5000)

    stored_lang_en = page.evaluate("() => localStorage.getItem('rsm_app_lang')")
    assert stored_lang_en == "en", f"Atteso localStorage 'rsm_app_lang' == 'en', ottenuto: {stored_lang_en}"
    details.append(
        "Scenario B2 superato: switch dinamico di ritorno a inglese senza reload "
        "('New Product', 'Invested Capital', .lang-btn[data-lang='en'].active, localStorage='en')"
    )

    # Verifica notifica toast in basso a destra in inglese al cambio sezione sidebar
    toast_locator = page.locator("#toastNotification")
    page.locator('.nav-item[data-section="magazzino"]').click()
    expect(toast_locator).to_have_text("View: Stock", timeout=5000)
    details.append("Scenario B3 superato: toast navigazione localizzato in inglese ('View: Stock')")

    # =========================================================================
    # SCENARIO C: Persistenza della lingua attraverso il ricaricamento (Reload)
    # =========================================================================
    # 1. Ricaricamento con inglese attivo e verifica persistenza
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".table-card", timeout=5000)
    page.wait_for_timeout(400)

    expect(add_btn_span).to_have_text("New Product", timeout=5000)
    expect(kpi_title_invested).to_have_text("Invested Capital", timeout=5000)
    expect(lang_btn_en).to_have_class(re.compile(r"\bactive\b"), timeout=5000)
    expect(lang_btn_it).not_to_have_class(re.compile(r"\bactive\b"), timeout=5000)
    details.append("Scenario C1 superato: persistenza lingua inglese verificata dopo ricaricamento pagina")

    # 2. Selezione dell'italiano, ricaricamento e verifica persistenza
    lang_btn_it.click()
    page.wait_for_timeout(400)
    expect(add_btn_span).to_have_text("Nuovo Prodotto", timeout=5000)

    page.reload(wait_until="networkidle")
    page.wait_for_selector(".table-card", timeout=5000)
    page.wait_for_timeout(400)

    expect(add_btn_span).to_have_text("Nuovo Prodotto", timeout=5000)
    expect(kpi_title_invested).to_have_text("Capitale Investito", timeout=5000)
    expect(lang_btn_it).to_have_class(re.compile(r"\bactive\b"), timeout=5000)
    expect(lang_btn_en).not_to_have_class(re.compile(r"\bactive\b"), timeout=5000)

    stored_lang_reloaded = page.evaluate("() => localStorage.getItem('rsm_app_lang')")
    assert stored_lang_reloaded == "it", (
        f"Atteso localStorage 'rsm_app_lang' == 'it' dopo reload, ottenuto: {stored_lang_reloaded}"
    )
    details.append("Scenario C2 superato: persistenza lingua italiana verificata dopo ricaricamento pagina")

    # =========================================================================
    # SCENARIO D: Verifica zero errori console JavaScript
    # =========================================================================
    assert len(console_errors) == 0, f"Rilevati {len(console_errors)} errori JavaScript in console: {console_errors}"
    details.append("Scenario D superato: audit console JavaScript completato con 0 errori rossi")

    # =========================================================================
    # SCENARIO E: Checkpoint visivo screenshot e restituzione esito
    # =========================================================================
    screenshot_path = SCREENSHOTS_DIR / "level9_i18n.png"
    page.screenshot(path=str(screenshot_path), full_page=False)
    details.append(f"Scenario E superato: screenshot di checkpoint salvato in {screenshot_path.name}")

    return {
        "passed": True,
        "details": details,
        "screenshot_path": screenshot_path,
    }


def test_level9_i18n_pytest(sandbox_server: Any) -> None:
    """Entry point compatibile con pytest."""
    from playwright.sync_api import sync_playwright

    from tests.e2e.conftest import E2EContextManager

    with sync_playwright() as p, E2EContextManager(p, "level9_i18n", locale="en-US") as (page, console_errors):
        res = run_level9_i18n_checks(page, console_errors)
        assert res["passed"] is True
