#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finestra di dialogo per l'importazione Excel con AI per RSM."""

import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List
import customtkinter as ctk

from ..config import DARK_THEME, STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK
from ..utils import apply_dark_titlebar, center_window, money


class ExcelImportDialog(ctk.CTkToplevel):
    """
    Dialog di anteprima per l'importazione Excel tramite AI.
    Mostra i prodotti estratti dall'AI e permette di confermarli nel database.
    Stilata come EmailSyncDialog: dark card, padding, stessi font e colori.
    """

    def __init__(self, parent: tk.Misc, db: Any, products: List[Dict[str, Any]]) -> None:
        super().__init__(parent, fg_color=DARK_THEME["bg_main"])
        self.db = db
        self.products = products
        self.confirmed = False

        self.title("Importazione Excel — Anteprima AI")
        center_window(self, 900, 620)
        self.minsize(760, 500)
        self.transient(parent)
        self.grab_set()
        apply_dark_titlebar(self)

        self._build()

    def _build(self) -> None:
        c = DARK_THEME
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=22, pady=18)

        # Header
        head_box = ctk.CTkFrame(container, fg_color="transparent")
        head_box.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            head_box,
            text="Importazione Excel con AI",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")

        n = len(self.products)
        ctk.CTkLabel(
            head_box,
            text=(
                f"L'AI ha analizzato il file e trovato {n} prodott{'o' if n == 1 else 'i'} "
                "pronti per l'importazione. Controlla l'anteprima e conferma."
            ),
            font=("Segoe UI", 12),
            text_color=c["fg_muted"],
        ).pack(anchor="w", pady=(2, 0))

        # Tabella Anteprima
        table_card = ctk.CTkFrame(
            container,
            fg_color=c["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=c["border"],
        )
        table_card.pack(fill="both", expand=True, pady=(0, 12))

        columns = ("name", "size", "quantity", "purchased_price", "purchased_place", "selling_place", "status")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("name",            text="PRODOTTO",         anchor="w")
        self.tree.heading("size",            text="TAGLIA",           anchor="center")
        self.tree.heading("quantity",        text="Q.TA",             anchor="center")
        self.tree.heading("purchased_price", text="P. ACQUISTO",      anchor="center")
        self.tree.heading("purchased_place", text="L. ACQUISTO",      anchor="w")
        self.tree.heading("selling_place",   text="L. VENDITA",       anchor="w")
        self.tree.heading("status",          text="STATO",            anchor="center")

        self.tree.column("name",            width=240, anchor=tk.W)
        self.tree.column("size",            width=65,  anchor=tk.CENTER)
        self.tree.column("quantity",        width=55,  anchor=tk.CENTER)
        self.tree.column("purchased_price", width=100, anchor=tk.CENTER)
        self.tree.column("purchased_place", width=130, anchor=tk.W)
        self.tree.column("selling_place",   width=130, anchor=tk.W)
        self.tree.column("status",          width=100, anchor=tk.CENTER)

        yscroll = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)
        yscroll.pack(side="right", fill="y", padx=(0, 2), pady=2)

        # Popola la tabella
        for p in self.products:
            raw_status = str(p.get("status", "")).strip()
            if raw_status in ("Venduto", "Vendite Attive", STATUS_SOLD):
                db_status = STATUS_SOLD
                label_status = "Vendite Attive"
            elif raw_status in ("Pre-ordine", "Preordine", STATUS_PREORDER):
                db_status = STATUS_PREORDER
                label_status = "Pre-ordine"
            else:
                db_status = STATUS_STOCK
                label_status = "Magazzino"
            p["_db_status"] = db_status

            price_val = p.get("purchased_price", 0) or 0
            try:
                price_str = money(Decimal(str(price_val)))
            except Exception:
                price_str = str(price_val)

            self.tree.insert("", "end", values=(
                str(p.get("name", "")).strip(),
                str(p.get("size", "UNI")).strip() or "UNI",
                int(p.get("quantity", 1) or 1),
                price_str,
                str(p.get("purchased_place", "")).strip(),
                str(p.get("selling_place", "")).strip(),
                label_status,
            ))

        # Barra inferiore
        bottom_bar = ctk.CTkFrame(container, fg_color="transparent")
        bottom_bar.pack(fill="x")

        self.lbl_count = ctk.CTkLabel(
            bottom_bar,
            text=f"{n} prodott{'o' if n == 1 else 'i'} pronti per l'importazione.",
            font=("Segoe UI", 11, "bold"),
            text_color=c["fg_muted"],
        )
        self.lbl_count.pack(side="left")

        ctk.CTkButton(
            bottom_bar,
            text="Annulla",
            command=self.destroy,
            fg_color="#374151",
            hover_color="#4b5563",
            width=90,
        ).pack(side="right")

        ctk.CTkButton(
            bottom_bar,
            text="Conferma e Salva",
            command=self._confirm_and_save,
            fg_color="#059669",
            hover_color="#047857",
            font=("Segoe UI", 12, "bold"),
            width=160,
        ).pack(side="right", padx=(0, 10))

    def _confirm_and_save(self) -> None:
        """Inserisce tutti i prodotti nel database e chiude la dialog."""
        saved = 0
        for p in self.products:
            try:
                db_status = p.get("_db_status", STATUS_STOCK)

                purchased_raw = p.get("purchased_price", 0) or 0
                purchased = Decimal(str(purchased_raw)).quantize(Decimal("0.01"))

                selling_raw = p.get("selling_price", 0) or 0
                selling = Decimal(str(selling_raw)).quantize(Decimal("0.01")) if selling_raw else None

                sold_raw = p.get("sold_price", 0) or 0
                sold = Decimal(str(sold_raw)).quantize(Decimal("0.01")) if sold_raw else None

                fees_raw = p.get("fees", 0) or 0
                fees = Decimal(str(fees_raw)).quantize(Decimal("0.01"))

                qty = int(p.get("quantity", 1) or 1)
                if qty <= 0:
                    qty = 1

                sold_date   = str(p.get("sold_date",    "") or "").strip()
                if db_status == STATUS_SOLD and not sold_date:
                    sold_date = datetime.now().strftime("%Y-%m-%d")
                release_date = str(p.get("release_date", "") or "").strip()
                notes        = str(p.get("notes",        "") or "").strip()

                record = {
                    "name":             str(p.get("name", "")).strip(),
                    "size":             str(p.get("size", "UNI") or "UNI").strip() or "UNI",
                    "quantity":         qty,
                    "purchased_price":  purchased,
                    "purchased_place":  str(p.get("purchased_place", "") or "").strip(),
                    "selling_place":    str(p.get("selling_place",   "") or "").strip(),
                    "selling_price":    selling,
                    "sold_price":       sold,
                    "fees":             fees,
                    "sold_date":        sold_date,
                    "status":           db_status,
                    "release_date":     release_date if db_status == STATUS_PREORDER else "",
                    "notes":            notes,
                }
                self.db.save(record)
                saved += 1
            except Exception as e:
                print(f"[ExcelImportDialog] Errore salvataggio prodotto: {e}")

        self.confirmed = True
        self.saved_count = saved
        self.destroy()


class ExcelHintDialog(ctk.CTkToplevel):
    """
    Piccola dialog che appare dopo la selezione del file Excel/CSV,
    prima di avviare l'analisi AI. Permette all'utente di fornire
    indicazioni contestuali opzionali per aumentare la precisione dell'AI.

    Esempi di note utili:
    - "Dalla riga 15 in poi sono tutti pre-ordini"
    - "La colonna 'costo netto' è il prezzo di acquisto"
    - "I prodotti con 'eBay' nel negozio sono già venduti"

    Attributi pubblici dopo chiusura:
        confirmed (bool): True se l'utente ha premuto Procedi, False se Annulla.
        hint (str): Il testo inserito (può essere vuoto).
    """

    def __init__(self, parent: tk.Misc, filename: str) -> None:
        super().__init__(parent, fg_color=DARK_THEME["bg_main"])
        self.confirmed = False
        self.hint = ""

        self.title("Importazione AI — Suggerimento opzionale")
        center_window(self, 560, 340)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        apply_dark_titlebar(self)

        self._build(filename)

    def _build(self, filename: str) -> None:
        c = DARK_THEME
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=22, pady=18)

        # ── Header ──────────────────────────────────────────────────────────
        ctk.CTkLabel(
            container,
            text="Suggerimento per l'AI (opzionale)",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            container,
            text=(
                f"File selezionato: {filename}\n"
                "Puoi fornire indicazioni contestuali per aiutare l'AI a interpretare "
                "correttamente il file. Lascia vuoto per procedere con le regole standard."
            ),
            font=("Segoe UI", 11),
            text_color=c["fg_muted"],
            justify="left",
            wraplength=510,
        ).pack(anchor="w", pady=(4, 12))

        # ── Campo testo ──────────────────────────────────────────────────────
        hint_card = ctk.CTkFrame(
            container,
            fg_color=c["bg_card"],
            corner_radius=8,
            border_width=1,
            border_color=c["border"],
        )
        hint_card.pack(fill="both", expand=True, pady=(0, 12))

        self.txt_hint = ctk.CTkTextbox(
            hint_card,
            font=("Segoe UI", 12),
            fg_color="transparent",
            wrap="word",
            height=110,
        )
        self.txt_hint.pack(fill="both", expand=True, padx=10, pady=8)

        # Placeholder hint examples
        ctk.CTkLabel(
            container,
            text='Per esempio: "Dalla riga 10 in poi sono pre-ordini" oppure "Il campo Costo è il prezzo acquisto"',
            font=("Segoe UI", 10),
            text_color=c["fg_muted"],
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        # ── Pulsanti ────────────────────────────────────────────────────────
        btn_bar = ctk.CTkFrame(container, fg_color="transparent")
        btn_bar.pack(fill="x")

        ctk.CTkButton(
            btn_bar,
            text="Annulla",
            command=self.destroy,
            fg_color="#374151",
            hover_color="#4b5563",
            width=90,
        ).pack(side="right")

        ctk.CTkButton(
            btn_bar,
            text="Procedi senza note",
            command=self._proceed_no_hint,
            fg_color="#374151",
            hover_color="#4b5563",
            width=140,
        ).pack(side="right", padx=(0, 8))

        ctk.CTkButton(
            btn_bar,
            text="Procedi con nota",
            command=self._proceed_with_hint,
            font=("Segoe UI", 12, "bold"),
            width=150,
        ).pack(side="right", padx=(0, 8))

        # Focus sul campo di testo
        self.txt_hint.focus_set()
        # Bind Ctrl+Enter per procedere rapidamente
        self.bind("<Control-Return>", lambda _e: self._proceed_with_hint())

    def _proceed_with_hint(self) -> None:
        self.hint = self.txt_hint.get("1.0", "end").strip()
        self.confirmed = True
        self.destroy()

    def _proceed_no_hint(self) -> None:
        self.hint = ""
        self.confirmed = True
        self.destroy()
