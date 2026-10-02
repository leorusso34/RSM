"""Entry point principale per RSM."""

import ctypes
import sqlite3
import tkinter as tk
from tkinter import messagebox

from .config import APP_NAME
from .ui.main_window import InventoryApp


def main() -> None:
    # 1. Imposta AppUserModelID per visualizzare correttamente l'icona nitida nella taskbar di Windows
    try:
        app_id = "russostock.rsm.app.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (AttributeError, OSError):
        pass

    # 2. Abilita il supporto High DPI su Windows per testi e grafica nitidi
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
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
