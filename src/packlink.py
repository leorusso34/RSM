"""Modulo di integrazione con le REST API di Packlink PRO (v1).

Responsabilità:
- Creazione bozze di spedizione (drafts) su Packlink PRO (POST /v1/drafts).
- Validazione e formattazione payload mittente/destinatario e colli.
- Apertura diretta del pannello di gestione bozze nel browser.
"""

import http.client
import json
import re
from typing import Any

PACKLINK_API_HOST = "api.packlink.com"
PACKLINK_DRAFTS_PATH = "/v1/drafts"
PACKLINK_DRAFTS_WEB_URL = "https://pro.packlink.it/private/shipments/drafts"


def create_packlink_draft(
    api_key: str,
    recipient: dict[str, Any],
    package_info: dict[str, Any] | None = None,
    content: str = "Abbigliamento / Calzature",
    sender: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Crea una nuova bozza di spedizione su Packlink PRO via REST API.

    Se `sender` è None, Packlink PRO applica automaticamente l'indirizzo mittente
    predefinito salvato nell'account dell'utente.

    Args:
        api_key: Chiave API personale di Packlink PRO.
        recipient: Dizionario contenente i dati del destinatario (name, surname, street1, zip, city, phone, ecc.).
        package_info: Dimensioni e peso del collo (weight, length, width, height).
        content: Descrizione merci spedite (default: "Abbigliamento / Calzature").
        sender: Indirizzo mittente opzionale (se omesso usa il default dell'account Packlink).

    Returns:
        Dizionario con esito, ID bozza e codice di riferimento Packlink PRO.
    """
    clean_key = str(api_key or "").strip()
    if not clean_key:
        return {
            "success": False,
            "error": "Chiave API di Packlink PRO mancante. Configurala in 'Spedizioni Packlink' o nel file config.json.",
        }

    # Normalizzazione nome e cognome
    full_name = str(recipient.get("name", "")).strip()
    surname = str(recipient.get("surname", "")).strip()
    if not surname and " " in full_name:
        parts = full_name.split(" ", 1)
        full_name, surname = parts[0], parts[1]
    elif not surname:
        surname = "."

    street1 = str(recipient.get("street1", "")).strip()
    street2 = str(recipient.get("street2", "")).strip()
    zip_code = str(recipient.get("zip", "") or recipient.get("postal_code", "")).strip()
    city = str(recipient.get("city", "")).strip()
    country = str(recipient.get("country", "IT")).strip().upper() or "IT"
    phone = str(recipient.get("phone", "")).strip()
    email = str(recipient.get("email", "")).strip()

    if not full_name:
        return {"success": False, "error": "Il nome del destinatario è obbligatorio."}
    if not street1:
        return {"success": False, "error": "L'indirizzo di destinazione (via e civico) è obbligatorio."}
    if not zip_code:
        return {"success": False, "error": "Il CAP del destinatario è obbligatorio."}
    if not city:
        return {"success": False, "error": "La città del destinatario è obbligatoria."}
    if not phone:
        return {"success": False, "error": "Il numero di telefono del destinatario è obbligatorio per il corriere."}

    # Normalizzazione parametri collo
    pkg = package_info or {}
    try:
        weight = float(str(pkg.get("weight", 1.2)).replace(",", "."))
    except (ValueError, TypeError):
        weight = 1.2

    try:
        length = float(str(pkg.get("length", 34.0)).replace(",", "."))
    except (ValueError, TypeError):
        length = 34.0

    try:
        width = float(str(pkg.get("width", 23.0)).replace(",", "."))
    except (ValueError, TypeError):
        width = 23.0

    try:
        height = float(str(pkg.get("height", 13.0)).replace(",", "."))
    except (ValueError, TypeError):
        height = 13.0

    payload: dict[str, Any] = {
        "source": "RSM",
        "content": str(content or "Abbigliamento / Calzature").strip(),
        "to": {
            "name": full_name,
            "surname": surname,
            "company": str(recipient.get("company", "")).strip(),
            "street1": street1,
            "street2": street2,
            "zip": zip_code,
            "city": city,
            "country": country,
            "phone": phone,
            "email": email or "supporto@packlink.it",
        },
        "packages": [
            {
                "weight": max(0.1, round(weight, 2)),
                "length": max(1.0, round(length, 1)),
                "width": max(1.0, round(width, 1)),
                "height": max(1.0, round(height, 1)),
            }
        ],
    }

    if sender:
        payload["from"] = sender

    json_data = json.dumps(payload, ensure_ascii=False)
    headers = {
        "Authorization": clean_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "RSM-Inventory-Manager/1.6.3",
    }

    conn = http.client.HTTPSConnection(PACKLINK_API_HOST, timeout=20)
    try:
        conn.request("POST", PACKLINK_DRAFTS_PATH, body=json_data.encode("utf-8"), headers=headers)
        response = conn.getresponse()
        resp_bytes = response.read()
        status_code = response.status

        try:
            resp_json = json.loads(resp_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            resp_json = {}

        if status_code in (200, 201):
            draft_id = resp_json.get("id") or resp_json.get("reference")
            shipment_ref = resp_json.get("shipment_reference") or resp_json.get("reference") or draft_id
            return {
                "success": True,
                "draft_id": draft_id,
                "reference": shipment_ref,
                "web_url": PACKLINK_DRAFTS_WEB_URL,
                "data": resp_json,
            }

        # Gestione errori API
        if status_code == 401:
            return {
                "success": False,
                "error": "Chiave API di Packlink PRO non valida o non autorizzata. Verifica la chiave generata su Packlink PRO.",
                "status_code": 401,
            }

        err_detail = resp_json.get("message") or resp_json.get("error") or resp_bytes.decode("utf-8", errors="ignore")
        return {
            "success": False,
            "error": f"Errore Packlink PRO ({status_code}): {err_detail}",
            "status_code": status_code,
            "raw_response": resp_json,
        }
    except OSError as e:
        return {
            "success": False,
            "error": f"Errore di connessione verso {PACKLINK_API_HOST}: {e}",
        }
    finally:
        conn.close()


def fallback_regex_parse_address(raw_text: str) -> dict[str, Any]:
    """Estrazione euristica locale tramite regex per recapiti, CAP, telefono e città

    nel caso in cui il servizio AI proxy non sia momentaneamente raggiungibile.
    """
    text = raw_text.strip()
    result: dict[str, Any] = {
        "name": "",
        "surname": "",
        "street1": "",
        "street2": "",
        "zip": "",
        "city": "",
        "phone": "",
        "email": "",
        "weight": 1.2,
        "length": 34.0,
        "width": 23.0,
        "height": 13.0,
    }

    # Estrazione email
    email_m = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    if email_m:
        result["email"] = email_m.group(0)

    # Estrazione telefono (italiano / internazionale)
    phone_m = re.search(r"(?:\+39\s*)?(?:3\d{2}[\s\.-]?\d{6,7}|0\d{1,3}[\s\.-]?\d{5,7})", text)
    if phone_m:
        result["phone"] = re.sub(r"[\s\.-]", "", phone_m.group(0))

    # Estrazione CAP (5 cifre)
    zip_m = re.search(r"\b\d{5}\b", text)
    if zip_m:
        result["zip"] = zip_m.group(0)

    # Estrazione peso se presente (es. 1.5kg o 500g)
    weight_kg = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:kg|chili)\b", text, re.IGNORECASE)
    if weight_kg:
        try:
            result["weight"] = float(weight_kg.group(1).replace(",", "."))
        except ValueError:
            pass
    else:
        weight_g = re.search(r"(\d+)\s*(?:g|grammi)\b", text, re.IGNORECASE)
        if weight_g:
            try:
                result["weight"] = float(weight_g.group(1)) / 1000.0
            except ValueError:
                pass

    return result
