"""
Finestra modale di dialogo per la notifica e il download degli aggiornamenti di RSM.
"""

import re
import threading
import tkinter as tk
from typing import Any

import customtkinter as ctk

from ..config import APP_VERSION, DARK_THEME
from ..updater import apply_update_and_restart
from ..utils import apply_dark_titlebar, center_window


class UpdateDialog(ctk.CTkToplevel):
    """
    Finestra modale di notifica e download aggiornamento.
    Blocca l'interfaccia sottostante durante il processo per garantire sicurezza e integrità dei dati.
    """

    def __init__(
        self,
        parent: tk.Misc,
        update_info: dict[str, Any],
    ) -> None:
        super().__init__(parent, fg_color=DARK_THEME["bg_main"])

        self.update_info = update_info
        self._is_updating = False

        self.title("Aggiornamento Disponibile")
        center_window(self, 520, 390)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        apply_dark_titlebar(self)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Escape>", lambda _e: self._on_close())

    def _build_ui(self) -> None:
        c = DARK_THEME
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=26, pady=22)

        # Intestazione
        ctk.CTkLabel(
            outer,
            text="Nuova Versione Disponibile",
            font=("Segoe UI", 18, "bold"),
            anchor="w",
        ).pack(fill="x")

        ver = self.update_info.get("version", "").strip()
        clean_ver = re.sub(r"^[^\d]*", "", ver) or ver or "Nuova"
        subtitle_text = f"Versione {clean_ver} disponibile (versione attuale: v{APP_VERSION})"
        ctk.CTkLabel(
            outer,
            text=subtitle_text,
            font=("Segoe UI", 12),
            text_color=c["fg_muted"],
            anchor="w",
        ).pack(fill="x", pady=(2, 14))

        # Box Changelog
        ctk.CTkLabel(
            outer,
            text="NOVITÀ DELL'AGGIORNAMENTO:",
            font=("Segoe UI", 10, "bold"),
            text_color=c["fg_muted"],
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self.txt_changelog = ctk.CTkTextbox(
            outer,
            height=130,
            font=("Segoe UI", 12),
            fg_color=c["bg_card"],
            border_width=1,
            border_color=c["border"],
            wrap="word",
        )
        self.txt_changelog.pack(fill="both", expand=True, pady=(0, 12))
        self.txt_changelog.insert("1.0", self.update_info.get("changelog", "Nessuna nota di rilascio specificata."))
        self.txt_changelog.configure(state="disabled")

        # Barra di avanzamento e stato
        self.progress_bar = ctk.CTkProgressBar(outer, height=8, corner_radius=4)
        self.progress_bar.set(0.0)

        self.lbl_status = ctk.CTkLabel(
            outer,
            text="I tuoi dati e impostazioni non verranno toccati.",
            font=("Segoe UI", 11),
            text_color=c["fg_muted"],
            anchor="w",
        )
        self.lbl_status.pack(fill="x", pady=(0, 8))

        # Footer Pulsanti
        self.footer = ctk.CTkFrame(outer, fg_color="transparent")
        self.footer.pack(fill="x", pady=(8, 0))

        self.btn_update = ctk.CTkButton(
            self.footer,
            text=f"Aggiorna alla versione {clean_ver}",
            command=self._start_update,
            fg_color="#059669",
            hover_color="#047857",
            font=("Segoe UI", 12, "bold"),
        )
        self.btn_update.pack(side="left")

        self.btn_cancel = ctk.CTkButton(
            self.footer,
            text="Più Tardi",
            command=self.destroy,
            fg_color="#374151",
            hover_color="#4b5563",
            font=("Segoe UI", 12),
        )
        self.btn_cancel.pack(side="right")

    def _on_close(self) -> None:
        if self._is_updating:
            return  # Impedisce la chiusura durante il download
        self.destroy()

    def _start_update(self) -> None:
        if self._is_updating:
            return

        self._is_updating = True
        self.btn_update.configure(state="disabled")
        self.btn_cancel.configure(state="disabled")

        # Mostra barra di avanzamento
        self.progress_bar.pack(fill="x", before=self.lbl_status, pady=(0, 8))
        self.lbl_status.configure(text="Avvio download...", text_color=DARK_THEME["fg_main"])

        download_url = self.update_info.get("download_url", "")
        if not download_url:
            self.lbl_status.configure(text="Errore: URL di download non valido", text_color=DARK_THEME["danger"])
            self.btn_cancel.configure(state="normal")
            self._is_updating = False
            return

        threading.Thread(target=self._update_worker, args=(download_url,), daemon=True).start()

    def _update_worker(self, download_url: str) -> None:
        try:
            def on_progress(fraction: float) -> None:
                percent = int(fraction * 100)
                self.after(0, lambda p=fraction, pct=percent: self._update_progress_ui(p, pct))

            def on_status(msg: str) -> None:
                self.after(0, lambda m=msg: self.lbl_status.configure(text=m, text_color=DARK_THEME["fg_main"]))

            apply_update_and_restart(
                download_url=download_url,
                progress_callback=on_progress,
                status_callback=on_status,
            )
        except Exception as exc:  # noqa: BLE001
            self.after(0, lambda e=exc: self._on_error(str(e)))

    def _update_progress_ui(self, fraction: float, percent: int) -> None:
        self.progress_bar.set(fraction)
        self.lbl_status.configure(text=f"Download in corso: {percent}%", text_color=DARK_THEME["fg_main"])

    def _on_error(self, error_message: str) -> None:
        self._is_updating = False
        self.lbl_status.configure(
            text=f"Errore durante l'aggiornamento: {error_message}",
            text_color=DARK_THEME["danger"],
        )
        self.btn_cancel.configure(state="normal", text="Chiudi")
