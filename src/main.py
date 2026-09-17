#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entry point principale per RSM."""

import sqlite3
import tkinter as tk
from tkinter import messagebox

import ctypes

from .config import APP_NAME
from .ui.main_window import InventoryApp


def main() -> None:
    # 1. Imposta AppUserModelID per visualizzare correttamente l'icona nitida nella taskbar di Windows
    try:
        app_id = "russostock.rsm.app.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass

    # 2. Abilita il supporto High DPI su Windows per testi e grafica nitidi
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    try:
        app = InventoryApp()
        app.after(50, lambda: (app.deiconify(), app.state("zoomed")))
        app.mainloop()
    except sqlite3.Error as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Errore Database", f"Impossibile avviare {APP_NAME}:\n{exc}")
        root.destroy()
        raise


if __name__ == "__main__":
    main()
