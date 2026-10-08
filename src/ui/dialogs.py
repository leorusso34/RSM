"""Finestre di dialogo per RSM."""

import sqlite3
import sys
import tkinter as tk
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from tkinter import messagebox
from typing import Any

import customtkinter as ctk
from PIL import Image

from ..config import DARK_THEME, PROJECT_DIR, STATUS_PREORDER, STATUS_SOLD, STATUS_STOCK
from ..utils import (
    apply_dark_titlebar,
    calculate_profit,
    center_window,
    money,
    parse_date,
    parse_int,
    parse_money,
)


class CTkScrollableDropdown:
    """
    Menu a tendina personalizzato con barra di scorrimento nativa e supporto
    completo per rotellina del mouse (scroll) per widget CTkComboBox.
    Sostituisce il menu popup standard di Tkinter per permettere lo scorrimento
    fluido degli elenchi lunghi (es. luoghi di acquisto/vendita).
    """

    def __init__(self, combo: ctk.CTkComboBox, max_height: int = 500) -> None:
        self.combo = combo
        self.max_height = max_height
        self._popup: tk.Toplevel | None = None
        self._scroll_frame: ctk.CTkScrollableFrame | None = None
        self._bind_click_id: str | None = None
        self._bind_esc_id: str | None = None
        self._bind_wheel_id: str | None = None
        self._bind_conf_id: str | None = None

        self.combo._open_dropdown_menu = self.open
        if hasattr(self.combo, "_dropdown_menu") and self.combo._dropdown_menu:
            self.combo._dropdown_menu.close = self.close

        if hasattr(self.combo, "_entry") and self.combo._entry:
            self.combo._entry.bind("<Down>", lambda _e: self.open(), add="+")

        self.combo.bind("<Destroy>", lambda _e: self.close(), add="+")

    def is_open(self) -> bool:
        return bool(self._popup and self._popup.winfo_exists())

    def open(self) -> None:
        if self.is_open():
            self.close()
            return

        raw_values = getattr(self.combo, "_values", None) or self.combo.cget("values") or []
        seen = set()
        values = []
        for v in raw_values:
            s = str(v).strip()
            if s and s not in seen:
                seen.add(s)
                values.append(s)

        if not values:
            return

        self.combo.update_idletasks()
        rx = self.combo.winfo_rootx()
        ry = self.combo.winfo_rooty()
        ch = self.combo.winfo_height()
        cw = self.combo.winfo_width()

        w = max(cw, 180)
        item_h = 28
        padding = 10
        needed_h = len(values) * (item_h + 2) + padding
        h = min(needed_h, self.max_height)

        screen_h = self.combo.winfo_screenheight()
        screen_w = self.combo.winfo_screenwidth()

        space_below = max(0, screen_h - (ry + ch + 15))
        space_above = max(0, ry - 15)

        # Se verso il basso sfora lo schermo, valuta se posizionarlo sopra o adattare l'altezza
        if ry + ch + h + 10 > screen_h:
            if space_above > space_below and space_above >= 180:
                h = min(h, space_above)
                y = ry - h - 2
            else:
                h = min(h, space_below)
                y = ry + ch + 2
        else:
            y = ry + ch + 2

        x = rx
        if x + w > screen_w - 10:
            x = max(10, screen_w - w - 10)

        self._popup = tk.Toplevel(self.combo)
        self._popup.overrideredirect(True)
        self._popup.attributes("-topmost", True)
        self._popup.geometry(f"{w}x{h}+{x}+{y}")

        c = DARK_THEME
        outer = ctk.CTkFrame(
            self._popup,
            fg_color=c["bg_card"],
            border_width=1,
            border_color="#334155",
            corner_radius=8,
        )
        outer.pack(fill="both", expand=True)

        self._scroll_frame = ctk.CTkScrollableFrame(
            outer,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=c.get("fg_subtle", "#475569"),
            scrollbar_button_hover_color=c.get("fg_muted", "#8b9bb4"),
        )
        self._scroll_frame.pack(fill="both", expand=True, padx=2, pady=2)

        current_val = self.combo.get().strip()
        target_idx = None

        for idx, val in enumerate(values):
            is_selected = (val == current_val)
            if is_selected:
                target_idx = idx

            btn = ctk.CTkButton(
                self._scroll_frame,
                text=val,
                anchor="w",
                height=item_h,
                fg_color=c["accent"] if is_selected else "transparent",
                hover_color=c["accent_hover"],
                text_color="#ffffff" if is_selected else c["fg_main"],
                font=("Segoe UI", 12),
                corner_radius=4,
                command=lambda v=val: self._select(v),
            )
            btn.pack(fill="x", pady=1, padx=2)

        if target_idx is not None and len(values) > 1:
            fraction = max(0.0, min(1.0, (target_idx - 1) / max(len(values), 1)))
            self._popup.after(20, lambda f=fraction: self._scroll_to(f))

        top = self.combo.winfo_toplevel()
        self._bind_click_id = top.bind("<ButtonPress-1>", self._on_outside_click, add="+")
        self._bind_esc_id = top.bind("<Escape>", lambda _e: self.close(), add="+")
        self._bind_wheel_id = top.bind("<MouseWheel>", self._on_outside_scroll, add="+")
        self._bind_conf_id = top.bind("<Configure>", self._on_parent_configure, add="+")

        self.combo._close_on_next_click = True

    def _scroll_to(self, fraction: float) -> None:
        if self.is_open() and self._scroll_frame:
            try:
                self._scroll_frame._parent_canvas.yview_moveto(fraction)
            except (tk.TclError, AttributeError):
                pass

    def _select(self, val: str) -> None:
        self.combo.set(val)
        if hasattr(self.combo, "_command") and self.combo._command:
            self.combo._command(val)
        self.close()

    def _on_outside_click(self, event) -> None:
        if not self.is_open():
            return
        px, py = event.x_root, event.y_root
        x1 = self._popup.winfo_rootx()
        y1 = self._popup.winfo_rooty()
        x2 = x1 + self._popup.winfo_width()
        y2 = y1 + self._popup.winfo_height()

        cx1 = self.combo.winfo_rootx()
        cy1 = self.combo.winfo_rooty()
        cx2 = cx1 + self.combo.winfo_width()
        cy2 = cy1 + self.combo.winfo_height()

        if not (x1 <= px <= x2 and y1 <= py <= y2) and not (cx1 <= px <= cx2 and cy1 <= py <= cy2):
            self.close()

    def _on_outside_scroll(self, event) -> None:
        if not self.is_open():
            return
        px, py = event.x_root, event.y_root
        x1 = self._popup.winfo_rootx()
        y1 = self._popup.winfo_rooty()
        x2 = x1 + self._popup.winfo_width()
        y2 = y1 + self._popup.winfo_height()
        if not (x1 <= px <= x2 and y1 <= py <= y2):
            self.close()

    def _on_parent_configure(self, event) -> None:
        if not self.is_open():
            return
        if event.widget == self.combo.winfo_toplevel():
            self.close()

    def close(self) -> None:
        if self.is_open():
            try:
                top = self.combo.winfo_toplevel()
                if self._bind_click_id:
                    top.unbind("<ButtonPress-1>", self._bind_click_id)
                    self._bind_click_id = None
                if self._bind_esc_id:
                    top.unbind("<Escape>", self._bind_esc_id)
                    self._bind_esc_id = None
                if self._bind_wheel_id:
                    top.unbind("<MouseWheel>", self._bind_wheel_id)
                    self._bind_wheel_id = None
                if self._bind_conf_id:
                    top.unbind("<Configure>", self._bind_conf_id)
                    self._bind_conf_id = None
            except (tk.TclError, AttributeError):
                pass
            try:
                self._popup.destroy()
            except (tk.TclError, AttributeError):
                pass
        self._popup = None
        if hasattr(self.combo, "_close_on_next_click"):
            self.combo._close_on_next_click = False


class ProductDialog(ctk.CTkToplevel):
    """Finestra di dialogo per la creazione o modifica di un singolo prodotto."""

    def __init__(
        self,
        parent: tk.Misc,
        initial_status: str,
        autocomplete_places: tuple[list[str], list[str]] = ([], []),
        record: sqlite3.Row | None = None,
    ) -> None:
        super().__init__(parent, fg_color=DARK_THEME["bg_main"])
        self.result: dict[str, Any] | None = None
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
            "quantity": tk.StringVar(value=str(rec["quantity"]) if rec and "quantity" in rec else "1"),
            "purchased_price": tk.StringVar(value=f'{rec["purchased_price"]:.2f}'.replace(".", ",") if rec else ""),
            "purchased_place": tk.StringVar(value=rec["purchased_place"] if rec else ""),
            "selling_place": tk.StringVar(value=rec["selling_place"] if rec else ""),
            "selling_price": tk.StringVar(
                value=f'{rec["selling_price"]:.2f}'.replace(".", ",") if rec and rec["selling_price"] is not None else ""
            ),
            "sold_price": tk.StringVar(
                value=f'{rec["sold_price"]:.2f}'.replace(".", ",") if rec and "sold_price" in rec and rec["sold_price"] is not None else ""
            ),
            "fees": tk.StringVar(
                value=f'{rec["fees"]:.2f}'.replace(".", ",") if rec and "fees" in rec and rec["fees"] is not None else "0,00"
            ),
            "sold_date": tk.StringVar(
                value=rec["sold_date"] if rec and "sold_date" in rec and rec["sold_date"] else ""
            ),
            "status": tk.StringVar(value=rec["status"] if rec else initial_status),
            "release_date": tk.StringVar(value=rec["release_date"] if rec else ""),
        }

        self.profit_info_var = tk.StringVar(value="-")

        # Carica icona ingranaggio per gestione luoghi di vendita
        gear_path = Path(getattr(sys, "_MEIPASS", PROJECT_DIR)) / "assets" / "settings_icon.png"
        if not gear_path.exists():
            gear_path = PROJECT_DIR / "assets" / "settings_icon.png"

        self._gear_img_muted = None
        self._gear_img_hover = None
        if gear_path.exists():
            try:
                pil_gear = Image.open(gear_path).convert("RGBA")
                _, _, _, ga = pil_gear.split()

                # Versione muted (#8b9bb4)
                muted_pil = Image.new("RGBA", pil_gear.size, (139, 155, 180, 255))
                muted_pil.putalpha(ga)
                self._gear_img_muted = ctk.CTkImage(light_image=muted_pil, dark_image=muted_pil, size=(13, 13))

                # Versione hover (#f1f5f9)
                hover_pil = Image.new("RGBA", pil_gear.size, (241, 245, 249, 255))
                hover_pil.putalpha(ga)
                self._gear_img_hover = ctk.CTkImage(light_image=hover_pil, dark_image=hover_pil, size=(13, 13))
            except (OSError, ValueError):
                pass

        self._build()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", self._on_return)
        self.bind("<KP_Enter>", self._on_return)
        self.bind("<Control-Return>", lambda _e: self._submit())
        self.bind("<Command-Return>", lambda _e: self._submit())
        self.after(80, self._focus_name)

    def _on_return(self, event=None) -> str | None:
        """Salva il prodotto alla pressione del tasto Invio (lascia il comportamento a capo solo se l'utente e nel box Note)."""
        if event and hasattr(self, "notes") and self.notes:
            textbox = getattr(self.notes, "_textbox", None)
            if event.widget == textbox:
                return None
        self._submit()
        return "break"

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
            text="Compila i dati del prodotto",
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
        self.name_entry = self._field_entry(form, "NOME PRODOTTO", "name", 0, 0, span=2)
        self._field_entry(form, "TAGLIA", "size", 1, 0)
        self._field_entry(form, "QUANTITA", "quantity", 1, 1)

        self._field_entry(form, "PREZZO ACQUISTO (€)", "purchased_price", 2, 0)
        self._field_combo(form, "LUOGO ACQUISTO", "purchased_place", self.purchased_places, 2, 1)

        # Selling place con ingranaggio
        lbl_frame = ctk.CTkFrame(form, fg_color="transparent")
        lbl_frame.grid(row=6, column=0, sticky="w", padx=(0, 6), pady=(8, 2))

        ctk.CTkLabel(lbl_frame, text="LUOGO VENDITA", font=("Segoe UI", 11, "bold")).pack(side="left")
        if self._gear_img_muted:
            gear_lbl = ctk.CTkLabel(lbl_frame, text="", image=self._gear_img_muted, cursor="hand2")
            gear_lbl.pack(side="left", padx=(6, 0))
            gear_lbl.bind("<Button-1>", lambda _e: self._open_manage_places())
            gear_lbl.bind("<Enter>", lambda _e: gear_lbl.configure(image=self._gear_img_hover))
            gear_lbl.bind("<Leave>", lambda _e: gear_lbl.configure(image=self._gear_img_muted))
        else:
            gear_lbl = ctk.CTkLabel(lbl_frame, text="⚙", font=("Segoe UI", 12), text_color=c["fg_muted"], cursor="hand2")
            gear_lbl.pack(side="left", padx=(6, 0))
            gear_lbl.bind("<Button-1>", lambda _e: self._open_manage_places())
            gear_lbl.bind("<Enter>", lambda _e: gear_lbl.configure(text_color=c["fg_main"]))
            gear_lbl.bind("<Leave>", lambda _e: gear_lbl.configure(text_color=c["fg_muted"]))

        self.selling_place_combo = ctk.CTkComboBox(form, variable=self.vars["selling_place"], values=self.selling_places, font=("Segoe UI", 12))
        self.selling_place_combo.grid(row=7, column=0, sticky="ew", padx=(0, 6))
        CTkScrollableDropdown(self.selling_place_combo)

        self._field_entry(form, "PREZZO VENDITA TOTALE (€)", "selling_price", 3, 1)

        # Stato
        self.lbl_status_lbl = ctk.CTkLabel(form, text="STATO PRODOTTO ", font=("Segoe UI", 11, "bold"))
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
        #ctk.CTkLabel(self.profit_card, text="CALCOLO PROFITTO NETTO E ROI", font=("Segoe UI", 10, "bold"), text_color=c["fg_muted"]).pack(anchor="w", padx=12, pady=(10, 0))
        ctk.CTkLabel(self.profit_card, textvariable=self.profit_info_var, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(2, 10))

        # Note
        ctk.CTkLabel(form, text="NOTE", font=("Segoe UI", 11, "bold")).grid(row=15, column=0, columnspan=2, sticky="w", pady=(10, 4))
        self.notes = ctk.CTkTextbox(form, height=80, font=("Segoe UI", 12), wrap="word")
        self.notes.grid(row=16, column=0, columnspan=2, sticky="nsew")
        if self.record:
            self.notes.insert("1.0", self.record["notes"])

        # Tracciamento profitto live
        for key in ("purchased_price", "selling_price", "sold_price", "fees", "quantity"):
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

    def _field_combo(self, parent: tk.Widget, label: str, key: str, values: list[str], group_row: int, column: int):
        l_row = group_row * 2
        e_row = l_row + 1
        px = (0, 6) if column == 0 else (6, 0)
        ctk.CTkLabel(parent, text=label, font=("Segoe UI", 11, "bold")).grid(
            row=l_row, column=column, sticky="w", padx=px, pady=(8, 2)
        )
        combo = ctk.CTkComboBox(parent, variable=self.vars[key], values=values, font=("Segoe UI", 12))
        combo.grid(row=e_row, column=column, sticky="ew", padx=px)
        CTkScrollableDropdown(combo)
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
        c = DARK_THEME
        if st == STATUS_SOLD:
            self.entry_fees.configure(state="normal")
            self.entry_sold_date.configure(state="normal")
            self.lbl_fees.configure(text_color=c["fg_main"])
            self.lbl_sold_date.configure(text_color=c["fg_main"])
            self.profit_card.grid()
            if not self.vars["sold_date"].get():
                self.vars["sold_date"].set(datetime.now(tz=timezone.utc).astimezone().date().isoformat())
        elif st == STATUS_PREORDER:
            self.entry_fees.configure(state="disabled")
            self.entry_sold_date.configure(state="disabled")
            self.lbl_fees.configure(text_color=c["fg_muted"])
            self.lbl_sold_date.configure(text_color=c["fg_muted"])
            self.profit_card.grid_remove()
            self.vars["fees"].set("0,00")
            self.vars["sold_date"].set("")
        else:
            self.entry_fees.configure(state="disabled")
            self.entry_sold_date.configure(state="disabled")
            self.lbl_fees.configure(text_color=c["fg_muted"])
            self.lbl_sold_date.configure(text_color=c["fg_muted"])
            self.profit_card.grid_remove()
            self.vars["fees"].set("0,00")
            self.vars["sold_date"].set("")
        self._update_profit_preview()

    def _update_profit_preview(self) -> None:
        try:
            buy = parse_money(self.vars["purchased_price"].get(), allow_empty=True) or Decimal(0)
            sold = parse_money(self.vars["selling_price"].get(), allow_empty=True)
            fees = parse_money(self.vars["fees"].get(), allow_empty=True) or Decimal(0)
            qty = parse_int(self.vars["quantity"].get(), 1)
            if sold is not None and buy >= 0:
                profit, roi = calculate_profit(buy, sold, fees, qty)
                prefix = "+" if profit >= 0 else ""
                roi_str = f"{roi:.1f}%" if buy > 0 else "-"
                self.profit_info_var.set(f"Profitto Netto Totale: {prefix}{money(profit)}   |   ROI: {roi_str}")
            else:
                self.profit_info_var.set("Inserisci il prezzo di vendita per calcolare profitto e ROI.")
        except (ValueError, TypeError, ArithmeticError):
            self.profit_info_var.set("Impossibile calcolare il profitto con i dati correnti.")

    def _submit(self) -> None:
        try:
            name = self.vars["name"].get().strip()
            if not name:
                raise ValueError("Il nome del prodotto e obbligatorio.")
            qty = parse_int(self.vars["quantity"].get(), 1)
            purchase = parse_money(self.vars["purchased_price"].get())
            sale = parse_money(self.vars["selling_price"].get(), allow_empty=True)
            fees = parse_money(self.vars["fees"].get(), allow_empty=True) or Decimal(0)
            st = self.vars["status"].get()
            sold = sale if st == STATUS_SOLD else None
            if st == STATUS_SOLD and sold is None:
                raise ValueError("Per i prodotti venduti e obbligatorio inserire il Prezzo di Vendita.")
            rec_rd = self.record.get("release_date", "") if self.record and "release_date" in self.record and self.record["release_date"] else ""
            release_date = parse_date(rec_rd)
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
            "release_date": release_date,
            "notes": self.notes.get("1.0", "end").strip(),
        }
        self.destroy()


class BulkStatusDialog(ctk.CTkToplevel):
    """Finestra di dialogo per la modifica di massa dello stato dei prodotti selezionati."""

    def __init__(
        self,
        parent: tk.Misc,
        count: int,
        target_status: str,
        selling_places: list[str] | None = None,
        default_place: str = "",
    ) -> None:
        super().__init__(parent, fg_color=DARK_THEME["bg_main"])
        self.result: dict[str, Any] | None = None
        self.count = count
        self.target_status = target_status

        if selling_places is not None:
            self.selling_places = list(selling_places)
        else:
            parent_db = getattr(parent, "db", None)
            if parent_db:
                _, self.selling_places = parent_db.get_distinct_places()
            else:
                from ..config import DEFAULT_SELLING_PLACES
                self.selling_places = list(DEFAULT_SELLING_PLACES)

        if not default_place and self.selling_places:
            default_place = self.selling_places[0]

        self.title("Spostamento di massa")
        center_window(self, 520, 460)
        self.minsize(500, 440)
        self.transient(parent)
        self.grab_set()
        apply_dark_titlebar(self)

        self.var_sold_price = tk.StringVar()
        self.var_fees = tk.StringVar(value="0,00")
        self.var_selling_place = tk.StringVar(value=default_place)

        self._build()
        self.bind("<Return>", lambda _e: self._submit())
        self.bind("<Escape>", lambda _e: self.destroy())

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

            ctk.CTkLabel(form, text="Luogo di vendita:", font=("Segoe UI", 11, "bold")).pack(anchor="w")
            combo_place = ctk.CTkComboBox(
                form,
                variable=self.var_selling_place,
                values=self.selling_places,
                font=("Segoe UI", 12),
            )
            combo_place.pack(fill="x", pady=(2, 10))
            CTkScrollableDropdown(combo_place)

        buttons = ctk.CTkFrame(outer, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", pady=(20, 0))
        ctk.CTkButton(buttons, text="Annulla", command=self.destroy, fg_color="#374151", hover_color="#4b5563").pack(side="right")
        ctk.CTkButton(buttons, text="Conferma Spostamento", command=self._submit).pack(side="right", padx=(0, 10))

    def _submit(self) -> None:
        extra = {}
        if self.target_status == STATUS_SOLD:
            try:
                sp_total = parse_money(self.var_sold_price.get(), allow_empty=True)
                fees_total = parse_money(self.var_fees.get(), allow_empty=True) or Decimal(0)
                if sp_total is None:
                    raise ValueError("Per i prodotti venduti e obbligatorio il prezzo di vendita totale.")
                selling_place = self.var_selling_place.get().strip()
                count_dec = Decimal(str(self.count))
                extra["sold_price"] = (sp_total / count_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if self.count > 0 else sp_total
                extra["fees"] = (fees_total / count_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if self.count > 0 else fees_total
                extra["sold_date"] = datetime.now(tz=timezone.utc).astimezone().date().isoformat()
                extra["selling_place"] = selling_place
                import uuid
                extra["bundle_id"] = str(uuid.uuid4())
            except ValueError as exc:
                messagebox.showerror("Valori non validi", str(exc), parent=self)
                return
        self.result = extra
        self.destroy()


class PartialStockMoveDialog(ctk.CTkToplevel):
    """
    Finestra per scegliere quante unità di un prodotto spostare in magazzino.
    Mostra una combobox con i valori da 1 alla quantità massima disponibile,
    con la quantità massima preselezionata di default.
    """

    def __init__(self, parent: tk.Misc, product_name: str, max_qty: int) -> None:
        super().__init__(parent, fg_color=DARK_THEME["bg_main"])
        self.result: int | None = None
        self.max_qty = max_qty

        self.title("Sposta in Magazzino")
        center_window(self, 420, 265)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        apply_dark_titlebar(self)

        self._build(product_name, max_qty)
        self.bind("<Return>", lambda _e: self._submit())
        self.bind("<Escape>", lambda _e: self.destroy())

    def _build(self, product_name: str, max_qty: int) -> None:
        c = DARK_THEME
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=26, pady=22)

        ctk.CTkLabel(
            outer,
            text="Sposta in Magazzino",
            font=("Segoe UI", 15, "bold"),
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            outer,
            text=product_name,
            font=("Segoe UI", 12),
            text_color=c["fg_muted"],
            anchor="w",
        ).pack(fill="x", pady=(2, 14))

        ctk.CTkLabel(
            outer,
            text=f"Quantità disponibile: {max_qty} pz",
            font=("Segoe UI", 11),
            text_color=c["fg_muted"],
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(
            outer,
            text="Quantità da spostare in magazzino:",
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self.var_qty = tk.StringVar(value=str(max_qty))
        combo = ctk.CTkComboBox(
            outer,
            variable=self.var_qty,
            values=[str(i) for i in range(1, max_qty + 1)],
            font=("Segoe UI", 12),
            state="readonly",
        )
        combo.pack(fill="x", pady=(0, 4))
        combo.focus_set()

        buttons = ctk.CTkFrame(outer, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", pady=(16, 0))
        ctk.CTkButton(
            buttons,
            text="Annulla",
            command=self.destroy,
            fg_color="#374151",
            hover_color="#4b5563",
        ).pack(side="right")
        ctk.CTkButton(
            buttons,
            text="Conferma Spostamento",
            command=self._submit,
            fg_color=DARK_THEME["accent"],
            hover_color=DARK_THEME["accent_hover"],
            font=("Segoe UI", 12, "bold"),
        ).pack(side="right", padx=(0, 10))

    def _submit(self) -> None:
        try:
            qty = int(self.var_qty.get())
            if qty < 1 or qty > self.max_qty:
                raise ValueError()
        except ValueError:
            return
        self.result = qty
        self.destroy()


class ManagePlacesDialog(ctk.CTkToplevel):
    """Finestra per la gestione dei luoghi di vendita."""

    def __init__(self, parent: tk.Misc, db: Any, current_places: list[str], on_update: callable) -> None:
        super().__init__(parent, fg_color=DARK_THEME["bg_main"])
        self.db = db
        self.current_places = current_places
        self.on_update = on_update
        self.selected_place: str | None = None
        self._place_widgets: dict[str, ctk.CTkButton] = {}

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

        ctk.CTkButton(input_frame, text="Aggiungi", command=self._add_place).pack(side="right")

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