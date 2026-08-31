#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configurazione tema scuro tramite CustomTkinter."""

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

from ..config import DARK_THEME


def setup_app_theme(root) -> None:
    """Configura il tema scuro globale tramite CustomTkinter."""

    # Tema globale CTK
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    c = DARK_THEME

    # ----------------------------------------------------------------
    # ttk.Treeview e Treeview.Heading rimangono ttk (CTK non ha Treeview)
    # ----------------------------------------------------------------
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # Rimuovi completamente il bordo di focus attorno alla tabella
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    style.configure(
        "Treeview",
        background=c["bg_card"],
        fieldbackground=c["bg_card"],
        foreground=c["fg_main"],
        rowheight=34,
        borderwidth=0,
        highlightthickness=0,
        lightcolor=c["bg_card"],
        darkcolor=c["bg_card"],
        bordercolor=c["bg_card"],
        relief="flat",
        font=("Segoe UI", 9),
    )
    style.map(
        "Treeview",
        background=[("selected", c["table_select"])],
        foreground=[("selected", c["table_select_fg"])],
        bordercolor=[("focus", c["bg_card"]), ("!focus", c["bg_card"])],
        lightcolor=[("focus", c["bg_card"]), ("!focus", c["bg_card"])],
        darkcolor=[("focus", c["bg_card"]), ("!focus", c["bg_card"])],
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

    # Scrollbar ttk per il Treeview
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
