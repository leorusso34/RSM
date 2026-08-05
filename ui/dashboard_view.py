#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vista Dashboard e Grafici Statistici per Russo Stock Manager."""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Any

from config import LIGHT_THEME, STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK
from database import InventoryDatabase
from utils import money


class DashboardView(ttk.Frame):
    """Componente vista dashboard con KPI e grafici Canvas nativi."""

    def __init__(self, parent: tk.Widget, db: InventoryDatabase) -> None:
        super().__init__(parent, style="TFrame")
        self.db = db
        self.kpi_vars: Dict[str, tk.StringVar] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        c = LIGHT_THEME
        container = ttk.Frame(self, padding=(16, 12))
        container.pack(fill="both", expand=True)

        # Intestazione Dashboard
        head_frame = ttk.Frame(container)
        head_frame.pack(fill="x", pady=(0, 16))
        ttk.Label(head_frame, text="Dashboard & Analisi Finanziaria", style="Section.TLabel").pack(anchor="w")
        ttk.Label(head_frame, text="Panoramica completa dei profitti, del capitale investito e dell'andamento vendite", style="Muted.TLabel").pack(anchor="w")

        # Griglia Carte KPI (4 schede)
        kpis_frame = ttk.Frame(container)
        kpis_frame.pack(fill="x", pady=(0, 16))

        cards_data = [
            ("invested", "CAPITALE INVESTITO", "#2563eb", "Magazzino + Pre-ordini"),
            ("stock_val", "VALORE MAGAZZINO", "#059669", "Pezzi in magazzino"),
            ("profit_tot", "PROFITTO NETTO GENERATO", "#10b981", "Incassi - Costi - Spese"),
            ("roi_avg", "ROI MEDIO REALE", "#7c3aed", "Ritorno sull'investimento"),
        ]

        for idx, (key, label, accent_color, subtext) in enumerate(cards_data):
            kpis_frame.columnconfigure(idx, weight=1)
            card = tk.Frame(
                kpis_frame,
                bg=c["bg_card"],
                highlightbackground="#e2e8f0",
                highlightthickness=1,
                padx=16,
                pady=14,
            )
            card.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 6, 0 if idx == len(cards_data)-1 else 6))

            var_val = tk.StringVar(value="-")
            var_sub = tk.StringVar(value=subtext)
            self.kpi_vars[key] = var_val

            # Linea d'accento in alto
            accent_bar = tk.Frame(card, bg=accent_color, height=3)
            accent_bar.pack(fill="x", pady=(0, 8))

            tk.Label(card, text=label, bg=c["bg_card"], fg=c["fg_muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
            tk.Label(card, textvariable=var_val, bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(4, 2))
            tk.Label(card, textvariable=var_sub, bg=c["bg_card"], fg=c["fg_subtle"], font=("Segoe UI", 8)).pack(anchor="w")

        # Area dei Grafici (due colonne)
        charts_frame = ttk.Frame(container)
        charts_frame.pack(fill="both", expand=True)
        charts_frame.columnconfigure(0, weight=3)
        charts_frame.columnconfigure(1, weight=2)
        charts_frame.rowconfigure(0, weight=1)

        # Grafico 1: Bar Chart Profitto Mensile
        chart1_card = tk.Frame(charts_frame, bg=c["bg_card"], highlightbackground="#e2e8f0", highlightthickness=1, padx=16, pady=14)
        chart1_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        tk.Label(chart1_card, text="ANDAMENTO PROFITTO MENSILE (€)", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(chart1_card, text="Utili netti generati per ciascun mese di vendita", bg=c["bg_card"], fg=c["fg_muted"], font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 10))

        self.canvas_monthly = tk.Canvas(chart1_card, bg=c["bg_card"], highlightthickness=0)
        self.canvas_monthly.pack(fill="both", expand=True)

        # Grafico 2: Distribution Bar / Pie per Stato Prodotti
        chart2_card = tk.Frame(charts_frame, bg=c["bg_card"], highlightbackground="#e2e8f0", highlightthickness=1, padx=16, pady=14)
        chart2_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        tk.Label(chart2_card, text="RIPARTIZIONE INVENTARIO (PEZZI)", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(chart2_card, text="Distribuzione volumi per stato", bg=c["bg_card"], fg=c["fg_muted"], font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 10))

        self.canvas_dist = tk.Canvas(chart2_card, bg=c["bg_card"], highlightthickness=0)
        self.canvas_dist.pack(fill="both", expand=True)

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
            canvas.create_text(
                width / 2, height / 2,
                text="Nessuna vendita registrata con data di vendita.",
                fill=LIGHT_THEME["fg_muted"],
                font=("Segoe UI", 10),
            )
            return

        margin_left = 50
        margin_bottom = 35
        margin_top = 20
        margin_right = 20

        plot_width = width - margin_left - margin_right
        plot_height = height - margin_top - margin_bottom

        max_profit = max((s["profit"] for s in sales), default=1.0)
        max_profit = max(max_profit, 10.0)

        num_bars = len(sales)
        bar_gap = 12
        bar_width = max(15, min(50, (plot_width - (num_bars + 1) * bar_gap) / max(num_bars, 1)))

        # Griglia orizzontale
        for i in range(4):
            y_val = margin_top + plot_height * (i / 3)
            profit_val = max_profit * (1 - i / 3)
            canvas.create_line(margin_left, y_val, width - margin_right, y_val, fill="#e2e8f0", dash=(2, 2))
            canvas.create_text(
                margin_left - 8, y_val,
                text=f"€{int(profit_val)}",
                anchor="e",
                fill=LIGHT_THEME["fg_muted"],
                font=("Segoe UI", 8),
            )

        # Disegno barre
        for idx, item in enumerate(sales):
            x0 = margin_left + bar_gap + idx * (bar_width + bar_gap)
            x1 = x0 + bar_width

            profit = max(0, item["profit"])
            bar_h = (profit / max_profit) * plot_height
            y1 = margin_top + plot_height
            y0 = y1 - bar_h

            # Barra profitto
            canvas.create_rectangle(x0, y0, x1, y1, fill="#10b981", outline="#059669", width=1)

            # Etichetta mese
            month_label = item["month"]
            if len(month_label) >= 7:
                month_label = month_label[5:7] + "/" + month_label[2:4]
            canvas.create_text(
                (x0 + x1) / 2, y1 + 14,
                text=month_label,
                fill=LIGHT_THEME["fg_muted"],
                font=("Segoe UI", 8, "bold"),
            )

            # Valore in alto alla barra
            if bar_width >= 25:
                canvas.create_text(
                    (x0 + x1) / 2, y0 - 8,
                    text=f"€{int(profit)}",
                    fill=LIGHT_THEME["fg_main"],
                    font=("Segoe UI", 8, "bold"),
                )

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
            canvas.create_text(
                width / 2, height / 2,
                text="Nessun articolo presente nel database.",
                fill=LIGHT_THEME["fg_muted"],
                font=("Segoe UI", 10),
            )
            return

        categories = [
            ("In Magazzino", stock_c, "#059669"),
            ("Pre-ordini", pre_c, "#d97706"),
            ("Venduti", sold_c, "#2563eb"),
        ]

        # Ripartizione visuale a barre orizzontali ed etichette eleganti
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

        # Legenda e percentuali
        start_y = 100
        for label, count, color in categories:
            pct = (count / total * 100) if total > 0 else 0
            canvas.create_rectangle(margin_x, start_y, margin_x + 16, start_y + 16, fill=color, outline="")
            canvas.create_text(
                margin_x + 26, start_y + 8,
                text=f"{label}: {count} pz ({pct:.1f}%)",
                anchor="w",
                fill=LIGHT_THEME["fg_main"],
                font=("Segoe UI", 10, "bold"),
            )
            start_y += 35
