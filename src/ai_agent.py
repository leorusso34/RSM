"""Modulo per l'integrazione con Google Gemini AI per l'estrazione dati prodotti."""

import http.client
import json
import re
import urllib.parse
from typing import Any

from .config import RSM_AUTH_KEY, WORKER_URL


def _safe_parse_json_products(raw_content: str) -> list[dict[str, Any]]:
    """
    Decodifica in modo resiliente il payload JSON dei prodotti restituito dall'AI.
    Se la risposta è stata troncata ai limiti di token, ripara automaticamente
    l'array JSON per recuperare tutti i prodotti generati fino all'ultimo valido.
    """
    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    # 1. Tentativo standard diretto
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data.get("products", [])
        elif isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # 2. Riparazione JSON troncato: trova l'ultimo oggetto chiuso '}' e sigilla l'array
    idx = cleaned.rfind("}")
    while idx > 0:
        candidate = cleaned[:idx + 1] + "]}"
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data.get("products", [])
            elif isinstance(data, list):
                return data
        except json.JSONDecodeError:
            idx = cleaned.rfind("}", 0, idx)

    # 3. Fallback: estrazione manuale di tutti gli oggetti JSON validi
    pattern = re.compile(r'\{[^{}]*"name"[^{}]*\}')
    objects = []
    for match in pattern.finditer(cleaned):
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict) and obj.get("name"):
                objects.append(obj)
        except (json.JSONDecodeError, ValueError):
            pass
    if objects:
        return objects

    raise ValueError(f"Impossibile interpretare la risposta AI come elenco prodotti JSON: {raw_content[:200]}...")


def parse_product_with_ai(prompt: str) -> list[dict[str, Any]]:
    """
    Invia la richiesta testuale al Cloudflare Worker proxy per estrarre i dati
    di UNO O PIÙ prodotti tramite Google Gemini.
    Restituisce una lista di dizionari, uno per prodotto.
    """
    if not WORKER_URL:
        raise RuntimeError("WORKER_URL non è configurato.")

    # Schema per un singolo prodotto (riutilizzato dentro l'array)
    product_schema = {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING"},
            "size": {"type": "STRING", "description": "A meno che non venga scritto diversamente metti rigorosamente UNI come valore di default."},
            "quantity": {"type": "INTEGER", "description": "Non ci sono limiti di quantità, e il valore di default è sempre 1, ma se viene scritto un numero subito dopo una x, allora la quantità sarà quel numero."},
            "purchased_price": {"type": "NUMBER", "description": "Prezzo di acquisto UNITARIO per singolo pezzo. Se viene indicato un prezzo totale per più pezzi, dividi per la quantità."},
            "purchased_place": {"type": "STRING"},
            "status": {"type": "STRING", "description": "Scegli rigorosamente tra: 'In Stock', 'Pre-ordine', 'Venduto', o 'Completato'. Default: 'In Stock'."},
            "release_date": {"type": "STRING", "description": "Se non inserita la data inserire la data di oggi. Formato: YYYY-MM-DD."}
        },
        "required": ["name", "quantity", "purchased_price", "status"]
    }

    # Schema radice: un oggetto con una lista di prodotti
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "products": {
                "type": "ARRAY",
                "items": product_schema
            }
        },
        "required": ["products"]
    }

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {
            "parts": [{"text": "Sei un assistente per l'inventario. Estrai TUTTI i prodotti menzionati nel testo. Restituisci sempre una lista 'products', anche se c'è un solo prodotto. I prezzi devono essere SEMPRE UNITARI per singolo pezzo (se il prezzo indicato è totale per più pezzi, dividilo per la quantità). Mappa i dati nello schema JSON, senza commenti o markdown. Formato date: YYYY-MM-DD."}]
        },
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 65536,
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        }
    }

    data = json.dumps(payload).encode("utf-8")

    parsed_w = urllib.parse.urlparse(WORKER_URL.strip())
    w_host = parsed_w.netloc
    w_path = f"{parsed_w.path.rstrip('/')}/api/gemini/generate"
    w_headers = {"Content-Type": "application/json"}
    if RSM_AUTH_KEY:
        w_headers["X-RSM-Auth"] = RSM_AUTH_KEY.strip()

    conn_cls = http.client.HTTPSConnection if parsed_w.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(w_host, timeout=25)
    try:
        conn.request("POST", w_path, body=data, headers=w_headers)
        response = conn.getresponse()
        resp_data = response.read().decode("utf-8")
        if response.status != 200:
            raise RuntimeError(f"Errore Proxy AI ({response.status}): {resp_data}")
        result = json.loads(resp_data)
        if "candidates" in result and len(result["candidates"]) > 0:
            content = result["candidates"][0]["content"]["parts"][0]["text"]
            return _safe_parse_json_products(content)
        raise ValueError(f"Risposta inaspettata dal proxy AI: {resp_data}")
    except (OSError, http.client.HTTPException, ValueError) as e:
        raise RuntimeError(f"Errore di connessione proxy AI: {e!s}") from e
    finally:
        conn.close()


def parse_excel_with_ai(raw_text: str, user_hint: str = "") -> list[dict[str, Any]]:
    """
    Analizza l'intero contenuto testuale di un file Excel/CSV con una singola
    chiamata al Cloudflare Worker proxy e restituisce la lista di prodotti estratti in formato JSON.
    """
    if not WORKER_URL:
        raise RuntimeError("WORKER_URL non è configurato.")

    hint_clause = f"\nNOTA DELL'UTENTE SULLA STRUTTURA DEL FILE:\n\"{user_hint.strip()}\"\n" if user_hint.strip() else ""

    system_instruction = (
        "Sei un assistente specializzato nell'estrazione ed importazione dati per un software gestionale di magazzino (RSM).\n"
        "Riceverai il testo grezzo estratto da un foglio di calcolo (Excel o CSV) con tutte le sue righe e colonne.\n"
        "Il tuo compito è comprendere la struttura della tabella, identificare le colonne rilevanti e convertire OGNI riga "
        "valida di prodotto in un oggetto strutturato conforme allo schema JSON richiesto.\n\n"
        "REGOLE DI MAPPATURA DEI CAMPI:\n"
        "1. 'name': Nome del prodotto/scarpa/articolo (es. 'Jordan 4 Military Black', 'Travis Scott Olive').\n"
        "2. 'size': Taglia del prodotto. Se la taglia è un numero o un valore specifico (es. '42', '42.5', 'US 9', 'M', 'L'), riportala pulita. "
        "Se assente o non applicabile, usa rigorosamente 'UNI'.\n"
        "3. 'quantity': Quantità acquistata. Numero intero >= 1. Se assente, usa 1.\n"
        "4. 'purchased_price': Prezzo di acquisto UNITARIO in euro (numero con decimali, es. 120 o 120.50). "
        "ATTENZIONE CRITICA: Se il prezzo indicato nel foglio è il TOTALE dell'ordine per più pezzi, "
        "devi dividerlo per la quantità per ottenere sempre e solo il prezzo unitario!\n"
        "5. 'purchased_place': Luogo o piattaforma di acquisto (es. 'SNKRS', 'Nike', 'Privato', 'Foot Locker'). Se vuoto, lascia stringa vuota.\n"
        "6. 'status': Stato attuale del prodotto. Scegli RIGOROSAMENTE tra questi quattro valori esatti:\n"
        "   - 'In Stock' (se l'articolo è disponibile in magazzino o invenduto)\n"
        "   - 'Pre-ordine' (se ordinato ma non ancora arrivato)\n"
        "   - 'Venduto' (se è già stato venduto)\n"
        "   - 'Completato' (se la vendita è conclusa)\n"
        "   Se non specificato o ambiguo, usa 'In Stock'.\n"
        "7. 'selling_place': Se lo stato è Venduto o Completato, la piattaforma di vendita (es. 'StockX', 'Vinted', 'eBay'). Altrimenti stringa vuota.\n"
        "8. 'sold_price': Se venduto, il prezzo effettivo incassato/venduto unitario. Altrimenti null.\n"
        "9. 'fees': Commissioni di vendita totali per la transazione in euro. Se assenti, usa 0.0.\n"
        "10. 'release_date': Data di uscita o acquisto nel formato 'YYYY-MM-DD'. Se manca l'anno, usa l'anno corrente. Se non deducibile, usa la data odierna.\n"
        "11. 'notes': Codice SKU/style code o eventuali note aggiuntive.\n\n"
        "REGOLE GENERALI:\n"
        "- Salta le righe di intestazione, i totali riepilogativi, le righe vuote o le note generali a piè pagina.\n"
        "- Restituisci SEMPRE tutti i prodotti trovati come array 'products' nello schema JSON.\n"
        f"{hint_clause}"
    )

    product_schema = {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING"},
            "size": {"type": "STRING"},
            "quantity": {"type": "INTEGER"},
            "purchased_price": {"type": "NUMBER"},
            "purchased_place": {"type": "STRING"},
            "status": {"type": "STRING"},
            "selling_place": {"type": "STRING"},
            "sold_price": {"type": "NUMBER"},
            "fees": {"type": "NUMBER"},
            "release_date": {"type": "STRING"},
            "notes": {"type": "STRING"}
        },
        "required": ["name", "quantity", "purchased_price", "status"]
    }

    response_schema = {
        "type": "OBJECT",
        "properties": {
            "products": {
                "type": "ARRAY",
                "items": product_schema
            }
        },
        "required": ["products"]
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"Ecco il contenuto del foglio di calcolo da importare:\n\n{raw_text}"
                    }
                ]
            }
        ],
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 65536,
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        }
    }

    data = json.dumps(payload).encode("utf-8")

    parsed_w = urllib.parse.urlparse(WORKER_URL.strip())
    w_host = parsed_w.netloc
    w_path = f"{parsed_w.path.rstrip('/')}/api/gemini/generate"
    w_headers = {"Content-Type": "application/json"}
    if RSM_AUTH_KEY:
        w_headers["X-RSM-Auth"] = RSM_AUTH_KEY.strip()

    conn_cls = http.client.HTTPSConnection if parsed_w.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(w_host, timeout=180)
    try:
        conn.request("POST", w_path, body=data, headers=w_headers)
        response = conn.getresponse()
        resp_data = response.read().decode("utf-8")
        if response.status != 200:
            raise RuntimeError(f"Errore Proxy AI ({response.status}): {resp_data}")
        result = json.loads(resp_data)
        if "candidates" in result and len(result["candidates"]) > 0:
            content = result["candidates"][0]["content"]["parts"][0]["text"]
            return _safe_parse_json_products(content)
        raise ValueError(f"Risposta AI inaspettata dal proxy: {resp_data}")
    except TimeoutError:
        raise RuntimeError("Tempo scaduto: il server proxy AI ha impiegato più di 3 minuti. Riprova.") from None
    except (OSError, http.client.HTTPException, ValueError) as e:
        raise RuntimeError(f"Errore proxy AI Excel import: {e!s}") from e
    finally:
        conn.close()
