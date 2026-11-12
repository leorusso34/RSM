"""Livello 8: Integrazione 17TRACK nel Side-Drawer dei Prodotti Venduti.

Verifiche E2E:
1. Creazione e selezione di un prodotto venduto (stato completed).
2. Apertura del side-drawer (#sideDrawer) e verifica presenza della sezione 'Spedizione & Tracking (17TRACK)'.
3. Verifica dello stato iniziale: form compatto con input codice (#drawerTrackingInput) e dropdown corriere (#drawerCarrierSelect).
4. Test Inserimento Senza Corriere (Auto 17TRACK):
   - Inserimento codice di tracciamento reale '179224188527748'.
   - Selezione lasciata su 'Auto (17TRACK)'.
   - Invio tramite pulsante 'Salva e Monitora' (#btnSaveDrawerTracking).
   - Verifica riconoscimento automatico del corriere: 'BRT Bartolini(DPD)'.
   - Conferma stato consegnato: badge 'Consegnato' (.drawer-tracking-badge.delivered).
   - Verifica di tutti gli aggiornamenti (8 tappe totali):
     * Prime 3 tappe visibili immediatamente con indicatori luminosi e date.
     * Presenza del pulsante a tendina 'Espandi cronologia completa (altre 5 tappe)'.
     * Click per espandere: srotolamento fluido di tutte le 8 tappe (#drawerTrackingHiddenEvents visibile).
     * Click per comprimere: ritorno alla vista compatta con le ultime tappe.
5. Test Aggiornamento (Refresh):
   - Click sul pulsante di aggiornamento nella card (.tracking-icon-btn con titolo 'Aggiorna').
   - Verifica notifica toast e persistenza dello stato 'Consegnato'.
6. Test Modifica Tracking:
   - Click sul pulsante 'Modifica' (icona matita).
   - Verifica ricomparsa del form con codice precompilato.
   - Forzatura esplicita del corriere 'BRT Bartolini' ('brt').
   - Salvataggio e verifica card aggiornata con corriere BRT.
7. Test Eliminazione Tracking:
   - Click sul pulsante 'Rimuovi' (icona cestino) con conferma dialog.
   - Verifica rimozione del tracking e ripristino del form iniziale vuoto.
8. Audit console JavaScript (0 errori).
9. Registrazione video completa level8_17track.webm.
"""

import json
import re
import urllib.request
from typing import Any

from playwright.sync_api import Page, expect

from tests.e2e.conftest import SANDBOX_BASE_URL


def run_level8_17track_checks(page: Page, console_errors: list[str]) -> dict[str, Any]:
    """Esegue tutte le asserzioni e i controlli del Livello 8 (17TRACK nel Side-Drawer)."""
    details = []

    # 1. Creazione di un prodotto venduto sandbox via API per il test
    prod_payload = {
        "name": "Jordan 4 Retro Military Black",
        "size": "42.5",
        "quantity": 1,
        "purchasedPrice": 210.0,
        "purchasedPlace": "SNKRS",
        "status": "completed",
        "soldPrice": 340.0,
        "fees": 25.0,
        "date": "2026-11-03",
        "notes": "Test E2E Spedizione 17TRACK",
    }
    req = urllib.request.Request(
        f"{SANDBOX_BASE_URL}/api/products",
        data=json.dumps(prod_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        created = json.loads(resp.read().decode("utf-8"))
        prod_id = created.get("id")
    assert prod_id is not None, "Creazione prodotto venduto fallita"
    details.append(f"Prodotto venduto creato con successo (ID #{prod_id})")

    # 2. Caricamento interfaccia e switch alla tab Storico Vendite (dove risiedono i prodotti completati)
    page.goto(SANDBOX_BASE_URL, wait_until="networkidle")
    page.wait_for_selector(".table-card", timeout=5000)
    page.wait_for_timeout(400)

    # Naviga alla sezione Storico Vendite
    page.click("li.nav-item[data-section='storico']")
    page.wait_for_selector("#inventory-table-body tr", timeout=5000)
    page.wait_for_timeout(300)

    # Click sulla riga del prodotto per aprire il side-drawer
    product_row = page.locator("tr:has-text('Jordan 4 Retro Military Black')")
    expect(product_row).to_be_visible(timeout=5000)
    product_row.click()

    # 3. Verifica apertura side-drawer
    drawer = page.locator("#sideDrawer")
    expect(drawer).to_have_class(re.compile(r"\bopen\b"), timeout=5000)
    details.append("Side-drawer aperto con successo al clic sul prodotto venduto")

    # Verifica titolo sezione tracking
    section_title = page.locator("#drawerTrackingSectionTitle")
    expect(section_title).to_have_text("Spedizione & Tracking (17TRACK)")
    details.append("Titolo sezione 'Spedizione & Tracking (17TRACK)' verificato")

    # 4. Verifica stato iniziale (nessun tracking associato)
    tracking_input = page.locator("#drawerTrackingInput")
    carrier_select = page.locator("#drawerCarrierSelect")
    save_btn = page.locator("#btnSaveDrawerTracking")
    expect(tracking_input).to_be_visible()
    expect(carrier_select).to_be_visible()
    expect(save_btn).to_be_visible()
    details.append("Form di inserimento tracciamento iniziale presente e visibile")

    # 5. TEST AUTO-CORRIERE: Inserimento codice 179224188527748 con corriere Automatico
    tracking_code = "179224188527748"
    tracking_input.fill(tracking_code)
    carrier_select.select_option("")  # Auto (17TRACK)
    with page.expect_response(lambda r: "/tracking" in r.url and r.request.method == "POST", timeout=20000):
        save_btn.click()
    details.append(f"Inviato codice {tracking_code} con corriere automatico a 17TRACK")

    # Attesa comparsa card tracking
    tracking_card = page.locator(".tracking-card-container")
    expect(tracking_card).to_be_visible(timeout=15000)

    # Verifica corriere riconosciuto automaticamente (BRT Bartolini)
    carrier_label = page.locator(".tracking-card-carrier")
    expect(carrier_label).to_contain_text("BRT Bartolini")
    details.append("Corriere 'BRT Bartolini' riconosciuto automaticamente da 17TRACK")

    # Verifica stato consegnato
    status_badge = page.locator("#drawerTrackingStatusBadge")
    expect(status_badge).to_be_visible()
    expect(status_badge).to_contain_text("Consegnato")
    expect(status_badge).to_have_class(re.compile(r"\bdelivered\b"))
    details.append("Stato 'Consegnato' con badge verde (.delivered) verificato con successo")

    # Verifica pillola codice tracciamento
    code_pill = page.locator(".tracking-code-pill")
    expect(code_pill).to_contain_text(tracking_code)

    # 6. Verifica delle tappe ed espansione tendina (8 tappe totali)
    # Prime 3 tappe visibili
    visible_nodes = page.locator(".tracking-timeline-list > .tracking-timeline-node")
    expect(visible_nodes).to_have_count(3)
    details.append("Prime 3 tappe visibili con spaziatura regolare e indicatori luminosi")

    # Pulsante tendina con conteggio delle tappe residue
    toggle_btn = page.locator("#drawerTrackingToggleBtn")
    expect(toggle_btn).to_be_visible()
    expect(toggle_btn).to_contain_text("altre 5 tappe")
    details.append("Pulsante a tendina 'Espandi cronologia completa (altre 5 tappe)' presente")

    # Click per espandere tutte le tappe
    toggle_btn.click()
    page.wait_for_timeout(300)
    hidden_events = page.locator("#drawerTrackingHiddenEvents")
    expect(hidden_events).to_be_visible()
    expect(toggle_btn).to_contain_text("Comprimi cronologia")

    # Verifica presenza complessiva di tutte le 8 tappe
    all_nodes = page.locator(".tracking-timeline-node")
    expect(all_nodes).to_have_count(8)
    details.append("Cronologia completa espansa con successo: tutte le 8 tappe sono presenti e visibili")

    # Click per ricomprimere
    toggle_btn.click()
    page.wait_for_timeout(300)
    expect(hidden_events).to_be_hidden()
    expect(toggle_btn).to_contain_text("altre 5 tappe")
    details.append("Cronologia ricompressa correttamente alla vista compatta")

    # 7. Test Aggiornamento (Refresh)
    refresh_btn = page.locator('.tracking-icon-btn[title*="Aggiorna"]')
    expect(refresh_btn).to_be_visible()
    with page.expect_response(lambda r: "/tracking?refresh=1" in r.url and r.status == 200, timeout=20000):
        refresh_btn.click()
    page.wait_for_timeout(300)
    expect(status_badge).to_contain_text("Consegnato")
    details.append("Pulsante refresh collaudato con conferma stato 'Consegnato'")

    # 8. Test Modifica Tracking
    edit_tracking_btn = page.locator('.tracking-icon-btn[title*="Modifica"]')
    expect(edit_tracking_btn).to_be_visible()
    edit_tracking_btn.click()
    page.wait_for_selector("#drawerTrackingInput", timeout=5000)

    # Verifica form di modifica ricomparso con codice precompilato
    drawer_tracking_input = page.locator("#drawerTrackingInput")
    expect(drawer_tracking_input).to_be_visible()
    expect(drawer_tracking_input).to_have_value(tracking_code)

    # Forzatura esplicita corriere BRT e re-invio
    carrier_select.select_option("brt")
    with page.expect_response(lambda r: "/tracking" in r.url and r.request.method == "POST", timeout=20000):
        page.locator("#btnSaveDrawerTracking").click()
    page.wait_for_selector(".tracking-card-container", timeout=15000)
    expect(carrier_label).to_contain_text("BRT Bartolini")
    details.append("Modifica tracking con selezione esplicita corriere BRT completata con successo")

    # 9. Test Eliminazione Tracking (il dialog di conferma è gestito automaticamente da E2EContextManager)
    delete_tracking_btn = page.locator('.tracking-icon-btn[title*="Rimuovi"]')
    expect(delete_tracking_btn).to_be_visible()
    with page.expect_response(lambda r: "/tracking" in r.url and r.request.method == "DELETE", timeout=10000):
        delete_tracking_btn.click()
    page.wait_for_selector("#drawerTrackingInput", timeout=5000)

    # Verifica ripristino form vuoto iniziale
    empty_tracking_input = page.locator("#drawerTrackingInput")
    expect(empty_tracking_input).to_be_visible()
    expect(empty_tracking_input).to_have_value("")
    expect(status_badge).to_be_hidden()
    details.append("Eliminazione tracking verificata: rimosso dal database e ripristinato form iniziale")

    # Chiusura side-drawer (ESC rapido)
    page.keyboard.press("Escape")
    page.wait_for_selector("#sideDrawer.open", state="detached", timeout=3000)
    details.append("Side-drawer richiuso correttamente")

    # 10. Audit console JavaScript
    assert len(console_errors) == 0, f"Rilevati errori console durante il test 17TRACK: {console_errors}"
    details.append("Audit console superato: 0 errori JavaScript rilevati")

    return {
        "passed": True,
        "details": details,
        "screenshot_path": None,
    }


def test_level8_17track_pytest(sandbox_server: Any) -> None:
    """Entry point compatibile con pytest."""
    from playwright.sync_api import sync_playwright

    from tests.e2e.conftest import E2EContextManager

    with sync_playwright() as p, E2EContextManager(p, "level8_17track") as (page, console_errors):
        res = run_level8_17track_checks(page, console_errors)
        assert res["passed"] is True
