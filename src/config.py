#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configurazione e costanti per RSM."""

import sys
from pathlib import Path

APP_NAME = "RSM"
APP_VERSION = "1.1.0"
GITHUB_REPO = "leorusso34/RSM"

# Stati prodotti
STATUS_STOCK = "In Stock"
STATUS_PREORDER = "Pre-ordine"
STATUS_SOLD = "Venduto"
STATUS_COMPLETED = "Completato"

DEFAULT_SELLING_PLACES = [
    "alias", "CardMarket", "Catawiki", "chrono24", "discord", "ebay",
    "hypeboost", "klekt", "laced", "pirogi", "privato", "reso", "restocks",
    "sellpoint", "sneakeropeu", "stockx", "subito", "vestiaire", "vinted", "wethenew"
]

def app_directory() -> Path:
    """Restituisce la cartella del file .py o dell'eseguibile PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

BASE_DIR = app_directory()
PROJECT_DIR = BASE_DIR.parent if BASE_DIR.name == "src" else BASE_DIR
DATA_DIR = PROJECT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "russo_stock.db"
CONFIG_JSON_PATH = PROJECT_DIR / "config.json"

# Palette colori - Tema scuro moderno
DARK_THEME = {
    "bg_main": "#0e131f",        # Sfondo principale più profondo (stile Antigravity)
    "bg_card": "#151b2b",        # Sfondo contenitori molto simile allo sfondo (basso contrasto)
    "bg_input": "#1d2538",       # Sfondo input
    "fg_main": "#f1f5f9",        # Testo primario morbido
    "fg_muted": "#8b9bb4",       # Testo secondario integrato
    "fg_subtle": "#475569",      # Testo molto discreto
    "bg_sidebar": "#151b2b",     # Sfondo eventuale sidebar
    "accent": "#3b82f6",
    "accent_hover": "#2563eb",
    "success": "#10b981",
    "success_hover": "#059669",
    "danger": "#ef4444",
    "danger_hover": "#dc2626",
    "warning": "#f59e0b",
    "border": "#1d2538",           # Bordo fuso con lo sfondo
    "table_header": "#151b2b",     # Intestazione tabella uguale alla card
    "table_alt_row": "#121825",    # Righe alternate invisibili
    "table_select": "#2563eb",     # Riga selezionata
    "table_select_fg": "#ffffff",  # Testo riga selezionata
}
