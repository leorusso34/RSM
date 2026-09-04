#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finestre di dialogo per RSM."""

import sqlite3
import tkinter as tk
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple
from tkinter import ttk, messagebox
import customtkinter as ctk

from ..config import DARK_THEME, STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK
from ..utils import calculate_profit, money, parse_date, parse_int, parse_money, center_window, apply_dark_titlebar


class ProductDialog(ctk.CTkToplevel):
    """Finestra di dialogo per la creazione o modifica di un singolo prodotto."""

    def __init__(
        self,
        parent: tk.Misc,
        initial_status: str,
        autocomplete_places: Tuple[List[str], List[str]] = ([], []),
        record: Optional[sqlite3.Row] = None,
    ) -> None:
        super().__init__(parent, fg_color=DARK_THEME["bg_main"])
        self.result: Optional[Dict[str, Any]] = None
        self.record = record
        self.purchased_places, self.selling_places = autocomplete_places

        self.title("Modifica prodotto" if record else "Nuovo prodotto")
        center_window(self, 750, 550)
        self.minsize(650, 500)
        self.transient(parent)
        self.grab_set()
        apply_dark_titlebar(self)

        rec = record
        self.vars = {
            "name": tk.StringVar(value=rec["name"] if rec else ""),
            "size": tk.StringVar(value=rec["size"] if rec else ""),
            "quantity": tk.StringVar(value=str(rec["quantity"]) if rec and "quantity" in rec.keys() else "1"),
            "purchased_price": tk.StringVar(value=f'{rec["purchased_price"]:.2f}'.replace(".", ",") if rec else ""),
            "purchased_place": tk.StringVar(value=rec["purchased_place"] if rec else ""),
            "selling_place": tk.StringVar(value=rec["selling_place"] if rec else ""),
            "selling_price": tk.StringVar(
                value=f'{rec["selling_price"]:.2f}'.replace(".", ",") if rec and rec["selling_price"] is not None else ""
            ),
            "sold_price": tk.StringVar(
                value=f'{rec["sold_price"]:.2f}'.replace(".", ",") if rec and "sold_price" in rec.keys() and rec["sold_price"] is not None else ""
            ),
            "fees": tk.StringVar(
                value=f'{rec["fees"]:.2f}'.replace(".", ",") if rec and "fees" in rec.keys() and rec["fees"] is not None else "0,00"
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

    def destroy(self) -> None:
        super().destroy()

    def _build(self) -> None:
        c = DARK_THEME
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=26, pady=20)

        ctk.CTkLabel(outer, text="Dettagli prodotto", font=("Segoe UI", 18, "bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(
            outer,
            text="Compila i dati del prodotto (* indica i campi obbligatori)",
            font=("Segoe UI", 13),
            text_color=c["fg_muted"],
            anchor="w",
        ).pack(fill="x", pady=(2, 14))

        # Form scrollabile - sostituisce Canvas + Scrollbar con CTKScrollableFrame
        form_area = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        form_area.pack(fill="both", expand=True, padx=40)
        form = form_area

        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        # Campi base
        self.name_entry = self._field_entry(form, "NOME PRODOTTO *", "name", 0, 0, span=2)
        self._field_entry(form, "TAGLIA", "size", 1, 0)
        self._field_entry(form, "QUANTITA *", "quantity", 1, 1)

        self._field_entry(form, "PREZZO ACQUISTO (€)", "purchased_price", 2, 0)
        self._field_combo(form, "LUOGO ACQUISTO", "purchased_place", self.purchased_places, 2, 1)

        # Selling place con ingranaggio
        lbl_frame = ctk.CTkFrame(form, fg_color="transparent")
        lbl_frame.grid(row=6, column=0, sticky="w", padx=(0, 6), pady=(8, 2))

        ctk.CTkLabel(lbl_frame, text="LUOGO VENDITA", font=("Segoe UI", 11, "bold")).pack(side="left")
        gear_lbl = ctk.CTkLabel(lbl_frame, text="⚙", font=("Segoe UI", 12), text_color=c["fg_muted"], cursor="hand2")
        gear_lbl.pack(side="left", padx=(6, 0), pady=(0, 2))
        gear_lbl.bind("<Button-1>", lambda _e: self._open_manage_places())
        gear_lbl.bind("<Enter>", lambda _e: gear_lbl.configure(text_color=c["fg_main"]))
        gear_lbl.bind("<Leave>", lambda _e: gear_lbl.configure(text_color=c["fg_muted"]))

        self.selling_place_combo = ctk.CTkComboBox(form, variable=self.vars["selling_place"], values=self.selling_places, font=("Segoe UI", 12))
        self.selling_place_combo.grid(row=7, column=0, sticky="ew", padx=(0, 6))

        self._field_entry(form, "PREZZO VENDITA (€)", "selling_price", 3, 1)

        # Stato
        self.lbl_status_lbl = ctk.CTkLabel(form, text="STATO PRODOTTO *", font=("Segoe UI", 11, "bold"))
        self.lbl_status_lbl.grid(row=8, column=0, columnspan=2, sticky="w", pady=(12, 4))

        status_box = ctk.CTkComboBox(
            form,
            variable=self.vars["status"],
            values=(STATUS_STOCK, STATUS_PREORDER, STATUS_SOLD),
            command=lambda v: self._on_status_changed(),
            font=("Segoe UI", 12),
        )
        status_box.grid(row=9, column=0, columnspan=2, sticky="ew")

        # Commissioni e data vendita
        self.lbl_fees = ctk.CTkLabel(form, text="COMMISSIONI / SPESE (€)", font=("Segoe UI", 11, "bold"))
        self.lbl_fees.grid(row=10, column=0, sticky="w", pady=(10, 4))
        self.entry_fees = ctk.CTkEntry(form, textvariable=self.vars["fees"], font=("Segoe UI", 12))
        self.entry_fees.grid(row=11, column=0, sticky="ew", padx=(0, 6))

        self.lbl_sold_date = ctk.CTkLabel(form, text="DATA VENDITA (AAAA-MM-GG)", font=("Segoe UI", 11, "bold"))
        self.lbl_sold_date.grid(row=10, column=1, sticky="w", pady=(10, 4))
        self.entry_sold_date = ctk.CTkEntry(form, textvariable=self.vars["sold_date"], font=("Segoe UI", 12))
        self.entry_sold_date.grid(row=11, column=1, sticky="ew", padx=(6, 0))

        # Card profitto con angoli arrotondati
        self.profit_card = ctk.CTkFrame(form, corner_radius=10, border_width=1, border_color=c["border"], fg_color=c["bg_input"])
        self.profit_card.grid(row=14, column=0, columnspan=2, sticky="ew", pady=(14, 4))
        ctk.CTkLabel(self.profit_card, text="CALCOLO PROFITTO NETTO E ROI", font=("Segoe UI", 10, "bold"), text_color=c["fg_muted"]).pack(anchor="w", padx=12, pady=(10, 0))
        ctk.CTkLabel(self.profit_card, textvariable=self.profit_info_var, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(2, 10))

        # Note
        ctk.CTkLabel(form, text="NOTE", font=("Segoe UI", 11, "bold")).grid(row=15, column=0, columnspan=2, sticky="w", pady=(10, 4))
        self.notes = ctk.CTkTextbox(form, height=80, font=("Segoe UI", 12), wrap="word")
        self.notes.grid(row=16, column=0, columnspan=2, sticky="nsew")
        if self.record:
            self.notes.insert("1.0", self.record["notes"])

        # Tracciamento profitto live
        for key in ("purchased_price", "sold_price", "fees", "quantity"):
            self.vars[key].trace_add("write", lambda *_a: self._update_profit_preview())

        # Bottoni
        buttons = ctk.CTkFrame(outer, fg_color="transparent")
        buttons.pack(fill="x", pady=(16, 0))
        ctk.CTkButton(buttons, text="Annulla", command=self.destroy, fg_color="#374151", hover_color="#4b5563").pack(side="right")
        ctk.CTkButton(buttons, text="Salva Prodotto", command=self._submit).pack(side="right", padx=(0, 10))

        self._on_status_changed()

    def _field_entry(self, parent: tk.Widget, label: str, key: str, group_row: int, column: int, span: int = 1):
        l_row = group_row * 2
        e_row = l_row + 1
        px = (0, 6) if column == 0 and span == 1 else ((6, 0) if column == 1 else 0)
        ctk.CTkLabel(parent, text=label, font=("Segoe UI", 11, "bold")).grid(
            row=l_row, column=column, columnspan=span, sticky="w", padx=px, pady=(8, 2)
        )
        entry = ctk.CTkEntry(parent, textvariable=self.vars[key], font=("Segoe UI", 12))
        entry.grid(row=e_row, column=column, columnspan=span, sticky="ew", padx=px)
        return entry

    def _field_combo(self, parent: tk.Widget, label: str, key: str, values: List[str], group_row: int, column: int):
        l_row = group_row * 2
        e_row = l_row + 1
        px = (0, 6) if column == 0 else (6, 0)
        ctk.CTkLabel(parent, text=label, font=("Segoe UI", 11, "bold")).grid(
            row=l_row, column=column, sticky="w", padx=px, pady=(8, 2)
        )
        combo = ctk.CTkComboBox(parent, variable=self.vars[key], values=values, font=("Segoe UI", 12))
        combo.grid(row=e_row, column=column, sticky="ew", padx=px)
        return combo

    def _open_manage_places(self) -> None:
        parent_db = getattr(self.master, "db", None)
        if not parent_db:
            return
        ManagePlacesDialog(self, parent_db, self.selling_places, self._on_places_updated)

    def _on_places_updated(self) -> None:
        parent_db = getattr(self.master, "db", None)
        if parent_db:
            _, selling = parent_db.get_distinct_places()
            self.selling_places = selling
            self.selling_place_combo.configure(values=self.selling_places)
            if self.vars["selling_place"].get() not in self.selling_places:
                self.vars["selling_place"].set("")

    def _on_status_changed(self) -> None:
        st = self.vars["status"].get()
        if st == STATUS_SOLD:
            self.entry_fees.configure(state="normal")
            self.entry_sold_date.configure(state="normal")
            self.lbl_fees.configure(text_color=DARK_THEME["fg_main"])
            self.lbl_sold_date.configure(text_color=DARK_THEME["fg_main"])
            self.profit_card.grid()
            if not self.vars["sold_date"].get():
                self.vars["sold_date"].set(datetime.now().strftime("%Y-%m-%d"))
        else:
            self.entry_fees.configure(state="disabled")
            self.entry_sold_date.configure(state="disabled")
            self.lbl_fees.configure(text_color=DARK_THEME["fg_muted"])
            self.lbl_sold_date.configure(text_color=DARK_THEME["fg_muted"])
            self.profit_card.grid_remove()
            self.vars["fees"].set("0,00")
            self.vars["sold_date"].set("")
        self._update_profit_preview()

    def _update_profit_preview(self) -> None:
        try:
            buy = parse_money(self.vars["purchased_price"].get(), allow_empty=True) or 0.0
            sold = parse_money(self.vars["selling_price"].get(), allow_empty=True)
            fees = parse_money(self.vars["fees"].get(), allow_empty=True) or 0.0
            qty = parse_int(self.vars["quantity"].get(), 1)
            if sold is not None and buy > 0:
                profit, roi = calculate_profit(buy, sold, fees, qty)
                prefix = "+" if profit >= 0 else ""
                self.profit_info_var.set(f"Profitto Netto Totale: {prefix}{money(profit)}   |   ROI: {roi:.1f}%")
            else:
                self.profit_info_var.set("Inserisci il prezzo di vendita per calcolare profitto e ROI.")
        except Exception:
            self.profit_info_var.set("Impossibile calcolare il profitto con i dati correnti.")

    def _submit(self) -> None:
        try:
            name = self.vars["name"].get().strip()
            if not name:
                raise ValueError("Il nome del prodotto e obbligatorio.")
            qty = parse_int(self.vars["quantity"].get(), 1)
            purchase = parse_money(self.vars["purchased_price"].get())
            sale = parse_money(self.vars["selling_price"].get(), allow_empty=True)
            fees = parse_money(self.vars["fees"].get(), allow_empty=True) or 0.0
            st = self.vars["status"].get()
            sold = sale if st == STATUS_SOLD else None
            if st == STATUS_SOLD and sold is None:
                raise ValueError("Per i prodotti venduti e obbligatorio inserire il Prezzo di Vendita.")
            release = ""
            sold_date = self.vars["sold_date"].get().strip()
            sold_date = parse_date(sold_date)
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


class BulkStatusDialog(ctk.CTkToplevel):
    """Finestra di dialogo per la modifica di massa dello stato dei prodotti selezionati."""

    def __init__(self, parent: tk.Misc, count: int, target_status: str) -> None:
        super().__init__(parent, fg_color=DARK_THEME["bg_main"])
        self.result: Optional[Dict[str, Any]] = None
        self.count = count
        self.target_status = target_status

        self.title("Spostamento di massa")
        center_window(self, 520, 460)
        self.minsize(500, 440)
        self.transient(parent)
        self.grab_set()
        apply_dark_titlebar(self)

        self.var_sold_price = tk.StringVar()
        self.var_fees = tk.StringVar(value="0,00")
        self.var_sold_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))

        self._build()
        self.bind("<Return>", lambda _e: self._submit())

    def _build(self) -> None:
        c = DARK_THEME
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(
            outer,
            text=f"Spostamento di massa in: {self.target_status}",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            outer,
            text=f"Stai per convertire {self.count} prodotti selezionati.",
            font=("Segoe UI", 12),
            text_color=c["fg_muted"],
        ).pack(anchor="w", pady=(2, 16))

        if self.target_status == STATUS_SOLD:
            form = ctk.CTkFrame(outer, fg_color="transparent")
            form.pack(fill="x", pady=6)

            ctk.CTkLabel(form, text="Prezzo vendita TOTALE (€):", font=("Segoe UI", 11, "bold")).pack(anchor="w")
            ent_price = ctk.CTkEntry(form, textvariable=self.var_sold_price, font=("Segoe UI", 12))
            ent_price.pack(fill="x", pady=(2, 10))
            ent_price.focus_set()

            ctk.CTkLabel(form, text="Commissioni/Spese TOTALI (€):", font=("Segoe UI", 11, "bold")).pack(anchor="w")
            ctk.CTkEntry(form, textvariable=self.var_fees, font=("Segoe UI", 12)).pack(fill="x", pady=(2, 10))

            ctk.CTkLabel(form, text="Data di vendita (AAAA-MM-GG):", font=("Segoe UI", 11, "bold")).pack(anchor="w")
            ctk.CTkEntry(form, textvariable=self.var_sold_date, font=("Segoe UI", 12)).pack(fill="x", pady=(2, 10))

        buttons = ctk.CTkFrame(outer, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", pady=(20, 0))
        ctk.CTkButton(buttons, text="Annulla", command=self.destroy, fg_color="#374151", hover_color="#4b5563").pack(side="right")
        ctk.CTkButton(buttons, text="Conferma Spostamento (Invio)", command=self._submit).pack(side="right", padx=(0, 10))

    def _submit(self) -> None:
        extra = {}
        if self.target_status == STATUS_SOLD:
            try:
                sp_total = parse_money(self.var_sold_price.get(), allow_empty=True)
                fees_total = parse_money(self.var_fees.get(), allow_empty=True) or Decimal("0")
                dt = self.var_sold_date.get().strip()
                if sp_total is None:
                    raise ValueError("Per i prodotti venduti e obbligatorio il prezzo di vendita totale.")
                dt = parse_date(dt)
                count_dec = Decimal(str(self.count))
                extra["sold_price"] = (sp_total / count_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if self.count > 0 else sp_total
                extra["fees"] = (fees_total / count_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if self.count > 0 else fees_total
                extra["sold_date"] = dt
                import uuid
                extra["bundle_id"] = str(uuid.uuid4())
            except ValueError as exc:
                messagebox.showerror("Valori non validi", str(exc), parent=self)
                return
        self.result = extra
        self.destroy()


class ManagePlacesDialog(ctk.CTkToplevel):
    """Finestra per la gestione dei luoghi di vendita."""

    def __init__(self, parent: tk.Misc, db: Any, current_places: List[str], on_update: callable) -> None:
        super().__init__(parent, fg_color=DARK_THEME["bg_main"])
        self.db = db
        self.current_places = current_places
        self.on_update = on_update
        self.selected_place: Optional[str] = None
        self._place_widgets: Dict[str, ctk.CTkButton] = {}

        self.title("Gestione Luoghi di Vendita")
        center_window(self, 550, 650)
        self.minsize(450, 600)
        self.transient(parent)
        self.grab_set()
        apply_dark_titlebar(self)

        self._build()

    def _build(self) -> None:
        c = DARK_THEME
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(outer, text="Luoghi di Vendita", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ctk.CTkLabel(outer, text="Aggiungi nuovi luoghi o elimina quelli che non usi piu.", font=("Segoe UI", 12), text_color=c["fg_muted"]).pack(anchor="w", pady=(2, 14))

        # Frame aggiungi con angoli arrotondati
        add_frame = ctk.CTkFrame(outer, corner_radius=10, border_width=1, border_color=c["border"], fg_color=c["bg_input"])
        add_frame.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(add_frame, text="INSERISCI NUOVO LUOGO:", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 6))

        input_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=12, pady=(0, 12))

        self.var_new = tk.StringVar()
        entry = ctk.CTkEntry(input_frame, textvariable=self.var_new, font=("Segoe UI", 13))
        entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        entry.bind("<Return>", lambda _e: self._add_place())
        entry.focus_set()

        ctk.CTkButton(input_frame, text="Aggiungi (Invio)", command=self._add_place).pack(side="right")

        # Lista luoghi esistenti in CTkScrollableFrame
        ctk.CTkLabel(outer, text="LUOGHI ESISTENTI:", font=("Segoe UI", 11, "bold")).pack(anchor="w")

        self.scroll_frame = ctk.CTkScrollableFrame(
            outer,
            fg_color=c["bg_input"],
            corner_radius=10,
            border_width=1,
            border_color=c["border"]
        )
        self.scroll_frame.pack(fill="both", expand=True, pady=(4, 10))

        self._render_places()

        btn_frame = ctk.CTkFrame(outer, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(btn_frame, text="Elimina Selezionato", command=self._delete_place, fg_color=c["danger"], hover_color=c["danger_hover"]).pack(side="left")
        ctk.CTkButton(btn_frame, text="Chiudi", command=self.destroy, fg_color="#374151", hover_color="#4b5563").pack(side="right")

    def _render_places(self) -> None:
        c = DARK_THEME
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        self._place_widgets.clear()
        for p in self.current_places:
            is_selected = (p == self.selected_place)
            btn = ctk.CTkButton(
                self.scroll_frame,
                text=f"  {p}",
                anchor="w",
                font=("Segoe UI", 13),
                fg_color=c["accent"] if is_selected else "transparent",
                hover_color=c["accent_hover"] if is_selected else "#28334a",
                text_color="#ffffff" if is_selected else c["fg_main"],
                height=34,
                corner_radius=6,
                command=lambda name=p: self._select_place(name)
            )
            btn.pack(fill="x", pady=2, padx=4)
            self._place_widgets[p] = btn

    def _select_place(self, name: str) -> None:
        c = DARK_THEME
        self.selected_place = name
        for p, btn in self._place_widgets.items():
            is_selected = (p == name)
            btn.configure(
                fg_color=c["accent"] if is_selected else "transparent",
                hover_color=c["accent_hover"] if is_selected else "#28334a",
                text_color="#ffffff" if is_selected else c["fg_main"]
            )

    def _add_place(self) -> None:
        val = self.var_new.get().strip()
        if not val:
            return
        self.db.add_custom_place(val)
        self.selected_place = val
        self._refresh()
        self.var_new.set("")

    def _delete_place(self) -> None:
        if not self.selected_place:
            messagebox.showwarning("Attenzione", "Seleziona un luogo da eliminare.", parent=self)
            return
        val = self.selected_place
        self.db.delete_custom_place(val)
        self.selected_place = None
        self._refresh()

    def _refresh(self) -> None:
        self.on_update()
        _, selling = self.db.get_distinct_places()
        self.current_places = selling
        self._render_places()