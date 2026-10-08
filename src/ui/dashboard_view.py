"""Vista Dashboard e Grafici Statistici per RSM."""

import sys
import tkinter as tk
from decimal import Decimal
from typing import Any

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from ..config import (
    CHART_PALETTE,
    DARK_THEME,
)
from ..database import InventoryDatabase
from ..utils import apply_dark_titlebar, center_window, format_month_label, money


class DashboardView(ctk.CTkFrame):
    """Componente vista dashboard con KPI e grafici Canvas nativi."""

    def __init__(self, parent: tk.Widget, db: InventoryDatabase) -> None:
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self.kpi_vars: dict[str, tk.StringVar] = {}
        self._resize_after_id = None
        self._build_ui()

    def _build_ui(self) -> None:
        c = DARK_THEME
        container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=4, pady=4)

        # Griglia Carte KPI (4 schede)
        kpis_frame = ctk.CTkFrame(container, fg_color="transparent")
        kpis_frame.pack(fill="x", padx=12, pady=(8, 16))

        cards_data = [
            ("invested", "CAPITALE INVESTITO", "#2563eb"),
            ("stock_val", "VALORE MAGAZZINO", "#059669"),
            ("profit_tot", "PROFITTO NETTO GENERATO", "#10b981"),
            ("roi_avg", "ROI MEDIO REALE", "#7c3aed"),
        ]

        for idx, (key, label, accent_color) in enumerate(cards_data):
            kpis_frame.columnconfigure(idx, weight=1)
            card = ctk.CTkFrame(kpis_frame, fg_color=c["bg_card"], corner_radius=10)
            card.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 6, 0 if idx == len(cards_data)-1 else 6))

            var_val = tk.StringVar(value="-")
            self.kpi_vars[key] = var_val

            # Linea accento in alto
            accent_bar = ctk.CTkFrame(card, fg_color=accent_color, height=4, corner_radius=0)
            accent_bar.pack(fill="x")

            ctk.CTkLabel(card, text=label, font=("Segoe UI", 11, "bold"), text_color=c["fg_muted"]).pack(anchor="w", padx=16, pady=(8, 0))
            ctk.CTkLabel(card, textvariable=var_val, font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=16, pady=(4, 12))

        # Area dei Grafici (griglia dinamica a 2 colonne)
        self.charts_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.charts_frame.pack(fill="both", expand=True, padx=12, pady=(0, 16))
        self.charts_frame.columnconfigure(0, weight=1, uniform="chart_col")
        self.charts_frame.columnconfigure(1, weight=1, uniform="chart_col")

        # Grafico 1: Bar Chart Profitto Mensile
        self.chart1_card = ctk.CTkFrame(self.charts_frame, fg_color=c["bg_card"], corner_radius=10, height=320)

        ctk.CTkLabel(self.chart1_card, text="ANDAMENTO PROFITTO MENSILE (€)", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(self.chart1_card, text="Utili netti generati per ciascun mese di vendita", font=("Segoe UI", 11), text_color=c["fg_muted"]).pack(anchor="w", padx=16, pady=(0, 10))

        self.canvas_monthly = tk.Canvas(self.chart1_card, bg=c["bg_card"], highlightthickness=0, height=230)
        self.canvas_monthly.pack(fill="both", expand=True, padx=4, pady=(0, 14))

        # Grafico 2: Distribution per Stato Prodotti
        self.chart2_card = ctk.CTkFrame(self.charts_frame, fg_color=c["bg_card"], corner_radius=10, height=320)

        ctk.CTkLabel(self.chart2_card, text="RIPARTIZIONE INVENTARIO (PEZZI)", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(self.chart2_card, text="Distribuzione volumi per stato", font=("Segoe UI", 11), text_color=c["fg_muted"]).pack(anchor="w", padx=16, pady=(0, 10))

        self.canvas_dist = tk.Canvas(self.chart2_card, bg=c["bg_card"], highlightthickness=0, height=230)
        self.canvas_dist.pack(fill="both", expand=True, padx=4, pady=(0, 14))

        # Grafico 3: Grafico a Torta Profitto per Piattaforma
        self.chart3_card = ctk.CTkFrame(self.charts_frame, fg_color=c["bg_card"], corner_radius=10, height=320)

        ctk.CTkLabel(self.chart3_card, text="PROFITTO PER PIATTAFORMA (€)", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(self.chart3_card, text="Ripartizione del guadagno netto per canale di vendita", font=("Segoe UI", 11), text_color=c["fg_muted"]).pack(anchor="w", padx=16, pady=(0, 10))

        self.canvas_platform = tk.Canvas(self.chart3_card, bg=c["bg_card"], highlightthickness=0, height=230)
        self.canvas_platform.pack(fill="both", expand=True, padx=4, pady=(0, 14))

        # Grafico 4: Volume Vendite nel Tempo (Pezzi per Mese)
        self.chart4_card = ctk.CTkFrame(self.charts_frame, fg_color=c["bg_card"], corner_radius=10, height=320)

        ctk.CTkLabel(self.chart4_card, text="VOLUME VENDITE NEL TEMPO (PEZZI)", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(self.chart4_card, text="Distribuzione del numero di pezzi venduti per mese", font=("Segoe UI", 11), text_color=c["fg_muted"]).pack(anchor="w", padx=16, pady=(0, 10))

        self.canvas_volume = tk.Canvas(self.chart4_card, bg=c["bg_card"], highlightthickness=0, height=230)
        self.canvas_volume.pack(fill="both", expand=True, padx=4, pady=(0, 14))

        # Grafico 5: Top Prodotti per Profitto
        self.chart5_card = ctk.CTkFrame(self.charts_frame, fg_color=c["bg_card"], corner_radius=10, height=320)

        ctk.CTkLabel(self.chart5_card, text="TOP PRODOTTI PER PROFITTO (€)", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(self.chart5_card, text="Classifica dei prodotti con maggior utile netto generato", font=("Segoe UI", 11), text_color=c["fg_muted"]).pack(anchor="w", padx=16, pady=(0, 10))

        self.canvas_top_products = tk.Canvas(self.chart5_card, bg=c["bg_card"], highlightthickness=0, height=230)
        self.canvas_top_products.pack(fill="both", expand=True, padx=4, pady=(0, 14))

        self.chart_cards = {
            "monthly": self.chart1_card,
            "dist": self.chart2_card,
            "platform_pie": self.chart3_card,
            "volume_monthly": self.chart4_card,
            "top_products": self.chart5_card,
        }

        self._bind_context_menu(self.chart1_card, "monthly")
        self._bind_context_menu(self.canvas_monthly, "monthly")
        self._bind_context_menu(self.chart2_card, "dist")
        self._bind_context_menu(self.canvas_dist, "dist")
        self._bind_context_menu(self.chart3_card, "platform_pie")
        self._bind_context_menu(self.canvas_platform, "platform_pie")
        self._bind_context_menu(self.chart4_card, "volume_monthly")
        self._bind_context_menu(self.canvas_volume, "volume_monthly")
        self._bind_context_menu(self.chart5_card, "top_products")
        self._bind_context_menu(self.canvas_top_products, "top_products")

        self._bind_global_context_menu(self.charts_frame)
        self._bind_global_context_menu(container)
        self._bind_global_context_menu(self)

        self._apply_layout()
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, event=None) -> None:
        """Ridisegna i grafici in modo reattivo quando la vista cambia dimensione o torna visibile."""
        if not self.winfo_viewable():
            return
        if self._resize_after_id:
            try:
                self.after_cancel(self._resize_after_id)
            except (tk.TclError, ValueError):
                pass
        self._resize_after_id = self.after(150, self._delayed_refresh)

    def _delayed_refresh(self) -> None:
        self._resize_after_id = None
        if self.winfo_viewable():
            self.refresh()

    def _bind_global_context_menu(self, widget: tk.Widget):
        menu = tk.Menu(self, tearoff=0, bg=DARK_THEME["bg_card"], fg=DARK_THEME["fg_main"], activebackground=DARK_THEME["accent"])
        menu.add_command(label="Personalizza layout...", command=self._open_layout_settings)

        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)

        widget.bind("<Button-3>", show_menu)
        widget.bind("<Button-2>", show_menu)
        if sys.platform == "darwin":
            widget.bind("<Control-Button-1>", show_menu)

    def _bind_context_menu(self, widget: tk.Widget, chart_id: str):
        menu = tk.Menu(self, tearoff=0, bg=DARK_THEME["bg_card"], fg=DARK_THEME["fg_main"], activebackground=DARK_THEME["accent"])
        menu.add_command(label="Nascondi grafico", command=lambda: self._hide_chart(chart_id))
        menu.add_separator()
        menu.add_command(label="Personalizza layout...", command=self._open_layout_settings)

        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)

        widget.bind("<Button-3>", show_menu)
        widget.bind("<Button-2>", show_menu)
        if sys.platform == "darwin":
            widget.bind("<Control-Button-1>", show_menu)

    def _hide_chart(self, chart_id: str):
        import json
        default_layout = ["monthly", "dist", "platform_pie", "volume_monthly", "top_products"]
        layout_str = self.db.get_setting("dashboard_layout", json.dumps(default_layout))
        try:
            layout = json.loads(layout_str)
        except (json.JSONDecodeError, ValueError, TypeError):
            layout = default_layout
        if chart_id in layout:
            layout.remove(chart_id)
            self.db.set_setting("dashboard_layout", json.dumps(layout))
            self._apply_layout()

    def _apply_layout(self):
        import json
        default_layout = ["monthly", "dist", "platform_pie", "volume_monthly", "top_products"]
        layout_str = self.db.get_setting("dashboard_layout", json.dumps(default_layout))
        try:
            layout = json.loads(layout_str)
        except (json.JSONDecodeError, ValueError, TypeError):
            layout = default_layout

        for card in self.chart_cards.values():
            card.grid_remove()

        active_charts = [cid for cid in layout if cid in self.chart_cards]
        num_visible = len(active_charts)

        for idx, chart_id in enumerate(active_charts):
            card = self.chart_cards[chart_id]
            if num_visible == 1:
                card.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
            else:
                r = idx // 2
                c = idx % 2
                padx = (0, 6) if c == 0 else (6, 0)
                card.grid(row=r, column=c, columnspan=1, sticky="nsew", padx=padx, pady=6)

        self.charts_frame.update_idletasks()
        self.after(100, self.refresh)

    def _open_layout_settings(self):
        import json
        c = DARK_THEME
        top = ctk.CTkToplevel(self, fg_color=c["bg_main"])
        top.title("Personalizza Dashboard")
        center_window(top, 480, 540)
        top.minsize(420, 460)
        top.transient(self.winfo_toplevel())
        top.grab_set()
        apply_dark_titlebar(top)

        outer = ctk.CTkFrame(top, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=22, pady=20)

        # Header
        ctk.CTkLabel(outer, text="Personalizza Dashboard", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ctk.CTkLabel(
            outer,
            text="Attiva o disattiva i grafici e trascina con il mouse per riordinarli.",
            font=("Segoe UI", 12),
            text_color=c["fg_muted"],
        ).pack(anchor="w", pady=(2, 14))

        layout_str = self.db.get_setting("dashboard_layout", '["monthly", "dist", "platform_pie", "volume_monthly", "top_products"]')
        try:
            current_layout = json.loads(layout_str)
        except (json.JSONDecodeError, ValueError, TypeError):
            current_layout = ["monthly", "dist", "platform_pie", "volume_monthly", "top_products"]

        all_charts = {
            "monthly": "Andamento Profitto Mensile",
            "dist": "Ripartizione Inventario (Pezzi)",
            "platform_pie": "Profitto per Piattaforma (Grafico a Torta)",
            "volume_monthly": "Volume Vendite nel Tempo (Pezzi per Mese)",
            "top_products": "Top Prodotti per Profitto (€)",
        }

        temp_layout = current_layout.copy()
        for ch in all_charts:
            if ch not in temp_layout:
                temp_layout.append(ch)

        chart_vars = {}
        for ch in all_charts:
            chart_vars[ch] = tk.BooleanVar(value=(ch in current_layout))

        # Contenitore per le card dei grafici con supporto Drag & Drop
        cards_container = ctk.CTkFrame(
            outer,
            fg_color="transparent",
        )
        cards_container.pack(fill="both", expand=True, pady=(0, 16))
        cards_container.columnconfigure(0, weight=1)

        drag_state = {"active": False, "cid": None}
        card_widgets = {}
        grip_labels = {}

        def refresh_positions():
            for idx, cid in enumerate(temp_layout):
                card_widgets[cid].grid(row=idx, column=0, sticky="ew", pady=4)

        def on_drag_start(event, cid):
            drag_state["active"] = True
            drag_state["cid"] = cid
            card_widgets[cid].configure(
                fg_color="#1e293b",
                border_width=2,
                border_color=c["accent"],
            )
            grip_labels[cid].configure(text_color="#60a5fa")

        def on_drag_motion(event):
            if not drag_state["active"] or not drag_state["cid"]:
                return

            mouse_y = event.y_root
            dragged_cid = drag_state["cid"]
            cur_idx = temp_layout.index(dragged_cid)

            # Calcolo calibrato: confronta la posizione Y del cursore con i punti mediani reali delle altre schede
            target_idx = 0
            for i, cid in enumerate(temp_layout):
                if cid == dragged_cid:
                    continue
                w = card_widgets[cid]
                card_mid_y = w.winfo_rooty() + (w.winfo_height() / 2)
                if mouse_y > card_mid_y:
                    target_idx = i + 1 if i < cur_idx else i

            target_idx = max(0, min(len(temp_layout) - 1, target_idx))

            if target_idx != cur_idx:
                temp_layout.remove(dragged_cid)
                temp_layout.insert(target_idx, dragged_cid)
                refresh_positions()

        def on_drag_end(event):
            if drag_state["cid"]:
                cid = drag_state["cid"]
                card_widgets[cid].configure(
                    fg_color=c["bg_card"],
                    border_width=1,
                    border_color=c["border"],
                )
                grip_labels[cid].configure(text_color=c["fg_muted"])
            drag_state["active"] = False
            drag_state["cid"] = None

        # Creazione singola e permanente dei widget (nessuna distruzione/ricostruzione = zero sfarfallio)
        for idx, cid in enumerate(temp_layout):
            card = ctk.CTkFrame(
                cards_container,
                fg_color=c["bg_card"],
                corner_radius=8,
                border_width=1,
                border_color=c["border"],
                cursor="fleur",
            )
            card_widgets[cid] = card

            # Switch moderno con label
            switch = ctk.CTkSwitch(
                card,
                text=all_charts.get(cid, cid),
                variable=chart_vars[cid],
                font=("Segoe UI", 12, "bold"),
                text_color=c["fg_main"],
                progress_color=c["accent"],
            )
            switch.pack(side="left", padx=12, pady=10)

            # Grip Handle
            grip_box = ctk.CTkFrame(card, fg_color="transparent")
            grip_box.pack(side="right", padx=12, pady=6)

            grip_lbl = ctk.CTkLabel(
                grip_box,
                text="⋮⋮",
                font=("Segoe UI", 16, "bold"),
                text_color=c["fg_muted"],
                cursor="fleur",
                width=28,
            )
            grip_lbl.pack(side="right")
            grip_labels[cid] = grip_lbl

            # Bind degli eventi sul card e sulla maniglia
            for widget in (card, grip_box, grip_lbl):
                widget.bind("<ButtonPress-1>", lambda e, item_id=cid: on_drag_start(e, item_id))
                widget.bind("<B1-Motion>", on_drag_motion)
                widget.bind("<ButtonRelease-1>", on_drag_end)

        refresh_positions()

        # Bottoni inferiori
        bottom_box = ctk.CTkFrame(outer, fg_color="transparent")
        bottom_box.pack(fill="x")

        def save():
            final_layout = [ch for ch in temp_layout if chart_vars[ch].get()]
            self.db.set_setting("dashboard_layout", json.dumps(final_layout))
            self._apply_layout()
            top.destroy()

        ctk.CTkButton(
            bottom_box,
            text="Annulla",
            command=top.destroy,
            fg_color="#374151",
            hover_color="#4b5563",
            width=90,
        ).pack(side="left")

        ctk.CTkButton(
            bottom_box,
            text="Salva Layout",
            command=save,
            font=("Segoe UI", 12, "bold"),
            width=130,
        ).pack(side="right")

    def refresh(self) -> None:
        """Aggiorna i dati KPI e ridisegna i grafici."""
        totals = self.db.totals()
        self.kpi_vars["invested"].set(money(totals["committed_total"]))
        self.kpi_vars["stock_val"].set(f"{money(totals['stock_total'])} ({totals['stock_count']} pz)")
        self.kpi_vars["profit_tot"].set(money(totals["sold_profit"]))
        self.kpi_vars["roi_avg"].set(f"{totals['sold_roi']:.1f}% ({totals['sold_count']} v.)")
        self._draw_monthly_chart()
        self._draw_distribution_chart(totals)
        self._draw_platform_pie_chart()
        self._draw_monthly_volume_chart()
        self._draw_top_products_chart()

    def _draw_monthly_chart(self, retry_count: int = 0) -> None:
        canvas = self.canvas_monthly
        canvas.delete("all")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 50 or height < 50:
            if not self.winfo_viewable():
                return
            if retry_count < 5:
                self.after(100, lambda: self._draw_monthly_chart(retry_count + 1))
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
        max_profit = max((s["profit"] for s in sales), default=Decimal(0))
        min_profit = min((s["profit"] for s in sales), default=Decimal(0))
        max_profit = max(max_profit, Decimal(10))
        min_profit = min(min_profit, Decimal(0))
        profit_range = max_profit - min_profit
        num_bars = len(sales)
        bar_gap = 14
        bar_width = max(20, min(70, (plot_width - (num_bars + 1) * bar_gap) / max(num_bars, 1)))
        for i in range(4):
            y_val = margin_top + plot_height * (i / 3)
            profit_val = max_profit - profit_range * (Decimal(i) / Decimal(3))
            canvas.create_line(margin_left, y_val, width - margin_right, y_val, fill=DARK_THEME["border"], dash=(2, 2))
            canvas.create_text(margin_left - 8, y_val, text=f"€{int(profit_val)}", anchor="e", fill=DARK_THEME["fg_muted"], font=("Segoe UI", 9, "bold"))
        zero_y = margin_top + float(max_profit / profit_range) * plot_height
        for idx, item in enumerate(sales):
            x0 = margin_left + bar_gap + idx * (bar_width + bar_gap)
            x1 = x0 + bar_width
            profit = item["profit"]
            y_profit = margin_top + float((max_profit - profit) / profit_range) * plot_height
            y0 = min(zero_y, y_profit)
            y1 = max(zero_y, y_profit)
            bar_color = "#ef4444" if profit < 0 else CHART_PALETTE[idx % len(CHART_PALETTE)]
            canvas.create_rectangle(x0, y0, x1, y1, fill=bar_color, outline=bar_color, width=1)
            
            month_label = format_month_label(item["month"])
            canvas.create_text((x0 + x1) / 2, y1 + 16, text=month_label, fill=DARK_THEME["fg_main"], font=("Segoe UI", 10, "bold"))
            if bar_width >= 25:
                canvas.create_text((x0 + x1) / 2, y0 - 8, text=f"€{int(profit)}", fill=DARK_THEME["fg_main"], font=("Segoe UI", 9, "bold"))

    def _draw_distribution_chart(self, totals: dict[str, Any], retry_count: int = 0) -> None:
        canvas = self.canvas_dist
        canvas.delete("all")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 50 or height < 50:
            if not self.winfo_viewable():
                return
            if retry_count < 5:
                self.after(100, lambda: self._draw_distribution_chart(totals, retry_count + 1))
            return
        stock_c = totals["stock_count"]
        pre_c = totals["preorder_count"]
        active_c = totals.get("sold_count_active", 0)
        total = stock_c + pre_c + active_c
        if total == 0:
            canvas.create_text(width / 2, height / 2, text="Nessun articolo presente nel database.", fill=DARK_THEME["fg_muted"], font=("Segoe UI", 10))
            return
        categories = [
            ("In Magazzino", stock_c, "#059669"),
            ("Pre-ordini", pre_c, "#d97706"),
            ("Vendite Attive", active_c, "#2563eb"),
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
            canvas.create_rectangle(margin_x, start_y, margin_x + 18, start_y + 18, fill=color, outline="")
            canvas.create_text(margin_x + 28, start_y + 9, text=f"{label}: {count} pz ({pct:.1f}%)", anchor="w", fill=DARK_THEME["fg_main"], font=("Segoe UI", 11, "bold"))
            start_y += 35

    def _draw_platform_pie_chart(self, retry_count: int = 0) -> None:
        """Disegna il grafico a torta del profitto per piattaforma/canale di vendita con legenda percentuali."""
        canvas = self.canvas_platform
        canvas.delete("all")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 50 or height < 50:
            if not self.winfo_viewable():
                return
            if retry_count < 5:
                self.after(100, lambda: self._draw_platform_pie_chart(retry_count + 1))
            return

        platforms = self.db.get_profit_by_platform()
        positive_items = [p for p in platforms if p["profit"] > Decimal(0)]
        total_positive_profit = sum((p["profit"] for p in positive_items), Decimal(0))

        if not platforms or total_positive_profit <= Decimal(0):
            canvas.create_text(
                width / 2, height / 2,
                text="Nessun profitto registrato per canale di vendita.",
                fill=DARK_THEME["fg_muted"],
                font=("Segoe UI", 10)
            )
            return

        palette = CHART_PALETTE

        if len(positive_items) > 5:
            main_items = positive_items[:4]
            other_profit = sum((p["profit"] for p in positive_items[4:]), Decimal(0))
            other_count = sum(p["count"] for p in positive_items[4:])
            slices = main_items + [{
                "platform": "Altro",
                "profit": other_profit,
                "count": other_count
            }]
        else:
            slices = positive_items

        margin = 16
        pie_center_x = min(width * 0.30, 105 + margin)
        pie_center_y = height / 2
        radius = min(pie_center_x - margin, (height / 2) - margin, 85)
        radius = max(radius, 45)

        # Rendering della torta in Alta Definizione (Supersampling 4x con filtro Lanczos per anti-aliasing)
        img_size = int(radius * 2)
        scale = 4
        hi_res_size = img_size * scale

        pie_img = Image.new("RGBA", (hi_res_size, hi_res_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(pie_img)

        # In PIL gli angoli partono da ore 3 (0°) e avanzano in senso orario; ore 12 corrisponde a -90° (270°)
        current_deg = -90.0
        pad = 2 * scale
        bbox = [pad, pad, hi_res_size - pad, hi_res_size - pad]

        for idx, item in enumerate(slices):
            color = palette[idx % len(palette)]
            pct = float(item["profit"] / total_positive_profit)
            extent = pct * 360.0

            if extent >= 0.5:
                draw.pieslice(
                    bbox,
                    start=current_deg,
                    end=current_deg + extent,
                    fill=color,
                    outline=DARK_THEME["bg_card"],
                    width=2 * scale
                )
                current_deg += extent

        # Foro centrale donut in HD
        inner_r = (hi_res_size / 2) * 0.44
        center_pt = hi_res_size / 2
        inner_bbox = [
            center_pt - inner_r,
            center_pt - inner_r,
            center_pt + inner_r,
            center_pt + inner_r,
        ]
        draw.ellipse(inner_bbox, fill=DARK_THEME["bg_card"], outline=DARK_THEME["bg_card"])

        # Ricampionamento Lanczos per bordi ultra-definiti
        smooth_pie = pie_img.resize((img_size, img_size), resample=Image.Resampling.LANCZOS)
        self._pie_photo = ImageTk.PhotoImage(smooth_pie)

        canvas.create_image(pie_center_x, pie_center_y, image=self._pie_photo, anchor="center")

        legend_x = max(pie_center_x + radius + 18, width * 0.38)
        item_height = 32
        legend_y_start = max(16, (height - (len(slices) * item_height)) / 2)

        for idx, item in enumerate(slices):
            color = palette[idx % len(palette)]
            pct = float(item["profit"] / total_positive_profit)

            cur_y = legend_y_start + idx * item_height
            canvas.create_rectangle(
                legend_x, cur_y + 4,
                legend_x + 14, cur_y + 18,
                fill=color,
                outline=""
            )
            plat_name = str(item["platform"])
            if len(plat_name) > 16:
                plat_name = plat_name[:14] + "..."

            canvas.create_text(
                legend_x + 22, cur_y + 11,
                text=plat_name,
                anchor="w",
                fill=DARK_THEME["fg_main"],
                font=("Segoe UI", 10, "bold")
            )
            val_text = f"{money(item['profit'])}  ({pct * 100:.1f}%)"
            canvas.create_text(
                width - 18, cur_y + 11,
                text=val_text,
                anchor="e",
                fill=DARK_THEME["fg_muted"],
                font=("Segoe UI", 10, "bold")
            )

    def _draw_monthly_volume_chart(self, retry_count: int = 0) -> None:
        """Disegna la distribuzione del volume di pezzi venduti per mese nello stesso stile della ripartizione inventario."""
        canvas = self.canvas_volume
        canvas.delete("all")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 50 or height < 50:
            if not self.winfo_viewable():
                return
            if retry_count < 5:
                self.after(100, lambda: self._draw_monthly_volume_chart(retry_count + 1))
            return

        sales = self.db.get_monthly_sales()
        valid_sales = [s for s in sales if s.get("count", 0) > 0]
        total_qty = sum(s["count"] for s in valid_sales)

        if not valid_sales or total_qty == 0:
            canvas.create_text(
                width / 2, height / 2,
                text="Nessuna vendita registrata con data di vendita.",
                fill=DARK_THEME["fg_muted"],
                font=("Segoe UI", 10)
            )
            return

        sorted_recent = sorted(valid_sales, key=lambda s: s["month"], reverse=True)

        if len(sorted_recent) > 5:
            main_months = sorted_recent[:4]
            other_qty = sum(s["count"] for s in sorted_recent[4:])
            items_to_show = main_months + [{
                "month": "Mesi prec.",
                "count": other_qty
            }]
        else:
            items_to_show = sorted_recent

        # Mappa univoca 1:1 di ogni elemento visualizzato al rispettivo colore dedicato
        item_colors = {}
        for idx, it in enumerate(items_to_show):
            item_colors[it["month"]] = CHART_PALETTE[idx % len(CHART_PALETTE)]

        bar_y = 35
        bar_h = 24
        margin_x = 20
        avail_w = width - 2 * margin_x
        current_x = margin_x

        # Disegna la barra orizzontale superiore garantendo identici colori e corrispondenza
        for it in items_to_show:
            count = it["count"]
            if count > 0:
                seg_w = (count / total_qty) * avail_w
                color = item_colors.get(it["month"], CHART_PALETTE[0])
                canvas.create_rectangle(current_x, bar_y, current_x + seg_w, bar_y + bar_h, fill=color, outline="")
                current_x += seg_w

        start_y = 85
        item_spacing = 30
        for item in items_to_show:
            color = item_colors.get(item["month"], CHART_PALETTE[0])
            month_key = item["month"]
            label_text = format_month_label(month_key) if month_key != "Mesi prec." else "Mesi prec."

            count = item["count"]
            pct = (count / total_qty * 100) if total_qty > 0 else 0

            canvas.create_rectangle(margin_x, start_y + 4, margin_x + 14, start_y + 18, fill=color, outline="")
            canvas.create_text(
                margin_x + 22, start_y + 11,
                text=label_text,
                anchor="w",
                fill=DARK_THEME["fg_main"],
                font=("Segoe UI", 10, "bold")
            )
            canvas.create_text(
                width - margin_x, start_y + 11,
                text=f"{count} pz  ({pct:.1f}%)",
                anchor="e",
                fill=DARK_THEME["fg_muted"],
                font=("Segoe UI", 10, "bold")
            )
            start_y += item_spacing

    def _draw_top_products_chart(self, retry_count: int = 0) -> None:
        """Disegna la classifica a barre orizzontali dei top prodotti per utile netto generato."""
        canvas = self.canvas_top_products
        canvas.delete("all")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 50 or height < 50:
            if not self.winfo_viewable():
                return
            if retry_count < 5:
                self.after(100, lambda: self._draw_top_products_chart(retry_count + 1))
            return

        top_products = self.db.get_top_profitable_products(limit=5)
        if not top_products:
            canvas.create_text(
                width / 2, height / 2,
                text="Nessun prodotto venduto con profitto registrato.",
                fill=DARK_THEME["fg_muted"],
                font=("Segoe UI", 10)
            )
            return

        max_profit = max((p["profit"] for p in top_products), default=Decimal(1))
        if max_profit <= 0:
            max_profit = Decimal(1)

        start_y = 14
        item_spacing = 42
        margin_left = 20
        margin_right = 20

        rank_colors = [
            "#f59e0b",  # 1° Oro
            "#94a3b8",  # 2° Argento
            "#d97706",  # 3° Bronzo
            "#64748b",  # 4° Ardesia
            "#64748b",  # 5° Ardesia
        ]

        for idx, item in enumerate(top_products):
            y = start_y + idx * item_spacing
            rank_color = rank_colors[idx % len(rank_colors)]

            # Badge posizione #1, #2...
            canvas.create_text(
                margin_left, y + 8,
                text=f"#{idx + 1}",
                anchor="w",
                fill=rank_color,
                font=("Segoe UI", 10, "bold")
            )

            # Nome Prodotto
            prod_name = str(item["name"])
            if len(prod_name) > 28:
                prod_name = prod_name[:26] + "..."

            canvas.create_text(
                margin_left + 28, y + 8,
                text=prod_name,
                anchor="w",
                fill=DARK_THEME["fg_main"],
                font=("Segoe UI", 10, "bold")
            )

            # Profitto in € e quantità
            profit_str = f"+ {money(item['profit'])}  ({item['count']} pz)"
            canvas.create_text(
                width - margin_right, y + 8,
                text=profit_str,
                anchor="e",
                fill="#10b981",
                font=("Segoe UI", 10, "bold")
            )

            # Barra orizzontale di avanzamento
            bar_track_y = y + 21
            bar_track_h = 6
            bar_x_start = margin_left + 28
            bar_max_w = width - margin_right - bar_x_start
            bar_fill_w = max(4, float(item["profit"] / max_profit) * bar_max_w)

            # Sfondo barra
            canvas.create_rectangle(
                bar_x_start, bar_track_y,
                width - margin_right, bar_track_y + bar_track_h,
                fill="#1f2937",
                outline=""
            )
            # Riempimento barra in verde smeraldo
            canvas.create_rectangle(
                bar_x_start, bar_track_y,
                bar_x_start + bar_fill_w, bar_track_y + bar_track_h,
                fill="#10b981",
                outline=""
            )