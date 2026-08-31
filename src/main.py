#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entry point principale per Russo Stock Manager."""

import sqlite3
import tkinter as tk
from tkinter import messagebox

import ctypes

from .config import APP_NAME
from .ui.main_window import InventoryApp


def main() -> None:
    # Abilita il supporto High DPI su Windows per testi nitidi (non sgranati)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    try:
        app = InventoryApp()
        app.update_idletasks()
        app.after(0, lambda: app.state("zoomed"))
        app.mainloop()
    except sqlite3.Error as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Errore Database", f"Impossibile avviare {APP_NAME}:\n{exc}")
        root.destroy()
        raise


if __name__ == "__main__":
    main()
