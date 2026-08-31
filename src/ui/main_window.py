#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finestra principale dell'applicazione InventoryApp per Russo Stock Manager."""

import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional
import customtkinter as ctk

from ..config import APP_NAME, APP_VERSION, DB_PATH, DARK_THEME, STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK, STATUS_COMPLETED, PROJECT_DIR
from ..database import InventoryDatabase
from .dashboard_view import DashboardView
from .dialogs import BulkStatusDialog, ProductDialog
from .ai_dialog import AIDialog
from .theme import setup_app_theme
from ..utils import export_to_csv, money, parse_excel_file, parse_money, calculate_profit


class InventoryApp(ctk.CTk):
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

    TAB_NAMES = ["Magazzino", "Pre-ordini", "Vendite Attive", "Vendite Completate", "Dashboard & Grafici"]

    def __init__(self) -> None:
        super().__init__()
        self.db = InventoryDatabase()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1440x860")
        self.minsize(1080, 680)
        self.state("zoomed")

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

        self.tab_name_to_status = {
            "Magazzino": STATUS_STOCK,
            "Pre-ordini": STATUS_PREORDER,
            "Vendite Attive": STATUS_SOLD,
            "Vendite Completate": STATUS_COMPLETED,
        }
        self.status_to_tab_name = {v: k for k, v in self.tab_name_to_status.items()}

        try:
            import sys
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
        """Forza la titlebar di Windows 10/11 in modalita scura."""
        try:
            import ctypes
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(value), ctypes.sizeof(value))
        except Exception:
            pass

    def _build_ui(self) -> None:
        c = DARK_THEME

        self.configure(fg_color=DARK_THEME["bg_main"]); container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=12, pady=12)

        # 1. Header superiore
        header = ctk.CTkFrame(container, fg_color=c["bg_card"], corner_radius=10)
        header.pack(fill="x", pady=(0, 14))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", padx=16, pady=12)

        try:
            from PIL import Image
            import sys
            w_path = Path(getattr(sys, "_MEIPASS", PROJECT_DIR)) / "app_icon.ico"
            if not w_path.exists():
                w_path = PROJECT_DIR / "app_icon.ico"
            img = Image.open(w_path).resize((32, 32), Image.Resampling.LANCZOS)
            self._header_logo = ctk.CTkImage(light_image=img, dark_image=img, size=(32, 32))
            ctk.CTkLabel(title_box, image=self._header_logo, text="").pack(side="left", padx=(0, 10))
        except Exception:
            pass

        text_box = ctk.CTkFrame(title_box, fg_color="transparent")
        text_box.pack(side="left")
        ctk.CTkLabel(text_box, text=APP_NAME.upper(), font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ctk.CTkLabel(text_box, text="Gestione Magazzino, Pre-ordini, Vendite e Profitto Netto", font=("Segoe UI", 10), text_color=c["fg_muted"]).pack(anchor="w")

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right", padx=16, pady=12)
        ctk.CTkButton(actions, text="Importa Excel", command=self.import_excel, fg_color="#374151", hover_color="#4b5563").pack(side="left", padx=3)
        ctk.CTkButton(actions, text="Esporta CSV", command=self.export_csv, fg_color="#374151", hover_color="#4b5563").pack(side="left", padx=3)
        ctk.CTkButton(actions, text="Backup DB Sicuro", command=self.backup_database, fg_color="#374151", hover_color="#4b5563").pack(side="left", padx=3)
        ctk.CTkButton(actions, text="✨ AI", width=60, command=self.open_ai_insert).pack(side="left", padx=(8, 0))
        ctk.CTkButton(actions, text="+ Nuovo Prodotto", command=self.add_product).pack(side="left", padx=(4, 0))

        # 2. KPI Cards
        kpis = ctk.CTkFrame(container, fg_color="transparent")
        kpis.pack(fill="x", pady=(0, 14))
        self.kpi_vars: Dict[str, tk.StringVar] = {}

        cards = [
            ("stock_total", "STOCK TOTALE (\u20ac)", "#2563eb"),
            ("stock_count", "IN MAGAZZINO", "#3b82f6"),
            ("sold_profit_active", "PROFITTO VENDITE ATTIVE", "#10b981"),
            ("sold_profit_completed", "PROFITTO STORICO COMPLETATE", "#059669"),
            ("all_count", "PEZZI TOTALI GESTITI", "#7c3aed"),
        ]

        for index, (key, label, color) in enumerate(cards):
            kpis.columnconfigure(index, weight=1)
            card = ctk.CTkFrame(kpis, fg_color=c["bg_card"], corner_radius=10)
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 4, 0 if index == len(cards) - 1 else 4))
            var = tk.StringVar(value="-")
            self.kpi_vars[key] = var
            ctk.CTkFrame(card, fg_color=color, height=4, corner_radius=0).pack(fill="x")
            ctk.CTkLabel(card, text=label, font=("Segoe UI", 9, "bold"), text_color=c["fg_muted"]).pack(anchor="w", padx=16, pady=(6, 0))
            ctk.CTkLabel(card, textvariable=var, font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=16, pady=(2, 12))

        # 3. Toolbar Ricerca e Filtri
        toolbar_card = ctk.CTkFrame(container, fg_color=c["bg_card"], corner_radius=10, border_width=1, border_color=c["border"])
        toolbar_card.pack(fill="x", pady=(0, 10))

        r1 = ctk.CTkFrame(toolbar_card, fg_color="transparent")
        r1.pack(fill="x", padx=14, pady=(10, 0))

        ctk.CTkLabel(r1, text="Cerca:", font=("Segoe UI", 11, "bold")).pack(side="left")
        self.search_entry = ctk.CTkEntry(r1, textvariable=self.search_var, width=280)
        self.search_entry.pack(side="left", padx=(6, 8))
        self.search_var.trace_add("write", self._on_search_changed)

        self.btn_toggle_filters = ctk.CTkButton(r1, text="Filtri Avanzati \u25bc", command=self._toggle_filter_panel, fg_color="#374151", hover_color="#4b5563", width=130)
        self.btn_toggle_filters.pack(side="left", padx=4)
        ctk.CTkButton(r1, text="Azzera Filtri", command=self._reset_filters, fg_color="#374151", hover_color="#4b5563").pack(side="left", padx=4)
        ctk.CTkLabel(r1, text="Suggerimento: usa Ctrl+Click o Shift+Click per selezione multipla", font=("Segoe UI", 10), text_color=c["fg_muted"]).pack(side="right")

        self.filter_panel = ctk.CTkFrame(toolbar_card, fg_color="transparent")

        ctk.CTkLabel(self.filter_panel, text="Luogo Acquisto:", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", padx=(0, 4), pady=6)
        self.combo_filter_purchased = ctk.CTkComboBox(self.filter_panel, variable=self.filter_purchased_place_var, width=160, command=lambda v: self.refresh_tables())
        self.combo_filter_purchased.grid(row=0, column=1, sticky="w", padx=(0, 12))

        ctk.CTkLabel(self.filter_panel, text="Luogo Vendita:", font=("Segoe UI", 10)).grid(row=0, column=2, sticky="w", padx=(0, 4))
        self.combo_filter_selling = ctk.CTkComboBox(self.filter_panel, variable=self.filter_selling_place_var, width=160, command=lambda v: self.refresh_tables())
        self.combo_filter_selling.grid(row=0, column=3, sticky="w", padx=(0, 12))

        ctk.CTkLabel(self.filter_panel, text="Prezzo Min (\u20ac):", font=("Segoe UI", 10)).grid(row=0, column=4, sticky="w", padx=(0, 4))
        ctk.CTkEntry(self.filter_panel, textvariable=self.filter_min_price_var, width=90).grid(row=0, column=5, sticky="w", padx=(0, 12))
        self.filter_min_price_var.trace_add("write", lambda *_a: self.refresh_tables())

        ctk.CTkLabel(self.filter_panel, text="Prezzo Max (\u20ac):", font=("Segoe UI", 10)).grid(row=0, column=6, sticky="w", padx=(0, 4))
        ctk.CTkEntry(self.filter_panel, textvariable=self.filter_max_price_var, width=90).grid(row=0, column=7, sticky="w", padx=(0, 12))
        self.filter_max_price_var.trace_add("write", lambda *_a: self.refresh_tables())

        # 4. Status bar (CREATA PRIMA DEL NOTEBOOK)
        bottom = ctk.CTkFrame(container, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", pady=(8, 0))

        self.lbl_selected_info = ctk.CTkLabel(bottom, text="0 prodotti selezionati", font=("Segoe UI", 10), text_color=c["fg_muted"])
        self.lbl_selected_info.pack(side="left", padx=(0, 7))
        ctk.CTkLabel(bottom, textvariable=self.status_bar_var, font=("Segoe UI", 10), text_color=c["fg_muted"]).pack(side="right")

        # 5. CTkTabview (sostituisce ttk.Notebook)
        self.notebook = ctk.CTkTabview(container, command=self._on_tab_changed)
        self.notebook.pack(side="top", fill="both", expand=True)
        # Allinea a sinistra e aumenta il font per replicare il vecchio look
        self.notebook._segmented_button.grid(row=1, column=0, sticky="w", padx=10)
        self.notebook._segmented_button.configure(font=("Segoe UI", 13, "bold"))

        self._create_tab(STATUS_STOCK, "Magazzino")
        self._create_tab(STATUS_PREORDER, "Pre-ordini")
        self._create_tab(STATUS_SOLD, "Vendite Attive")
        self._create_tab(STATUS_COMPLETED, "Vendite Completate")

        dash_tab = self.notebook.add("Dashboard & Grafici")
        self.dashboard_view = DashboardView(dash_tab, self.db)
        self.dashboard_view.pack(fill="both", expand=True)

        self.context_menu = tk.Menu(self, tearoff=0, bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 10))

    def _create_tab(self, status: str, title: str) -> None:
        c = DARK_THEME
        frame = self.notebook.add(title)

        tree_frame = ctk.CTkFrame(frame, fg_color=c["bg_card"], corner_radius=0)
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
                stretch=True,
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

        tree.bind("<ButtonPress-1>", lambda e, t=tree: self._on_drag_start(e, t))
        tree.bind("<B1-Motion>", lambda e, t=tree: self._on_drag_motion(e, t))
        tree.bind("<ButtonRelease-1>", lambda e, t=tree: self._on_drag_release(e, t))

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
        item = tree.identify_row(event.y)
        if item:
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
            self.btn_toggle_filters.configure(text="Filtri Avanzati \u25bc")
        else:
            self.filter_panel.pack(fill="x", padx=14, pady=(0, 10))
            self.btn_toggle_filters.configure(text="Filtri Avanzati \u25b2")

    def _reset_filters(self) -> None:
        self.search_var.set("")
        self.filter_purchased_place_var.set("")
        self.filter_selling_place_var.set("")
        self.filter_min_price_var.set("")
        self.filter_max_price_var.set("")
        self.refresh()

    def current_status(self) -> Optional[str]:
        return self.tab_name_to_status.get(self.notebook.get())

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

    def _on_tab_changed(self, *_args) -> None:
        if self.notebook.get() == "Dashboard & Grafici":
            self.dashboard_view.refresh()
        self._update_action_states()

    def _switch_tab(self, direction: int) -> str:
        names = self.TAB_NAMES
        current = self.notebook.get()
        if current in names:
            next_idx = (names.index(current) + direction) % len(names)
            self.notebook.set(names[next_idx])
        return "break"

    def refresh(self) -> None:
        self._update_autocomplete_combos()
        self.refresh_tables()
        self.refresh_totals()
        self._update_action_states()

    def _update_autocomplete_combos(self) -> None:
        purchased, selling = self.db.get_distinct_places()
        self.combo_filter_purchased.configure(values=[""] + purchased)
        self.combo_filter_selling.configure(values=[""] + selling)

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

            for bid, b_rows in bundles.items():
                names = [r["name"] for r in b_rows]
                title = f"Vendita Multipla ({', '.join(sorted(set(names)))})"
                if len(title) > 60: title = title[:57] + "...)"
                p_qty = sum(r["quantity"] or 1 for r in b_rows)
                p_purchased = sum(r["purchased_price"] * (r["quantity"] or 1) for r in b_rows)
                p_sold = sum((r["sold_price"] or 0) * (r["quantity"] or 1) for r in b_rows)
                p_fees = sum(r["fees"] * (r["quantity"] or 1) for r in b_rows)
                p_profit, p_roi = calculate_profit(p_purchased, p_sold, p_fees, 1)
                p_values = (
                    title, "-", p_qty, money(p_purchased), "-",
                    str(b_rows[0]["selling_place"]).strip() if b_rows[0]["selling_place"] else "",
                    money(p_sold), money(p_fees), money(p_profit), f"{p_roi:.1f}%", b_rows[0]["sold_date"]
                )
                parent_iid = f"bundle_{bid}"
                tree.insert("", "end", iid=parent_iid, values=p_values, tags=("stripe",) if len(tree.get_children()) % 2 else (), open=False)
                for r in b_rows:
                    qty = r["quantity"] or 1
                    c_values = (
                        f"  ↳ {r['name']}", r["size"], qty, money(r["purchased_price"]),
                        str(r["purchased_place"]).strip() if r["purchased_place"] else "",
                        str(r["selling_place"]).strip() if r["selling_place"] else "",
                        "-", "-", "-", "-", r["sold_date"],
                    )
                    tree.insert(parent_iid, "end", iid=str(r["id"]), values=c_values)

            for row in normal_rows:
                qty = row["quantity"] or 1
                sp = row["sold_price"] if row["sold_price"] is not None else row["selling_price"]
                sp = sp if sp is not None else 0
                profit, roi = calculate_profit(row["purchased_price"], sp, row["fees"], qty)
                values = (
                    row["name"], row["size"], qty, money(row["purchased_price"]),
                    str(row["purchased_place"]).strip() if row["purchased_place"] else "",
                    str(row["selling_place"]).strip() if row["selling_place"] else "",
                    money(sp) if sp is not None else "-",
                    money(row["fees"]) if row["fees"] else "€ 0,00",
                    money(profit) if status_key in (STATUS_SOLD, STATUS_COMPLETED) else "-",
                    f"{roi:.1f}%" if status_key in (STATUS_SOLD, STATUS_COMPLETED) and row["purchased_price"] > 0 else "-",
                    row["sold_date"],
                )
                tree.insert("", "end", iid=str(row["id"]), values=values, tags=("stripe",) if len(tree.get_children()) % 2 else ())

            for s_id in selected:
                if tree.exists(s_id):
                    tree.selection_add(s_id)

        self.status_bar_var.set("Vista aggiornata")

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

    def _on_drag_start(self, event, tree):
        region = tree.identify("region", event.x, event.y)
        if region in ("cell", "tree"):
            item = tree.identify_row(event.y)
            if item in tree.selection():
                self._drag_data = {"x": event.x, "y": event.y, "tree": tree, "dragging": False, "window": None}
                return "break"
        self._drag_data = None

    def _on_drag_motion(self, event, tree):
        if getattr(self, "_drag_data", None):
            dy = abs(event.y - self._drag_data["y"])
            dx = abs(event.x - self._drag_data["x"])
            if (dx > 5 or dy > 5) and not self._drag_data["dragging"]:
                self._drag_data["dragging"] = True
                tree.config(cursor="hand2")
                count = len(tree.selection())
                win = tk.Toplevel(self)
                win.overrideredirect(True)
                win.attributes("-alpha", 0.85)
                win.attributes("-topmost", True)
                lbl = tk.Label(
                    win,
                    text=f"Spostando {count} element{'o' if count == 1 else 'i'}...",
                    bg="#2563eb", fg="white", font=("Segoe UI", 10, "bold"), padx=12, pady=8, relief="raised"
                )
                lbl.pack()
                self._drag_data["window"] = win
            if self._drag_data["dragging"] and self._drag_data.get("window"):
                self._drag_data["window"].geometry(f"+{event.x_root + 15}+{event.y_root + 15}")

    def _on_drag_release(self, event, tree):
        if getattr(self, "_drag_data", None):
            if self._drag_data.get("window"):
                self._drag_data["window"].destroy()
            if self._drag_data.get("dragging"):
                tree.config(cursor="")
                x_root, y_root = event.x_root, event.y_root
                try:
                    seg_btn = self.notebook._segmented_button
                    for name, btn in seg_btn._buttons_dict.items():
                        bx, by = btn.winfo_rootx(), btn.winfo_rooty()
                        bw, bh = btn.winfo_width(), btn.winfo_height()
                        if bx <= x_root <= bx + bw and by <= y_root <= by + bh:
                            if name == "Vendite Attive":
                                self.after(50, self.move_selected_to_sold)
                            break
                except Exception:
                    pass
            else:
                if not (event.state & 0x0001 or event.state & 0x0004):
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
        if count == 0:
            self.lbl_selected_info.configure(text="0 prodotti selezionati")
            return
        from decimal import Decimal
        total_cost = Decimal("0")
        for item_id in ids:
            prod = self.db.get(item_id)
            if prod:
                total_cost += prod["purchased_price"]
        avg_cost = total_cost / count
        from ..utils import money
        self.lbl_selected_info.configure(text=f"{count} selezionati | Totale: {money(total_cost)} | Media: {money(avg_cost)}")

    def open_ai_insert(self) -> None:
        dialog = AIDialog(self, self.db)
        self.wait_window(dialog)
        if not dialog.result:
            return
        places = self.db.get_distinct_places()
        cur_st = self.current_status() or STATUS_STOCK
        last_target = None
        for record in dialog.result:
            prod_dialog = ProductDialog(self, cur_st, autocomplete_places=places, record=record)
            self.wait_window(prod_dialog)
            if prod_dialog.result:
                new_id = self.db.save(prod_dialog.result)
                last_target = prod_dialog.result["status"]
        if last_target:
            self.refresh()
            if last_target in self.status_to_tab_name:
                self.notebook.set(self.status_to_tab_name[last_target])
            tree = self.trees[last_target]
            if tree.exists(str(new_id)):
                tree.selection_set(str(new_id))
                tree.see(str(new_id))
            n = len(dialog.result)
            self.status_bar_var.set(f"{n} prodott{'o' if n == 1 else 'i'} generati e aggiunti con successo")

    def add_product(self) -> None:
        cur_st = self.current_status() or STATUS_STOCK
        places = self.db.get_distinct_places()
        dialog = ProductDialog(self, cur_st, autocomplete_places=places)
        self.wait_window(dialog)
        if dialog.result:
            new_id = self.db.save(dialog.result)
            target = dialog.result["status"]
            self.refresh()
            if target in self.status_to_tab_name:
                self.notebook.set(self.status_to_tab_name[target])
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
            messagebox.showinfo("Azione non consentita", "Questa vendita è stata segnata come Completata.\nNon è possibile modificarla. Serve solo come storico.", parent=self)
            return
        if record.get("bundle_id"):
            messagebox.showinfo("Azione non consentita", "Questo prodotto fa parte di una Vendita Multipla.\nNon è possibile modificarlo singolarmente per non sfasare i totali della vendita in blocco.", parent=self)
            return
        places = self.db.get_distinct_places()
        dialog = ProductDialog(self, record["status"], autocomplete_places=places, record=record)
        self.wait_window(dialog)
        if dialog.result:
            self.db.save(dialog.result, prod_id)
            target = dialog.result["status"]
            self.refresh()
            if target in self.status_to_tab_name:
                self.notebook.set(self.status_to_tab_name[target])
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
                messagebox.showinfo("Azione non consentita", "Uno o più prodotti selezionati fanno parte di una Vendita Multipla.\nNon puoi spostarli in Magazzino separatamente.\n\nSe vuoi annullare la vendita, elimina l'intera Vendita Multipla e ricrea i prodotti.", parent=self)
                return
        if messagebox.askyesno("Conferma spostamento", f"Spostare {len(ids)} prodotti in 'In Magazzino'?", parent=self):
            self.db.update_status_many(ids, STATUS_STOCK)
            self.refresh()
            self.notebook.set("Magazzino")
            self.status_bar_var.set(f"{len(ids)} prodotti spostati in magazzino")

    def move_selected_to_sold(self) -> None:
        ids = self.selected_ids()
        if not ids:
            return
        if len(ids) == 1:
            prod_id = ids[0]
            record = self.db.get(prod_id)
            if not record: return
            record_dict = dict(record)
            record_dict["status"] = STATUS_SOLD
            places = self.db.get_distinct_places()
            dialog = ProductDialog(self, STATUS_SOLD, autocomplete_places=places, record=record_dict)
            self.wait_window(dialog)
            if dialog.result:
                self.db.save(dialog.result, prod_id)
                self.refresh()
                self.notebook.set("Vendite Attive")
                self.status_bar_var.set("Prodotto venduto con successo")
        else:
            dialog = BulkStatusDialog(self, len(ids), STATUS_SOLD)
            self.wait_window(dialog)
            if dialog.result is not None:
                self.db.update_status_many(ids, STATUS_SOLD, extra_data=dialog.result)
                self.refresh()
                self.notebook.set("Vendite Attive")
                self.status_bar_var.set(f"{len(ids)} prodotti contrassegnati come venduti")

    def export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self, title="Esporta prodotti in CSV", defaultextension=".csv",
            filetypes=[("File CSV", "*.csv")], initialfile=f"russo_stock_{datetime.now():%Y%m%d_%H%M}.csv",
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
            if not messagebox.askyesno("Conferma importazione", f"Trovati {len(records)} prodotti nell'Excel.\n(Tutti i prodotti sotto la sezione PREORDER verranno importati come Pre-ordini).\n\nAggiungere all'inventario?", parent=self):
                return
            inserted = self.db.insert_many(records)
            self.refresh()
            messagebox.showinfo("Importazione Completata", f"Importati con successo {inserted} prodotti!\n(Righe ignorate: {skipped})", parent=self)
            self.status_bar_var.set(f"Importati {inserted} prodotti da Excel")
        except Exception as exc:
            messagebox.showerror("Errore Importazione Excel", str(exc), parent=self)

    def backup_database(self) -> None:
        if not DB_PATH.exists():
            messagebox.showwarning("Database non trovato", "Il file del database non è ancora stato creato.", parent=self)
            return
        target = filedialog.asksaveasfilename(
            parent=self, title="Salva Backup Sicuro SQLite", defaultextension=".db",
            filetypes=[("Database SQLite", "*.db")], initialfile=f"russo_stock_backup_{datetime.now():%Y%m%d_%H%M}.db",
        )
        if target:
            try:
                self.db.backup_database_safe(Path(target))
                self.status_bar_var.set("Backup del database completato")
                messagebox.showinfo("Backup Completato in Sicurezza", f"Backup atomico SQLite creato con successo:\n{target}", parent=self)
            except Exception as exc:
                messagebox.showerror("Errore Backup", str(exc), parent=self)

    def _on_close(self) -> None:
        self.db.close()
        self.destroy()
