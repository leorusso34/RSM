#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finestre di dialogo per Russo Stock Manager."""

import sqlite3
import tkinter as tk
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from tkinter import ttk, messagebox

from config import LIGHT_THEME, STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK
from utils import calculate_profit, money, parse_int, parse_money


class ProductDialog(tk.Toplevel):
    """Finestra di dialogo per la creazione o modifica di un singolo prodotto."""

    def __init__(
        self,
        parent: tk.Misc,
        initial_status: str,
        autocomplete_places: Tuple[List[str], List[str]] = ([], []),
        record: Optional[sqlite3.Row] = None,
    ) -> None:
        super().__init__(parent)
        self.result: Optional[Dict[str, Any]] = None
        self.record = record
        self.purchased_places, self.selling_places = autocomplete_places

        self.title("Modifica prodotto" if record else "Nuovo prodotto")
        self.geometry("650x780")
        self.minsize(580, 720)
        c = LIGHT_THEME
        self.configure(bg=c["bg_card"])
        self.transient(parent)
        self.grab_set()

        # Inizializzazione variabili
        rec = record
        self.vars = {
            "name": tk.StringVar(value=rec["name"] if rec else ""),
            "size": tk.StringVar(value=rec["size"] if rec else ""),
            "quantity": tk.StringVar(value=str(rec["quantity"]) if rec and "quantity" in rec.keys() else "1"),
            "purchased_price": tk.StringVar(value=f'{rec["purchased_price"]:.2f}' if rec else ""),
            "purchased_place": tk.StringVar(value=rec["purchased_place"] if rec else ""),
            "selling_place": tk.StringVar(value=rec["selling_place"] if rec else ""),
            "selling_price": tk.StringVar(
                value=f'{rec["selling_price"]:.2f}' if rec and rec["selling_price"] is not None else ""
            ),
            "sold_price": tk.StringVar(
                value=f'{rec["sold_price"]:.2f}' if rec and "sold_price" in rec.keys() and rec["sold_price"] is not None else ""
            ),
            "fees": tk.StringVar(
                value=f'{rec["fees"]:.2f}' if rec and "fees" in rec.keys() and rec["fees"] is not None else "0.00"
            ),
            "sold_date": tk.StringVar(
                value=rec["sold_date"] if rec and "sold_date" in rec.keys() and rec["sold_date"] else ""
            ),
            "status": tk.StringVar(value=rec["status"] if rec else initial_status),
            "release_date": tk.StringVar(value=rec["release_date"] if rec else ""),
        }

        self.profit_info_var = tk.StringVar(value="-")

        self._build()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Control-Return>", lambda _e: self._submit())
        self.after(80, self._focus_name)

    def _focus_name(self) -> None:
        self.name_entry.focus_set()

    def _build(self) -> None:
        c = LIGHT_THEME
        outer = tk.Frame(self, bg=c["bg_card"], padx=26, pady=20)
        outer.pack(fill="both", expand=True)

        tk.Label(
            outer,
            text="Dettagli prodotto",
            bg=c["bg_card"],
            fg=c["fg_main"],
            font=("Segoe UI", 18, "bold"),
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            outer,
            text="Compila i dati del prodotto (* indica i campi obbligatori)",
            bg=c["bg_card"],
            fg=c["fg_muted"],
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", pady=(2, 14))

        # Canvas scorrevole per il form in caso di schermi ridotti
        form = tk.Frame(outer, bg=c["bg_card"])
        form.pack(fill="both", expand=True)

        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        # Campi base
        self.name_entry = self._field_entry(form, "NOME PRODOTTO *", "name", 0, 0, span=2)
        self._field_entry(form, "TAGLIA", "size", 1, 0)
        self._field_entry(form, "QUANTITÀ *", "quantity", 1, 1)

        self._field_entry(form, "PREZZO ACQUISTO (€) *", "purchased_price", 2, 0)
        self._field_combo(form, "LUOGO ACQUISTO", "purchased_place", self.purchased_places, 2, 1)

        self._field_combo(form, "LUOGO VENDITA", "selling_place", self.selling_places, 3, 0)
        self._field_entry(form, "PREZZO VENDITA STIMATO (€)", "selling_price", 3, 1)

        # Sezione Stato
        lbl_status = tk.Label(form, text="STATO PRODOTTO *", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold"))
        lbl_status.grid(row=8, column=0, columnspan=2, sticky="w", pady=(12, 4))

        status_box = ttk.Combobox(
            form,
            textvariable=self.vars["status"],
            values=(STATUS_STOCK, STATUS_PREORDER, STATUS_SOLD),
            state="readonly",
            font=("Segoe UI", 10),
        )
        status_box.grid(row=9, column=0, columnspan=2, sticky="ew", ipady=4)
        status_box.bind("<<ComboboxSelected>>", lambda _e: self._on_status_changed())

        # Sezione Pre-ordine (Data uscita)
        self.lbl_release = tk.Label(form, text="DATA USCITA (AAAA-MM-GG)", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold"))
        self.lbl_release.grid(row=10, column=0, sticky="w", pady=(10, 4))
        self.entry_release = ttk.Entry(form, textvariable=self.vars["release_date"], font=("Segoe UI", 10))
        self.entry_release.grid(row=11, column=0, sticky="ew", padx=(0, 6), ipady=4)

        # Sezione Venduto (Prezzo effettivo, Spese/Commissioni, Data vendita)
        self.lbl_sold_price = tk.Label(form, text="PREZZO VENDITA EFFETTIVO (€) *", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold"))
        self.lbl_sold_price.grid(row=10, column=1, sticky="w", pady=(10, 4))
        self.entry_sold_price = ttk.Entry(form, textvariable=self.vars["sold_price"], font=("Segoe UI", 10))
        self.entry_sold_price.grid(row=11, column=1, sticky="ew", padx=(6, 0), ipady=4)

        self.lbl_fees = tk.Label(form, text="COMMISSIONI / SPESE (€)", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold"))
        self.lbl_fees.grid(row=12, column=0, sticky="w", pady=(10, 4))
        self.entry_fees = ttk.Entry(form, textvariable=self.vars["fees"], font=("Segoe UI", 10))
        self.entry_fees.grid(row=13, column=0, sticky="ew", padx=(0, 6), ipady=4)

        self.lbl_sold_date = tk.Label(form, text="DATA VENDITA (AAAA-MM-GG)", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold"))
        self.lbl_sold_date.grid(row=12, column=1, sticky="w", pady=(10, 4))
        self.entry_sold_date = ttk.Entry(form, textvariable=self.vars["sold_date"], font=("Segoe UI", 10))
        self.entry_sold_date.grid(row=13, column=1, sticky="ew", padx=(6, 0), ipady=4)

        # Card anteprima Profitto & ROI
        self.profit_card = tk.Frame(form, bg="#f1f5f9", highlightbackground="#cbd5e1", highlightthickness=1, padx=12, pady=10)
        self.profit_card.grid(row=14, column=0, columnspan=2, sticky="ew", pady=(14, 4))
        tk.Label(self.profit_card, text="CALCOLO PROFITTO NETTO E ROI", bg="#f1f5f9", fg=c["fg_muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(self.profit_card, textvariable=self.profit_info_var, bg="#f1f5f9", fg=c["fg_main"], font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(2, 0))

        # Note
        tk.Label(form, text="NOTE", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold")).grid(row=15, column=0, columnspan=2, sticky="w", pady=(10, 4))
        self.notes = tk.Text(
            form,
            height=3,
            wrap="word",
            bg=c["bg_input"],
            fg=c["fg_main"],
            insertbackground=c["fg_main"],
            relief="flat",
            padx=8,
            pady=6,
            font=("Segoe UI", 10),
        )
        self.notes.grid(row=16, column=0, columnspan=2, sticky="nsew")
        if self.record:
            self.notes.insert("1.0", self.record["notes"])

        # Tracciamento per calcolo profitto live
        for key in ("purchased_price", "sold_price", "fees", "quantity"):
            self.vars[key].trace_add("write", lambda *_a: self._update_profit_preview())

        # Bottoni
        buttons = tk.Frame(outer, bg=c["bg_card"])
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text="Annulla", style="Secondary.TButton", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Salva Prodotto", style="Accent.TButton", command=self._submit).pack(side="right", padx=(0, 10))

        self._on_status_changed()

    def _field_entry(self, parent: tk.Widget, label: str, key: str, group_row: int, column: int, span: int = 1) -> ttk.Entry:
        c = LIGHT_THEME
        l_row = group_row * 2
        e_row = l_row + 1
        px = (0, 6) if column == 0 and span == 1 else ((6, 0) if column == 1 else 0)

        tk.Label(parent, text=label, bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold")).grid(
            row=l_row, column=column, columnspan=span, sticky="w", padx=px, pady=(8, 2)
        )
        entry = ttk.Entry(parent, textvariable=self.vars[key], font=("Segoe UI", 10))
        entry.grid(row=e_row, column=column, columnspan=span, sticky="ew", padx=px, ipady=4)
        return entry

    def _field_combo(self, parent: tk.Widget, label: str, key: str, values: List[str], group_row: int, column: int) -> ttk.Combobox:
        c = LIGHT_THEME
        l_row = group_row * 2
        e_row = l_row + 1
        px = (0, 6) if column == 0 else (6, 0)

        tk.Label(parent, text=label, bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold")).grid(
            row=l_row, column=column, sticky="w", padx=px, pady=(8, 2)
        )
        combo = ttk.Combobox(parent, textvariable=self.vars[key], values=values, font=("Segoe UI", 10))
        combo.grid(row=e_row, column=column, sticky="ew", padx=px, ipady=4)
        return combo

    def _on_status_changed(self) -> None:
        st = self.vars["status"].get()

        # Preorder fields
        if st == STATUS_PREORDER:
            self.entry_release.configure(state="normal")
            self.lbl_release.configure(fg=LIGHT_THEME["fg_main"])
        else:
            self.entry_release.configure(state="disabled")
            self.lbl_release.configure(fg=LIGHT_THEME["fg_muted"])
            if st == STATUS_STOCK:
                self.vars["release_date"].set("")

        # Sold fields
        if st == STATUS_SOLD:
            self.entry_sold_price.configure(state="normal")
            self.entry_fees.configure(state="normal")
            self.entry_sold_date.configure(state="normal")
            self.lbl_sold_price.configure(fg=LIGHT_THEME["fg_main"])
            self.lbl_fees.configure(fg=LIGHT_THEME["fg_main"])
            self.lbl_sold_date.configure(fg=LIGHT_THEME["fg_main"])
            self.profit_card.grid()
            if not self.vars["sold_date"].get():
                self.vars["sold_date"].set(datetime.now().strftime("%Y-%m-%d"))
        else:
            self.entry_sold_price.configure(state="disabled")
            self.entry_fees.configure(state="disabled")
            self.entry_sold_date.configure(state="disabled")
            self.lbl_sold_price.configure(fg=LIGHT_THEME["fg_muted"])
            self.lbl_fees.configure(fg=LIGHT_THEME["fg_muted"])
            self.lbl_sold_date.configure(fg=LIGHT_THEME["fg_muted"])
            self.profit_card.grid_remove()

        self._update_profit_preview()

    def _update_profit_preview(self) -> None:
        try:
            buy = parse_money(self.vars["purchased_price"].get(), allow_empty=True) or 0.0
            sold = parse_money(self.vars["sold_price"].get(), allow_empty=True)
            fees = parse_money(self.vars["fees"].get(), allow_empty=True) or 0.0
            qty = parse_int(self.vars["quantity"].get(), 1)

            if sold is not None and buy > 0:
                profit, roi = calculate_profit(buy, sold, fees, qty)
                color_symbol = "+" if profit >= 0 else ""
                self.profit_info_var.set(
                    f"Profitto Netto Totale: {color_symbol}{money(profit)}   |   ROI: {roi:.1f}%"
                )
            else:
                self.profit_info_var.set("Inserisci il prezzo di vendita per calcolare profitto e ROI.")
        except Exception:
            self.profit_info_var.set("Impossibile calcolare il profitto con i dati correnti.")

    def _submit(self) -> None:
        try:
            name = self.vars["name"].get().strip()
            if not name:
                raise ValueError("Il nome del prodotto è obbligatorio.")

            qty = parse_int(self.vars["quantity"].get(), 1)
            purchase = parse_money(self.vars["purchased_price"].get())
            sale = parse_money(self.vars["selling_price"].get(), allow_empty=True)
            sold = parse_money(self.vars["sold_price"].get(), allow_empty=True)
            fees = parse_money(self.vars["fees"].get(), allow_empty=True) or 0.0

            st = self.vars["status"].get()
            if st == STATUS_SOLD and sold is None:
                raise ValueError("Per i prodotti venduti è obbligatorio inserire il Prezzo Effettivo di vendita.")

            release = self.vars["release_date"].get().strip()
            if release:
                datetime.strptime(release, "%Y-%m-%d")

            sold_date = self.vars["sold_date"].get().strip()
            if sold_date:
                datetime.strptime(sold_date, "%Y-%m-%d")

        except ValueError as exc:
            msg = "Le date devono essere nel formato AAAA-MM-GG." if "time data" in str(exc) else str(exc)
            messagebox.showerror("Dati non validi", msg, parent=self)
            return

        self.result = {
            "name": name,
            "size": self.vars["size"].get().strip(),
            "quantity": qty,
            "purchased_price": purchase,
            "purchased_place": self.vars["purchased_place"].get().strip(),
            "selling_place": self.vars["selling_place"].get().strip(),
            "selling_price": sale,
            "sold_price": sold,
            "fees": fees,
            "sold_date": sold_date,
            "status": st,
            "release_date": release,
            "notes": self.notes.get("1.0", "end").strip(),
        }
        self.destroy()


class BulkStatusDialog(tk.Toplevel):
    """Finestra di dialogo per la modifica di massa dello stato dei prodotti selezionati."""

    def __init__(self, parent: tk.Misc, count: int, target_status: str) -> None:
        super().__init__(parent)
        self.result: Optional[Dict[str, Any]] = None
        self.count = count
        self.target_status = target_status

        self.title(f"Azione di massa su {count} prodotti")
        self.geometry("460x360")
        self.resizable(False, False)
        c = LIGHT_THEME
        self.configure(bg=c["bg_card"])
        self.transient(parent)
        self.grab_set()

        self.var_sold_price = tk.StringVar()
        self.var_fees = tk.StringVar(value="0.00")
        self.var_sold_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))

        self._build()

    def _build(self) -> None:
        c = LIGHT_THEME
        outer = tk.Frame(self, bg=c["bg_card"], padx=24, pady=20)
        outer.pack(fill="both", expand=True)

        tk.Label(
            outer,
            text=f"Spostamento di massa in: {self.target_status}",
            bg=c["bg_card"],
            fg=c["fg_main"],
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")

        tk.Label(
            outer,
            text=f"Stai per convertire {self.count} prodotti selezionati.",
            bg=c["bg_card"],
            fg=c["fg_muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 16))

        if self.target_status == STATUS_SOLD:
            form = tk.Frame(outer, bg=c["bg_card"])
            form.pack(fill="x", pady=6)

            tk.Label(form, text="Prezzo vendita effettivo unitario (€) (opzionale):", bg=c["bg_card"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
            ttk.Entry(form, textvariable=self.var_sold_price).pack(fill="x", pady=(2, 10), ipady=3)

            tk.Label(form, text="Commissioni/Spese unitarie (€):", bg=c["bg_card"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
            ttk.Entry(form, textvariable=self.var_fees).pack(fill="x", pady=(2, 10), ipady=3)

            tk.Label(form, text="Data di vendita (AAAA-MM-GG):", bg=c["bg_card"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
            ttk.Entry(form, textvariable=self.var_sold_date).pack(fill="x", pady=(2, 10), ipady=3)

        buttons = tk.Frame(outer, bg=c["bg_card"])
        buttons.pack(fill="x", side="bottom", pady=(20, 0))
        ttk.Button(buttons, text="Annulla", style="Secondary.TButton", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Conferma Spostamento", style="Accent.TButton", command=self._submit).pack(side="right", padx=(0, 10))

    def _submit(self) -> None:
        extra = {}
        if self.target_status == STATUS_SOLD:
            try:
                sp = parse_money(self.var_sold_price.get(), allow_empty=True)
                fees = parse_money(self.var_fees.get(), allow_empty=True) or 0.0
                dt = self.var_sold_date.get().strip()
                if dt:
                    datetime.strptime(dt, "%Y-%m-%d")
                if sp is not None:
                    extra["sold_price"] = sp
                extra["fees"] = fees
                extra["sold_date"] = dt
            except ValueError as exc:
                messagebox.showerror("Valori non validi", str(exc), parent=self)
                return

        self.result = extra
        self.destroy()
