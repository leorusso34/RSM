#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Definizione del tema grafico scuro (Dark Theme) per Tkinter / ttk."""

import tkinter as tk
from tkinter import ttk
from ..config import DARK_THEME

def setup_app_theme(root: tk.Tk) -> None:
    """Configura gli stili ttk per l'interfaccia a tema chiaro."""
    style = ttk.Style(root)

    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    c = DARK_THEME

    # Stile globale della finestra
    root.configure(bg=c["bg_main"])

    # Frame
    style.configure("TFrame", background=c["bg_main"])
    style.configure("Card.TFrame", background=c["bg_card"], relief="flat")
    style.configure("Header.TFrame", background=c["bg_card"])

    # Etichette (Labels)
    style.configure("TLabel", background=c["bg_main"], foreground=c["fg_main"], font=("Segoe UI", 10))
    style.configure("Card.TLabel", background=c["bg_card"], foreground=c["fg_main"], font=("Segoe UI", 10))
    style.configure("Muted.TLabel", background=c["bg_main"], foreground=c["fg_muted"], font=("Segoe UI", 9))
    style.configure("CardMuted.TLabel", background=c["bg_card"], foreground=c["fg_muted"], font=("Segoe UI", 9))
    style.configure("Title.TLabel", background=c["bg_card"], foreground=c["fg_main"], font=("Segoe UI", 22, "bold"))
    style.configure("Section.TLabel", background=c["bg_main"], foreground=c["fg_main"], font=("Segoe UI", 14, "bold"))

    # KPI Labels
    style.configure("KpiValue.TLabel", background=c["bg_card"], foreground=c["fg_main"], font=("Segoe UI", 18, "bold"))
    style.configure("KpiLabel.TLabel", background=c["bg_card"], foreground=c["fg_muted"], font=("Segoe UI", 9, "bold"))
    style.configure("KpiSub.TLabel", background=c["bg_card"], foreground=c["success"], font=("Segoe UI", 9))

    # Bottoni
    style.configure(
        "TButton",
        background="#334155",
        foreground=c["fg_main"],
        borderwidth=0,
        focuscolor="none",
        padding=(12, 8),
        font=("Segoe UI", 9, "bold"),
    )
    style.map("TButton", background=[("active", "#475569")])

    style.configure("Accent.TButton", background=c["accent"], foreground="white")
    style.map("Accent.TButton", background=[("active", c["accent_hover"])])

    style.configure("Success.TButton", background=c["success"], foreground="white")
    style.map("Success.TButton", background=[("active", c["success_hover"])])

    style.configure("Danger.TButton", background=c["danger"], foreground="white")
    style.map("Danger.TButton", background=[("active", c["danger_hover"])])

    style.configure("Secondary.TButton", background="#374151", foreground=c["fg_main"])
    style.map("Secondary.TButton", background=[("active", "#4b5563")])

    # Personalizzazione listbox della combobox
    root.option_add("*TCombobox*Listbox.background", c["bg_input"])
    root.option_add("*TCombobox*Listbox.foreground", c["fg_main"])
    root.option_add("*TCombobox*Listbox.selectBackground", c["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))

    # TEntry
    style.configure("TEntry", fieldbackground=c["bg_input"], foreground=c["fg_main"], borderwidth=0, padding=4)
    style.configure("TCombobox", fieldbackground=c["bg_input"], background=c["bg_input"], foreground=c["fg_main"], padding=5)
    style.map("TCombobox", fieldbackground=[("readonly", c["bg_input"])], foreground=[("readonly", c["fg_main"])])

    # Scrollbar compatta coerente con il tema scuro
    style.configure(
        "TScrollbar",
        background="#3b4a60",
        troughcolor=c["bg_main"],
        bordercolor=c["bg_main"],
        darkcolor="#263244",
        lightcolor="#3b4a60",
        arrowcolor=c["fg_muted"],
        gripcount=0,
        width=11,
    )
    style.map(
        "TScrollbar",
        background=[("active", c["accent"]), ("pressed", c["accent_hover"])],
        arrowcolor=[("active", c["fg_main"])],
    )

    # Schede (Notebook)
    style.configure(
        "TNotebook", 
        background=c["bg_main"], 
        borderwidth=0,
        lightcolor=c["bg_main"],
        darkcolor=c["bg_main"],
        bordercolor=c["bg_main"]
    )
    style.configure(
        "TNotebook.Tab",
        background=c["bg_main"],
        foreground=c["fg_muted"],
        padding=(16, 10),
        font=("Segoe UI", 10, "bold"),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", c["bg_card"])],
        foreground=[("selected", c["accent"])],
    )

    # Tabelle (Treeview)
    style.configure(
        "Treeview",
        background=c["bg_card"],
        fieldbackground=c["bg_card"],
        foreground=c["fg_main"],
        rowheight=34,
        borderwidth=0,
        lightcolor=c["bg_main"],
        darkcolor=c["bg_main"],
        bordercolor=c["bg_main"],
        relief="flat",
        font=("Segoe UI", 9),
    )
    style.map(
        "Treeview",
        background=[("selected", c["table_select"])],
        foreground=[("selected", c["table_select_fg"])],
    )
    style.configure(
        "Treeview.Heading",
        background=c["table_header"],
        foreground=c["fg_main"],
        relief="flat",
        borderwidth=1,
        padding=8,
        font=("Segoe UI", 9, "bold"),
    )
    style.map("Treeview.Heading", background=[("active", "#3b4a60")])
