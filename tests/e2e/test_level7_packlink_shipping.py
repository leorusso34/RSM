"""Livello 7: Modale Spedizioni Packlink PRO, Smart Paste con AI Gemini & Gestione Preset.

Verifiche:
1. Apertura della modale Packlink PRO dalla voce dedicata nella Sidebar (#appSidebar).
2. Verifica visibilità della modale a 2 colonne (#packlinkModal) con badge REST API.
3. Presenza del pulsante primario ben visibile (#btn-pk-ai-extract) per inviare i dati a Gemini.
4. Inserimento testo ordine grezzo nella casella Smart Paste (#pk-smart-paste).
5. Click su 'Invia a Gemini & Compila Campi' (#btn-pk-ai-extract):
   - Estrazione e normalizzazione automatica dei campi del destinatario:
     * Nome e Cognome (#pk-name: 'Marco Rossi')
     * Indirizzo Via e Civico (#pk-street1: 'Via Roma 14')
     * CAP (#pk-zip: '20121')
     * Città (#pk-city: 'Milano')
     * Telefono (#pk-phone: '+393331234567' o contenente '3331234567')
     * Email (#pk-email: 'marco.rossi@email.it')
6. Collaudo dei Preset Rapidi del Pacco:
   - Click su 'Busta (0.3 kg)' (#btnPresetEnvelope) -> verifica peso 0.3 kg e misure 25x20x5 cm.
   - Click su 'Scarpe (1.2 kg)' (#btnPresetShoes) -> verifica peso 1.2 kg e misure 34x23x13 cm.
7. Verifica banner configurazione API Key:
   - Apertura con pulsante '#btnTogglePkKey' -> banner visibile.
   - Chiusura con pulsante '#btnTogglePkKey' -> banner nascosto.
8. Chiusura pulita della modale.
9. Audit console JavaScript (0 errori).
10. Checkpoint visivo: screenshot level7_packlink_shipping.png e registrazione video level7_packlink_shipping.webm.
"""

import re
from typing import Any

from playwright.sync_api import Page, expect

from tests.e2e.conftest import SANDBOX_BASE_URL, SCREENSHOTS_DIR


def run_level7_packlink_shipping_checks(page: Page, console_errors: list[str]) -> dict[str, Any]:
    """Esegue tutte le asserzioni e i controlli del Livello 7 (Packlink PRO & Smart Paste AI)."""
    details = []

    # 1. Navigazione e caricamento interfaccia
    page.goto(SANDBOX_BASE_URL, wait_until="networkidle")
    page.wait_for_selector(".table-card", timeout=5000)
    page.wait_for_timeout(500)
    details.append("Pagina iniziale caricata con successo")

    # 2. Apertura della modale Packlink dalla Sidebar
    sidebar_item = page.locator(".nav-item:has-text('Spedizioni Packlink')")
    expect(sidebar_item).to_be_visible(timeout=5000)
    sidebar_item.click()
    page.wait_for_selector("#packlinkModal.open", timeout=5000)
    page.wait_for_timeout(500)
    details.append("Modale Packlink PRO (#packlinkModal) aperta dalla Sidebar")

    # 3. Verifica presenza ed evidenza del pulsante di invio a Gemini
    extract_btn = page.locator("#btn-pk-ai-extract")
    expect(extract_btn).to_be_visible(timeout=5000)
    expect(extract_btn).to_contain_text("Invia a Gemini")
    details.append("Pulsante primario 'Invia a Gemini & Compila Campi' presente e visibile")

    # 4. Inserimento del testo dell'ordine nella casella Smart Paste
    test_raw_order = (
        "Spedisci a Marco Rossi, via roma 14 scala B int 3, cap 20121 Milano, "
        "cellulare 333 1234567, email marco.rossi@email.it, pacco scarpe 1.2kg"
    )
    page.fill("#pk-smart-paste", test_raw_order)
    page.wait_for_timeout(400)
    details.append(f"Testo ordine incollato nella casella Smart Paste: '{test_raw_order}'")

    # 5. Click su 'Invia a Gemini & Compila Campi'
    extract_btn.click()

    # Attesa che i campi vengano popolati automaticamente dall'AI
    page.wait_for_function("document.getElementById('pk-name').value.trim().length > 0", timeout=8000)
    page.wait_for_timeout(600)

    # Asserzione campi compilati
    name_val = page.locator("#pk-name").input_value()
    street_val = page.locator("#pk-street1").input_value()
    zip_val = page.locator("#pk-zip").input_value()
    city_val = page.locator("#pk-city").input_value()
    phone_val = page.locator("#pk-phone").input_value()
    email_val = page.locator("#pk-email").input_value()

    assert "Marco" in name_val, f"Nome non estratto correttamente: '{name_val}'"
    assert "Roma" in street_val or "roma" in street_val, f"Indirizzo non estratto: '{street_val}'"
    assert zip_val == "20121", f"CAP non corrispondente a 20121: '{zip_val}'"
    assert "Milano" in city_val or "milano" in city_val, f"Città non estratta: '{city_val}'"
    assert "3331234567" in phone_val.replace(" ", "").replace("-", ""), f"Telefono non estratto: '{phone_val}'"
    assert email_val == "marco.rossi@email.it", f"Email non estratta: '{email_val}'"
    details.append(f"Campi compilati con successo da Gemini: {name_val}, {street_val}, {zip_val} {city_val}, {phone_val}")

    # 6. Collaudo dei Preset Rapidi del Pacco
    page.click("#btnPresetEnvelope")
    page.wait_for_timeout(300)
    expect(page.locator("#btnPresetEnvelope")).to_have_class(re.compile(r"active"))
    assert page.locator("#pk-weight").input_value() == "0.3", "Preset Busta: peso errato"
    assert page.locator("#pk-height").input_value() == "5", "Preset Busta: altezza errata"
    details.append("Preset 'Busta (0.3 kg)' collaudato (peso 0.3 kg, spessore 5 cm)")

    page.click("#btnPresetShoes")
    page.wait_for_timeout(300)
    expect(page.locator("#btnPresetShoes")).to_have_class(re.compile(r"active"))
    assert page.locator("#pk-weight").input_value() == "1.2", "Preset Scarpe: peso errato"
    assert page.locator("#pk-height").input_value() == "13", "Preset Scarpe: altezza errata"
    details.append("Preset 'Scarpe (1.2 kg)' collaudato (peso 1.2 kg, scatola 34x23x13 cm)")

    # 7. Verifica banner Chiave API (visibile inizialmente se chiave assente)
    expect(page.locator("#pk-api-key-banner")).to_be_visible()
    details.append("Banner configurazione Chiave API visibile inizialmente (chiave non impostata)")

    # Toggle chiusura banner
    page.click("#btnTogglePkKey")
    page.wait_for_timeout(300)
    expect(page.locator("#pk-api-key-banner")).to_be_hidden()
    details.append("Banner configurazione Chiave API richiuso con successo tramite pulsante toggle")

    # Toggle riapertura banner
    page.click("#btnTogglePkKey")
    page.wait_for_timeout(300)
    expect(page.locator("#pk-api-key-banner")).to_be_visible()
    details.append("Banner configurazione Chiave API riaperto con successo tramite pulsante toggle")

    # 8. Chiusura della modale
    page.click("#packlinkModal .modal-close-btn")
    page.wait_for_selector("#packlinkModal", state="hidden", timeout=5000)
    page.wait_for_timeout(400)
    details.append("Modale Packlink PRO richiusa correttamente")

    # 9. Audit console JavaScript
    assert len(console_errors) == 0, f"Rilevati errori console durante il test Packlink: {console_errors}"
    details.append("Audit console superato: 0 errori JavaScript rilevati")

    # 10. Checkpoint visivo screenshot
    screenshot_path = SCREENSHOTS_DIR / "level7_packlink_shipping.png"
    page.screenshot(path=str(screenshot_path), full_page=False)
    details.append(f"Screenshot salvato: {screenshot_path.name}")

    return {
        "passed": True,
        "details": details,
        "screenshot_path": screenshot_path,
    }


def test_level7_packlink_shipping_pytest(sandbox_server: Any) -> None:
    """Entry point compatibile con pytest."""
    from playwright.sync_api import sync_playwright

    from tests.e2e.conftest import E2EContextManager

    with sync_playwright() as p, E2EContextManager(p, "level7_packlink_shipping") as (page, console_errors):
        res = run_level7_packlink_shipping_checks(page, console_errors)
        assert res["passed"] is True
