import json
import http.client
import socket
import re
from datetime import datetime
from typing import Any, List, Dict


def _safe_parse_json_products(raw_content: str) -> List[Dict[str, Any]]:
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
        except Exception:
            pass
    if objects:
        return objects

    raise ValueError(f"Impossibile interpretare la risposta AI come elenco prodotti JSON: {raw_content[:200]}...")

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
            "parts": [{"text": "Sei un assistente per l'inventario. Estrai TUTTI i prodotti menzionati nel testo. Restituisci sempre una lista 'products', anche se c'è un solo prodotto. Mappa i dati nello schema JSON, senza commenti o markdown. Formato date: YYYY-MM-DD."}]
        },
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 65536,
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        }
    }

    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    _prev_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(20)

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
            return _safe_parse_json_products(content)
        else:
            raise ValueError(f"Risposta inaspettata: {resp_data}")
    except Exception as e:
        raise RuntimeError(f"Errore di connessione: {str(e)}")
    finally:
        socket.setdefaulttimeout(_prev_timeout)
        conn.close()


def parse_excel_with_ai(raw_text: str, api_key: str, user_hint: str = "") -> List[Dict[str, Any]]:
    """
    Analizza l'intero contenuto testuale di un file Excel/CSV con una singola
    chiamata a Gemini e restituisce la lista di prodotti estratti in formato JSON.

    Regole di estrazione per il modello AI:
    - Status default: 'In Stock' (Magazzino) se non è chiaro.
    - Se trova un prezzo di vendita o un luogo di vendita → 'Venduto' (Vendite Attive).
    - Se trova la parola "preorder", "pre-order" o "pre ordine" → 'Pre-ordine'.
    - Taglia di default: 'UNI' se non specificata.
    - Quantità di default: 1 se non specificata.
    - Restituisce TUTTI i prodotti trovati nella tabella, uno per riga dati.
    - Se user_hint è fornito, viene trattato come istruzione prioritaria aggiuntiva.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    host = "generativelanguage.googleapis.com"
    path = f"/v1beta/models/gemini-3.1-flash-lite:generateContent?key={api_key}"

    product_schema = {
        "type": "OBJECT",
        "properties": {
            "name":             {"type": "STRING", "description": "Nome del prodotto. Obbligatorio."},
            "size":             {"type": "STRING", "description": "Taglia. Default 'UNI' se non specificata."},
            "quantity":         {"type": "INTEGER", "description": "Quantità. Default 1."},
            "purchased_price":  {"type": "NUMBER", "description": "Prezzo di acquisto. Obbligatorio. Usa 0 se mancante."},
            "purchased_place":  {"type": "STRING", "description": "Luogo o sito di acquisto. Vuoto se non trovato."},
            "selling_place":    {"type": "STRING", "description": "Luogo o piattaforma di vendita. Vuoto se non trovato."},
            "selling_price":    {"type": "NUMBER", "description": "Prezzo di vendita stimato. 0 se non trovato."},
            "sold_price":       {"type": "NUMBER", "description": "Prezzo di vendita effettivo. 0 se non trovato."},
            "fees":             {"type": "NUMBER", "description": "Commissioni o spese. Default 0."},
            "sold_date":        {"type": "STRING", "description": f"Data vendita in formato YYYY-MM-DD. Se lo stato è Venduto e non c'è una data specifica nel foglio, usa rigorosamente la data odierna: {today_str}."},
            "status":           {"type": "STRING", "description": (
                "Stato del prodotto. Scegli RIGOROSAMENTE tra: 'In Stock', 'Pre-ordine', 'Venduto'. "
                "Regole: se trovi un prezzo di vendita effettivo o un luogo di vendita → 'Venduto'. "
                "Se trovi 'preorder', 'pre-order', 'pre ordine' → 'Pre-ordine'. "
                "In tutti gli altri casi → 'In Stock' (DEFAULT)."
            )},
            "release_date":     {"type": "STRING", "description": "Data di uscita prodotto in formato YYYY-MM-DD. Vuoto se non trovata."},
            "notes":            {"type": "STRING", "description": "Note aggiuntive. Vuoto se non presenti."},
        },
        "required": ["name", "quantity", "purchased_price", "status"]
    }

    response_schema = {
        "type": "OBJECT",
        "properties": {
            "products": {"type": "ARRAY", "items": product_schema}
        },
        "required": ["products"]
    }

    system_prompt = (
        f"Sei un assistente esperto di inventari. La data di oggi è {today_str}. "
        "Ti verrà fornito il contenuto grezzo di un file Excel o CSV, con righe e colonne separate da tabulazioni. "
        "Il tuo compito è identificare OGNI riga che rappresenta un prodotto fisico e restituire la lista 'products' con tutti i dati estratti. "
        "Ignora le righe di intestazione, righe totali, righe vuote e sezioni di testo non dati. "
        "Riconosci automaticamente le colonne indipendentemente dalla lingua (italiano, inglese, ecc.) e dal formato (valute, date, simboli). "
        f"Se lo stato è 'Venduto' e non è presente una data specifica nel foglio, assegna la data di oggi ({today_str}) come sold_date. "
        "Non inventare dati non presenti: usa i valori di default specificati nello schema. "
        "Formato date: YYYY-MM-DD. Formato numeri: senza simboli di valuta."
    )

    hint_section = ""
    if user_hint and user_hint.strip():
        hint_section = (
            "ISTRUZIONI AGGIUNTIVE PRIORITARIE fornite dall'utente "
            "(seguile con precedenza assoluta sulle regole generali):\n"
            f"{user_hint.strip()}\n\n"
        )

    user_prompt = (
        f"{hint_section}"
        f"Data di oggi: {today_str}\n"
        "Analizza il seguente contenuto di un file Excel/CSV ed estrai tutti i prodotti presenti:\n\n"
        f"{raw_text}"
    )

    payload = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 65536,
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        }
    }

    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    _prev_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(180)  # Timeout esteso a 3 minuti per file Excel corposi

    conn = http.client.HTTPSConnection(host, timeout=180)
    try:
        conn.request("POST", path, body=data, headers=headers)
        response = conn.getresponse()
        resp_data = response.read().decode("utf-8")

        if response.status != 200:
            raise RuntimeError(f"Errore API Gemini ({response.status}): {resp_data}")

        result = json.loads(resp_data)
        if "candidates" in result and len(result["candidates"]) > 0:
            content = result["candidates"][0]["content"]["parts"][0]["text"]
            return _safe_parse_json_products(content)
        else:
            raise ValueError(f"Risposta AI inaspettata: {resp_data}")
    except (socket.timeout, TimeoutError) as e:
        raise RuntimeError("Tempo scaduto: il server AI ha impiegato più di 3 minuti ad analizzare il file. Riprova tra poco.")
    except Exception as e:
        err_msg = str(e)
        if "timed out" in err_msg.lower():
            raise RuntimeError("Tempo scaduto: l'analisi ha superato il tempo massimo. Riprova.")
        raise RuntimeError(f"Errore AI Excel import: {err_msg}")
    finally:
        socket.setdefaulttimeout(_prev_timeout)
        conn.close()
