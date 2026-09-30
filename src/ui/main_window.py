#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finestra principale dell'applicazione InventoryApp per RSM."""

import threading
import tkinter as tk
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional
import customtkinter as ctk

from ..config import APP_NAME, APP_VERSION, DB_PATH, DARK_THEME, STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK, STATUS_COMPLETED, PROJECT_DIR, GITHUB_REPO
from ..database import InventoryDatabase
from .dashboard_view import DashboardView
from .dialogs import BulkStatusDialog, PartialStockMoveDialog, ProductDialog
from .ai_dialog import AIDialog
from .email_sync_dialog import EmailSyncDialog
from .theme import setup_app_theme
from ..utils import export_to_csv, money, read_spreadsheet_raw, parse_money, calculate_profit, center_window, apply_window_icon
from .excel_import_dialog import ExcelImportDialog, ExcelHintDialog
from ..ai_agent import parse_excel_with_ai
from ..ebay_api import open_search_in_browser
from .ebay_price_dialog import EbayPriceDialog
from ..updater import check_for_updates
from .update_dialog import UpdateDialog



class InventoryApp(ctk.CTk):
    """Finestra principale dell'applicazione di gestione inventario RSM."""

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
        center_window(self, 1440, 860)
        self.minsize(1080, 680)
        

        self.search_var = tk.StringVar()
        self.status_bar_var = tk.StringVar(value="Pronto")
        self.filter_purchased_place_var = tk.StringVar()
        self.filter_selling_place_var = tk.StringVar()
        self.filter_min_price_var = tk.StringVar()
        self.filter_max_price_var = tk.StringVar()

        self.sort_options = [
            "Data inserimento (Recenti)",
            "Data inserimento (Meno recenti)",
            "Nome (A-Z)",
            "Nome (Z-A)",
            "Prezzo acquisto (Min-Max)",
            "Prezzo acquisto (Max-Min)",
        ]
        self.sort_var = tk.StringVar(value=self.sort_options[0])

        self.current_sort: Dict[str, tuple[str, bool]] = {}
        self.trees: Dict[str, ttk.Treeview] = {}
        self._clipboard_ids: List[int] = []
        self._undo_stack: List[tuple[str, Any]] = []
        self._update_info: Optional[Dict[str, Any]] = None
        self.status_tabs = [STATUS_STOCK, STATUS_PREORDER, STATUS_SOLD, STATUS_COMPLETED]

        self.tab_name_to_status = {
            "Magazzino": STATUS_STOCK,
            "Pre-ordini": STATUS_PREORDER,
            "Vendite Attive": STATUS_SOLD,
            "Vendite Completate": STATUS_COMPLETED,
        }
        self.status_to_tab_name = {v: k for k, v in self.tab_name_to_status.items()}

        apply_window_icon(self)

        setup_app_theme(self)
        self._build_ui()
        self.refresh()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-n>", lambda _e: self.add_product())
        self.bind("<Control-f>", self._focus_search)
        self.bind("<Control-F>", self._focus_search)
        self.bind("<F5>", lambda _e: self.refresh())
        self.bind("<Control-z>", self.undo)
        self.bind("<Control-Z>", self.undo)
        self.bind("<KeyPress-e>", self._on_e_press)
        self.bind("<KeyPress-E>", self._on_e_press)
        self.bind("<Control-Tab>", lambda _e: self._switch_tab(1))
        self.bind("<Control-Shift-Tab>", lambda _e: self._switch_tab(-1))
        self.search_entry.focus_set()

        # Avvio del controllo silenzioso degli aggiornamenti in background
        self.after(1500, self._check_updates_background)

    def _build_ui(self) -> None:
        c = DARK_THEME

        self.configure(fg_color=DARK_THEME["bg_main"])
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=12, pady=12)

        # 1. Header superiore
        header = ctk.CTkFrame(container, fg_color=c["bg_card"], corner_radius=10, border_width=1, border_color=c["border"])
        header.pack(fill="x", pady=(0, 14))

        logo_box = ctk.CTkFrame(header, fg_color="transparent")
        logo_box.pack(side="left", padx=16, pady=8)

        try:
            from PIL import Image
            import sys
            logo_path = Path(getattr(sys, "_MEIPASS", PROJECT_DIR)) / "assets" / "app_logo.png"
            if not logo_path.exists():
                logo_path = PROJECT_DIR / "assets" / "app_logo.png"
            if not logo_path.exists():
                logo_path = PROJECT_DIR / "assets" / "app_icon.ico"
            img = Image.open(logo_path)
            self._header_logo = ctk.CTkImage(light_image=img, dark_image=img, size=(48, 48))
            ctk.CTkLabel(logo_box, image=self._header_logo, text="").pack(side="left")
        except Exception:
            pass

        # Pulsante badge aggiornamento disponibile (inizialmente nascosto)
        self.btn_update = ctk.CTkButton(
            logo_box,
            text="",
            command=self._open_updater,
            fg_color="#059669",
            hover_color="#047857",
            text_color="#ffffff",
            font=("Segoe UI", 12, "bold"),
            height=30,
            corner_radius=15,
        )

        # Icona per pulsante AI
        self._ai_btn_img = None
        try:
            ai_path = Path(getattr(sys, "_MEIPASS", PROJECT_DIR)) / "assets" / "ai_icon.png"
            if not ai_path.exists():
                ai_path = PROJECT_DIR / "assets" / "ai_icon.png"
            if ai_path.exists():
                ai_pil = Image.open(ai_path).convert("RGBA")
                self._ai_btn_img = ctk.CTkImage(light_image=ai_pil, dark_image=ai_pil, size=(18, 18))
        except Exception:
            pass

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right", padx=16, pady=12)
        ctk.CTkButton(actions, text="Importa Excel", command=self.import_excel, fg_color="#374151", hover_color="#4b5563").pack(side="left", padx=3)
        ctk.CTkButton(actions, text="Esporta CSV", command=self.export_csv, fg_color="#374151", hover_color="#4b5563").pack(side="left", padx=3)
        ctk.CTkButton(actions, text="Backup DB Sicuro", command=self.backup_database, fg_color="#374151", hover_color="#4b5563").pack(side="left", padx=3)
        ctk.CTkButton(actions, text="Sincronizza Email", command=self.open_email_sync).pack(side="left", padx=(8, 0))
        if self._ai_btn_img:
            ctk.CTkButton(actions, text="", image=self._ai_btn_img, width=42, command=self.open_ai_insert).pack(side="left", padx=(4, 0))
        else:
            ctk.CTkButton(actions, text="AI", width=60, command=self.open_ai_insert).pack(side="left", padx=(4, 0))
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
            ctk.CTkLabel(card, text=label, font=("Segoe UI", 11, "bold"), text_color=c["fg_muted"]).pack(anchor="w", padx=16, pady=(6, 0))
            ctk.CTkLabel(card, textvariable=var, font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=16, pady=(2, 12))

        # 3. Toolbar Ricerca e Filtri (Perfettamente centrata)
        toolbar_card = ctk.CTkFrame(container, fg_color=c["bg_card"], corner_radius=10, border_width=1, border_color=c["border"])
        toolbar_card.pack(fill="x", pady=(0, 10))

        r1 = ctk.CTkFrame(toolbar_card, fg_color="transparent")
        r1.pack(fill="x", padx=14, pady=10)

        search_center_box = ctk.CTkFrame(r1, fg_color="transparent")
        search_center_box.pack(anchor="center")

        ctk.CTkLabel(search_center_box, text="Cerca:", font=("Segoe UI", 12, "bold")).pack(side="left", padx=(0, 8))
        self.search_entry = ctk.CTkEntry(search_center_box, textvariable=self.search_var, width=320, font=("Segoe UI", 12))
        self.search_entry.pack(side="left", padx=(0, 10))
        self.search_var.trace_add("write", self._on_search_changed)

        self.btn_toggle_filters = ctk.CTkButton(search_center_box, text="Filtri Avanzati \u25bc", command=self._toggle_filter_panel, fg_color="#374151", hover_color="#4b5563", width=130, font=("Segoe UI", 12))
        self.btn_toggle_filters.pack(side="left", padx=(0, 6))
        ctk.CTkButton(search_center_box, text="Azzera Filtri", command=self._reset_filters, fg_color="#374151", hover_color="#4b5563", width=100, font=("Segoe UI", 12)).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(search_center_box, text="Ordina:", font=("Segoe UI", 12, "bold")).pack(side="left", padx=(0, 6))
        self.sort_combo = ctk.CTkOptionMenu(
            search_center_box,
            variable=self.sort_var,
            values=self.sort_options,
            width=225,
            font=("Segoe UI", 12),
            fg_color="#374151",
            button_color="#4b5563",
            button_hover_color="#64748b",
            command=lambda _v: self.refresh_tables(),
        )
        self.sort_combo.pack(side="left")

        self.filter_panel = ctk.CTkFrame(toolbar_card, fg_color="transparent")

        filter_center_box = ctk.CTkFrame(self.filter_panel, fg_color="transparent")
        filter_center_box.pack(anchor="center")

        ctk.CTkLabel(filter_center_box, text="Luogo Acquisto:", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 4), pady=6)
        self.combo_filter_purchased = ctk.CTkComboBox(filter_center_box, variable=self.filter_purchased_place_var, width=160, font=("Segoe UI", 12), command=lambda v: self.refresh_tables())
        self.combo_filter_purchased.grid(row=0, column=1, sticky="w", padx=(0, 14))

        ctk.CTkLabel(filter_center_box, text="Luogo Vendita:", font=("Segoe UI", 11, "bold")).grid(row=0, column=2, sticky="w", padx=(0, 4))
        self.combo_filter_selling = ctk.CTkComboBox(filter_center_box, variable=self.filter_selling_place_var, width=160, font=("Segoe UI", 12), command=lambda v: self.refresh_tables())
        self.combo_filter_selling.grid(row=0, column=3, sticky="w", padx=(0, 14))

        ctk.CTkLabel(filter_center_box, text="Prezzo Min (\u20ac):", font=("Segoe UI", 11, "bold")).grid(row=0, column=4, sticky="w", padx=(0, 4))
        ctk.CTkEntry(filter_center_box, textvariable=self.filter_min_price_var, width=90, font=("Segoe UI", 12)).grid(row=0, column=5, sticky="w", padx=(0, 14))
        self.filter_min_price_var.trace_add("write", lambda *_a: self.refresh_tables())

        ctk.CTkLabel(filter_center_box, text="Prezzo Max (\u20ac):", font=("Segoe UI", 11, "bold")).grid(row=0, column=6, sticky="w", padx=(0, 4))
        ctk.CTkEntry(filter_center_box, textvariable=self.filter_max_price_var, width=90, font=("Segoe UI", 12)).grid(row=0, column=7, sticky="w", padx=(0, 14))
        self.filter_max_price_var.trace_add("write", lambda *_a: self.refresh_tables())

        # 4. Status bar (CREATA PRIMA DEL NOTEBOOK)
        bottom = ctk.CTkFrame(container, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", pady=(8, 0))

        self.lbl_selected_info = ctk.CTkLabel(bottom, text="0 prodotti selezionati", font=("Segoe UI", 11), text_color=c["fg_muted"])
        self.lbl_selected_info.pack(side="left", padx=(0, 7))
        ctk.CTkLabel(bottom, textvariable=self.status_bar_var, font=("Segoe UI", 11), text_color=c["fg_muted"]).pack(side="right")

        # 5. Barra di Navigazione Pillole a Sinistra (Senza Emoji, Font più grande e chiaro)
        self.nav_bar = ctk.CTkFrame(container, fg_color="transparent")
        self.nav_bar.pack(side="top", fill="x", pady=(0, 10))

        self.tab_container = ctk.CTkFrame(container, fg_color=c["bg_card"], corner_radius=10, border_width=1, border_color=c["border"])
        self.tab_container.pack(side="top", fill="both", expand=True)

        self.tab_frames: Dict[str, ctk.CTkFrame] = {}
        self.tab_buttons: Dict[str, ctk.CTkButton] = {}
        self.current_tab_name = "Magazzino"

        tabs_info = [
            ("Magazzino", "Magazzino", STATUS_STOCK),
            ("Pre-ordini", "Pre-ordini", STATUS_PREORDER),
            ("Vendite Attive", "Vendite Attive", STATUS_SOLD),
            ("Vendite Completate", "Vendite Completate", STATUS_COMPLETED),
            ("Dashboard & Grafici", "Dashboard & Grafici", None),
        ]

        for key, label, status in tabs_info:
            frame = ctk.CTkFrame(self.tab_container, fg_color="transparent")
            self.tab_frames[key] = frame

            btn = ctk.CTkButton(
                self.nav_bar,
                text=label,
                font=("Segoe UI", 13, "bold"),
                height=36,
                corner_radius=8,
                fg_color="#2563eb" if key == "Magazzino" else "transparent",
                text_color="#ffffff" if key == "Magazzino" else "#e2e8f0",
                hover_color="#1d4ed8" if key == "Magazzino" else "#1e293b",
                command=lambda k=key: self.set_tab(k),
            )
            btn.pack(side="left", padx=(0, 6))
            self.tab_buttons[key] = btn

            if status is not None:
                self._create_tree_in_frame(status, frame)
            else:
                self.dashboard_view = DashboardView(frame, self.db)
                self.dashboard_view.pack(fill="both", expand=True)

        class _NotebookAdapter:
            def __init__(self, app):
                self._app = app
            def get(self) -> str:
                return self._app.current_tab_name
            def set(self, name: str) -> None:
                self._app.set_tab(name)

        self.notebook = _NotebookAdapter(self)
        self.set_tab("Magazzino")

        self.context_menu = tk.Menu(self, tearoff=0, bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 10))

    def set_tab(self, name: str) -> None:
        if name not in self.tab_frames:
            return
        self.current_tab_name = name
        c = DARK_THEME

        for key, frame in self.tab_frames.items():
            if key == name:
                frame.pack(fill="both", expand=True, padx=2, pady=2)
            else:
                frame.pack_forget()

        for key, btn in self.tab_buttons.items():
            if key == name:
                btn.configure(fg_color="#2563eb", text_color="#ffffff", hover_color="#1d4ed8")
            else:
                btn.configure(fg_color="transparent", text_color="#e2e8f0", hover_color="#1e293b")

        if name == "Dashboard & Grafici" and hasattr(self, "dashboard_view"):
            self.dashboard_view.refresh()

        self._update_action_states()

    def _create_tree_in_frame(self, status: str, frame: ctk.CTkFrame) -> None:
        c = DARK_THEME

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

        yscroll = ctk.CTkScrollbar(tree_frame, orientation="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)

        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns", padx=(2, 0))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        tree.bind("<Double-1>", lambda e, t=tree: self._on_tree_double_click(e, t))
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
        tree.bind("<Control-f>", self._focus_search)
        tree.bind("<Control-F>", self._focus_search)

        self.trees[status] = tree

    def _on_right_click(self, event: tk.Event, tree: ttk.Treeview) -> None:
        item = tree.identify_row(event.y)
        if item:
            if item not in tree.selection():
                tree.selection_set(item)
            tree.focus(item)
            tree.focus_set()
            self._update_action_states()

            self.context_menu.delete(0, "end")
            st = self.current_status()
            if st != STATUS_COMPLETED:
                self.context_menu.add_command(label="Modifica", command=self.edit_selected)
                self.context_menu.add_command(label="Duplica", command=self.duplicate_selected)

            if st in (STATUS_STOCK, STATUS_PREORDER):
                self.context_menu.add_separator()
                self.context_menu.add_command(label="Metti in vendita", command=self.move_selected_to_sold)

            if st == STATUS_PREORDER:
                self.context_menu.add_command(label="Conferma in magazzino", command=self.move_selected_to_stock)

            if st == STATUS_SOLD:
                self.context_menu.add_separator()
                self.context_menu.add_command(label="Completa Vendita", command=self.complete_selected_sales)

            if st in (STATUS_STOCK, STATUS_PREORDER):
                self.context_menu.add_separator()
                self.context_menu.add_command(label="Cerca su eBay", command=self._search_selected_on_ebay)
                self.context_menu.add_command(label="Prezzo Medio eBay", command=self._show_ebay_price_dialog)
            self.context_menu.add_separator()
            self.context_menu.add_command(label="Elimina", command=self.delete_selected)

            self.context_menu.post(event.x_root, event.y_root)

    def _search_selected_on_ebay(self) -> None:
        """Apre nel browser predefinito una scheda eBay per ogni prodotto selezionato."""
        ids = self.selected_ids()
        if not ids:
            return
        opened = 0
        for prod_id in ids:
            record = self.db.get(prod_id)
            if not record:
                continue
            name = record.get("name", "").strip()
            if not name:
                continue
            size = record.get("size", "").strip()
            # La taglia "UNI" indica taglia unica: non è un filtro utile su eBay.
            effective_size = "" if size.upper() == "UNI" else size
            open_search_in_browser(name, effective_size)
            opened += 1
        if opened:
            self.status_bar_var.set(f"Ricerca eBay aperta per {opened} prodott{'o' if opened == 1 else 'i'}")
        else:
            self.status_bar_var.set("Impossibile cercare su eBay: nessun prodotto valido selezionato")

    def _show_ebay_price_dialog(self) -> None:
        """Apre il dialog con i prezzi di mercato eBay per ciascun prodotto selezionato, in sequenza."""
        ids = self.selected_ids()
        if not ids:
            return

        client_id = self.db.get_setting("ebay_client_id", "")
        client_secret = self.db.get_setting("ebay_client_secret", "")
        if not client_id or not client_secret:
            messagebox.showwarning(
                "Credenziali eBay mancanti",
                "Inserisci 'ebay_client_id' e 'ebay_client_secret' nel file config.json "
                "per usare la funzione Prezzo Medio eBay.",
                parent=self,
            )
            return

        applied_old_records = []
        applied_count = 0

        for prod_id in ids:
            record = self.db.get(prod_id)
            if not record:
                continue
            name = record.get("name", "").strip()
            if not name:
                continue
            size = record.get("size", "").strip()

            def make_apply_callback(pid: int, old_rec: dict):
                def on_apply(avg_price: Decimal) -> None:
                    nonlocal applied_count
                    updated = dict(old_rec)
                    updated["selling_price"] = avg_price
                    self.db.save(updated, pid)
                    applied_old_records.append(old_rec)
                    applied_count += 1
                return on_apply

            dialog = EbayPriceDialog(
                self,
                product_name=name,
                product_size=size,
                client_id=client_id,
                client_secret=client_secret,
                on_apply_price=make_apply_callback(prod_id, dict(record)),
            )
            self.wait_window(dialog)

        if applied_old_records:
            self.refresh()
            self._push_undo(
                f"Applicato prezzo medio eBay a {applied_count} prodotti",
                lambda recs=applied_old_records: self._undo_update(recs),
            )
            self.status_bar_var.set(
                f"Prezzo stimato aggiornato per {applied_count} prodott{'o' if applied_count == 1 else 'i'} (media eBay)"
            )

    def complete_selected_sales(self) -> None:
        ids = self.selected_ids()
        if not ids: return
        old_records = [dict(self.db.get(i)) for i in ids if self.db.get(i)]
        with self.db.connection:
            self.db.connection.execute(f"UPDATE products SET is_completed = 1 WHERE id IN ({','.join('?'*len(ids))})", ids)
        self.refresh()
        if old_records:
            self._push_undo(f"Completate {len(ids)} vendite", lambda recs=old_records: self._undo_update(recs))
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
        if hasattr(self, "sort_var") and hasattr(self, "sort_options"):
            self.sort_var.set(self.sort_options[0])
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
        names = list(self.tab_frames.keys())
        current = self.notebook.get()
        if current in names:
            next_idx = (names.index(current) + direction) % len(names)
            self.set_tab(names[next_idx])
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
                p_sold = sum((r["sold_price"] or 0) for r in b_rows)
                p_fees = sum((r["fees"] or Decimal("0")) for r in b_rows)
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

            # Ordinamento dinamico dei prodotti
            sort_mode = getattr(self, "sort_var", None).get() if hasattr(self, "sort_var") else ""

            if sort_mode == "Data inserimento (Recenti)":
                normal_rows.sort(key=lambda r: r.get("id", 0), reverse=True)
            elif sort_mode == "Data inserimento (Meno recenti)":
                normal_rows.sort(key=lambda r: r.get("id", 0))
            elif sort_mode == "Nome (A-Z)":
                normal_rows.sort(key=lambda r: str(r.get("name", "")).casefold())
            elif sort_mode == "Nome (Z-A)":
                normal_rows.sort(key=lambda r: str(r.get("name", "")).casefold(), reverse=True)
            elif sort_mode == "Prezzo acquisto (Min-Max)":
                normal_rows.sort(key=lambda r: r.get("purchased_price", Decimal("0")) or Decimal("0"))
            elif sort_mode == "Prezzo acquisto (Max-Min)":
                normal_rows.sort(key=lambda r: r.get("purchased_price", Decimal("0")) or Decimal("0"), reverse=True)

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

            restored = False
            for s_id in selected:
                if tree.exists(s_id):
                    tree.selection_add(s_id)
                    if not restored:
                        tree.focus(s_id)
                        restored = True

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
                    for name, btn in self.tab_buttons.items():
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
        total_cost = Decimal("0")
        total_qty = 0
        for item_id in ids:
            prod = self.db.get(item_id)
            if prod:
                qty = prod.get("quantity", 1) or 1
                total_cost += prod["purchased_price"] * qty
                total_qty += qty
        avg_cost = total_cost / total_qty if total_qty else Decimal("0")
        self.lbl_selected_info.configure(text=f"{count} selezionati | Totale: {money(total_cost)} | Media: {money(avg_cost)}")

    def open_email_sync(self) -> None:
        dialog = EmailSyncDialog(self, self.db, on_success_callback=self._on_email_sync_success)
        self.wait_window(dialog)

    def _on_email_sync_success(self) -> None:
        self.refresh()
        self.set_tab("Pre-ordini")
        self.status_bar_var.set("Pre-ordini importati con successo dalle email!")

    def open_ai_insert(self) -> None:
        dialog = AIDialog(self, self.db)
        self.wait_window(dialog)
        if not dialog.result:
            return
        places = self.db.get_distinct_places()
        cur_st = self.current_status() or STATUS_STOCK
        last_target = None
        created_ids = []
        for record in dialog.result:
            prod_dialog = ProductDialog(self, cur_st, autocomplete_places=places, record=record)
            self.wait_window(prod_dialog)
            if prod_dialog.result:
                new_id = self.db.save(prod_dialog.result)
                created_ids.append(new_id)
                last_target = prod_dialog.result["status"]
        if created_ids and last_target:
            self.refresh()
            if last_target in self.status_to_tab_name:
                self.notebook.set(self.status_to_tab_name[last_target])
            self._focus_tree_item(last_target, str(created_ids[-1]))
            self._push_undo(f"Aggiunti {len(created_ids)} prodotti AI", lambda nids=created_ids: self._undo_insert(nids))
            n = len(created_ids)
            self.status_bar_var.set(f"{n} prodott{'o aggiunto' if n == 1 else 'i aggiunti'} con successo")

    def _focus_tree_item(self, status: str, item_id: str) -> None:
        """Seleziona un elemento nella tabella, posiziona il cursore di focus e assegna il focus da tastiera."""
        if not status or status not in self.trees:
            return
        tree = self.trees[status]
        if tree.exists(item_id):
            tree.selection_set(item_id)
            tree.focus(item_id)
            tree.see(item_id)
            tree.focus_set()
            # Assicura il focus widget e focus item anche dopo che il window manager ha chiuso la finestra modale
            self.after(30, lambda: (
                tree.focus(item_id) if tree.exists(item_id) else None,
                tree.focus_set()
            ))

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
            self._focus_tree_item(target, str(new_id))
            self._push_undo(f"Aggiunto '{dialog.result.get('name')}'", lambda nids=[new_id]: self._undo_insert(nids))
            self.status_bar_var.set("Prodotto aggiunto con successo")
        else:
            cur_st = self.current_status()
            if cur_st and cur_st in self.trees:
                self.trees[cur_st].focus_set()

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

    def _focus_search(self, event=None) -> str:
        """Porta il focus sulla barra di ricerca e seleziona il testo esistente per cercare subito."""
        self.search_entry.focus_set()
        try:
            if hasattr(self.search_entry, "_entry"):
                self.search_entry._entry.select_range(0, "end")
                self.search_entry._entry.icursor("end")
            else:
                self.search_entry.select_range(0, "end")
        except Exception:
            pass
        return "break"

    def _on_e_press(self, event=None) -> Optional[str]:
        focused = self.focus_get()
        if focused and (
            isinstance(focused, (tk.Entry, ttk.Entry))
            or "entry" in str(focused).lower()
            or "textbox" in str(focused).lower()
            or "text" in str(focused).lower()
        ):
            return None
        self.edit_selected()
        return "break"

    def _on_tree_double_click(self, event: Any, tree: ttk.Treeview) -> None:
        """
        Gestisce il doppio click sulla tabella:
        - Su una riga bundle padre: espande il nodo mostrando i prodotti figli.
        - Su una riga normale o figlio di bundle: apre il dialog di modifica.
        """
        item = tree.identify_row(event.y)
        if not item:
            return
        tree.focus(item)
        tree.focus_set()
        if str(item).startswith("bundle_"):
            # Toggle apri/chiudi — return "break" impedisce a Tkinter di eseguire
            # un secondo toggle nativo che annullerebbe il nostro
            tree.item(item, open=not tree.item(item, "open"))
            return "break"
        self.edit_selected()

    def edit_selected(self) -> None:
        ids = self.selected_ids()
        if not ids:
            return

        valid_records = []
        for prod_id in ids:
            record = self.db.get(prod_id)
            if not record:
                continue
            if record.get("is_completed"):
                messagebox.showinfo(
                    "Azione non consentita",
                    f"'{record.get('name', 'Il prodotto')}' è una vendita Completata.\nNon è possibile modificarla (serve solo come storico).",
                    parent=self
                )
                continue
            if record.get("bundle_id"):
                messagebox.showinfo(
                    "Azione non consentita",
                    f"'{record.get('name', 'Il prodotto')}' fa parte di una Vendita Multipla.\nNon è possibile modificarlo singolarmente.",
                    parent=self
                )
                continue
            valid_records.append((prod_id, dict(record)))

        if not valid_records:
            return

        places = self.db.get_distinct_places()
        modified_old_records = []
        last_target = None
        last_id = None

        for prod_id, record in valid_records:
            dialog = ProductDialog(self, record["status"], autocomplete_places=places, record=record)
            self.wait_window(dialog)
            if dialog.result:
                self.db.save(dialog.result, prod_id)
                modified_old_records.append(record)
                last_target = dialog.result["status"]
                last_id = prod_id

        if modified_old_records:
            self.refresh()
            if last_target and last_target in self.status_to_tab_name:
                self.notebook.set(self.status_to_tab_name[last_target])
            if last_id and last_target:
                self._focus_tree_item(last_target, str(last_id))
            self._push_undo(
                f"Modificati {len(modified_old_records)} prodotti",
                lambda recs=modified_old_records: self._undo_update(recs)
            )
            count = len(modified_old_records)
            self.status_bar_var.set(f"{count} prodott{'o modificato' if count == 1 else 'i modificati'} con successo")
        else:
            cur_st = self.current_status()
            if cur_st and cur_st in self.trees:
                tree = self.trees[cur_st]
                sel = tree.selection()
                if sel:
                    self._focus_tree_item(cur_st, str(sel[0]))
                else:
                    tree.focus_set()


    def _clone_record(self, record: dict, force_status: Optional[str] = None) -> int:
        record_copy = dict(record)
        record_copy.pop("id", None)
        record_copy["name"] = f"{record_copy['name']} (Copia)"
        record_copy["bundle_id"] = ""
        record_copy["is_completed"] = 0
        if force_status:
            record_copy["status"] = force_status
        return self.db.save(record_copy)

    def duplicate_selected(self) -> None:
        ids = self.selected_ids()
        if not ids:
            return
        duplicated_ids = []
        for prod_id in ids:
            record = self.db.get(prod_id)
            if record:
                new_id = self._clone_record(record)
                if new_id:
                    duplicated_ids.append(new_id)
        if duplicated_ids:
            self.refresh()
            self._push_undo(f"Duplicati {len(duplicated_ids)} prodotti", lambda nids=duplicated_ids: self._undo_insert(nids))
            self.status_bar_var.set(f"Duplicati {len(duplicated_ids)} prodotti")

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
        pasted_ids = []
        current_tab = self.current_status()
        force_status = current_tab if current_tab in (STATUS_STOCK, STATUS_PREORDER) else None
        for prod_id in self._clipboard_ids:
            record = self.db.get(prod_id)
            if record:
                new_id = self._clone_record(record, force_status)
                if new_id:
                    pasted_ids.append(new_id)
        if pasted_ids:
            self.refresh()
            self._push_undo(f"Incollati {len(pasted_ids)} prodotti", lambda nids=pasted_ids: self._undo_insert(nids))
            self.status_bar_var.set(f"Incollati {len(pasted_ids)} prodotti")
        return "break"

    def delete_selected(self) -> None:
        ids = self.selected_ids()
        if not ids:
            return
        count = len(ids)
        msg = f"Eliminare definitivamente {count} prodotti selezionati?\nQuesta operazione non può essere annullata." if count > 1 else "Eliminare definitivamente il prodotto selezionato?"
        if messagebox.askyesno("Conferma eliminazione", msg, parent=self):
            old_records = [dict(self.db.get(i)) for i in ids if self.db.get(i)]
            deleted_count = self.db.delete_many(ids)
            if deleted_count > 0:
                self.refresh()
                if old_records:
                    self._push_undo(f"Eliminati {deleted_count} prodotti", lambda recs=old_records: self._undo_delete(recs))
                self.status_bar_var.set(f"Eliminati {deleted_count} prodotti")

    def move_selected_to_stock(self) -> None:
        ids = self.selected_ids()
        if not ids:
            return

        # I prodotti parte di una Vendita Multipla non possono essere spostati singolarmente
        for prod_id in ids:
            record = self.db.get(prod_id)
            if record and record.get("bundle_id"):
                messagebox.showinfo(
                    "Azione non consentita",
                    "Uno o più prodotti selezionati fanno parte di una Vendita Multipla.\n"
                    "Non puoi spostarli in Magazzino separatamente.\n\n"
                    "Se vuoi annullare la vendita, elimina l'intera Vendita Multipla e ricrea i prodotti.",
                    parent=self,
                )
                return

        if len(ids) == 1:
            # --- Singolo prodotto ---
            prod_id = ids[0]
            record = self.db.get(prod_id)
            if not record:
                return
            original_qty = record.get("quantity", 1) or 1
            old_records = [dict(record)]

            if original_qty > 1:
                # Quantità multipla: apre la dialog per scegliere quante unità spostare
                dialog = PartialStockMoveDialog(self, record.get("name", ""), original_qty)
                self.wait_window(dialog)
                if dialog.result is None:
                    return
                chosen_qty = dialog.result
            else:
                # Quantità 1: nessuna scelta possibile, sposta direttamente
                chosen_qty = 1

            # Cerca se esiste già un record compatibile in magazzino (da fondere)
            match = self.db.find_matching_stock_record(record, exclude_id=prod_id)

            if chosen_qty < original_qty:
                # --- Spostamento parziale ---
                remaining = original_qty - chosen_qty

                if match:
                    # Fonde con il record esistente: incrementa la quantità e aggiorna l'originale
                    old_match_qty = match.get("quantity", 1) or 1
                    self.db.merge_into_stock_record(match["id"], chosen_qty)
                    updated_original = dict(record)
                    updated_original["quantity"] = remaining
                    self.db.save(updated_original, prod_id)
                    self._push_undo(
                        "Spostamento parziale in magazzino (merge)",
                        lambda recs=old_records, mid=match["id"], mq=old_match_qty: (
                            self._undo_update(recs),
                            self.db.merge_into_stock_record(mid, -(chosen_qty)),
                            self.refresh(),
                        ),
                    )
                    self.status_bar_var.set(
                        f"Aggiunti {chosen_qty} pz al record esistente in magazzino"
                        f" — restano {remaining} pz in pre-ordine"
                    )
                else:
                    # Nessun record compatibile: crea una nuova riga in magazzino
                    new_record = dict(record)
                    new_record.pop("id", None)
                    new_record["quantity"] = chosen_qty
                    new_record["status"] = STATUS_STOCK
                    new_record["sold_price"] = None
                    new_record["sold_date"] = ""
                    new_record["fees"] = Decimal("0")
                    new_record["release_date"] = ""
                    new_record["bundle_id"] = ""
                    new_id = self.db.save(new_record)
                    updated_original = dict(record)
                    updated_original["quantity"] = remaining
                    self.db.save(updated_original, prod_id)
                    undo_ids = [new_id] if new_id else []
                    self._push_undo(
                        "Spostamento parziale in magazzino",
                        lambda recs=old_records, nids=undo_ids: (
                            self._undo_update(recs),
                            self.db.delete_many(nids) if nids else None,
                            self.refresh(),
                        ),
                    )
                    self.status_bar_var.set(
                        f"Spostati {chosen_qty} pz in magazzino"
                        f" — restano {remaining} pz in pre-ordine"
                    )
            else:
                # --- Spostamento totale ---
                if match:
                    # Fonde con il record esistente: incrementa e rimuove l'originale
                    self.db.merge_into_stock_record(match["id"], chosen_qty)
                    self.db.delete(prod_id)
                    self._push_undo(
                        "Spostamento in magazzino (merge)",
                        lambda recs=old_records, mid=match["id"], cq=chosen_qty: (
                            self.db.merge_into_stock_record(mid, -cq),
                            self._undo_delete(recs),
                            self.refresh(),
                        ),
                    )
                    self.status_bar_var.set("Prodotto aggiunto al record esistente in magazzino")
                else:
                    # Nessun record compatibile: semplice cambio di stato
                    self.db.update_status_many([prod_id], STATUS_STOCK)
                    self._push_undo(
                        "Spostamento in magazzino",
                        lambda recs=old_records: self._undo_update(recs),
                    )
                    self.status_bar_var.set("Prodotto spostato in magazzino")

            self.refresh()
            self.notebook.set("Magazzino")

        else:
            # --- Selezione multipla: conferma e sposta tutto in blocco ---
            if messagebox.askyesno(
                "Conferma spostamento",
                f"Spostare {len(ids)} prodotti in 'In Magazzino'?",
                parent=self,
            ):
                old_records = [dict(self.db.get(i)) for i in ids if self.db.get(i)]
                self.db.update_status_many(ids, STATUS_STOCK)
                self.refresh()
                self.notebook.set("Magazzino")
                if old_records:
                    self._push_undo(
                        "Spostamento in magazzino",
                        lambda recs=old_records: self._undo_update(recs),
                    )
                self.status_bar_var.set(f"{len(ids)} prodotti spostati in magazzino")


    def move_selected_to_sold(self) -> None:
        ids = self.selected_ids()
        if not ids:
            return
        old_records = [dict(self.db.get(i)) for i in ids if self.db.get(i)]
        if len(ids) == 1:
            prod_id = ids[0]
            record = self.db.get(prod_id)
            if not record:
                return
            original_qty = record.get("quantity", 1) or 1
            record_dict = dict(record)
            record_dict["status"] = STATUS_SOLD
            places = self.db.get_distinct_places()
            dialog = ProductDialog(self, STATUS_SOLD, autocomplete_places=places, record=record_dict)
            self.wait_window(dialog)
            if dialog.result:
                sold_qty = dialog.result.get("quantity", 1) or 1
                if sold_qty < original_qty:
                    # Vendita parziale: crea un nuovo record per la quota venduta
                    # e aggiorna il record originale con la quantità rimanente.
                    new_sold_record = dict(dialog.result)
                    new_sold_record.pop("id", None)
                    new_new_id = self.db.save(new_sold_record)
                    remaining = original_qty - sold_qty
                    updated_original = dict(record)
                    updated_original["quantity"] = remaining
                    self.db.save(updated_original, prod_id)
                    undo_ids = [new_new_id] if new_new_id else []
                    self._push_undo(
                        "Vendita parziale",
                        lambda recs=old_records, nids=undo_ids: (
                            self._undo_update(recs),
                            self.db.delete_many(nids) if nids else None,
                            self.refresh(),
                        ),
                    )
                    self.status_bar_var.set(
                        f"Venduti {sold_qty} pz — restano {remaining} pz in {record.get('status', 'magazzino')}"
                    )
                else:
                    # Vendita totale: comportamento classico (sovrascrive il record).
                    self.db.save(dialog.result, prod_id)
                    if old_records:
                        self._push_undo(
                            "Spostamento in vendita",
                            lambda recs=old_records: self._undo_update(recs),
                        )
                    self.status_bar_var.set("Prodotto venduto con successo")
                self.refresh()
                self.notebook.set("Vendite Attive")
        else:
            places = self.db.get_distinct_places()
            existing_places = {r.get("selling_place", "").strip() for r in old_records if r.get("selling_place", "").strip()}
            default_place = next(iter(existing_places)) if len(existing_places) == 1 else ""
            dialog = BulkStatusDialog(
                self,
                len(ids),
                STATUS_SOLD,
                selling_places=places[1],
                default_place=default_place,
            )
            self.wait_window(dialog)
            if dialog.result is not None:
                self.db.update_status_many(ids, STATUS_SOLD, extra_data=dialog.result)
                self.refresh()
                self.notebook.set("Vendite Attive")
                if STATUS_SOLD in self.trees:
                    self.trees[STATUS_SOLD].focus_set()
                if old_records:
                    self._push_undo(f"Spostamento {len(ids)} prodotti in vendita", lambda recs=old_records: self._undo_update(recs))
                self.status_bar_var.set(f"{len(ids)} prodotti contrassegnati come venduti")

    def _push_undo(self, desc: str, action_fn: Any) -> None:
        """Aggiunge un'azione invertibile alla pila di Undo (max 10 azioni)."""
        self._undo_stack.append((desc, action_fn))
        if len(self._undo_stack) > 10:
            self._undo_stack.pop(0)

    def undo(self, event=None) -> None:
        """Annulla l'ultima azione eseguita dall'utente."""
        if not self._undo_stack:
            self.status_bar_var.set("Nessuna azione da annullare")
            return
        desc, action_fn = self._undo_stack.pop()
        try:
            action_fn()
        except Exception as exc:
            self.status_bar_var.set(f"Impossibile annullare: {exc}")

    def _undo_insert(self, inserted_ids: List[int]) -> None:
        if inserted_ids:
            self.db.delete_many(inserted_ids)
            self.refresh()
            self.status_bar_var.set(f"Annullato: rimossi {len(inserted_ids)} prodotti aggiunti")

    def _undo_update(self, old_records: List[Dict[str, Any]]) -> None:
        for rec in old_records:
            pid = rec.get("id")
            if pid:
                self.db.save(rec, pid)
        self.refresh()
        self.status_bar_var.set(f"Annullato: ripristinate modifiche per {len(old_records)} prodotti")

    def _undo_delete(self, deleted_records: List[Dict[str, Any]]) -> None:
        restored = 0
        for rec in deleted_records:
            self.db.save(rec)
            restored += 1
        self.refresh()
        self.status_bar_var.set(f"Annullato: ripristinati {restored} prodotti eliminati")

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
        """Importa un file Excel/CSV qualsiasi tramite AI (analisi universale)."""
        path = filedialog.askopenfilename(
            parent=self,
            title="Importa file Excel o CSV",
            filetypes=[("Excel / CSV", "*.xlsx *.xlsm *.csv")],
        )
        if not path:
            return

        api_key = self.db.get_setting("gemini_api_key", "")
        if not api_key:
            messagebox.showwarning(
                "API Key mancante",
                "Inserisci la tua Chiave API Gemini nelle impostazioni prima di usare l'importazione AI.\n"
                "(Puoi salvarla dalla finestra Sincronizzazione Email → campo 'API Key Gemini')",
                parent=self,
            )
            return

        # Mostra la dialog per il suggerimento contestuale opzionale
        filename = Path(path).name
        hint_dialog = ExcelHintDialog(self, filename)
        self.wait_window(hint_dialog)

        if not hint_dialog.confirmed:
            # L'utente ha premuto Annulla nella hint dialog
            return

        user_hint = hint_dialog.hint  # Può essere stringa vuota

        # Mostra stato di elaborazione
        self.status_bar_var.set("Analisi AI del file in corso...")
        self.update_idletasks()

        def _run_import():
            try:
                raw_text = read_spreadsheet_raw(path)
                if not raw_text.strip():
                    self.after(0, lambda: messagebox.showerror(
                        "File vuoto",
                        "Il file selezionato non contiene dati leggibili.",
                        parent=self,
                    ))
                    self.after(0, lambda: self.status_bar_var.set("Importazione annullata: file vuoto"))
                    return
                products = parse_excel_with_ai(raw_text, api_key, user_hint=user_hint)
                self.after(0, lambda: _on_ai_done(products))
            except Exception as exc:
                err = str(exc)
                self.after(0, lambda: messagebox.showerror(
                    "Errore Importazione AI",
                    f"Impossibile analizzare il file:\n{err}",
                    parent=self,
                ))
                self.after(0, lambda: self.status_bar_var.set("Errore durante l'analisi AI"))

        def _on_ai_done(products):
            if not products:
                messagebox.showwarning(
                    "Nessun prodotto trovato",
                    "L'AI non ha rilevato prodotti validi nel file.\n"
                    "Assicurati che il file contenga righe con nome e prezzo.",
                    parent=self,
                )
                self.status_bar_var.set("Nessun prodotto trovato nel file")
                return

            dialog = ExcelImportDialog(self, self.db, products)
            self.wait_window(dialog)

            if dialog.confirmed:
                saved = getattr(dialog, "saved_count", len(products))
                self.refresh()
                self.status_bar_var.set(f"Importati {saved} prodotti da Excel con AI")
                messagebox.showinfo(
                    "Importazione Completata",
                    f"Importati con successo {saved} prodott{'o' if saved == 1 else 'i'} dall'Excel!",
                    parent=self,
                )
            else:
                self.status_bar_var.set("Importazione Excel annullata")

        threading.Thread(target=_run_import, daemon=True).start()


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

    def _check_updates_background(self) -> None:
        """Controlla silenziosamente in background la presenza di aggiornamenti su GitHub."""
        token = self.db.get_setting("github_token", "")
        repo = self.db.get_setting("github_repo", GITHUB_REPO)

        def worker(tok: str, rep: str):
            info = check_for_updates(current_version=APP_VERSION, repo=rep, github_token=tok)
            if info:
                self.after(0, lambda: self._on_update_found(info))

        threading.Thread(target=worker, args=(token, repo), daemon=True).start()

    def _on_update_found(self, update_info: Dict[str, Any]) -> None:
        """Mostra il badge dell'aggiornamento accanto al logo."""
        self._update_info = update_info
        ver = update_info.get("version", "")
        self.btn_update.configure(text=f"Aggiorna a {ver}")
        self.btn_update.pack(side="left", padx=(14, 0))

    def _open_updater(self) -> None:
        """Apre la finestra modale di aggiornamento."""
        if not self._update_info:
            return
        token = self.db.get_setting("github_token", "")
        UpdateDialog(self, self._update_info, github_token=token)

    def _on_close(self) -> None:
        self.db.close()
        self.destroy()
