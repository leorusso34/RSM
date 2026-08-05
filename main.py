#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entry point principale per Russo Stock Manager."""

import sqlite3
import tkinter as tk
from tkinter import messagebox

from config import APP_NAME
from ui.main_window import InventoryApp


def main() -> None:
    try:
        app = InventoryApp()
        app.mainloop()
    except sqlite3.Error as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Errore Database", f"Impossibile avviare {APP_NAME}:\n{exc}")
        root.destroy()
        raise


if __name__ == "__main__":
    main()
