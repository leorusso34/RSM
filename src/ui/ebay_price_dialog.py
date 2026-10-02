#!/usr/bin/env python3
"""Dialog per la visualizzazione dei prezzi di mercato eBay di un prodotto."""

import threading
import tkinter as tk
from collections.abc import Callable
from decimal import Decimal

import customtkinter as ctk

from ..config import DARK_THEME
from ..ebay_api import fetch_market_prices, open_search_in_browser
from ..utils import apply_dark_titlebar, center_window


class EbayPriceDialog(ctk.CTkToplevel):
    """
    Finestra di dialogo che mostra i prezzi di mercato eBay per un prodotto.

    Recupera min, media e max in un thread separato per non bloccare la UI,
    mostrando uno stato di caricamento durante l'attesa.
    Offre due azioni rapide:
      - Applica il prezzo medio come prezzo stimato nel database.
      - Apre eBay nel browser per consultare le inserzioni di persona.
    """

    def __init__(
        self,
        parent: tk.Misc,
        product_name: str,
        product_size: str,
        client_id: str,
        client_secret: str,
        on_apply_price: Callable[[Decimal], None] | None = None,
    ) -> None:
        """
        Args:
            parent:         Finestra padre.
            product_name:   Nome del prodotto da cercare.
            product_size:   Taglia del prodotto ("UNI" → ignorata).
            client_id:      App ID / Client ID eBay da config.json.
            client_secret:  Cert ID / Client Secret eBay da config.json.
            on_apply_price: Callback opzionale chiamato con il prezzo medio
                            (Decimal) quando l'utente preme "Applica Prezzo".
        """
        super().__init__(parent, fg_color=DARK_THEME["bg_main"])

        self._product_name  = product_name
        self._product_size  = product_size
        self._client_id     = client_id
        self._client_secret = client_secret
        self._on_apply_price = on_apply_price
        self._result: dict | None = None

        self.title("Prezzi di Mercato eBay")
        center_window(self, 460, 320)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        apply_dark_titlebar(self)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

        # Avvia la chiamata API in background immediatamente
        self.after(100, self._start_fetch)

    # ------------------------------------------------------------------
    # Costruzione UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        c = DARK_THEME
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=28, pady=22)

        # Intestazione
        ctk.CTkLabel(
            outer,
            text="Prezzi di Mercato eBay",
            font=("Segoe UI", 18, "bold"),
            anchor="w",
        ).pack(fill="x")

        self._lbl_subtitle = ctk.CTkLabel(
            outer,
            text=self._build_subtitle(),
            font=("Segoe UI", 12),
            text_color=c["fg_muted"],
            anchor="w",
        )
        self._lbl_subtitle.pack(fill="x", pady=(2, 18))

        # Area centrale — si sostituisce con i dati quando arrivano
        self._content_frame = ctk.CTkFrame(
            outer,
            fg_color=c["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=c["border"],
        )
        self._content_frame.pack(fill="x")
        self._show_loading()

        # Footer pulsanti
        footer = ctk.CTkFrame(outer, fg_color="transparent")
        footer.pack(fill="x", pady=(18, 0))

        self._btn_apply = ctk.CTkButton(
            footer,
            text="Applica come Prezzo Stimato",
            command=self._apply_price,
            state="disabled",
        )
        self._btn_apply.pack(side="left")

        self._btn_browser = ctk.CTkButton(
            footer,
            text="Vedi su eBay",
            command=self._open_browser,
            fg_color=DARK_THEME["bg_input"],
            hover_color="#263045",
            text_color=DARK_THEME["fg_main"],
        )
        self._btn_browser.pack(side="left", padx=(10, 0))

        ctk.CTkButton(
            footer,
            text="Chiudi",
            command=self.destroy,
            fg_color="#374151",
            hover_color="#4b5563",
        ).pack(side="right", padx=(10, 0))

    def _build_subtitle(self) -> str:
        size = self._product_size.strip()
        effective = "" if size.upper() == "UNI" else size
        if effective:
            return f"{self._product_name}  ·  taglia {effective}"
        return self._product_name

    # ------------------------------------------------------------------
    # Stati del content_frame
    # ------------------------------------------------------------------

    def _clear_content(self) -> None:
        for widget in self._content_frame.winfo_children():
            widget.destroy()

    def _show_loading(self) -> None:
        self._clear_content()
        ctk.CTkLabel(
            self._content_frame,
            text="Recupero prezzi in corso...",
            font=("Segoe UI", 13),
            text_color=DARK_THEME["fg_muted"],
        ).pack(pady=28)

    def _show_results(self, result: dict) -> None:
        self._clear_content()
        c = DARK_THEME

        grid = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=18)
        grid.columnconfigure((0, 1, 2), weight=1)

        labels = [
            ("MINIMO",  f"€ {result['min']:.2f}",  c["success"]),
            ("MEDIA",   f"€ {result['avg']:.2f}",  c["accent"]),
            ("MASSIMO", f"€ {result['max']:.2f}",  c["warning"]),
        ]
        for col, (title, value, color) in enumerate(labels):
            cell = ctk.CTkFrame(grid, fg_color=c["bg_input"], corner_radius=8)
            cell.grid(row=0, column=col, padx=6, sticky="nsew")
            ctk.CTkLabel(
                cell,
                text=title,
                font=("Segoe UI", 10, "bold"),
                text_color=c["fg_muted"],
            ).pack(pady=(12, 2))
            ctk.CTkLabel(
                cell,
                text=value,
                font=("Segoe UI", 16, "bold"),
                text_color=color,
            ).pack(pady=(0, 12))

        ctk.CTkLabel(
            self._content_frame,
            text=f"Analizzate {result['count']} inserzioni a prezzo fisso su eBay.it",
            font=("Segoe UI", 11),
            text_color=c["fg_muted"],
        ).pack(pady=(0, 14))

    def _show_error(self, message: str) -> None:
        self._clear_content()
        ctk.CTkLabel(
            self._content_frame,
            text=message,
            font=("Segoe UI", 12),
            text_color=DARK_THEME["danger"],
            wraplength=380,
        ).pack(pady=28, padx=16)

    # ------------------------------------------------------------------
    # Logica asincrona
    # ------------------------------------------------------------------

    def _start_fetch(self) -> None:
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self) -> None:
        try:
            result = fetch_market_prices(
                self._product_name,
                self._product_size,
                self._client_id,
                self._client_secret,
            )
            self.after(0, lambda: self._on_fetch_success(result))
        except Exception as exc:  # noqa: BLE001
            self.after(0, lambda msg=str(exc): self._on_fetch_error(msg))

    def _on_fetch_success(self, result: dict) -> None:
        self._result = result
        self._show_results(result)
        if self._on_apply_price:
            self._btn_apply.configure(state="normal")

    def _on_fetch_error(self, message: str) -> None:
        self._show_error(message)

    # ------------------------------------------------------------------
    # Azioni pulsanti
    # ------------------------------------------------------------------

    def _apply_price(self) -> None:
        if self._result and self._on_apply_price:
            avg = Decimal(str(self._result["avg"]))
            self._on_apply_price(avg)
            self.destroy()

    def _open_browser(self) -> None:
        effective_size = "" if self._product_size.strip().upper() == "UNI" else self._product_size
        open_search_in_browser(self._product_name, effective_size)
