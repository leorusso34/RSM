#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configurazione e costanti per Russo Stock Manager."""

import sys
from pathlib import Path

APP_NAME = "Russo Stock Manager"
APP_VERSION = "2.0.0"

# Stati prodotti
STATUS_STOCK = "In Stock"
STATUS_PREORDER = "Pre-order"
STATUS_SOLD = "Venduto"

def app_directory() -> Path:
    """Restituisce la cartella del file .py o dell'eseguibile PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

BASE_DIR = app_directory()
DB_PATH = BASE_DIR / "russo_stock.db"

# Palette Colori - Tema Chiaro Moderno
LIGHT_THEME = {
    "bg_main": "#f8fafc",          # Sfondo principale
    "bg_card": "#ffffff",          # Sfondo carte e contenitori
    "bg_sidebar": "#ffffff",       # Sfondo eventuale sidebar
    "bg_input": "#f1f5f9",         # Sfondo campi di testo
    "fg_main": "#0f172a",          # Testo principale (molto scuro, leggibile)
    "fg_muted": "#64748b",         # Testo secondario
    "fg_subtle": "#94a3b8",        # Testo discreto
    "border": "#e2e8f0",           # Bordi soft
    "accent": "#2563eb",           # Blu accent (bottoni primari, selezionato)
    "accent_hover": "#1d4ed8",     # Blu hover
    "success": "#10b981",          # Verde (guadagni, magazzino)
    "success_hover": "#059669",
    "warning": "#f59e0b",          # Arancione/Giallo (pre-ordini)
    "danger": "#ef4444",           # Rosso (elimina, perdite)
    "danger_hover": "#dc2626",
    "table_header": "#e2e8f0",     # Intestazione tabella
    "table_alt_row": "#f8fafc",    # Righe alternate
    "table_select": "#dbeafe",     # Riga selezionata
    "table_select_fg": "#1e40af",  # Testo riga selezionata
}
