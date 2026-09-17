#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modulo di integrazione con le API eBay per RSM.

Responsabilità attuali:
  - Costruzione dell'URL di ricerca eBay (apertura nel browser dell'utente).

Responsabilità future (quando richiesto):
  - Autenticazione OAuth 2.0 con le credenziali Client Credentials Grant.
  - Chiamate alla Browse API (item_summary/search) per recuperare prezzi di mercato.
"""

import urllib.parse
import webbrowser


# ---------------------------------------------------------------------------
# URL di ricerca pubblica (nessuna autenticazione richiesta)
# ---------------------------------------------------------------------------

EBAY_SEARCH_URL = "https://www.ebay.it/sch/i.html"


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
