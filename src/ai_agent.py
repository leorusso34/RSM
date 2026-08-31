import json
import http.client
from typing import Any, List, Dict

def parse_product_with_ai(prompt: str, api_key: str) -> List[Dict[str, Any]]:
    """
    Invia la richiesta testuale all'API di Gemini per estrarre i dati di UNO O PIÙ prodotti.
    Restituisce una lista di dizionari, uno per prodotto.
    Utilizza http.client puro per evitare blocchi causati da urllib su Windows.
    """
    host = "generativelanguage.googleapis.com"
    path = f"/v1beta/models/gemini-3.1-flash-lite:generateContent?key={api_key}"

    # Schema per un singolo prodotto (riutilizzato dentro l'array)
    product_schema = {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING"},
            "size": {"type": "STRING", "description": "A meno che non venga scritto diversamente metti rigorosamente UNI come valore di default."},
            "quantity": {"type": "INTEGER", "description": "Non ci sono limiti di quantità, e il valore di default è sempre 1, ma se viene scritto un numero subito dopo una x, allora la quantità sarà quel numero."},
            "purchased_price": {"type": "NUMBER"},
            "purchased_place": {"type": "STRING"},
            "status": {"type": "STRING", "description": "Scegli rigorosamente tra: 'In Stock', 'Pre-ordine', 'Venduto', o 'Completato'. Default: 'In Stock'."},
            "release_date": {"type": "STRING", "description": "Se non inserita la data inserire la data di oggi. Formato: AAAA-MM-GG."}
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
            "parts": [{"text": "Sei un assistente per l'inventario. Estrai TUTTI i prodotti menzionati nel testo. Restituisci sempre una lista 'products', anche se c'è un solo prodotto. Mappa i dati nello schema JSON, senza commenti o markdown. Formato date: AAAA-MM-GG."}]
        },
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        }
    }

    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    import socket as _socket
    _prev_timeout = _socket.getdefaulttimeout()
    _socket.setdefaulttimeout(20)

    conn = http.client.HTTPSConnection(host, timeout=20)
    try:
        conn.request("POST", path, body=data, headers=headers)
        response = conn.getresponse()
        resp_data = response.read().decode("utf-8")

        if response.status != 200:
            raise RuntimeError(f"Errore API ({response.status}): {resp_data}")

        result = json.loads(resp_data)
        if "candidates" in result and len(result["candidates"]) > 0:
            content = result["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(content)
            return parsed.get("products", [])
        else:
            raise ValueError(f"Risposta inaspettata: {resp_data}")
    except Exception as e:
        raise RuntimeError(f"Errore di connessione: {str(e)}")
    finally:
        _socket.setdefaulttimeout(_prev_timeout)
        conn.close()
