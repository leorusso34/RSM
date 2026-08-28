#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configurazione e costanti per Russo Stock Manager."""

import sys
from pathlib import Path

APP_NAME = "Russo Stock Manager"
APP_VERSION = "2.0.0"

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

# Palette colori - Tema scuro moderno
DARK_THEME = {
    "bg_main": "#111827",          # Sfondo principale
    "bg_card": "#1f2937",          # Sfondo carte e contenitori
    "bg_sidebar": "#182230",       # Sfondo eventuale sidebar
    "bg_input": "#273449",         # Sfondo campi di testo
    "fg_main": "#f3f4f6",          # Testo principale
    "fg_muted": "#a7b0c0",         # Testo secondario
    "fg_subtle": "#7f8ba0",        # Testo discreto
    "border": "#374151",           # Bordi soft
    "accent": "#2563eb",           # Blu accent (bottoni primari, selezionato)
    "accent_hover": "#1d4ed8",     # Blu hover
    "success": "#10b981",          # Verde (guadagni, magazzino)
    "success_hover": "#059669",
    "warning": "#f59e0b",          # Arancione/Giallo (pre-ordini)
    "danger": "#ef4444",           # Rosso (elimina, perdite)
    "danger_hover": "#dc2626",
    "table_header": "#263244",     # Intestazione tabella
    "table_alt_row": "#202b3c",    # Righe alternate
    "table_select": "#1d4ed8",     # Riga selezionata
    "table_select_fg": "#ffffff",  # Testo riga selezionata
}
