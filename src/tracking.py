"""Modulo di integrazione con le API di 17TRACK tramite Cloudflare Worker Proxy di RSM.

Fornisce:
- Interrogazione in tempo reale dello stato delle spedizioni.
- Riconoscimento automatico del corriere o forzatura manuale (BRT, Poste, GLS, InPost, UPS, DHL, ecc.).
- Normalizzazione e formattazione della cronologia delle tappe/eventi.
"""

import http.client
import json
import urllib.parse
from datetime import datetime, timezone
from typing import Any

# Configurazione del Worker Cloudflare di RSM
WORKER_URL = "https://rsm-proxy.leorusso34-441.workers.dev"
RSM_AUTH_KEY = "CucGxi.PEhfgR6MFry*s"

STATUS_LABELS_IT: dict[str, str] = {
    "Delivered": "Consegnato",
    "InTransit": "In Transito",
    "PickedUp": "Ritirato",
    "OutForDelivery": "In Consegna",
    "ForDelivery": "In Consegna",
    "AvailableForPickup": "Disponibile per il ritiro",
    "Returning": "In Restituzione",
    "Returned": "Restituito al mittente",
    "NotFound": "In attesa di tracciamento",
    "Alert": "Avviso / Eccezione",
    "Expired": "Spedizione Scaduta",
    "Undelivered": "Mancata Consegna",
}


def translate_status(raw_status: str) -> str:
    """Traduce lo stato di 17TRACK in italiano comprensibile per l'utente."""
    return STATUS_LABELS_IT.get(raw_status, raw_status or "In Lavorazione")


def fetch_tracking_info(
    tracking_number: str,
    carrier: str = "",
    timeout: int = 15,
    worker_url: str = WORKER_URL,
    auth_key: str = RSM_AUTH_KEY,
) -> dict[str, Any]:
    """Interroga le API di 17TRACK tramite il Worker Cloudflare di RSM.

    Args:
        tracking_number: Codice della spedizione / lettera di vettura.
        carrier: Chiave opzionale del corriere (es. 'brt', 'poste', 'sda', 'gls', 'inpost', 'ups', 'dhl').
        timeout: Timeout in secondi della connessione HTTP (default: 15s).
        worker_url: URL base del Worker Cloudflare proxy (configurabile per i test).
        auth_key: Chiave di autenticazione per l'header X-RSM-Auth.

    Returns:
        Dizionario strutturato con l'esito della chiamata, corriere, stato ed elenco delle tappe.
    """
    clean_number = "".join(str(tracking_number or "").split()).strip()
    if not clean_number:
        return {
            "success": False,
            "error": "Codice di tracciamento vuoto o non valido.",
        }

    clean_carrier = str(carrier or "").strip().lower()

    parsed_url = urllib.parse.urlparse(worker_url.strip())
    host = parsed_url.netloc
    if not host:
        return {
            "success": False,
            "error": f"URL del proxy Cloudflare non valido: {worker_url}",
        }

    query_params: dict[str, str] = {"number": clean_number}
    if clean_carrier:
        # Assicura che 'inpost' punti specificamente al corriere InPost Italy (17TRACK provider 100469)
        if clean_carrier in ("inpost", "inpost-it", "inpost_it", "inpost-italy"):
            query_params["carrier"] = "inpost-it"
        else:
            query_params["carrier"] = clean_carrier

    query_str = urllib.parse.urlencode(query_params)
    path = f"/api/tracking?{query_str}"

    headers = {
        "Accept": "application/json",
        "X-RSM-Auth": auth_key,
    }

    conn = None
    try:
        conn_cls = http.client.HTTPSConnection if parsed_url.scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(host, timeout=timeout)
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        raw_body = resp.read().decode("utf-8")
        status_code = resp.status
    except Exception as err:  # noqa: BLE001
        return {
            "success": False,
            "error": f"Errore di connessione di rete con il servizio di tracking: {err}",
        }
    finally:
        if conn:
            conn.close()

    if status_code != 200:
        return {
            "success": False,
            "status_code": status_code,
            "error": f"Il server di tracking ha risposto con codice HTTP {status_code}: {raw_body[:200]}",
        }

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "La risposta del servizio di tracking non è in formato JSON valido.",
            "raw": raw_body[:300],
        }

    data_block = payload.get("data", {})
    accepted_list = data_block.get("accepted", [])
    rejected_list = data_block.get("rejected", [])

    if rejected_list and not accepted_list:
        rejected_item = rejected_list[0]
        err_info = rejected_item.get("error", {})
        err_msg = err_info.get("message") or "Spedizione non riconosciuta o codice non valido."
        return {
            "success": False,
            "error": err_msg,
            "tracking_number": clean_number,
            "carrier": clean_carrier,
        }

    if not accepted_list:
        # Se 17TRACK restituisce un payload generico senza accepted
        msg = payload.get("message") or "Nessuna informazione di tracciamento disponibile per questo codice."
        return {
            "success": False,
            "error": msg,
            "tracking_number": clean_number,
            "carrier": clean_carrier,
        }

    item = accepted_list[0]
    track_info = item.get("track_info", {})
    latest_status = track_info.get("latest_status", {})

    status_name = latest_status.get("status") or "NotFound"
    sub_status = latest_status.get("sub_status_descr") or latest_status.get("sub_status") or ""

    providers = track_info.get("tracking", {}).get("providers", [])
    carrier_name = "Corriere"
    carrier_key = clean_carrier
    events_raw: list[dict[str, Any]] = []

    if providers:
        primary_provider = providers[0]
        provider_info = primary_provider.get("provider", {})
        carrier_name = provider_info.get("name") or carrier_name
        carrier_alias = provider_info.get("alias") or provider_info.get("key") or ""
        if not carrier_key and carrier_alias:
            carrier_key = str(carrier_alias).lower()
        events_raw = primary_provider.get("events", [])

    parsed_events: list[dict[str, Any]] = []
    for ev in events_raw:
        time_iso = ev.get("time_iso") or ev.get("time_utc") or ""
        desc = str(ev.get("description") or "").strip()
        location = str(ev.get("location") or "").strip()
        stage = str(ev.get("stage") or "").strip()

        # Formattazione data leggibile
        formatted_date = time_iso
        if time_iso:
            try:
                # Estrai parte data e ora: es. 2026-11-03T15:27:00+01:00 -> 03/11/2026 15:27
                clean_iso = time_iso.split("+")[0].split("Z")[0]
                dt = datetime.fromisoformat(clean_iso)
                formatted_date = dt.strftime("%d/%m/%Y %H:%M")
            except Exception:  # noqa: BLE001
                formatted_date = time_iso

        parsed_events.append(
            {
                "time_iso": time_iso,
                "formatted_date": formatted_date,
                "description": desc,
                "location": location,
                "stage": stage,
            }
        )

    # Ordina gli eventi dal più recente al più vecchio se hanno timestamp
    parsed_events.sort(key=lambda x: x.get("time_iso") or "", reverse=True)

    latest_event = parsed_events[0] if parsed_events else None

    return {
        "success": True,
        "tracking_number": clean_number,
        "carrier": carrier_key,
        "carrier_name": carrier_name,
        "status": status_name,
        "status_label": translate_status(status_name),
        "sub_status": sub_status,
        "latest_event": latest_event,
        "events": parsed_events,
        "events_count": len(parsed_events),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
