#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finestra principale dell'applicazione InventoryApp per Russo Stock Manager."""

import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from ..config import APP_NAME, APP_VERSION, DB_PATH, DARK_THEME, STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK, STATUS_COMPLETED
from ..database import InventoryDatabase
from .dashboard_view import DashboardView
from .dialogs import BulkStatusDialog, ProductDialog
from .theme import setup_app_theme
from ..utils import export_to_csv, money, parse_excel_file, parse_money, calculate_profit


class InventoryApp(tk.Tk):
    """Finestra principale dell'applicazione di gestione inventario Russo Stock Manager."""

    COLUMNS = (
        "name", "size", "quantity", "purchased_price", "purchased_place",
        "selling_place", "sale_price", "fees", "profit", "roi", "sold_date"
    )

    HEADINGS = {
        "name": "NOME PRODOTTO",
        "size": "TAGLIA",
        "quantity": "Q.TÀ",
        "purchased_price": "P. ACQUISTO",
        "purchased_place": "L. ACQUISTO",
        "selling_place": "L. VENDITA",
        "sale_price": "P. VENDITA",
        "fees": "COMMISSIONI / SPESE",
        "profit": "PROFITTO",
        "roi": "ROI",
        "sold_date": "DATA VENDITA",
    }

    def __init__(self) -> None:
        super().__init__()
        self.db = InventoryDatabase()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1440x860")
        self.minsize(1080, 680)
        self.state("zoomed")

        # Variabili di stato
        self.search_var = tk.StringVar()
        self.status_bar_var = tk.StringVar(value="Pronto")
        self.filter_purchased_place_var = tk.StringVar()
        self.filter_selling_place_var = tk.StringVar()
        self.filter_min_price_var = tk.StringVar()
        self.filter_max_price_var = tk.StringVar()

        self.current_sort: Dict[str, tuple[str, bool]] = {}
        self.trees: Dict[str, ttk.Treeview] = {}
        self._clipboard_ids: List[int] = []
        self.status_tabs = [STATUS_STOCK, STATUS_PREORDER, STATUS_SOLD, STATUS_COMPLETED]

        try:
            import sys
            from ..config import PROJECT_DIR
            icon_path = Path(getattr(sys, "_MEIPASS", PROJECT_DIR)) / "app_icon.ico"
            if icon_path.exists():
                self.iconbitmap(str(icon_path))
            else:
                fallback_path = PROJECT_DIR / "app_icon.ico"
                if fallback_path.exists():
                    self.iconbitmap(str(fallback_path))
        except Exception as e:
            print(f"Icona non caricata: {e}")

        setup_app_theme(self)
        self._apply_dark_titlebar()
        self._build_ui()
        self.refresh()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-n>", lambda _e: self.add_product())
        self.bind("<Control-f>", lambda _e: self.search_entry.focus_set())
        self.bind("<F5>", lambda _e: self.refresh())
        self.bind("<Control-Tab>", lambda _e: self._switch_tab(1))
        self.bind("<Control-Shift-Tab>", lambda _e: self._switch_tab(-1))
        self.after(150, self.search_entry.focus_set)

    def _apply_dark_titlebar(self) -> None:
        """Forza la titlebar di Windows 10/11 in modalità scura per matchare il tema."""
        try:
            import ctypes
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            value = ctypes.c_int(1)
            # Try Windows 11
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
            # Try Windows 10
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(value), ctypes.sizeof(value))
        except Exception:
            pass

    def _build_ui(self) -> None:
        c = DARK_THEME
        
        # Ripristiniamo la barra nativa scura (permette lo snap ai bordi, e riduci a icona)
        self._apply_dark_titlebar()
        
        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        # 1. Header superiore
        header = ttk.Frame(container, style="Card.TFrame", padding=(16, 12))
        header.pack(fill="x", pady=(0, 14))

        # Box per logo e titolo
        title_box = ttk.Frame(header, style="Card.TFrame")
        title_box.pack(side="left")
        
        # Carica il logo da mostrare nell'interfaccia
        try:
            from PIL import Image, ImageTk
            import sys
            w_path = Path(getattr(sys, "_MEIPASS", PROJECT_DIR)) / "app_icon.ico"
            if not w_path.exists():
                w_path = PROJECT_DIR / "app_icon.ico"
                
            img = Image.open(w_path).resize((32, 32), Image.Resampling.LANCZOS)
            self._header_logo = ImageTk.PhotoImage(img)
            lbl_logo = tk.Label(title_box, image=self._header_logo, bg=c["bg_card"])
            lbl_logo.pack(side="left", padx=(0, 10))
        except Exception:
            pass

        text_box = ttk.Frame(title_box, style="Card.TFrame")
        text_box.pack(side="left")
        
        ttk.Label(text_box, text=APP_NAME.upper(), style="Title.TLabel").pack(anchor="w")
        ttk.Label(text_box, text="Gestione Magazzino, Pre-ordini, Vendite e Profitto Netto", style="CardMuted.TLabel").pack(anchor="w")

        actions = ttk.Frame(header, style="Card.TFrame")
        actions.pack(side="right", pady=2)
        ttk.Button(actions, text="Importa Excel", command=self.import_excel).pack(side="left", padx=3)
        ttk.Button(actions, text="Esporta CSV", command=self.export_csv).pack(side="left", padx=3)
        ttk.Button(actions, text="Backup DB Sicuro", command=self.backup_database).pack(side="left", padx=3)
        ttk.Button(actions, text="+ Nuovo Prodotto", style="Accent.TButton", command=self.add_product).pack(side="left", padx=(8, 0))

        # Test Sfondo/Watermark rimosso via git
        
        # 2. Barra Carte KPI
        kpis = ttk.Frame(container)
        kpis.pack(fill="x", pady=(0, 14))
        self.kpi_vars: Dict[str, tk.StringVar] = {}

        cards = [
            ("stock_total", "STOCK TOTALE (€)", "#2563eb"),
            ("stock_count", "IN MAGAZZINO", "#3b82f6"),
            ("sold_profit_active", "PROFITTO VENDITE ATTIVE", "#10b981"),
            ("sold_profit_completed", "PROFITTO STORICO COMPLETATE", "#059669"),
            ("all_count", "PEZZI TOTALI GESTITI", "#7c3aed"),
        ]

        for index, (key, label, color) in enumerate(cards):
            kpis.columnconfigure(index, weight=1)
            card = tk.Frame(
                kpis,
                bg=c["bg_card"],
                highlightthickness=0,  # RIMOSSO BORDO DURO!
                padx=16,
                pady=12,
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
        toolbar_card = tk.Frame(container, bg=c["bg_card"], highlightbackground=c["border"], highlightthickness=1, padx=14, pady=10)
        toolbar_card.pack(fill="x", pady=(0, 10))

        # Riga 1: Ricerca e tasto filtri
        r1 = tk.Frame(toolbar_card, bg=c["bg_card"])
        r1.pack(fill="x")

        tk.Label(r1, text="Cerca:", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9, "bold")).pack(side="left")
        self.search_entry = ttk.Entry(r1, textvariable=self.search_var, width=32)
        self.search_entry.pack(side="left", padx=(6, 8), ipady=2)
        self.search_var.trace_add("write", self._on_search_changed)

        self.btn_toggle_filters = ttk.Button(r1, text="Filtri Avanzati ▼", command=self._toggle_filter_panel)
        self.btn_toggle_filters.pack(side="left", padx=4)

        ttk.Button(r1, text="Azzera Tutti i Filtri", command=self._reset_filters).pack(side="left", padx=4)

        tk.Label(r1, text="Suggerimento: usa Ctrl+Click o Shift+Click per la selezione multipla", bg=c["bg_card"], fg=c["fg_muted"], font=("Segoe UI", 9)).pack(side="right")

        # Panel dei Filtri avanzati (inizialmente nascosto o visibile su toggle)
        self.filter_panel = tk.Frame(toolbar_card, bg=c["bg_card"])
        # Non packato inizialmente

        tk.Label(self.filter_panel, text="Luogo Acquisto:", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=(0, 4), pady=6)
        self.combo_filter_purchased = ttk.Combobox(self.filter_panel, textvariable=self.filter_purchased_place_var, width=18)
        self.combo_filter_purchased.grid(row=0, column=1, sticky="w", padx=(0, 12))
        self.combo_filter_purchased.bind("<<ComboboxSelected>>", lambda _e: self.refresh_tables())

        tk.Label(self.filter_panel, text="Luogo Vendita:", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9)).grid(row=0, column=2, sticky="w", padx=(0, 4))
        self.combo_filter_selling = ttk.Combobox(self.filter_panel, textvariable=self.filter_selling_place_var, width=18)
        self.combo_filter_selling.grid(row=0, column=3, sticky="w", padx=(0, 12))
        self.combo_filter_selling.bind("<<ComboboxSelected>>", lambda _e: self.refresh_tables())

        tk.Label(self.filter_panel, text="Prezzo Min (€):", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9)).grid(row=0, column=4, sticky="w", padx=(0, 4))
        entry_min = ttk.Entry(self.filter_panel, textvariable=self.filter_min_price_var, width=10)
        entry_min.grid(row=0, column=5, sticky="w", padx=(0, 12))
        self.filter_min_price_var.trace_add("write", lambda *_a: self.refresh_tables())

        tk.Label(self.filter_panel, text="Prezzo Max (€):", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9)).grid(row=0, column=6, sticky="w", padx=(0, 4))
        entry_max = ttk.Entry(self.filter_panel, textvariable=self.filter_max_price_var, width=10)
        entry_max.grid(row=0, column=7, sticky="w", padx=(0, 12))
        self.filter_max_price_var.trace_add("write", lambda *_a: self.refresh_tables())

        # 4. Notebook con Schede Tabellari e Dashboard
        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill="both", expand=True)

        self._create_tab(STATUS_STOCK, "Magazzino")
        self._create_tab(STATUS_PREORDER, "Pre-ordini")
        self._create_tab(STATUS_SOLD, "Vendite Attive")
        from ..config import STATUS_COMPLETED
        self._create_tab(STATUS_COMPLETED, "Vendite Completate")

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

        self.btn_delete = ttk.Button(bottom, text="Elimina Prodotto/i", style="Danger.TButton", command=self.delete_selected)
        self.btn_delete.pack(side="left", padx=4)

        self.btn_move_stock = ttk.Button(bottom, text="Sposta in Magazzino", style="Accent.TButton", command=self.move_selected_to_stock)
        self.btn_move_stock.pack(side="left", padx=4)

        self.btn_move_sold = ttk.Button(bottom, text="Segna come Venduto...", style="Success.TButton", command=self.move_selected_to_sold)
        self.btn_move_sold.pack(side="left", padx=4)

        ttk.Label(bottom, textvariable=self.status_bar_var, style="Muted.TLabel").pack(side="right")

        # Context Menu (Menu a tendina)
        self.context_menu = tk.Menu(self, tearoff=0, bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 9))

    def _create_tab(self, status: str, title: str) -> None:
        frame = ttk.Frame(self.notebook, padding=(0, 8, 0, 0))
        self.notebook.add(frame, text=title)

        tree_frame = ttk.Frame(frame, style="Card.TFrame")
        tree_frame.pack(fill="both", expand=True)

        is_stock = status in (STATUS_STOCK, STATUS_PREORDER)

        if is_stock:
            visible_cols = ("name", "size", "quantity", "purchased_price", "purchased_place")
            widths = {
                "name": 450,
                "size": 80,
                "quantity": 70,
                "purchased_price": 140,
                "purchased_place": 220,
            }
        else:
            visible_cols = self.COLUMNS
            widths = {
                "name": 220,
                "size": 60,
                "quantity": 50,
                "purchased_price": 95,
                "purchased_place": 125,
                "selling_place": 125,
                "sale_price": 95,
                "fees": 120,
                "profit": 95,
                "roi": 60,
                "sold_date": 105,
            }
            
        tree = ttk.Treeview(tree_frame, columns=self.COLUMNS, displaycolumns=visible_cols, show="headings", selectmode="extended")
        tree.tag_configure("stripe", background=DARK_THEME["table_alt_row"])

        for column in self.COLUMNS:
            tree.heading(column, text=self.HEADINGS[column], anchor="center", command=lambda c=column, s=status: self.sort_tree(s, c))
            col_width = widths.get(column, 100)
                
            tree.column(
                column,
                width=col_width,
                minwidth=45,
                anchor=tk.W if column == "name" else tk.CENTER,
                stretch=True, # Tutte le colonne si espandono proporzionalmente
            )

        yscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)

        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        tree.bind("<Double-1>", lambda _e: self.edit_selected())
        tree.bind("<Button-3>", lambda e: self._on_right_click(e, tree))
        tree.bind("<Delete>", lambda _e: self.delete_selected())
        tree.bind("<<TreeviewSelect>>", lambda _e: self._update_action_states())

        # Bindings Drag & Drop
        tree.bind("<ButtonPress-1>", lambda e, t=tree: self._on_drag_start(e, t))
        tree.bind("<B1-Motion>", lambda e, t=tree: self._on_drag_motion(e, t))
        tree.bind("<ButtonRelease-1>", lambda e, t=tree: self._on_drag_release(e, t))

        # Keyboard Selection Bindings
        tree.bind("<Shift-Up>", lambda e, t=tree: self._extend_selection(e, t, -1))
        tree.bind("<Shift-Down>", lambda e, t=tree: self._extend_selection(e, t, 1))
        tree.bind("<Control-Shift-Up>", lambda e, t=tree: self._extend_selection(e, t, -1))
        tree.bind("<Control-Shift-Down>", lambda e, t=tree: self._extend_selection(e, t, 1))
        tree.bind("<Control-a>", lambda e, t=tree: self._select_all(e, t))
        tree.bind("<Control-A>", lambda e, t=tree: self._select_all(e, t))
        tree.bind("<Control-c>", self._copy_to_clipboard)
        tree.bind("<Control-C>", self._copy_to_clipboard)
        tree.bind("<Control-v>", self._paste_from_clipboard)
        tree.bind("<Control-V>", self._paste_from_clipboard)

        self.trees[status] = tree

    def _on_right_click(self, event: tk.Event, tree: ttk.Treeview) -> None:
        """Mostra il menu a tendina al click col tasto destro."""
        item = tree.identify_row(event.y)
        if item:
            # Se clicchi un elemento non selezionato, lo seleziona
            if item not in tree.selection():
                tree.selection_set(item)
            self._update_action_states()
            
            self.context_menu.delete(0, "end")
            st = self.current_status()
            if st != STATUS_COMPLETED:
                self.context_menu.add_command(label="Modifica", command=self.edit_selected)
                self.context_menu.add_command(label="Duplica", command=self.duplicate_selected)
                
            if st == STATUS_PREORDER:
                self.context_menu.add_separator()
                self.context_menu.add_command(label="Conferma in magazzino", command=self.move_selected_to_stock)
                
            if st == STATUS_SOLD:
                self.context_menu.add_separator()
                self.context_menu.add_command(label="Completa Vendita", command=self.complete_selected_sales)
                
            self.context_menu.add_separator()
            self.context_menu.add_command(label="Elimina", command=self.delete_selected)

            self.context_menu.post(event.x_root, event.y_root)

    def complete_selected_sales(self) -> None:
        ids = self.selected_ids()
        if not ids: return
        
        # Blocchiamo l'azione se ci sono prodotti di un bundle ma non abbiamo l'intero bundle? 
        # Actually selected_ids restituisce tutti i figli, quindi aggiorna tutto il bundle se selezionato dal genitore.
        with self.db.connection:
            self.db.connection.execute(f"UPDATE products SET is_completed = 1 WHERE id IN ({','.join('?'*len(ids))})", ids)
        self.refresh()
        self.status_bar_var.set(f"{len(ids)} prodotti contrassegnati come vendita completata")

    def _on_search_changed(self, *args) -> None:
        if hasattr(self, "_search_timer"):
            self.after_cancel(self._search_timer)
        self._search_timer = self.after(250, self.refresh_tables)

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
        if 0 <= idx < len(self.status_tabs):
            return self.status_tabs[idx]
        return None

    def current_tree(self) -> Optional[ttk.Treeview]:
        st = self.current_status()
        return self.trees.get(st) if st else None

    def selected_ids(self) -> List[int]:
        tree = self.current_tree()
        if not tree:
            return []
        
        selection = tree.selection()
        ids = set()
        for item_id in selection:
            if str(item_id).startswith("bundle_"):
                # If it's a bundle, get all its children
                children = tree.get_children(item_id)
                for child in children:
                    try:
                        ids.add(int(child))
                    except ValueError:
                        pass
            else:
                try:
                    ids.add(int(item_id))
                except ValueError:
                    pass
        return list(ids)

    def _on_tab_changed(self) -> None:
        if self.notebook.index("current") == 4:
            self.dashboard_view.refresh()
        self._update_action_states()
    def _switch_tab(self, direction: int) -> str:
        current = self.notebook.index("current")
        total = self.notebook.index("end")
        if total > 0:
            next_idx = (current + direction) % total
            self.notebook.select(next_idx)
        return "break"

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

        try:
            min_p = parse_money(self.filter_min_price_var.get(), allow_empty=True)
            max_p = parse_money(self.filter_max_price_var.get(), allow_empty=True)
        except ValueError:
            self.status_bar_var.set("Inserire filtri prezzo validi")
            return

        if min_p is not None and max_p is not None and min_p > max_p:
            self.status_bar_var.set("Il prezzo minimo non può superare il massimo")
            return

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

            bundles = {}
            normal_rows = []
            
            for row in rows:
                r_dict = dict(row)
                if status_key in (STATUS_SOLD, STATUS_COMPLETED) and r_dict.get("bundle_id"):
                    bundles.setdefault(r_dict["bundle_id"], []).append(r_dict)
                else:
                    normal_rows.append(r_dict)

            # Insert bundles (multi-sales)
            for bid, b_rows in bundles.items():
                names = [r["name"] for r in b_rows]
                # Creiamo il titolo accorciando se troppo lungo
                title = f"Vendita Multipla ({', '.join(sorted(set(names)))})"
                if len(title) > 60: title = title[:57] + "...)"
                
                p_qty = sum(r["quantity"] or 1 for r in b_rows)
                # Nel db, i prezzi sono unitari, quindi moltiplichiamo per qty
                p_purchased = sum(r["purchased_price"] * (r["quantity"] or 1) for r in b_rows)
                p_sold = sum((r["sold_price"] or 0) * (r["quantity"] or 1) for r in b_rows)
                p_fees = sum(r["fees"] * (r["quantity"] or 1) for r in b_rows)
                
                p_profit, p_roi = calculate_profit(p_purchased, p_sold, p_fees, 1)
                
                p_values = (
                    title,
                    "-",
                    p_qty,
                    money(p_purchased),
                    "-",
                    str(b_rows[0]["selling_place"]).strip() if b_rows[0]["selling_place"] else "",
                    money(p_sold),
                    money(p_fees),
                    money(p_profit),
                    f"{p_roi:.1f}%",
                    b_rows[0]["sold_date"]
                )
                parent_iid = f"bundle_{bid}"
                tree.insert("", "end", iid=parent_iid, values=p_values, tags=("stripe",) if len(tree.get_children()) % 2 else (), open=False)
                
                for r in b_rows:
                    qty = r["quantity"] or 1
                    c_values = (
                        f"  ↳ {r['name']}",
                        r["size"],
                        qty,
                        money(r["purchased_price"]),
                        str(r["purchased_place"]).strip() if r["purchased_place"] else "",
                        str(r["selling_place"]).strip() if r["selling_place"] else "",
                        "-", # Prezzo nascosto per i figli del bundle
                        "-",
                        "-",
                        "-",
                        r["sold_date"],
                    )
                    tree.insert(parent_iid, "end", iid=str(r["id"]), values=c_values)

            # Insert normal items
            for row in normal_rows:
                qty = row["quantity"] or 1
                sp = row["sold_price"] if row["sold_price"] is not None else row["selling_price"]
                sp = sp if sp is not None else 0
                profit, roi = calculate_profit(row["purchased_price"], sp, row["fees"], qty)

                values = (
                    row["name"],
                    row["size"],
                    qty,
                    money(row["purchased_price"]),
                    str(row["purchased_place"]).strip() if row["purchased_place"] else "",
                    str(row["selling_place"]).strip() if row["selling_place"] else "",
                    money(sp) if sp is not None else "-",
                    money(row["fees"]) if row["fees"] else "€ 0,00",
                    money(profit) if status_key in (STATUS_SOLD, STATUS_COMPLETED) else "-",
                    f"{roi:.1f}%" if status_key in (STATUS_SOLD, STATUS_COMPLETED) and row["purchased_price"] > 0 else "-",
                    row["sold_date"],
                )
                tree.insert("", "end", iid=str(row["id"]), values=values, tags=("stripe",) if len(tree.get_children()) % 2 else ())

            # Ripristina selezione se ancora esistente
            for s_id in selected:
                if tree.exists(s_id):
                    tree.selection_add(s_id)

        self.status_bar_var.set("Vista aggiornata")

    # --- KEYBOARD SELECTION METHODS ---
    def _get_visually_next(self, tree: ttk.Treeview, item: str) -> str:
        if tree.item(item, "open") and tree.get_children(item):
            return tree.get_children(item)[0]
        curr = item
        while curr:
            nxt = tree.next(curr)
            if nxt:
                return nxt
            curr = tree.parent(curr)
        return ""

    def _get_visually_prev(self, tree: ttk.Treeview, item: str) -> str:
        prv = tree.prev(item)
        if prv:
            curr = prv
            while tree.item(curr, "open") and tree.get_children(curr):
                curr = tree.get_children(curr)[-1]
            return curr
        else:
            return tree.parent(item)

    def _extend_selection(self, event, tree: ttk.Treeview, direction: int) -> str:
        focus = tree.focus()
        if not focus:
            return "break"
            
        target = self._get_visually_next(tree, focus) if direction == 1 else self._get_visually_prev(tree, focus)
            
        if target:
            tree.selection_add(target)
            tree.focus(target)
            tree.see(target)
            self._update_action_states()
            
        return "break"

    def _select_all(self, event, tree: ttk.Treeview) -> str:
        def get_all(parent=""):
            items = []
            for child in tree.get_children(parent):
                items.append(child)
                items.extend(get_all(child))
            return items
        
        all_items = get_all()
        if all_items:
            tree.selection_set(all_items)
            self._update_action_states()
        return "break"

    # --- DRAG AND DROP METHODS ---
    def _on_drag_start(self, event, tree):
        region = tree.identify("region", event.x, event.y)
        if region in ("cell", "tree"):
            item = tree.identify_row(event.y)
            if item in tree.selection():
                self._drag_data = {"x": event.x, "y": event.y, "tree": tree, "dragging": False, "window": None}
                return "break" # Evita che Tkinter deselezioni altri elementi se si sta per trascinare
        self._drag_data = None

    def _on_drag_motion(self, event, tree):
        if getattr(self, "_drag_data", None):
            dy = abs(event.y - self._drag_data["y"])
            dx = abs(event.x - self._drag_data["x"])
            if (dx > 5 or dy > 5) and not self._drag_data["dragging"]:
                self._drag_data["dragging"] = True
                tree.config(cursor="hand2")
                
                # Create ghost window
                count = len(tree.selection())
                win = tk.Toplevel(self)
                win.overrideredirect(True)
                win.attributes("-alpha", 0.85)
                # Ensure it floats above everything
                win.attributes("-topmost", True)
                
                lbl = tk.Label(
                    win, 
                    text=f"Spostando {count} element{'o' if count == 1 else 'i'}...", 
                    bg="#2563eb",
                    fg="white",
                    font=("Segoe UI", 10, "bold"),
                    padx=12, 
                    pady=8,
                    relief="raised"
                )
                lbl.pack()
                self._drag_data["window"] = win

            if self._drag_data["dragging"] and self._drag_data.get("window"):
                # Move window with cursor
                self._drag_data["window"].geometry(f"+{event.x_root + 15}+{event.y_root + 15}")

    def _on_drag_release(self, event, tree):
        if getattr(self, "_drag_data", None):
            # Destroy ghost window if exists
            if self._drag_data.get("window"):
                self._drag_data["window"].destroy()
                
            if self._drag_data.get("dragging"):
                tree.config(cursor="")
                x_root, y_root = event.x_root, event.y_root
                widget = self.winfo_containing(x_root, y_root)
                if widget and ("notebook" in str(widget).lower() or "tab" in str(widget).lower() or widget == self.notebook):
                    nb_x = x_root - self.notebook.winfo_rootx()
                    nb_y = y_root - self.notebook.winfo_rooty()
                    try:
                        tab_idx = self.notebook.tk.call(self.notebook._w, "identify", "tab", nb_x, nb_y)
                        if tab_idx != "":
                            tab_text = self.notebook.tab(int(tab_idx), "text")
                            if tab_text == "Vendite Attive":
                                self.after(50, self.move_selected_to_sold)
                    except Exception:
                        pass
            else:
                # Se era solo un clic su un elemento già selezionato, Tkinter non l'ha gestito (per via del break).
                # Ripristiniamo la selezione singola se non c'erano modificatori.
                if not (event.state & 0x0001 or event.state & 0x0004): # Shift o Control
                    item = tree.identify_row(event.y)
                    if item:
                        tree.selection_set(item)
            self._drag_data = None

    def refresh_totals(self) -> None:
        totals = self.db.totals()
        self.kpi_vars["stock_total"].set(money(totals["stock_total"]))
        self.kpi_vars["stock_count"].set(str(totals["stock_count"]))
        self.kpi_vars["sold_profit_active"].set(money(totals["sold_profit_active"]))
        self.kpi_vars["sold_profit_completed"].set(money(totals["sold_profit_completed"]))
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

            if target in self.status_tabs:
                self.notebook.select(self.status_tabs.index(target))

            tree = self.trees[target]
            if tree.exists(str(new_id)):
                tree.selection_set(str(new_id))
                tree.see(str(new_id))

            self.status_bar_var.set("Prodotto aggiunto con successo")

    def sort_tree(self, status: str, column: str) -> None:
        """Ordina la tabella selezionata localmente, mantenendo il tipo numerico."""
        tree = self.trees.get(status)
        if not tree:
            return
        previous = self.current_sort.get(status, ("", True))
        ascending = not previous[1] if previous[0] == column else True
        self.current_sort[status] = (column, ascending)
        items = [(tree.set(item, column), item) for item in tree.get_children("")]
        numeric_columns = {"quantity", "purchased_price", "sale_price", "fees", "profit", "roi"}
        if column in numeric_columns:
            def sort_value(item: tuple[str, str]) -> tuple[int, object]:
                raw = item[0].replace("€", "").replace(".", "").replace(",", ".").replace("%", "").strip()
                try:
                    return (0, float(raw))
                except ValueError:
                    return (1, 0)
        else:
            def sort_value(item: tuple[str, str]) -> tuple[int, object]:
                return (0, item[0].casefold())
        for _, item in sorted(items, key=sort_value, reverse=not ascending):
            tree.move(item, "", "end")

    def edit_selected(self) -> None:
        ids = self.selected_ids()
        if len(ids) != 1:
            return

        prod_id = ids[0]
        record = self.db.get(prod_id)
        if not record:
            self.refresh()
            return
            
        if record.get("is_completed"):
            messagebox.showinfo(
                "Azione non consentita", 
                "Questa vendita è stata segnata come Completata.\nNon è possibile modificarla. Serve solo come storico.", 
                parent=self
            )
            return
            
        if record.get("bundle_id"):
            messagebox.showinfo(
                "Azione non consentita", 
                "Questo prodotto fa parte di una Vendita Multipla.\nNon è possibile modificarlo singolarmente per non sfasare i totali della vendita in blocco.", 
                parent=self
            )
            return

        places = self.db.get_distinct_places()
        dialog = ProductDialog(self, record["status"], autocomplete_places=places, record=record)
        self.wait_window(dialog)

        if dialog.result:
            self.db.save(dialog.result, prod_id)
            target = dialog.result["status"]
            self.refresh()

            if target in self.status_tabs:
                self.notebook.select(self.status_tabs.index(target))

            tree = self.trees[target]
            if tree.exists(str(prod_id)):
                tree.selection_set(str(prod_id))
                tree.see(str(prod_id))

            self.status_bar_var.set("Prodotto modificato con successo")

    def _clone_record(self, record: dict, force_status: Optional[str] = None) -> None:
        record.pop("id", None)
        record["name"] = f"{record['name']} (Copia)"
        record["bundle_id"] = ""
        record["is_completed"] = 0
        if force_status:
            record["status"] = force_status
        self.db.save(record)

    def duplicate_selected(self) -> None:
        ids = self.selected_ids()
        if not ids:
            return
            
        duplicated = 0
        for prod_id in ids:
            record = self.db.get(prod_id)
            if record:
                self._clone_record(record)
                duplicated += 1
                
        if duplicated > 0:
            self.refresh()
            self.status_bar_var.set(f"Duplicati {duplicated} prodotti")

    def _copy_to_clipboard(self, event=None) -> str:
        ids = self.selected_ids()
        if not ids:
            return "break"
            
        self._clipboard_ids = ids
        
        # Copia anche come testo negli appunti di sistema
        tree = self.trees.get(self.current_status())
        if tree:
            lines = []
            for item in tree.selection():
                values = tree.item(item, "values")
                lines.append("\t".join(str(v) for v in values))
            if lines:
                self.clipboard_clear()
                self.clipboard_append("\n".join(lines))
                
        self.status_bar_var.set(f"Copiati {len(ids)} elementi negli appunti")
        return "break"

    def _paste_from_clipboard(self, event=None) -> str:
        if not getattr(self, "_clipboard_ids", None):
            return "break"
            
        pasted = 0
        current_tab = self.current_status()
        # Se incolliamo nella tab Pre-ordini o Magazzino, impostiamo lo stato in base alla tab
        force_status = current_tab if current_tab in (STATUS_STOCK, STATUS_PREORDER) else None
        
        for prod_id in self._clipboard_ids:
            record = self.db.get(prod_id)
            if record:
                self._clone_record(record, force_status)
                pasted += 1
                
        if pasted > 0:
            self.refresh()
            self.status_bar_var.set(f"Incollati {pasted} prodotti")
            
        return "break"

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

        for prod_id in ids:
            record = self.db.get(prod_id)
            if record and record.get("bundle_id"):
                messagebox.showinfo(
                    "Azione non consentita", 
                    "Uno o più prodotti selezionati fanno parte di una Vendita Multipla.\nNon puoi spostarli in Magazzino separatamente.\n\nSe vuoi annullare la vendita, elimina l'intera Vendita Multipla e ricrea i prodotti.", 
                    parent=self
                )
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

        if len(ids) == 1:
            prod_id = ids[0]
            record = self.db.get(prod_id)
            if not record: return
            
            # Forziamo lo status per far apparire i campi vendita
            record_dict = dict(record)
            record_dict["status"] = STATUS_SOLD
            
            places = self.db.get_distinct_places()
            dialog = ProductDialog(self, STATUS_SOLD, autocomplete_places=places, record=record_dict)
            self.wait_window(dialog)
            
            if dialog.result:
                self.db.save(dialog.result, prod_id)
                self.refresh()
                self.notebook.select(2)
                self.status_bar_var.set("Prodotto venduto con successo")
        else:
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
        products_data = self.db.all_products()
        if ids:
            products_data = [row for row in products_data if row["id"] in ids]
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
