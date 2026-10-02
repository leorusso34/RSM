"""Finestra di dialogo per l'inserimento rapido tramite Intelligenza Artificiale con CustomTkinter."""

import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import Any

import customtkinter as ctk
from PIL import Image

from ..ai_agent import parse_product_with_ai
from ..config import DARK_THEME, PROJECT_DIR, STATUS_STOCK
from ..speech_helper import SpeechTranscriber
from ..utils import apply_dark_titlebar, center_window


class AIDialog(ctk.CTkToplevel):
    """Finestra di dialogo moderna per l'inserimento rapido tramite Intelligenza Artificiale."""

    def __init__(self, parent: tk.Misc, db: Any) -> None:
        super().__init__(parent, fg_color=DARK_THEME["bg_main"])
        self.db = db
        self.result: list[dict[str, Any]] | None = None
        self.transcriber: SpeechTranscriber | None = None
        self.is_recording: bool = False

        self.title("Inserimento Rapido con AI")
        center_window(self, 620, 520)
        self.minsize(540, 440)
        self.transient(parent)
        self.grab_set()
        apply_dark_titlebar(self)

        self.api_key_var = tk.StringVar(value=self.db.get_setting("gemini_api_key", ""))
        self.status_var = tk.StringVar(value="")

        # Carica icona microfono pulita e versione rossa attiva
        mic_path = Path(getattr(sys, "_MEIPASS", PROJECT_DIR)) / "assets" / "mic_icon.png"
        if not mic_path.exists():
            mic_path = PROJECT_DIR / "assets" / "mic_icon.png"

        pil_img = Image.open(mic_path).convert("RGBA")
        target_h = 22
        target_w = max(1, round(target_h * (pil_img.width / max(1, pil_img.height))))
        self._mic_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(target_w, target_h))

        # Versione rossa durante la registrazione vocale
        _, _, _, a = pil_img.split()
        red_pil = Image.new("RGBA", pil_img.size, (239, 68, 68, 255))
        red_pil.putalpha(a)
        self._mic_img_rec = ctk.CTkImage(light_image=red_pil, dark_image=red_pil, size=(target_w, target_h))

        # Carica icona AI per header
        ai_path = Path(getattr(sys, "_MEIPASS", PROJECT_DIR)) / "assets" / "ai_icon.png"
        if not ai_path.exists():
            ai_path = PROJECT_DIR / "assets" / "ai_icon.png"
        self._ai_header_img = None
        if ai_path.exists():
            try:
                ai_pil = Image.open(ai_path).convert("RGBA")
                self._ai_header_img = ctk.CTkImage(light_image=ai_pil, dark_image=ai_pil, size=(22, 22))
            except (OSError, ValueError):
                pass

        self._build_ui()

    def _build_ui(self) -> None:
        c = DARK_THEME
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=22, pady=18)

        # Header
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 14))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(anchor="w")
        if self._ai_header_img:
            ctk.CTkLabel(title_box, text="", image=self._ai_header_img).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(title_box, text="Inserimento Rapido", font=("Segoe UI", 18, "bold")).pack(side="left")

        ctk.CTkLabel(
            header,
            text="Descrivi i prodotti a voce o per testo e Gemini estrarrà automaticamente tutti i dati.",
            font=("Segoe UI", 12),
            text_color=c["fg_muted"],
        ).pack(anchor="w", pady=(2, 0))

        # Sezione API Key
        api_card = ctk.CTkFrame(container, fg_color=c["bg_card"], corner_radius=10, border_width=1, border_color=c["border"])
        api_card.pack(fill="x", pady=(0, 14))

        api_inner = ctk.CTkFrame(api_card, fg_color="transparent")
        api_inner.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(api_inner, text="GEMINI API KEY:", font=("Segoe UI", 10, "bold"), text_color=c["fg_muted"]).pack(anchor="w")

        api_row = ctk.CTkFrame(api_inner, fg_color="transparent")
        api_row.pack(fill="x", pady=(4, 0))

        self.api_entry = ctk.CTkEntry(api_row, textvariable=self.api_key_var, placeholder_text="Incolla la tua Gemini API Key (AIzaSy...)", show="*", font=("Segoe UI", 12))
        self.api_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkButton(api_row, text="Salva Chiave", command=self._save_api_key, fg_color="#374151", hover_color="#4b5563", width=110, font=("Segoe UI", 11)).pack(side="right")

        # Sezione Prompt & Microfono
        prompt_card = ctk.CTkFrame(container, fg_color=c["bg_card"], corner_radius=10, border_width=1, border_color=c["border"])
        prompt_card.pack(fill="both", expand=True, pady=(0, 14))

        prompt_inner = ctk.CTkFrame(prompt_card, fg_color="transparent")
        prompt_inner.pack(fill="both", expand=True, padx=14, pady=12)

        prompt_top_row = ctk.CTkFrame(prompt_inner, fg_color="transparent")
        prompt_top_row.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(prompt_top_row, text="COSA VUOI AGGIUNGERE?", font=("Segoe UI", 11, "bold")).pack(side="left")

        # Pulsante Microfono a sfondo 100% pulito e trasparente (senza scritte, clicca per avviare/fermare)
        self.btn_mic = ctk.CTkButton(
            prompt_top_row,
            text="",
            image=self._mic_img,
            width=34,
            height=34,
            fg_color="transparent",
            hover_color="#1d2538",
            border_width=0,
            corner_radius=6,
            command=self._toggle_listening,
        )
        self.btn_mic.pack(side="right")

        self.prompt_text = ctk.CTkTextbox(
            prompt_inner,
            wrap="word",
            font=("Segoe UI", 12),
            fg_color=c["bg_input"],
            text_color=c["fg_main"],
            border_width=1,
            border_color=c["border"],
            corner_radius=8,
        )
        self.prompt_text.pack(fill="both", expand=True)

        # Barra inferiore: stato e pulsanti di azione
        bottom_bar = ctk.CTkFrame(container, fg_color="transparent")
        bottom_bar.pack(fill="x")

        self.lbl_status = ctk.CTkLabel(bottom_bar, textvariable=self.status_var, font=("Segoe UI", 11), text_color=c["fg_muted"])
        self.lbl_status.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(bottom_bar, text="Annulla", command=self.destroy, fg_color="#374151", hover_color="#4b5563", width=90).pack(side="right")

        self.btn_generate = ctk.CTkButton(
            bottom_bar,
            text="Analizza e Crea",
            command=self._generate,
            font=("Segoe UI", 12, "bold"),
            width=150,
        )
        self.btn_generate.pack(side="right", padx=(0, 10))

    def _save_api_key(self) -> None:
        key = self.api_key_var.get().strip()
        if key:
            self.db.set_setting("gemini_api_key", key)
            self.status_var.set("Chiave API salvata con successo!")
            messagebox.showinfo("Salvataggio", "Chiave API Gemini salvata correttamente.", parent=self)
        else:
            self.status_var.set("Inserisci una chiave API valida.")
            messagebox.showwarning("Chiave Mancante", "Inserisci una chiave API valida.", parent=self)

    def _generate(self) -> None:
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("API Key mancante", "Per favore inserisci e salva la tua Gemini API Key prima di procedere.", parent=self)
            return

        prompt = self.prompt_text.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("Testo mancante", "Scrivi o detta i prodotti che desideri inserire.", parent=self)
            return

        self.btn_generate.configure(state="disabled")
        self.status_var.set("Analisi del testo con Gemini in corso...")

        threading.Thread(target=self._run_ai, args=(prompt, api_key), daemon=True).start()

    def _run_ai(self, prompt: str, api_key: str) -> None:
        try:
            parsed_data = parse_product_with_ai(prompt, api_key)
            self.after(0, lambda: self._on_ai_success(parsed_data))
        except Exception as exc:  # noqa: BLE001
            err_msg = str(exc)
            self.after(0, lambda msg=err_msg: self._on_ai_error(msg))

    def _on_ai_success(self, parsed_list: list[dict[str, Any]]) -> None:
        count = len(parsed_list)
        if count == 0:
            self.btn_generate.configure(state="normal")
            self.status_var.set("Nessun prodotto rilevato nel testo inserito.")
            messagebox.showinfo("Nessun Prodotto", "L'AI non ha trovato prodotti validi nel testo. Riprova con maggiori dettagli.", parent=self)
            return

        records = []
        for parsed_data in parsed_list:
            try:
                pp = float(parsed_data.get("purchased_price", 0.0))
            except (ValueError, TypeError):
                pp = 0.0

            try:
                qty = int(parsed_data.get("quantity", 1))
            except (ValueError, TypeError):
                qty = 1

            records.append({
                "name": str(parsed_data.get("name", "")).strip(),
                "size": str(parsed_data.get("size", "UNI")).strip(),
                "quantity": qty,
                "purchased_price": pp,
                "purchased_place": str(parsed_data.get("purchased_place", "")).strip(),
                "selling_place": "",
                "selling_price": None,
                "sold_price": None,
                "fees": 0.0,
                "status": parsed_data.get("status", STATUS_STOCK),
                "release_date": str(parsed_data.get("release_date", "")).strip(),
                "notes": "Generato automaticamente tramite AI."
            })

        self.result = records
        self.destroy()

    def _on_ai_error(self, error_msg: str) -> None:
        self.btn_generate.configure(state="normal")
        self.status_var.set("Errore durante l'analisi.")
        messagebox.showerror("Errore AI", error_msg, parent=self)

    def _toggle_listening(self) -> None:
        if self.is_recording:
            # Se sta già registrando, un secondo clic interrompe e trascrive subito l'audio
            if self.transcriber:
                self.transcriber.stop()
            self.status_var.set("Elaborazione e trascrizione in corso...")
            self.btn_mic.configure(image=self._mic_img)
            return

        # Avvio nuova registrazione vocale
        self.is_recording = True
        self.btn_mic.configure(image=self._mic_img_rec)
        self.status_var.set("Inizializzazione microfono...")

        api_key = self.api_key_var.get().strip()
        self.transcriber = SpeechTranscriber()
        self.transcriber.start(
            on_result=self._on_speech_result,
            on_error=self._on_speech_error,
            on_listening=self._on_listening,
            api_key=api_key,
            max_duration=20
        )

    def _on_listening(self) -> None:
        def update_ui():
            self.status_var.set("Microfono attivo: parla ora... (clicca di nuovo per terminare)")
        self.after(0, update_ui)

    def _on_speech_result(self, text: str) -> None:
        def update_ui():
            self.is_recording = False
            self.btn_mic.configure(image=self._mic_img)
            self.status_var.set("Trascrizione vocale completata con successo!")
            current = self.prompt_text.get("1.0", "end").strip()
            if current:
                self.prompt_text.insert("end", " " + text)
            else:
                self.prompt_text.insert("end", text)
        self.after(0, update_ui)

    def _on_speech_error(self, error_msg: str) -> None:
        def update_ui():
            self.is_recording = False
            self.btn_mic.configure(image=self._mic_img)
            self.status_var.set(f"⚠️ {error_msg}")
        self.after(0, update_ui)
