#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vista Dashboard e Grafici Statistici per Russo Stock Manager."""

import tkinter as tk
from decimal import Decimal
from tkinter import ttk
from typing import Dict, List, Any
import customtkinter as ctk

from ..config import DARK_THEME, STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK
from ..database import InventoryDatabase
from ..utils import money, center_window, apply_dark_titlebar


class DashboardView(ctk.CTkFrame):
    """Componente vista dashboard con KPI e grafici Canvas nativi."""

    def __init__(self, parent: tk.Widget, db: InventoryDatabase) -> None:
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self.kpi_vars: Dict[str, tk.StringVar] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        c = DARK_THEME
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=16, pady=12)

        # Griglia Carte KPI (4 schede)
        kpis_frame = ctk.CTkFrame(container, fg_color="transparent")
        kpis_frame.pack(fill="x", pady=(0, 16))

        cards_data = [
            ("invested", "CAPITALE INVESTITO", "#2563eb", "Magazzino + Pre-ordini"),
            ("stock_val", "VALORE MAGAZZINO", "#059669", "Pezzi in magazzino"),
            ("profit_tot", "PROFITTO NETTO GENERATO", "#10b981", "Incassi - Costi - Spese"),
            ("roi_avg", "ROI MEDIO REALE", "#7c3aed", "Ritorno sull'investimento"),
        ]

        for idx, (key, label, accent_color, subtext) in enumerate(cards_data):
            kpis_frame.columnconfigure(idx, weight=1)
            card = ctk.CTkFrame(kpis_frame, fg_color=c["bg_card"], corner_radius=10)
            card.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 6, 0 if idx == len(cards_data)-1 else 6))

            var_val = tk.StringVar(value="-")
            var_sub = tk.StringVar(value=subtext)
            self.kpi_vars[key] = var_val

            # Linea accento in alto
            accent_bar = ctk.CTkFrame(card, fg_color=accent_color, height=4, corner_radius=0)
            accent_bar.pack(fill="x")

            ctk.CTkLabel(card, text=label, font=("Segoe UI", 8, "bold"), text_color=c["fg_muted"]).pack(anchor="w", padx=16, pady=(8, 0))
            ctk.CTkLabel(card, textvariable=var_val, font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=16, pady=(4, 2))
            ctk.CTkLabel(card, textvariable=var_sub, font=("Segoe UI", 8), text_color=c.get("fg_subtle", c["fg_muted"])).pack(anchor="w", padx=16, pady=(0, 14))

        # Area dei Grafici (due colonne)
        self.charts_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.charts_frame.pack(fill="both", expand=True)
        self.charts_frame.columnconfigure(0, weight=3)
        self.charts_frame.columnconfigure(1, weight=2)
        self.charts_frame.rowconfigure(0, weight=1)

        # Grafico 1: Bar Chart Profitto Mensile
        self.chart1_card = ctk.CTkFrame(self.charts_frame, fg_color=c["bg_card"], corner_radius=10)

        ctk.CTkLabel(self.chart1_card, text="ANDAMENTO PROFITTO MENSILE (€)", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(self.chart1_card, text="Utili netti generati per ciascun mese di vendita", font=("Segoe UI", 9), text_color=c["fg_muted"]).pack(anchor="w", padx=16, pady=(0, 10))

        self.canvas_monthly = tk.Canvas(self.chart1_card, bg=c["bg_card"], highlightthickness=0)
        self.canvas_monthly.pack(fill="both", expand=True, padx=4, pady=(0, 14))

        # Grafico 2: Distribution per Stato Prodotti
        self.chart2_card = ctk.CTkFrame(self.charts_frame, fg_color=c["bg_card"], corner_radius=10)

        ctk.CTkLabel(self.chart2_card, text="RIPARTIZIONE INVENTARIO (PEZZI)", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(self.chart2_card, text="Distribuzione volumi per stato", font=("Segoe UI", 9), text_color=c["fg_muted"]).pack(anchor="w", padx=16, pady=(0, 10))

        self.canvas_dist = tk.Canvas(self.chart2_card, bg=c["bg_card"], highlightthickness=0)
        self.canvas_dist.pack(fill="both", expand=True, padx=4, pady=(0, 14))

        self.chart_cards = {
            "monthly": self.chart1_card,
            "dist": self.chart2_card
        }

        self._bind_context_menu(self.chart1_card, "monthly")
        self._bind_context_menu(self.canvas_monthly, "monthly")
        self._bind_context_menu(self.chart2_card, "dist")
        self._bind_context_menu(self.canvas_dist, "dist")

        self._bind_global_context_menu(self.charts_frame)
        self._bind_global_context_menu(container)
        self._bind_global_context_menu(self)

        self._apply_layout()

    def _bind_global_context_menu(self, widget: tk.Widget):
        menu = tk.Menu(self, tearoff=0, bg=DARK_THEME["bg_card"], fg=DARK_THEME["fg_main"], activebackground=DARK_THEME["accent"])
        menu.add_command(label="Personalizza layout...", command=self._open_layout_settings)

        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)

        widget.bind("<Button-3>", show_menu)

    def _bind_context_menu(self, widget: tk.Widget, chart_id: str):
        menu = tk.Menu(self, tearoff=0, bg=DARK_THEME["bg_card"], fg=DARK_THEME["fg_main"], activebackground=DARK_THEME["accent"])
        menu.add_command(label="Nascondi grafico", command=lambda: self._hide_chart(chart_id))
        menu.add_separator()
        menu.add_command(label="Personalizza layout...", command=self._open_layout_settings)

        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)

        widget.bind("<Button-3>", show_menu)

    def _hide_chart(self, chart_id: str):
        import json
        layout_str = self.db.get_setting("dashboard_layout", '["monthly", "dist"]')
        try:
            layout = json.loads(layout_str)
        except Exception:
            layout = ["monthly", "dist"]
        if chart_id in layout:
            layout.remove(chart_id)
            self.db.set_setting("dashboard_layout", json.dumps(layout))
            self._apply_layout()

    def _apply_layout(self):
        import json
        layout_str = self.db.get_setting("dashboard_layout", '["monthly", "dist"]')
        try:
            layout = json.loads(layout_str)
        except Exception:
            layout = ["monthly", "dist"]
        for card in self.chart_cards.values():
            card.grid_remove()
        col = 0
        for chart_id in layout:
            if chart_id in self.chart_cards:
                self.charts_frame.columnconfigure(col, weight=1)
                padx = (0, 8) if col == 0 and len(layout) > 1 else (8, 0) if col > 0 else (0, 0)
                self.chart_cards[chart_id].grid(row=0, column=col, sticky="nsew", padx=padx)
                col += 1
        self.charts_frame.update_idletasks()
        self.after(100, self.refresh)

    def _open_layout_settings(self):
        import json
        top = ctk.CTkToplevel(self, fg_color=DARK_THEME["bg_main"])
        top.title("Personalizza Dashboard")
        center_window(top, 400, 420)
        top.transient(self.winfo_toplevel())
        top.grab_set()
        apply_dark_titlebar(top)

        ctk.CTkLabel(top, text="Seleziona e riordina i grafici da visualizzare.", font=("Segoe UI", 10)).pack(pady=10)

        list_frame = tk.Frame(top, bg=DARK_THEME["bg_card"])
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        layout_str = self.db.get_setting("dashboard_layout", '["monthly", "dist"]')
        try:
            current_layout = json.loads(layout_str)
        except Exception:
            current_layout = ["monthly", "dist"]

        all_charts = {
            "monthly": "Grafico: Andamento Profitto Mensile",
            "dist": "Grafico: Ripartizione Inventario"
        }

        self._temp_layout = current_layout.copy()
        for c in all_charts:
            if c not in self._temp_layout:
                self._temp_layout.append(c)

        self._chart_vars = {}
        for c in all_charts:
            var = tk.BooleanVar(value=(c in current_layout))
            self._chart_vars[c] = var

        listbox = tk.Listbox(list_frame, bg=DARK_THEME["bg_card"], fg=DARK_THEME["fg_main"], selectbackground=DARK_THEME["accent"], font=("Segoe UI", 10), bd=0, highlightthickness=0)
        listbox.pack(side="left", fill="both", expand=True)

        for c in self._temp_layout:
            prefix = "☑  " if self._chart_vars[c].get() else "☐  "
            listbox.insert(tk.END, prefix + all_charts[c])

        def toggle_item(event):
            idx = listbox.curselection()
            if not idx: return
            idx = idx[0]
            cid = self._temp_layout[idx]
            self._chart_vars[cid].set(not self._chart_vars[cid].get())
            prefix = "☑  " if self._chart_vars[cid].get() else "☐  "
            listbox.delete(idx)
            listbox.insert(idx, prefix + all_charts[cid])
            listbox.selection_set(idx)

        listbox.bind("<Double-Button-1>", toggle_item)

        btn_frame = ctk.CTkFrame(top, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 10))

        def move_up():
            idx = listbox.curselection()
            if not idx or idx[0] == 0: return
            idx = idx[0]
            self._temp_layout[idx-1], self._temp_layout[idx] = self._temp_layout[idx], self._temp_layout[idx-1]
            val = listbox.get(idx)
            listbox.delete(idx)
            listbox.insert(idx-1, val)
            listbox.selection_set(idx-1)

        def move_down():
            idx = listbox.curselection()
            if not idx or idx[0] == len(self._temp_layout)-1: return
            idx = idx[0]
            self._temp_layout[idx+1], self._temp_layout[idx] = self._temp_layout[idx], self._temp_layout[idx+1]
            val = listbox.get(idx)
            listbox.delete(idx)
            listbox.insert(idx+1, val)
            listbox.selection_set(idx+1)

        ctk.CTkButton(btn_frame, text="Spunta/Nascondi", command=lambda: toggle_item(None), fg_color="#374151", hover_color="#4b5563").pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(btn_frame, text="▲", command=move_up, width=60, fg_color="#374151", hover_color="#4b5563").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="▼", command=move_down, width=60, fg_color="#374151", hover_color="#4b5563").pack(side="left", padx=(5, 0))

        def save():
            final_layout = [c for c in self._temp_layout if self._chart_vars[c].get()]
            self.db.set_setting("dashboard_layout", json.dumps(final_layout))
            self._apply_layout()
            top.destroy()

        ctk.CTkButton(top, text="Salva Layout", command=save).pack(pady=10)

    def refresh(self) -> None:
        """Aggiorna i dati KPI e ridisegna i grafici."""
        totals = self.db.totals()
        self.kpi_vars["invested"].set(money(totals["committed_total"]))
        self.kpi_vars["stock_val"].set(f"{money(totals['stock_total'])} ({totals['stock_count']} pz)")
        self.kpi_vars["profit_tot"].set(money(totals["sold_profit"]))
        self.kpi_vars["roi_avg"].set(f"{totals['sold_roi']:.1f}% ({totals['sold_count']} v.)")
        self._draw_monthly_chart()
        self._draw_distribution_chart(totals)

    def _draw_monthly_chart(self) -> None:
        canvas = self.canvas_monthly
        canvas.delete("all")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 50 or height < 50:
            self.after(100, self._draw_monthly_chart)
            return
        sales = self.db.get_monthly_sales()
        if not sales:
            canvas.create_text(width / 2, height / 2, text="Nessuna vendita registrata con data di vendita.", fill=DARK_THEME["fg_muted"], font=("Segoe UI", 10))
            return
        margin_left = 50
        margin_bottom = 40
        margin_top = 20
        margin_right = 20
        plot_width = width - margin_left - margin_right
        plot_height = height - margin_top - margin_bottom
        max_profit = max((s["profit"] for s in sales), default=Decimal("0"))
        min_profit = min((s["profit"] for s in sales), default=Decimal("0"))
        max_profit = max(max_profit, Decimal("10"))
        min_profit = min(min_profit, Decimal("0"))
        profit_range = max_profit - min_profit
        num_bars = len(sales)
        bar_gap = 14
        bar_width = max(20, min(70, (plot_width - (num_bars + 1) * bar_gap) / max(num_bars, 1)))
        for i in range(4):
            y_val = margin_top + plot_height * (i / 3)
            profit_val = max_profit - profit_range * (Decimal(i) / Decimal("3"))
            canvas.create_line(margin_left, y_val, width - margin_right, y_val, fill=DARK_THEME["border"], dash=(2, 2))
            canvas.create_text(margin_left - 8, y_val, text=f"\u20ac{int(profit_val)}", anchor="e", fill=DARK_THEME["fg_muted"], font=("Segoe UI", 8))
        zero_y = margin_top + float(max_profit / profit_range) * plot_height
        for idx, item in enumerate(sales):
            x0 = margin_left + bar_gap + idx * (bar_width + bar_gap)
            x1 = x0 + bar_width
            profit = item["profit"]
            y_profit = margin_top + float((max_profit - profit) / profit_range) * plot_height
            y0 = min(zero_y, y_profit)
            y1 = max(zero_y, y_profit)
            bar_color = "#10b981" if profit >= 0 else "#ef4444"
            canvas.create_rectangle(x0, y0, x1, y1, fill=bar_color, outline=bar_color, width=1)
            
            month_key = item["month"]
            month_label = month_key
            if len(month_key) >= 7 and "-" in month_key:
                year_part, month_part = month_key[:4], month_key[5:7]
                months_it = {
                    "01": "Gen", "02": "Feb", "03": "Mar", "04": "Apr",
                    "05": "Mag", "06": "Giu", "07": "Lug", "08": "Ago",
                    "09": "Set", "10": "Ott", "11": "Nov", "12": "Dic"
                }
                months_full = {
                    "01": "Gennaio", "02": "Febbraio", "03": "Marzo", "04": "Aprile",
                    "05": "Maggio", "06": "Giugno", "07": "Luglio", "08": "Agosto",
                    "09": "Settembre", "10": "Ottobre", "11": "Novembre", "12": "Dicembre"
                }
                if bar_width >= 55:
                    month_label = f"{months_full.get(month_part, month_part)} {year_part}"
                else:
                    month_label = f"{months_it.get(month_part, month_part)} '{year_part[2:]}"

            canvas.create_text((x0 + x1) / 2, y1 + 16, text=month_label, fill=DARK_THEME["fg_main"], font=("Segoe UI", 9, "bold"))
            if bar_width >= 25:
                canvas.create_text((x0 + x1) / 2, y0 - 8, text=f"\u20ac{int(profit)}", fill=DARK_THEME["fg_main"], font=("Segoe UI", 8, "bold"))

    def _draw_distribution_chart(self, totals: Dict[str, Any]) -> None:
        canvas = self.canvas_dist
        canvas.delete("all")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 50 or height < 50:
            self.after(100, lambda: self._draw_distribution_chart(totals))
            return
        stock_c = totals["stock_count"]
        pre_c = totals["preorder_count"]
        sold_c = totals["sold_count"]
        total = stock_c + pre_c + sold_c
        if total == 0:
            canvas.create_text(width / 2, height / 2, text="Nessun articolo presente nel database.", fill=DARK_THEME["fg_muted"], font=("Segoe UI", 10))
            return
        categories = [
            ("In Magazzino", stock_c, "#059669"),
            ("Pre-ordini", pre_c, "#d97706"),
            ("Vendite Attive", totals.get("sold_count_active", 0), "#2563eb"),
            ("Completate", totals.get("sold_count_completed", 0), "#db2777"),
        ]
        bar_y = 40
        bar_h = 30
        margin_x = 20
        avail_w = width - 2 * margin_x
        current_x = margin_x
        for label, count, color in categories:
            if count > 0:
                seg_w = (count / total) * avail_w
                canvas.create_rectangle(current_x, bar_y, current_x + seg_w, bar_y + bar_h, fill=color, outline="")
                current_x += seg_w
        start_y = 100
        for label, count, color in categories:
            pct = (count / total * 100) if total > 0 else 0
            canvas.create_rectangle(margin_x, start_y, margin_x + 16, start_y + 16, fill=color, outline="")
            canvas.create_text(margin_x + 26, start_y + 8, text=f"{label}: {count} pz ({pct:.1f}%)", anchor="w", fill=DARK_THEME["fg_main"], font=("Segoe UI", 10, "bold"))
            start_y += 35