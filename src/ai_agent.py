import json
import http.client
from typing import Dict, Any

def parse_product_with_ai(prompt: str, api_key: str) -> Dict[str, Any]:
    """
    Invia la richiesta testuale all'API di Gemini per estrarre i dati del prodotto in formato JSON.
    Utilizza http.client puro per evitare blocchi causati da urllib su Windows.
    """
    host = "generativelanguage.googleapis.com"
    path = f"/v1beta/models/gemini-3.1-flash-lite:generateContent?key={api_key}"
    
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING"},
            "size": {"type": "STRING"},
            "quantity": {"type": "INTEGER"},
            "purchased_price": {"type": "NUMBER"},
            "purchased_place": {"type": "STRING"},
            "status": {"type": "STRING", "description": "Scegli rigorosamente tra questi valori esatti: 'In Stock', 'Pre-ordine', 'Venduto', o 'Completato'. Se il prodotto e' in magazzino usa 'In Stock'. Se non specificato, usa 'In Stock'."},
            "release_date": {"type": "STRING"}
        },
        "required": ["name", "quantity", "purchased_price", "status"]
    }

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {
            "parts": [{"text": "Sei un assistente per l'inventario. Estrai i dati dal testo fornito dall'utente. Mappa i dati esattamente nello schema JSON richiesto, senza aggiungere commenti, markdown o testo. Formato date: AAAA-MM-GG."}]
        },
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        }
    }

    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    # Imposta un timeout globale sui socket come fallback aggiuntivo
    import socket as _socket
    _prev_timeout = _socket.getdefaulttimeout()
    _socket.setdefaulttimeout(20)

    # Connessione HTTPS diretta con timeout rigoroso
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
            return json.loads(content)
        else:
            raise ValueError(f"Risposta inaspettata: {resp_data}")
    except Exception as e:
        raise RuntimeError(f"Errore di connessione: {str(e)}")
    finally:
        _socket.setdefaulttimeout(_prev_timeout)
        conn.close()
