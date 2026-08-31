import tkinter as tk
from tkinter import messagebox
import threading
import customtkinter as ctk

from ..config import DARK_THEME, STATUS_STOCK
from ..ai_agent import parse_product_with_ai
from ..utils import center_window, apply_dark_titlebar


class AIDialog(ctk.CTkToplevel):
    def __init__(self, parent, db) -> None:
        super().__init__(parent, fg_color=DARK_THEME["bg_main"])
        self.db = db
        self.result = None
        self.title("Inserimento Rapido con AI")
        center_window(self, 600, 520)
        self.minsize(500, 420)
        self.transient(parent)
        self.grab_set()
        apply_dark_titlebar(self)
        self.api_key_var = tk.StringVar(value=self.db.get_setting("gemini_api_key", ""))
        self._build_ui()

    def _build_ui(self) -> None:
        c = DARK_THEME
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        header = ctk.CTkFrame(main_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(header, text="Inserimento Rapido AI", font=("Segoe UI", 16, "bold")).pack(side="left")
        api_frame = ctk.CTkFrame(main_frame, corner_radius=10, border_width=1, border_color=c["border"], fg_color=c["bg_input"])
        api_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(api_frame, text="Gemini API Key:", font=("Segoe UI", 11, "bold"), text_color=c["fg_muted"]).pack(anchor="w", padx=12, pady=(10, 0))
        api_input_frame = ctk.CTkFrame(api_frame, fg_color="transparent")
        api_input_frame.pack(fill="x", padx=12, pady=(5, 10))
        self.api_entry = ctk.CTkEntry(api_input_frame, textvariable=self.api_key_var, font=("Segoe UI", 12), show="*")
        self.api_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(api_input_frame, text="Salva Chiave", command=self._save_api_key, width=120).pack(side="left", padx=(10, 0))
        prompt_header = ctk.CTkFrame(main_frame, fg_color="transparent")
        prompt_header.pack(fill="x", pady=(10, 5))
        ctk.CTkLabel(prompt_header, text="Cosa vuoi aggiungere?", font=("Segoe UI", 12, "bold")).pack(side="left")
        import os, sys
        from PIL import Image
        def get_asset_path(filename):
            if hasattr(sys, "_MEIPASS"):
                return os.path.join(sys._MEIPASS, "assets", filename)
            return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", filename)
        try:
            mic_path = get_asset_path("mic_icon.png")
            img = Image.open(mic_path)
            self.mic_img = ctk.CTkImage(light_image=img, dark_image=img, size=(20, 20))
            self.btn_mic = ctk.CTkLabel(prompt_header, image=self.mic_img, text="", cursor="hand2")
            self.btn_mic.bind("<Button-1>", lambda e: self._start_listening())
            self.btn_mic.pack(side="right", padx=(5, 0))
        except Exception:
            self.btn_mic = ctk.CTkButton(prompt_header, text="Mic", command=self._start_listening, width=40)
            self.btn_mic.pack(side="right")
        self.prompt_text = ctk.CTkTextbox(main_frame, font=("Segoe UI", 12), wrap="word", height=120)
        self.prompt_text.pack(fill="both", expand=True)
        bottom_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        bottom_frame.pack(fill="x", pady=(15, 0))
        self.status_lbl = ctk.CTkLabel(bottom_frame, text="", font=("Segoe UI", 11), text_color=c["fg_muted"])
        self.status_lbl.pack(side="left")
        ctk.CTkButton(bottom_frame, text="Annulla", command=self.destroy, fg_color="#374151", hover_color="#4b5563").pack(side="right", padx=(10, 0))
        self.btn_generate = ctk.CTkButton(bottom_frame, text="Analizza e Crea", command=self._generate)
        self.btn_generate.pack(side="right")

    def _save_api_key(self):
        key = self.api_key_var.get().strip()
        if key:
            self.db.set_setting("gemini_api_key", key)
            self.status_lbl.configure(text="Chiave API salvata!", text_color=DARK_THEME["fg_main"])
        else:
            self.status_lbl.configure(text="Inserisci una chiave API valida.", text_color="red")

    def _generate(self):
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("API Key mancante", "Inserisci e salva la tua Gemini API Key.", parent=self)
            return
        prompt = self.prompt_text.get("1.0", "end").strip()
        if not prompt:
            return
        self.btn_generate.configure(state="disabled")
        self.status_lbl.configure(text="L'AI sta analizzando...", text_color=DARK_THEME["fg_muted"])
        threading.Thread(target=self._run_ai, args=(prompt, api_key), daemon=True).start()

    def _run_ai(self, prompt, api_key):
        try:
            parsed_data = parse_product_with_ai(prompt, api_key)
            self.after(0, lambda: self._on_ai_success(parsed_data))
        except Exception as e:
            self.after(0, lambda: self._on_ai_error(str(e)))

    def _on_ai_success(self, parsed_list):
        count = len(parsed_list)
        suffix = "prodotto estratto" if count == 1 else f"{count} prodotti estratti"
        self.status_lbl.configure(text=suffix.capitalize() + " con successo!", text_color=DARK_THEME["fg_main"])
        records = []
        for d in parsed_list:
            try:
                pp = float(d.get("purchased_price", 0.0))
            except (ValueError, TypeError):
                pp = 0.0
            try:
                qty = int(d.get("quantity", 1))
            except (ValueError, TypeError):
                qty = 1
            records.append({"name": d.get("name", ""), "size": d.get("size", ""), "quantity": qty,
                "purchased_price": pp, "purchased_place": d.get("purchased_place", ""),
                "selling_place": "", "selling_price": None, "sold_price": None, "fees": 0.0,
                "status": d.get("status", STATUS_STOCK), "release_date": d.get("release_date", ""),
                "notes": "Generato automaticamente tramite AI."})
        self.result = records
        self.destroy()

    def _on_ai_error(self, error_msg):
        self.btn_generate.configure(state="normal")
        self.status_lbl.configure(text="Errore durante l'analisi.", text_color="red")
        messagebox.showerror("Errore AI", error_msg, parent=self)

    def _start_listening(self):
        if getattr(self, "is_listening", False):
            return
        self.is_listening = True
        self.status_lbl.configure(text="Inizializzazione microfono...", text_color=DARK_THEME["fg_muted"])
        from ..speech_helper import transcribe_from_microphone
        transcribe_from_microphone(on_result=self._on_speech_result, on_error=self._on_speech_error, on_listening=self._on_listening)

    def _on_listening(self):
        self.after(0, lambda: self.status_lbl.configure(text="Parla ora...", text_color=DARK_THEME["fg_main"]))

    def _on_speech_result(self, text):
        def _upd():
            self.is_listening = False
            self.status_lbl.configure(text="Trascrizione completata.", text_color=DARK_THEME["fg_main"])
            cur = self.prompt_text.get("1.0", "end").strip()
            self.prompt_text.insert("end", (" " if cur else "") + text)
        self.after(0, _upd)

    def _on_speech_error(self, error_msg):
        def _upd():
            self.is_listening = False
            self.status_lbl.configure(text="Errore microfono.", text_color="red")
            messagebox.showerror("Errore Microfono", error_msg, parent=self)
        self.after(0, _upd)