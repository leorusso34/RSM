#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finestra principale dell'applicazione InventoryApp per Russo Stock Manager."""

import csv
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional

from config import APP_NAME, APP_VERSION, DB_PATH, LIGHT_THEME, STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK
from database import InventoryDatabase
from ui.dashboard_view import DashboardView
from ui.dialogs import BulkStatusDialog, ProductDialog
from ui.theme import setup_app_theme
from utils import export_to_csv, money, parse_excel_file, parse_money


class InventoryApp(tk.Tk):
    """Finestra principale dell'applicazione di gestione inventario Russo Stock Manager."""

    COLUMNS = (
        "id", "name", "size", "quantity", "purchased_price", "purchased_place",
        "selling_place", "selling_price", "sold_price", "fees", "profit",
        "roi", "sold_date", "release_date"
    )

    HEADINGS = {
        "id": "ID",
        "name": "NOME PRODOTTO",
        "size": "TAGLIA",
        "quantity": "QTA",
        "purchased_price": "PREZZO ACQUISTO",
        "purchased_place": "LUOGO ACQUISTO",
        "selling_place": "LUOGO VENDITA",
        "selling_price": "STIMATO",
        "sold_price": "INCASSO VENDITA",
        "fees": "COMMISS./SPESE",
        "profit": "PROFITTO NETTO",
        "roi": "ROI %",
        "sold_date": "DATA VENDITA",
        "release_date": "DATA USCITA",
    }

    def __init__(self) -> None:
        super().__init__()
        self.db = InventoryDatabase()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1440x860")
        self.minsize(1080, 680)

        # Variabili di stato
        self.search_var = tk.StringVar()
        self.status_bar_var = tk.StringVar(value="Pronto")
        self.filter_purchased_place_var = tk.StringVar()
        self.filter_selling_place_var = tk.StringVar()
        self.filter_min_price_var = tk.StringVar()
        self.filter_max_price_var = tk.StringVar()

        self.current_sort: Dict[str, tuple[str, bool]] = {}
        self.trees: Dict[str, ttk.Treeview] = {}

        setup_app_theme(self)
        self._build_ui()
        self.refresh()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-n>", lambda _e: self.add_product())
        self.bind("<Control-f>", lambda _e: self.search_entry.focus_set())
        self.bind("<F5>", lambda _e: self.refresh())
        self.after(150, self.search_entry.focus_set)

    def _build_ui(self) -> None:
        c = LIGHT_THEME
        container = ttk.Frame(self, padding=20)
        container.pack(fill="both", expand=True)

        # 1. Header superiore
        header = ttk.Frame(container, style="Card.TFrame", padding=(16, 12))
        header.pack(fill="x", pady=(0, 14))

        title_box = ttk.Frame(header, style="Card.TFrame")
        title_box.pack(side="left")
        ttk.Label(title_box, text=APP_NAME.upper(), style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="Gestione Magazzino, Pre-ordini, Vendite e Profitto Netto", style="CardMuted.TLabel").pack(anchor="w")

        actions = ttk.Frame(header, style="Card.TFrame")
        actions.pack(side="right", pady=2)
        ttk.Button(actions, text="Importa Excel", command=self.import_excel).pack(side="left", padx=3)
        ttk.Button(actions, text="Esporta CSV", command=self.export_csv).pack(side="left", padx=3)
        ttk.Button(actions, text="Backup DB Sicuro", command=self.backup_database).pack(side="left", padx=3)
        ttk.Button(actions, text="+ Nuovo Prodotto", style="Accent.TButton", command=self.add_product).pack(side="left", padx=(8, 0))

        # 2. Barra Carte KPI
        kpis = ttk.Frame(container)
        kpis.pack(fill="x", pady=(0, 14))
        self.kpi_vars: Dict[str, tk.StringVar] = {}

        cards = [
            ("stock_total", "STOCK TOTALE (€)", "#2563eb"),
            ("stock_count", "PEZZI IN MAGAZZINO", "#059669"),
            ("preorder_count", "PRE-ORDINI", "#d97706"),
            ("sold_profit", "PROFITTO NETTO VENDITE", "#10b981"),
            ("all_count", "PEZZI TOTALI GESTITI", "#7c3aed"),
        ]

        for index, (key, label, color) in enumerate(cards):
            kpis.columnconfigure(index, weight=1)
            card = tk.Frame(
                kpis,
                bg=c["bg_card"],
                highlightbackground="#e2e8f0",
                highlightthickness=1,
                padx=14,
                pady=10,
            )
            card.grid(
                row=0,
                column=index,
                sticky="nsew",
                padx=(0 if index == 0 else 4, 0 if index == len(cards) - 1 else 4),
            )
            var = tk.StringVar(value="-")
            self.kpi_vars[key] = var

            # Accento superiore
            tk.Frame(card, bg=color, height=3).pack(fill="x", pady=(0, 6))
            tk.Label(card, text=label, bg=c["bg_card"], fg=c["fg_muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
            tk.Label(card, textvariable=var, bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(2, 0))

        # 3. Toolbar Ricerca e Filtri Avanzati
        toolbar_card = tk.Frame(container, bg=c["bg_card"], highlightbackground="#e2e8f0", highlightthickness=1, padx=14, pady=10)
        toolbar_card.pack(fill="x", pady=(0, 10))

        # Riga 1: Ricerca e tasto filtri
        r1 = tk.Frame(toolbar_card, bg=c["bg_card"])
        r1.pack(fill="x")

        tk.Label(r1, text="Cerca:", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold")).pack(side="left")
        self.search_entry = ttk.Entry(r1, textvariable=self.search_var, width=32)
        self.search_entry.pack(side="left", padx=(6, 8), ipady=2)
        self.search_var.trace_add("write", lambda *_args: self.refresh_tables())

        self.btn_toggle_filters = ttk.Button(r1, text="Filtri Avanzati ▼", command=self._toggle_filter_panel)
        self.btn_toggle_filters.pack(side="left", padx=4)

        ttk.Button(r1, text="Azzera Tutti i Filtri", command=self._reset_filters).pack(side="left", padx=4)

        tk.Label(r1, text="Suggerimento: usa Ctrl+Click o Shift+Click per la selezione multipla", bg=c["bg_card"], fg=c["fg_muted"], font=("Segoe UI", 9)).pack(side="right")

        # Panel dei Filtri avanzati (inizialmente nascosto o visibile su toggle)
        self.filter_panel = tk.Frame(toolbar_card, bg=c["bg_card"])
        # Non packato inizialmente

        tk.Label(self.filter_panel, text="Luogo Acquisto:", bg=c["bg_card"], font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=(0, 4), pady=6)
        self.combo_filter_purchased = ttk.Combobox(self.filter_panel, textvariable=self.filter_purchased_place_var, width=18)
        self.combo_filter_purchased.grid(row=0, column=1, sticky="w", padx=(0, 12))
        self.combo_filter_purchased.bind("<<ComboboxSelected>>", lambda _e: self.refresh_tables())

        tk.Label(self.filter_panel, text="Luogo Vendita:", bg=c["bg_card"], font=("Segoe UI", 9)).grid(row=0, column=2, sticky="w", padx=(0, 4))
        self.combo_filter_selling = ttk.Combobox(self.filter_panel, textvariable=self.filter_selling_place_var, width=18)
        self.combo_filter_selling.grid(row=0, column=3, sticky="w", padx=(0, 12))
        self.combo_filter_selling.bind("<<ComboboxSelected>>", lambda _e: self.refresh_tables())

        tk.Label(self.filter_panel, text="Prezzo Min (€):", bg=c["bg_card"], font=("Segoe UI", 9)).grid(row=0, column=4, sticky="w", padx=(0, 4))
        entry_min = ttk.Entry(self.filter_panel, textvariable=self.filter_min_price_var, width=10)
        entry_min.grid(row=0, column=5, sticky="w", padx=(0, 12))
        self.filter_min_price_var.trace_add("write", lambda *_a: self.refresh_tables())

        tk.Label(self.filter_panel, text="Prezzo Max (€):", bg=c["bg_card"], font=("Segoe UI", 9)).grid(row=0, column=6, sticky="w", padx=(0, 4))
        entry_max = ttk.Entry(self.filter_panel, textvariable=self.filter_max_price_var, width=10)
        entry_max.grid(row=0, column=7, sticky="w", padx=(0, 12))
        self.filter_max_price_var.trace_add("write", lambda *_a: self.refresh_tables())

        # 4. Notebook con Schede Tabellari e Dashboard
        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill="both", expand=True)

        self._create_tab(STATUS_STOCK, "In Magazzino")
        self._create_tab(STATUS_PREORDER, "Pre-ordini")
        self._create_tab(STATUS_SOLD, "Venduti")

        # Scheda Dashboard Statistici
        self.dashboard_view = DashboardView(self.notebook, self.db)
        self.notebook.add(self.dashboard_view, text="Dashboard & Grafici")

        self.notebook.bind("<<NotebookTabChanged>>", lambda _e: self._on_tab_changed())

        # 5. Barra azioni di massa e status bar inferiore
        bottom = ttk.Frame(container, padding=(0, 8, 0, 0))
        bottom.pack(fill="x")

        self.lbl_selected_info = ttk.Label(bottom, text="0 prodotti selezionati", style="Muted.TLabel")
        self.lbl_selected_info.pack(side="left", padx=(0, 12))

        self.btn_edit = ttk.Button(bottom, text="Modifica", command=self.edit_selected)
        self.btn_edit.pack(side="left", padx=4)

        self.btn_delete = ttk.Button(bottom, text="Elimina Selezionati", style="Danger.TButton", command=self.delete_selected)
        self.btn_delete.pack(side="left", padx=4)

        self.btn_move_stock = ttk.Button(bottom, text="Sposta in Magazzino", style="Accent.TButton", command=self.move_selected_to_stock)
        self.btn_move_stock.pack(side="left", padx=4)

        self.btn_move_sold = ttk.Button(bottom, text="Segna come Venduto...", style="Success.TButton", command=self.move_selected_to_sold)
        self.btn_move_sold.pack(side="left", padx=4)

        ttk.Label(bottom, textvariable=self.status_bar_var, style="Muted.TLabel").pack(side="right")

    def _create_tab(self, status: str, title: str) -> None:
        frame = ttk.Frame(self.notebook, padding=(0, 8, 0, 0))
        self.notebook.add(frame, text=title)

        tree_frame = ttk.Frame(frame, style="Card.TFrame")
        tree_frame.pack(fill="both", expand=True)

        # Abilitata la selezione multipla con selectmode="extended"
        tree = ttk.Treeview(tree_frame, columns=self.COLUMNS, show="headings", selectmode="extended")

        widths = {
            "id": 50,
            "name": 280,
            "size": 75,
            "quantity": 55,
            "purchased_price": 125,
            "purchased_place": 140,
            "selling_place": 140,
            "selling_price": 110,
            "sold_price": 125,
            "fees": 110,
            "profit": 130,
            "roi": 75,
            "sold_date": 105,
            "release_date": 105,
        }

        for column in self.COLUMNS:
            tree.heading(column, text=self.HEADINGS[column], command=lambda c=column, s=status: self.sort_tree(s, c))
            tree.column(
                column,
                width=widths.get(column, 100),
                minwidth=45,
                anchor="e" if column in {"purchased_price", "selling_price", "sold_price", "fees", "profit", "roi", "quantity"} else "w",
                stretch=column == "name",
            )

        yscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        tree.bind("<Double-1>", lambda _e: self.edit_selected())
        tree.bind("<Delete>", lambda _e: self.delete_selected())
        tree.bind("<<TreeviewSelect>>", lambda _e: self._update_action_states())

        self.trees[status] = tree

    def _toggle_filter_panel(self) -> None:
        if self.filter_panel.winfo_ismapped():
            self.filter_panel.pack_forget()
            self.btn_toggle_filters.configure(text="Filtri Avanzati ▼")
        else:
            self.filter_panel.pack(fill="x", pady=(8, 0))
            self.btn_toggle_filters.configure(text="Filtri Avanzati ▲")

    def _reset_filters(self) -> None:
        self.search_var.set("")
        self.filter_purchased_place_var.set("")
        self.filter_selling_place_var.set("")
        self.filter_min_price_var.set("")
        self.filter_max_price_var.set("")
        self.refresh()

    def current_status(self) -> Optional[str]:
        idx = self.notebook.index("current")
        if idx == 0:
            return STATUS_STOCK
        elif idx == 1:
            return STATUS_PREORDER
        elif idx == 2:
            return STATUS_SOLD
        return None

    def current_tree(self) -> Optional[ttk.Treeview]:
        st = self.current_status()
        return self.trees.get(st) if st else None

    def selected_ids(self) -> List[int]:
        tree = self.current_tree()
        if not tree:
            return []
        selection = tree.selection()
        return [int(item_id) for item_id in selection]

    def _on_tab_changed(self) -> None:
        if self.notebook.index("current") == 3:
            self.dashboard_view.refresh()
        self._update_action_states()

    def refresh(self) -> None:
        self._update_autocomplete_combos()
        self.refresh_tables()
        self.refresh_totals()
        self._update_action_states()

    def _update_autocomplete_combos(self) -> None:
        purchased, selling = self.db.get_distinct_places()
        self.combo_filter_purchased["values"] = [""] + purchased
        self.combo_filter_selling["values"] = [""] + selling

    def refresh_tables(self) -> None:
        st = self.current_status()
        if not st:
            return

        query = self.search_var.get()
        p_place = self.filter_purchased_place_var.get()
        s_place = self.filter_selling_place_var.get()

        min_p = parse_money(self.filter_min_price_var.get(), allow_empty=True)
        max_p = parse_money(self.filter_max_price_var.get(), allow_empty=True)

        for status_key, tree in self.trees.items():
            selected = tree.selection()
            tree.delete(*tree.get_children())

            rows = self.db.list_products(
                status=status_key,
                search=query,
                purchased_place=p_place,
                selling_place=s_place,
                min_price=min_p,
                max_price=max_p,
            )

            for row in rows:
                qty = row["quantity"] or 1
                sp = row["sold_price"] or row["selling_price"] or 0.0
                profit, roi = (
                    ((sp - row["purchased_price"] - row["fees"]) * qty, (sp - row["purchased_price"] - row["fees"]) / row["purchased_price"] * 100)
                    if row["purchased_price"] > 0 else (0.0, 0.0)
                )

                values = (
                    row["id"],
                    row["name"],
                    row["size"],
                    qty,
                    money(row["purchased_price"]),
                    row["purchased_place"],
                    row["selling_place"],
                    money(row["selling_price"]) if row["selling_price"] is not None else "-",
                    money(row["sold_price"]) if row["sold_price"] is not None else "-",
                    money(row["fees"]) if row["fees"] else "€ 0,00",
                    money(profit) if status_key == STATUS_SOLD else "-",
                    f"{roi:.1f}%" if status_key == STATUS_SOLD and row["purchased_price"] > 0 else "-",
                    row["sold_date"],
                    row["release_date"],
                )
                tree.insert("", "end", iid=str(row["id"]), values=values)

            # Ripristina selezione se ancora esistente
            for s_id in selected:
                if tree.exists(s_id):
                    tree.selection_add(s_id)

        self.status_bar_var.set("Vista aggiornata")

    def refresh_totals(self) -> None:
        totals = self.db.totals()
        self.kpi_vars["stock_total"].set(money(totals["stock_total"]))
        self.kpi_vars["stock_count"].set(str(totals["stock_count"]))
        self.kpi_vars["preorder_count"].set(str(totals["preorder_count"]))
        self.kpi_vars["sold_profit"].set(money(totals["sold_profit"]))
        self.kpi_vars["all_count"].set(str(totals["all_count"]))

    def _update_action_states(self) -> None:
        ids = self.selected_ids()
        count = len(ids)

        self.lbl_selected_info.configure(text=f"{count} prodotti selezionati")

        has_selection = count > 0
        state = "normal" if has_selection else "disabled"

        self.btn_edit.configure(state="normal" if count == 1 else "disabled")
        self.btn_delete.configure(state=state)

        cur_st = self.current_status()
        self.btn_move_stock.configure(state=state if cur_st != STATUS_STOCK else "disabled")
        self.btn_move_sold.configure(state=state if cur_st != STATUS_SOLD else "disabled")

    def add_product(self) -> None:
        cur_st = self.current_status() or STATUS_STOCK
        places = self.db.get_distinct_places()
        dialog = ProductDialog(self, cur_st, autocomplete_places=places)
        self.wait_window(dialog)

        if dialog.result:
            new_id = self.db.save(dialog.result)
            target = dialog.result["status"]
            self.refresh()

            tab_idx = 0 if target == STATUS_STOCK else (1 if target == STATUS_PREORDER else 2)
            self.notebook.select(tab_idx)

            tree = self.trees[target]
            if tree.exists(str(new_id)):
                tree.selection_set(str(new_id))
                tree.see(str(new_id))

            self.status_bar_var.set("Prodotto aggiunto con successo")

    def edit_selected(self) -> None:
        ids = self.selected_ids()
        if len(ids) != 1:
            return

        prod_id = ids[0]
        record = self.db.get(prod_id)
        if not record:
            self.refresh()
            return

        places = self.db.get_distinct_places()
        dialog = ProductDialog(self, record["status"], autocomplete_places=places, record=record)
        self.wait_window(dialog)

        if dialog.result:
            self.db.save(dialog.result, prod_id)
            target = dialog.result["status"]
            self.refresh()

            tab_idx = 0 if target == STATUS_STOCK else (1 if target == STATUS_PREORDER else 2)
            self.notebook.select(tab_idx)

            tree = self.trees[target]
            if tree.exists(str(prod_id)):
                tree.selection_set(str(prod_id))
                tree.see(str(prod_id))

            self.status_bar_var.set("Prodotto modificato con successo")

    def delete_selected(self) -> None:
        ids = self.selected_ids()
        if not ids:
            return

        count = len(ids)
        msg = f"Eliminare definitivamente {count} prodotti selezionati?\nQuesta operazione non può essere annullata." if count > 1 else "Eliminare definitivamente il prodotto selezionato?"

        if messagebox.askyesno("Conferma eliminazione", msg, parent=self):
            deleted_count = self.db.delete_many(ids)
            self.refresh()
            self.status_bar_var.set(f"Eliminati {deleted_count} prodotti")

    def move_selected_to_stock(self) -> None:
        ids = self.selected_ids()
        if not ids:
            return

        if messagebox.askyesno(
            "Conferma spostamento",
            f"Spostare {len(ids)} prodotti in 'In Magazzino'?",
            parent=self,
        ):
            self.db.update_status_many(ids, STATUS_STOCK)
            self.refresh()
            self.notebook.select(0)
            self.status_bar_var.set(f"{len(ids)} prodotti spostati in magazzino")

    def move_selected_to_sold(self) -> None:
        ids = self.selected_ids()
        if not ids:
            return

        dialog = BulkStatusDialog(self, len(ids), STATUS_SOLD)
        self.wait_window(dialog)

        if dialog.result is not None:
            self.db.update_status_many(ids, STATUS_SOLD, extra_data=dialog.result)
            self.refresh()
            self.notebook.select(2)
            self.status_bar_var.set(f"{len(ids)} prodotti contrassegnati come venduti")

    def export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Esporta prodotti in CSV",
            defaultextension=".csv",
            filetypes=[("File CSV", "*.csv")],
            initialfile=f"russo_stock_{datetime.now():%Y%m%d_%H%M}.csv",
        )
        if not path:
            return

        ids = self.selected_ids()
        if ids:
            placeholders = ", ".join("?" for _ in ids)
            rows = self.db.connection.execute(f"SELECT * FROM products WHERE id IN ({placeholders}) ORDER BY status, name", tuple(ids)).fetchall()
        else:
            rows = self.db.connection.execute("SELECT * FROM products ORDER BY status, name").fetchall()

        products_data = [dict(row) for row in rows]
        count = export_to_csv(path, products_data)

        self.status_bar_var.set(f"Esportati {count} prodotti")
        messagebox.showinfo("Esportazione completata", f"Esportati {count} prodotti nel file:\n{path}", parent=self)

    def import_excel(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Importa file Excel", filetypes=[("Excel", "*.xlsx *.xlsm")])
        if not path:
            return

        try:
            records, skipped = parse_excel_file(path)
            if not records:
                raise ValueError("Nessuna riga valida trovata. Verifica che le colonne NAME e PURCHASED PRICE siano presenti.")

            if not messagebox.askyesno(
                "Conferma importazione",
                f"Trovati {len(records)} prodotti nell'Excel.\n(Tutti i prodotti sotto la sezione PREORDER verranno importati come Pre-ordini).\n\nAggiungere all'inventario?",
                parent=self,
            ):
                return

            inserted = self.db.insert_many(records)
            self.refresh()
            messagebox.showinfo(
                "Importazione Completata",
                f"Importati con successo {inserted} prodotti!\n(Righe ignorate: {skipped})",
                parent=self,
            )
            self.status_bar_var.set(f"Importati {inserted} prodotti da Excel")

        except Exception as exc:
            messagebox.showerror("Errore Importazione Excel", str(exc), parent=self)

    def backup_database(self) -> None:
        if not DB_PATH.exists():
            messagebox.showwarning("Database non trovato", "Il file del database non è ancora stato creato.", parent=self)
            return

        target = filedialog.asksaveasfilename(
            parent=self,
            title="Salva Backup Sicuro SQLite",
            defaultextension=".db",
            filetypes=[("Database SQLite", "*.db")],
            initialfile=f"russo_stock_backup_{datetime.now():%Y%m%d_%H%M}.db",
        )
        if target:
            try:
                self.db.backup_database_safe(Path(target))
                self.status_bar_var.set("Backup del database completato")
                messagebox.showinfo(
                    "Backup Completato in Sicurezza",
                    f"Backup atomico SQLite creato con successo:\n{target}",
                    parent=self,
                )
            except Exception as exc:
                messagebox.showerror("Errore Backup", str(exc), parent=self)

    def _on_close(self) -> None:
        self.db.close()
        self.destroy()
