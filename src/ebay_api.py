"""
Modulo di integrazione con le API eBay per RSM.

Responsabilità:
  - Costruzione dell'URL di ricerca eBay (apertura nel browser dell'utente).
  - Autenticazione OAuth 2.0 con flusso Client Credentials Grant.
  - Recupero prezzi di mercato tramite Browse API (item_summary/search).
"""

import http.client
import json
import urllib.parse
import webbrowser

from .config import RSM_AUTH_KEY, WORKER_URL

# ---------------------------------------------------------------------------
# Costanti API eBay
# ---------------------------------------------------------------------------

EBAY_SEARCH_URL = "https://www.ebay.it/sch/i.html"


# ---------------------------------------------------------------------------
# URL di ricerca pubblica (nessuna autenticazione richiesta)
# ---------------------------------------------------------------------------

def build_search_url(name: str, size: str = "") -> str:
    """
    Costruisce l'URL di ricerca su eBay.it per un prodotto.

    Se `size` è valorizzata, viene accodata al nome per affinare la ricerca
    (es. 'Nike Air Max 90 42' per trovare solo quella taglia).

    Args:
        name:  Nome del prodotto.
        size:  Taglia/variante del prodotto (stringa vuota se assente).

    Returns:
        URL completo di ricerca eBay pronto per essere aperto nel browser.
    """
    query_parts = [name.strip()]
    if size and size.strip():
        query_parts.append(size.strip())
    query = " ".join(query_parts)
    params = urllib.parse.urlencode({"_nkw": query})
    return f"{EBAY_SEARCH_URL}?{params}"


def open_search_in_browser(name: str, size: str = "") -> None:
    """
    Apre direttamente nel browser predefinito dell'utente la pagina di ricerca
    eBay per il prodotto indicato.

    Args:
        name:  Nome del prodotto.
        size:  Taglia/variante del prodotto (stringa vuota se assente).
    """
    url = build_search_url(name, size)
    webbrowser.open(url)


# ---------------------------------------------------------------------------
# Cloudflare Worker Proxy — ricerca prezzi
# ---------------------------------------------------------------------------

def fetch_market_prices(
    name: str,
    size: str,
    limit: int = 100,
) -> dict:
    """
    Recupera i prezzi delle inserzioni eBay attive per un prodotto tramite il Cloudflare
    Worker proxy protetto e restituisce un riepilogo con min, media e max.

    Args:
        name:  Nome del prodotto.
        size:  Taglia (vuota o "UNI" → non inclusa nella query).
        limit: Numero massimo di risultati da analizzare (default 100).

    Returns:
        Dizionario con le chiavi:
          - "count"   (int)   — numero di inserzioni trovate
          - "min"     (float) — prezzo minimo trovato
          - "avg"     (float) — prezzo medio
          - "max"     (float) — prezzo massimo
          - "query"   (str)   — query utilizzata per la ricerca

    Raises:
        RuntimeError: se la chiamata API fallisce o WORKER_URL non è configurato.
        ValueError:   se non viene trovata nessuna inserzione valida.
    """
    if not WORKER_URL:
        raise RuntimeError("WORKER_URL non è configurato.")

    # Costruzione query (stessa logica dell'URL browser)
    query_parts = [name.strip()]
    effective_size = size.strip() if size.strip().upper() != "UNI" else ""
    if effective_size:
        query_parts.append(effective_size)
    query = " ".join(query_parts)

    parsed_w = urllib.parse.urlparse(WORKER_URL.strip())
    w_host = parsed_w.netloc
    params = urllib.parse.urlencode({"q": query, "limit": str(limit)})
    w_path = f"{parsed_w.path.rstrip('/')}/api/ebay/prices?{params}"
    w_headers = {"Accept": "application/json"}
    if RSM_AUTH_KEY:
        w_headers["X-RSM-Auth"] = RSM_AUTH_KEY.strip()

    conn_cls = http.client.HTTPSConnection if parsed_w.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(w_host, timeout=15)
    try:
        conn.request("GET", w_path, headers=w_headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
    finally:
        conn.close()

    data = json.loads(raw)
    if resp.status != 200:
        error = data.get("error") or data.get("errors", [{}])[0].get("message", "Errore sconosciuto")
        raise RuntimeError(f"Errore Proxy eBay ({resp.status}): {error}")

    items = data.get("itemSummaries", [])
    if not items:
        raise ValueError(f"Nessuna inserzione trovata su eBay per: {query}")

    prices = []
    for item in items:
        price_info = item.get("price", {})
        try:
            prices.append(float(price_info.get("value", 0)))
        except (TypeError, ValueError):
            continue

    prices = [p for p in prices if p > 0]
    if not prices:
        raise ValueError(f"Nessun prezzo valido trovato per: {query}")

    return {
        "count": len(prices),
        "min":   round(min(prices), 2),
        "avg":   round(sum(prices) / len(prices), 2),
        "max":   round(max(prices), 2),
        "query": query,
    }
