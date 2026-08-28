#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finestre di dialogo per Russo Stock Manager."""

import sqlite3
import tkinter as tk
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from tkinter import ttk, messagebox

from ..config import DARK_THEME, STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK
from ..utils import calculate_profit, money, parse_date, parse_int, parse_money


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
        parent.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()

        w = max(750, int(pw * 2 / 3))
        h = max(550, int(ph * 0.5))
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2

        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(650, 500)
        c = DARK_THEME
        self.configure(bg=c["bg_card"])
        self.transient(parent)
        self.grab_set()
        
        from ..utils import apply_dark_titlebar
        apply_dark_titlebar(self)

        # Inizializzazione variabili
        rec = record
        self.vars = {
            "name": tk.StringVar(value=rec["name"] if rec else ""),
            "size": tk.StringVar(value=rec["size"] if rec else ""),
            "quantity": tk.StringVar(value=str(rec["quantity"]) if rec and "quantity" in rec.keys() else "1"),
            "purchased_price": tk.StringVar(value=f'{rec["purchased_price"]:.2f}'.replace('.', ',') if rec else ""),
            "purchased_place": tk.StringVar(value=rec["purchased_place"] if rec else ""),
            "selling_place": tk.StringVar(value=rec["selling_place"] if rec else ""),
            "selling_price": tk.StringVar(
                value=f'{rec["selling_price"]:.2f}'.replace('.', ',') if rec and rec["selling_price"] is not None else ""
            ),
            "sold_price": tk.StringVar(
                value=f'{rec["sold_price"]:.2f}'.replace('.', ',') if rec and "sold_price" in rec.keys() and rec["sold_price"] is not None else ""
            ),
            "fees": tk.StringVar(
                value=f'{rec["fees"]:.2f}'.replace('.', ',') if rec and "fees" in rec.keys() and rec["fees"] is not None else "0,00"
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
        if hasattr(self, "_mousewheel_funcid"):
            self.unbind_all("<MouseWheel>")
        super().destroy()

    def _build(self) -> None:
        c = DARK_THEME
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

        form_area = tk.Frame(outer, bg=c["bg_card"])
        form_area.pack(fill="both", expand=True)
        form_canvas = tk.Canvas(form_area, bg=c["bg_card"], highlightthickness=0)
        form_scroll = ttk.Scrollbar(form_area, orient="vertical", command=form_canvas.yview)
        form_canvas.configure(yscrollcommand=form_scroll.set)
        form_scroll.pack(side="right", fill="y")
        
        # Aggiunto padx per stringere i campi centrali e lasciare spazio vuoto ai lati per lo scroll sicuro
        form_canvas.pack(side="left", fill="both", expand=True, padx=80)
        
        form = tk.Frame(form_canvas, bg=c["bg_card"])
        form_window = form_canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda _e: form_canvas.configure(scrollregion=form_canvas.bbox("all")))
        form_canvas.bind("<Configure>", lambda event: form_canvas.itemconfigure(form_window, width=event.width))
        
        def _on_mousewheel(event: tk.Event) -> None:
            try:
                if event.widget.winfo_toplevel() == self:
                    form_canvas.yview_scroll(int(-event.delta / 120), "units")
            except Exception:
                pass
                
        self._mousewheel_funcid = self.bind_all("<MouseWheel>", _on_mousewheel)

        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        # Campi base
        self.name_entry = self._field_entry(form, "NOME PRODOTTO *", "name", 0, 0, span=2)
        self._field_entry(form, "TAGLIA", "size", 1, 0)
        self._field_entry(form, "QUANTITÀ *", "quantity", 1, 1)

        self._field_entry(form, "PREZZO ACQUISTO (€) *", "purchased_price", 2, 0)
        self._field_combo(form, "LUOGO ACQUISTO", "purchased_place", self.purchased_places, 2, 1)

        # Selling place with Settings Gear
        lbl_frame = tk.Frame(form, bg=c["bg_card"])
        lbl_frame.grid(row=6, column=0, sticky="w", padx=(0, 6), pady=(8, 2))
        
        tk.Label(lbl_frame, text="LUOGO VENDITA", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold")).pack(side="left")
        
        # Aggiustato il font e aggiunto un piccolo padding inferiore (pady=(0,2)) per alzare la rotellina e allinearla al testo
        gear_lbl = tk.Label(lbl_frame, text="⚙", bg=c["bg_card"], fg=c["fg_muted"], font=("Segoe UI", 10), cursor="hand2")
        gear_lbl.pack(side="left", padx=(6, 0), pady=(0, 2))
        gear_lbl.bind("<Button-1>", lambda _e: self._open_manage_places())
        gear_lbl.bind("<Enter>", lambda _e: gear_lbl.configure(fg=c["fg_main"]))
        gear_lbl.bind("<Leave>", lambda _e: gear_lbl.configure(fg=c["fg_muted"]))
        
        self.selling_place_combo = ttk.Combobox(form, textvariable=self.vars["selling_place"], values=self.selling_places, state="readonly", font=("Segoe UI", 10))
        self.selling_place_combo.grid(row=7, column=0, sticky="ew", padx=(0, 6), ipady=4)

        self._field_entry(form, "PREZZO VENDITA (€)", "selling_price", 3, 1)

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

        # Sezione Venduto (Spese e Data)
        self.lbl_fees = tk.Label(form, text="COMMISSIONI / SPESE (€)", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold"))
        self.lbl_fees.grid(row=10, column=0, sticky="w", pady=(10, 4))
        self.entry_fees = ttk.Entry(form, textvariable=self.vars["fees"], font=("Segoe UI", 10))
        self.entry_fees.grid(row=11, column=0, sticky="ew", padx=(0, 6), ipady=4)

        self.lbl_sold_date = tk.Label(form, text="DATA VENDITA (AAAA-MM-GG)", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold"))
        self.lbl_sold_date.grid(row=10, column=1, sticky="w", pady=(10, 4))
        self.entry_sold_date = ttk.Entry(form, textvariable=self.vars["sold_date"], font=("Segoe UI", 10))
        self.entry_sold_date.grid(row=11, column=1, sticky="ew", padx=(6, 0), ipady=4)

        # Card anteprima Profitto & ROI
        self.profit_card = tk.Frame(form, bg=c["bg_input"], highlightbackground=c["border"], highlightthickness=1, padx=12, pady=10)
        self.profit_card.grid(row=14, column=0, columnspan=2, sticky="ew", pady=(14, 4))
        tk.Label(self.profit_card, text="CALCOLO PROFITTO NETTO E ROI", bg=c["bg_input"], fg=c["fg_muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(self.profit_card, textvariable=self.profit_info_var, bg=c["bg_input"], fg=c["fg_main"], font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(2, 0))

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
        c = DARK_THEME
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
        c = DARK_THEME
        l_row = group_row * 2
        e_row = l_row + 1
        px = (0, 6) if column == 0 else (6, 0)

        tk.Label(parent, text=label, bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold")).grid(
            row=l_row, column=column, sticky="w", padx=px, pady=(8, 2)
        )
        combo = ttk.Combobox(parent, textvariable=self.vars[key], values=values, font=("Segoe UI", 10))
        combo.grid(row=e_row, column=column, sticky="ew", padx=px, ipady=4)
        return combo

    def _open_manage_places(self) -> None:
        parent_db = getattr(self.master, 'db', None)
        if not parent_db:
            return
        
        ManagePlacesDialog(self, parent_db, self.selling_places, self._on_places_updated)

    def _on_places_updated(self) -> None:
        parent_db = getattr(self.master, 'db', None)
        if parent_db:
            _, selling = parent_db.get_distinct_places()
            self.selling_places = selling
            self.selling_place_combo["values"] = self.selling_places
            
            # Se il valore corrente è stato cancellato, sbiancalo
            if self.vars["selling_place"].get() not in self.selling_places:
                self.vars["selling_place"].set("")

    def _on_status_changed(self) -> None:
        st = self.vars["status"].get()

        # Sold fields
        if st == STATUS_SOLD:
            self.entry_fees.configure(state="normal")
            self.entry_sold_date.configure(state="normal")
            self.lbl_fees.configure(fg=DARK_THEME["fg_main"])
            self.lbl_sold_date.configure(fg=DARK_THEME["fg_main"])
            self.profit_card.grid()
            if not self.vars["sold_date"].get():
                self.vars["sold_date"].set(datetime.now().strftime("%Y-%m-%d"))
        else:
            self.entry_fees.configure(state="disabled")
            self.entry_sold_date.configure(state="disabled")
            self.lbl_fees.configure(fg=DARK_THEME["fg_muted"])
            self.lbl_sold_date.configure(fg=DARK_THEME["fg_muted"])
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
            fees = parse_money(self.vars["fees"].get(), allow_empty=True) or 0.0

            st = self.vars["status"].get()
            
            sold = sale if st == STATUS_SOLD else None

            if st == STATUS_SOLD and sold is None:
                raise ValueError("Per i prodotti venduti è obbligatorio inserire il Prezzo di Vendita.")

            # Data di uscita eliminata
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


class BulkStatusDialog(tk.Toplevel):
    """Finestra di dialogo per la modifica di massa dello stato dei prodotti selezionati."""

    def __init__(self, parent: tk.Misc, count: int, target_status: str) -> None:
        super().__init__(parent)
        self.result: Optional[Dict[str, Any]] = None
        self.count = count
        self.target_status = target_status

        self.title("Spostamento di massa")
        
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 520, 460
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(500, 440)
        c = DARK_THEME
        self.configure(bg=c["bg_card"])
        self.transient(parent)
        self.grab_set()

        from ..utils import apply_dark_titlebar
        apply_dark_titlebar(self)

        self.var_sold_price = tk.StringVar()
        self.var_fees = tk.StringVar(value="0,00")
        self.var_sold_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))

        self._build()
        self.bind("<Return>", lambda _e: self._submit())

    def _build(self) -> None:
        c = DARK_THEME
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

            tk.Label(form, text="Prezzo vendita TOTALE (€):", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
            ent_price = ttk.Entry(form, textvariable=self.var_sold_price, font=("Segoe UI", 10))
            ent_price.pack(fill="x", pady=(2, 10), ipady=3)
            ent_price.focus_set()

            tk.Label(form, text="Commissioni/Spese TOTALI (€):", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
            ttk.Entry(form, textvariable=self.var_fees, font=("Segoe UI", 10)).pack(fill="x", pady=(2, 10), ipady=3)

            tk.Label(form, text="Data di vendita (AAAA-MM-GG):", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
            ttk.Entry(form, textvariable=self.var_sold_date, font=("Segoe UI", 10)).pack(fill="x", pady=(2, 10), ipady=3)

        buttons = tk.Frame(outer, bg=c["bg_card"])
        buttons.pack(fill="x", side="bottom", pady=(20, 0))
        ttk.Button(buttons, text="Annulla", style="Secondary.TButton", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Conferma Spostamento (Invio)", style="Accent.TButton", command=self._submit).pack(side="right", padx=(0, 10))

    def _submit(self) -> None:
        extra = {}
        if self.target_status == STATUS_SOLD:
            try:
                sp_total = parse_money(self.var_sold_price.get(), allow_empty=True)
                fees_total = parse_money(self.var_fees.get(), allow_empty=True) or 0.0
                dt = self.var_sold_date.get().strip()
                if sp_total is None:
                    raise ValueError("Per i prodotti venduti è obbligatorio il prezzo di vendita totale.")
                
                dt = parse_date(dt)
                
                # Calcola i valori per singolo prodotto (totale diviso per la quantità di prodotti selezionati)
                extra["sold_price"] = round(sp_total / self.count, 2) if self.count > 0 else sp_total
                extra["fees"] = round(fees_total / self.count, 2) if self.count > 0 else fees_total
                extra["sold_date"] = dt
                import uuid
                extra["bundle_id"] = str(uuid.uuid4())
            except ValueError as exc:
                messagebox.showerror("Valori non validi", str(exc), parent=self)
                return

        self.result = extra
        self.destroy()


class ManagePlacesDialog(tk.Toplevel):
    """Finestra per la gestione dei luoghi di vendita."""

    def __init__(self, parent: tk.Misc, db: Any, current_places: List[str], on_update: callable) -> None:
        super().__init__(parent)
        self.db = db
        self.current_places = current_places
        self.on_update = on_update

        self.title("Gestione Luoghi di Vendita")
        
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 550, 650
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(450, 600)
        c = DARK_THEME
        self.configure(bg=c["bg_card"])
        self.transient(parent)
        self.grab_set()

        from ..utils import apply_dark_titlebar
        apply_dark_titlebar(self)

        self._build()

    def _build(self) -> None:
        c = DARK_THEME
        outer = tk.Frame(self, bg=c["bg_card"], padx=24, pady=24)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text="Luoghi di Vendita", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(outer, text="Aggiungi nuovi luoghi o elimina quelli che non usi più.", bg=c["bg_card"], fg=c["fg_muted"], font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 14))

        # Aggiungi Nuovo (spostato in alto per renderlo più visibile)
        add_frame = tk.Frame(outer, bg=c["bg_input"], padx=12, pady=12, highlightbackground=c["border"], highlightthickness=1)
        add_frame.pack(fill="x", pady=(0, 16))
        
        tk.Label(add_frame, text="INSERISCI NUOVO LUOGO:", bg=c["bg_input"], fg=c["fg_main"], font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 6))
        
        input_frame = tk.Frame(add_frame, bg=c["bg_input"])
        input_frame.pack(fill="x")
        
        self.var_new = tk.StringVar()
        entry = ttk.Entry(input_frame, textvariable=self.var_new, font=("Segoe UI", 11))
        entry.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=4)
        entry.bind("<Return>", lambda _e: self._add_place())
        entry.focus_set()
        
        ttk.Button(input_frame, text="Aggiungi (Invio)", style="Accent.TButton", command=self._add_place).pack(side="right")

        # Lista
        tk.Label(outer, text="LUOGHI ESISTENTI:", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        
        list_frame = tk.Frame(outer, bg=c["bg_card"])
        list_frame.pack(fill="both", expand=True, pady=(4, 10))
        
        self.listbox = tk.Listbox(
            list_frame, 
            bg=c["bg_input"], 
            fg=c["fg_main"], 
            selectbackground=c["accent"], 
            font=("Segoe UI", 11),
            activestyle="none",
            highlightthickness=1,
            highlightbackground=c["border"]
        )
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)

        for p in self.current_places:
            self.listbox.insert("end", p)

        # Bottoni Elimina e Chiudi
        btn_frame = tk.Frame(outer, bg=c["bg_card"])
        btn_frame.pack(fill="x", pady=(10, 0))
        
        ttk.Button(btn_frame, text="Elimina Selezionato", command=self._delete_place).pack(side="left")
        ttk.Button(btn_frame, text="Chiudi", style="Secondary.TButton", command=self.destroy).pack(side="right")

    def _add_place(self) -> None:
        val = self.var_new.get().strip()
        if not val:
            return
        
        self.db.add_custom_place(val)
        self._refresh()
        self.var_new.set("")

    def _delete_place(self) -> None:
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showwarning("Attenzione", "Seleziona un luogo da eliminare.", parent=self)
            return
            
        val = self.listbox.get(sel[0])
        self.db.delete_custom_place(val)
        self._refresh()

    def _refresh(self) -> None:
        self.on_update()
        _, selling = self.db.get_distinct_places()
        self.current_places = selling
        self.listbox.delete(0, "end")
        for p in self.current_places:
            self.listbox.insert("end", p)
