#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finestra di dialogo per la sincronizzazione ordini via email Gmail."""

import threading
import tkinter as tk
from tkinter import ttk, messagebox
from decimal import Decimal
from typing import Any, Dict, List, Optional
import customtkinter as ctk

from ..config import DARK_THEME, STATUS_PREORDER
from ..email_sync import (
    fetch_unread_order_emails,
    mark_emails_as_read,
    parse_order_email_with_gemini,
    test_gmail_connection,
)
from ..utils import apply_dark_titlebar, apply_window_icon, center_window, money, parse_money


class EmailSyncDialog(ctk.CTkToplevel):
    """Dialogo moderno per la gestione e sincronizzazione degli ordini via email Gmail."""

    def __init__(self, parent: tk.Misc, db: Any, on_success_callback: callable) -> None:
        super().__init__(parent, fg_color=DARK_THEME["bg_main"])
        self.db = db
        self.on_success_callback = on_success_callback
        self.extracted_products: List[Dict[str, Any]] = []
        self.processed_uids: List[str] = []
        self.is_scanning = False

        self.title("Sincronizzazione Email Ordini")
        center_window(self, 860, 660)
        self.minsize(780, 560)
        self.transient(parent)
        self.grab_set()
        apply_dark_titlebar(self)

        # Variabili
        self.var_email = tk.StringVar(value=self.db.get_setting("email_sync_address", ""))
        self.var_password = tk.StringVar(value=self.db.get_setting("email_sync_app_password", ""))
        self.var_api_key = tk.StringVar(value=self.db.get_setting("gemini_api_key", ""))
        self.var_status_msg = tk.StringVar(value="Pronto per la scansione delle email.")
        self.var_show_pass = tk.BooleanVar(value=False)

        self._build()

    def _build(self) -> None:
        c = DARK_THEME
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=22, pady=18)

        # Header
        head_box = ctk.CTkFrame(container, fg_color="transparent")
        head_box.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(head_box, text="Sincronizzazione Ordini via Email", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ctk.CTkLabel(
            head_box,
            text="Scarica le conferme d'ordine non lette da Gmail ed estrai i prodotti nei Pre-ordini con Gemini AI.",
            font=("Segoe UI", 12),
            text_color=c["fg_muted"],
        ).pack(anchor="w", pady=(2, 0))

        # Box Impostazioni Credenziali (Collassabile o Card compatta)
        self.config_card = ctk.CTkFrame(container, fg_color=c["bg_card"], corner_radius=10, border_width=1, border_color=c["border"])
        self.config_card.pack(fill="x", pady=(0, 12))

        cfg_inner = ctk.CTkFrame(self.config_card, fg_color="transparent")
        cfg_inner.pack(fill="x", padx=14, pady=10)

        # Riga 1: Email + Password per le app
        r1 = ctk.CTkFrame(cfg_inner, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(r1, text="Email Gmail:", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 6))
        self.ent_email = ctk.CTkEntry(r1, textvariable=self.var_email, placeholder_text="esempio@gmail.com", width=210, font=("Segoe UI", 12))
        self.ent_email.pack(side="left", padx=(0, 14))

        ctk.CTkLabel(r1, text="Password App (16 car.):", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 6))
        self.ent_pass = ctk.CTkEntry(r1, textvariable=self.var_password, placeholder_text="abcd efgh ijkl mnop", show="*", width=170, font=("Segoe UI", 12))
        self.ent_pass.pack(side="left", padx=(0, 8))

        ctk.CTkCheckBox(r1, text="Mostra", variable=self.var_show_pass, command=self._toggle_pass_visibility, width=70, font=("Segoe UI", 11)).pack(side="left", padx=(0, 10))

        # Riga 2: Chiave Gemini API + Bottoni Configurazione
        r2 = ctk.CTkFrame(cfg_inner, fg_color="transparent")
        r2.pack(fill="x", pady=(4, 0))

        ctk.CTkLabel(r2, text="API Key Gemini:", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 6))
        self.ent_api = ctk.CTkEntry(r2, textvariable=self.var_api_key, placeholder_text="AIzaSy...", show="*", width=210, font=("Segoe UI", 12))
        self.ent_api.pack(side="left", padx=(0, 14))

        ctk.CTkButton(r2, text="Test Connessione", command=self._test_connection, fg_color="#374151", hover_color="#4b5563", width=120, font=("Segoe UI", 11)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(r2, text="Salva Dati", command=self._save_credentials, fg_color="#374151", hover_color="#4b5563", width=90, font=("Segoe UI", 11)).pack(side="left")

        # Barra di Scansione & Azioni
        scan_bar = ctk.CTkFrame(container, fg_color="transparent")
        scan_bar.pack(fill="x", pady=(4, 8))

        self.btn_scan = ctk.CTkButton(
            scan_bar,
            text="Avvia Scansione Email Non Lette",
            command=self._start_email_scan,
            font=("Segoe UI", 12, "bold"),
            height=34,
        )
        self.btn_scan.pack(side="left", padx=(0, 14))

        self.lbl_status = ctk.CTkLabel(scan_bar, textvariable=self.var_status_msg, font=("Segoe UI", 11), text_color=c["fg_muted"])
        self.lbl_status.pack(side="left", fill="x", expand=True)

        self.progress_bar = ctk.CTkProgressBar(container, height=6, mode="indeterminate")

        # Tabella Anteprima Prodotti Trovati
        table_card = ctk.CTkFrame(container, fg_color=c["bg_card"], corner_radius=10, border_width=1, border_color=c["border"])
        table_card.pack(fill="both", expand=True, pady=(4, 12))

        columns = ("name", "size", "quantity", "price", "store", "date")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("name", text="PRODOTTO RILEVATO", anchor="w")
        self.tree.heading("size", text="TAGLIA", anchor="center")
        self.tree.heading("quantity", text="Q.TÀ", anchor="center")
        self.tree.heading("price", text="PREZZO (€)", anchor="center")
        self.tree.heading("store", text="NEGOZIO / SITO", anchor="w")
        self.tree.heading("date", text="DATA ORDINE", anchor="center")

        self.tree.column("name", width=270, anchor=tk.W)
        self.tree.column("size", width=65, anchor=tk.CENTER)
        self.tree.column("quantity", width=55, anchor=tk.CENTER)
        self.tree.column("price", width=95, anchor=tk.CENTER)
        self.tree.column("store", width=140, anchor=tk.W)
        self.tree.column("date", width=95, anchor=tk.CENTER)

        yscroll = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)
        yscroll.pack(side="right", fill="y", padx=(0, 2), pady=2)

        # Barra inferiore con pulsante Salva
        bottom_bar = ctk.CTkFrame(container, fg_color="transparent")
        bottom_bar.pack(fill="x")

        self.lbl_count_info = ctk.CTkLabel(bottom_bar, text="Nessun prodotto in attesa di importazione.", font=("Segoe UI", 11, "bold"), text_color=c["fg_muted"])
        self.lbl_count_info.pack(side="left")

        ctk.CTkButton(bottom_bar, text="Chiudi", command=self.destroy, fg_color="#374151", hover_color="#4b5563", width=90).pack(side="right")
        self.btn_save = ctk.CTkButton(
            bottom_bar,
            text="Salva Tutti nei Pre-ordini",
            command=self._save_all_to_preorders,
            fg_color="#059669",
            hover_color="#047857",
            font=("Segoe UI", 12, "bold"),
            width=200,
            state="disabled",
        )
        self.btn_save.pack(side="right", padx=(0, 10))

    def _toggle_pass_visibility(self) -> None:
        if self.var_show_pass.get():
            self.ent_pass.configure(show="")
        else:
            self.ent_pass.configure(show="*")

    def _save_credentials(self, notify: bool = True) -> bool:
        email_val = self.var_email.get().strip()
        pass_val = self.var_password.get().replace(" ", "").strip()
        api_val = self.var_api_key.get().strip()

        if not email_val or not pass_val:
            messagebox.showwarning("Dati incompleti", "Inserisci l'indirizzo Gmail e la Password per le App a 16 caratteri.", parent=self)
            return False

        self.db.set_setting("email_sync_address", email_val)
        self.db.set_setting("email_sync_app_password", pass_val)
        if api_val:
            self.db.set_setting("gemini_api_key", api_val)

        if notify:
            messagebox.showinfo("Salvataggio", "Credenziali salvate con successo nel database!", parent=self)
        return True

    def _test_connection(self) -> None:
        email_val = self.var_email.get().strip()
        pass_val = self.var_password.get().replace(" ", "").strip()
        if not email_val or not pass_val:
            messagebox.showwarning("Dati mancanti", "Compila prima Email e Password per le App.", parent=self)
            return

        self.var_status_msg.set("Verifica connessione a Gmail in corso...")
        self.update_idletasks()

        def _run_test():
            ok, msg = test_gmail_connection(email_val, pass_val)
            self.after(0, lambda: self._on_test_result(ok, msg))

        threading.Thread(target=_run_test, daemon=True).start()

    def _on_test_result(self, ok: bool, msg: str) -> None:
        if ok:
            self.var_status_msg.set("Connessione a Gmail stabilita con successo!")
            messagebox.showinfo("Connessione Riuscita", msg, parent=self)
        else:
            self.var_status_msg.set("Errore connessione a Gmail.")
            messagebox.showerror("Errore Connessione", msg, parent=self)

    def _start_email_scan(self) -> None:
        if self.is_scanning:
            return

        email_val = self.var_email.get().strip()
        pass_val = self.var_password.get().replace(" ", "").strip()
        api_key = self.var_api_key.get().strip()

        if not email_val or not pass_val:
            messagebox.showwarning("Credenziali mancanti", "Inserisci e salva prima le credenziali Gmail.", parent=self)
            return
        if not api_key:
            messagebox.showwarning("API Key mancante", "Inserisci la tua Chiave API Gemini per analizzare i testi delle email.", parent=self)
            return

        self._save_credentials(notify=False)
        self.is_scanning = True
        self.btn_scan.configure(state="disabled")
        self.progress_bar.pack(fill="x", pady=(0, 8), before=self.tree.master)
        self.progress_bar.start()

        self.var_status_msg.set("Connessione a Gmail e ricerca nuove email non lette...")

        def _scan_thread():
            try:
                emails = fetch_unread_order_emails(email_val, pass_val)
                # Filtra le email già elaborate in questa sessione
                new_emails = [e for e in emails if e.get("uid") not in self.processed_uids]
                if not new_emails:
                    self.after(0, lambda: self._on_scan_finished(0, "Nessuna nuova email non letta trovata nella casella INBOX."))
                    return

                total_emails = len(new_emails)
                new_found_products = []
                new_uids = []

                for idx, em in enumerate(new_emails, 1):
                    self.after(0, lambda i=idx, t=total_emails, s=em.get('subject', ''): self.var_status_msg.set(
                        f"Analisi con AI ({i}/{t}): {s[:35]}..."
                    ))
                    try:
                        prods = parse_order_email_with_gemini(em, api_key)
                        if prods:
                            new_found_products.extend(prods)
                            new_uids.append(em["uid"])
                    except Exception as err:
                        print(f"Errore parsing email UID {em.get('uid')}: {err}")

                self.after(0, lambda: self._on_scan_success(new_found_products, new_uids))

            except Exception as exc:
                self.after(0, lambda: self._on_scan_error(str(exc)))

        threading.Thread(target=_scan_thread, daemon=True).start()

    def _on_scan_success(self, new_products: List[Dict[str, Any]], new_uids: List[str]) -> None:
        self._stop_progress()
        added_count = 0

        for p in new_products:
            self.extracted_products.append(p)
            added_count += 1
            try:
                price_dec = parse_money(p.get("purchased_price", 0))
                price_str = money(price_dec)
            except Exception:
                price_str = str(p.get("purchased_price", "0,00"))

            self.tree.insert("", "end", values=(
                p.get("name", "Sconosciuto"),
                p.get("size", "UNI"),
                p.get("quantity", 1),
                price_str,
                p.get("purchased_place", "Online"),
                p.get("release_date", ""),
            ))

        for uid in new_uids:
            if uid not in self.processed_uids:
                self.processed_uids.append(uid)

        total_n = len(self.extracted_products)
        if added_count > 0:
            self.var_status_msg.set(f"Scansione completata: aggiunti {added_count} nuovi prodotti! (Totale in lista: {total_n})")
            self.lbl_count_info.configure(text=f"{total_n} prodotti pronti per essere salvati nei Pre-ordini.")
            self.btn_save.configure(state="normal")
        else:
            if total_n > 0:
                self.var_status_msg.set(f"Nessun nuovo prodotto rilevato. Rimangono {total_n} prodotti in lista.")
                self.btn_save.configure(state="normal")
            else:
                self.var_status_msg.set("Nessun prodotto rilevato nelle email analizzate.")
                self.lbl_count_info.configure(text="Nessun prodotto trovato.")
                self.btn_save.configure(state="disabled")

    def _on_scan_finished(self, count: int, msg: str) -> None:
        self._stop_progress()
        total_n = len(self.extracted_products)
        if total_n > 0:
            self.var_status_msg.set(f"{msg} (Rimangono {total_n} prodotti pronti da salvare).")
            self.lbl_count_info.configure(text=f"{total_n} prodotti pronti per essere salvati nei Pre-ordini.")
            self.btn_save.configure(state="normal")
        else:
            self.var_status_msg.set(msg)
            self.lbl_count_info.configure(text=msg)
            self.btn_save.configure(state="disabled")

    def _on_scan_error(self, err_msg: str) -> None:
        self._stop_progress()
        self.var_status_msg.set(f"Errore durante la scansione: {err_msg}")
        messagebox.showerror("Errore Scansione", f"Impossibile completare la scansione:\n{err_msg}", parent=self)

    def _stop_progress(self) -> None:
        self.is_scanning = False
        self.btn_scan.configure(state="normal")
        self.progress_bar.stop()
        self.progress_bar.pack_forget()

    def _save_all_to_preorders(self) -> None:
        if not self.extracted_products:
            return

        email_val = self.var_email.get().strip()
        pass_val = self.var_password.get().replace(" ", "").strip()

        saved_count = 0
        for p in self.extracted_products:
            try:
                purchase_val = parse_money(p.get("purchased_price", 0)) or Decimal("0")
                qty = int(p.get("quantity", 1))
                if qty <= 0:
                    qty = 1

                product_record = {
                    "name": str(p.get("name", "Prodotto Email")).strip(),
                    "size": str(p.get("size", "UNI")).strip(),
                    "quantity": qty,
                    "purchased_price": purchase_val,
                    "purchased_place": str(p.get("purchased_place", "Online")).strip(),
                    "selling_place": "",
                    "selling_price": None,
                    "sold_price": None,
                    "fees": Decimal("0"),
                    "sold_date": "",
                    "status": STATUS_PREORDER,
                    "release_date": str(p.get("release_date", "")).strip(),
                    "notes": "Importato automaticamente da email di ordine.",
                }
                self.db.save(product_record)
                saved_count += 1
            except Exception as e:
                print(f"Errore salvataggio prodotto pre-ordine: {e}")

        # Segna le email lette su Gmail in background
        if self.processed_uids:
            threading.Thread(target=mark_emails_as_read, args=(email_val, pass_val, self.processed_uids), daemon=True).start()

        messagebox.showinfo("Successo", f"{saved_count} prodotti salvati con successo nella scheda Pre-ordini!", parent=self)
        self.on_success_callback()
        self.destroy()
