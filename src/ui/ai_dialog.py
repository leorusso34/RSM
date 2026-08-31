import tkinter as tk
from tkinter import ttk, messagebox
import threading

from ..config import DARK_THEME, STATUS_STOCK
from ..ai_agent import parse_product_with_ai

class AIDialog(tk.Toplevel):
    """Finestra di dialogo per l'inserimento rapido tramite Intelligenza Artificiale."""

    def __init__(self, parent, db) -> None:
        super().__init__(parent)
        self.db = db
        self.result = None
        self.api_key_valid = False

        self.title("Inserimento Rapido con AI")
        
        # Centering window
        parent.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = 600, 500
        x, y = px + (pw - w) // 2, py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(500, 400)
        
        self.configure(bg=DARK_THEME["bg_card"])
        self.transient(parent)
        self.grab_set()

        from ..utils import apply_dark_titlebar
        apply_dark_titlebar(self)

        self.api_key_var = tk.StringVar(value=self.db.get_setting("gemini_api_key", ""))
        self.prompt_var = tk.StringVar()

        self._build_ui()

    def _build_ui(self) -> None:
        c = DARK_THEME
        main_frame = tk.Frame(self, bg=c["bg_card"], padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)

        # Header
        header = tk.Frame(main_frame, bg=c["bg_card"])
        header.pack(fill="x", pady=(0, 15))
        
        tk.Label(header, text="✨ Inserimento Rapido AI", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 16, "bold")).pack(side="left")

        # API Key Section
        api_frame = tk.Frame(main_frame, bg=c["bg_input"], highlightbackground=c["border"], highlightthickness=1, padx=10, pady=10)
        api_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(api_frame, text="Gemini API Key:", bg=c["bg_input"], fg=c["fg_muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        
        api_input_frame = tk.Frame(api_frame, bg=c["bg_input"])
        api_input_frame.pack(fill="x", pady=(5, 0))
        
        self.api_entry = ttk.Entry(api_input_frame, textvariable=self.api_key_var, font=("Segoe UI", 10), show="*")
        self.api_entry.pack(side="left", fill="x", expand=True, ipady=3)
        
        ttk.Button(api_input_frame, text="Salva Chiave", command=self._save_api_key).pack(side="left", padx=(10, 0))

        # Prompt Section
        prompt_header = tk.Frame(main_frame, bg=c["bg_card"])
        prompt_header.pack(fill="x", pady=(10, 5))
        
        tk.Label(prompt_header, text="Cosa vuoi aggiungere?", bg=c["bg_card"], fg=c["fg_main"], font=("Segoe UI", 10, "bold")).pack(side="left")
        
        import os
        import sys
        from PIL import Image, ImageTk

        def get_asset_path(filename):
            if hasattr(sys, '_MEIPASS'):
                return os.path.join(sys._MEIPASS, 'assets', filename)
            return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', filename)

        try:
            mic_path = get_asset_path("mic_icon.png")
            img = Image.open(mic_path)
            img = img.resize((20, 20), Image.Resampling.LANCZOS)
            self.mic_img = ImageTk.PhotoImage(img)
            self.btn_mic = tk.Label(prompt_header, image=self.mic_img, bg=c["bg_card"], cursor="hand2")
            self.btn_mic.bind("<Button-1>", lambda e: self._start_listening())
            self.btn_mic.pack(side="right", padx=(5, 0))
        except Exception:
            self.btn_mic = ttk.Button(prompt_header, text="🎙️", command=self._start_listening, width=3)
            self.btn_mic.pack(side="right")
    
        self.prompt_text = tk.Text(main_frame, height=5, wrap="word", bg=c["bg_input"], fg=c["fg_main"], insertbackground=c["fg_main"], relief="flat", padx=10, pady=10, font=("Segoe UI", 10))
        self.prompt_text.pack(fill="both", expand=True)

        # Status and Actions
        bottom_frame = tk.Frame(main_frame, bg=c["bg_card"])
        bottom_frame.pack(fill="x", pady=(15, 0))

        self.status_lbl = tk.Label(bottom_frame, text="", bg=c["bg_card"], fg=c["fg_muted"], font=("Segoe UI", 9))
        self.status_lbl.pack(side="left")

        self.btn_generate = ttk.Button(bottom_frame, text="✨ Analizza e Crea", style="Accent.TButton", command=self._generate)
        self.btn_generate.pack(side="right")
        
        ttk.Button(bottom_frame, text="Annulla", command=self.destroy).pack(side="right", padx=(0, 10))

    def _save_api_key(self):
        key = self.api_key_var.get().strip()
        if key:
            self.db.set_setting("gemini_api_key", key)
            self.status_lbl.configure(text="Chiave API salvata con successo!", fg=DARK_THEME["fg_main"])
        else:
            self.status_lbl.configure(text="Inserisci una chiave API valida.", fg="red")

    def _generate(self):
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("API Key mancante", "Per favore inserisci e salva la tua Gemini API Key prima di procedere.", parent=self)
            return
            
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        if not prompt:
            return
            
        self.btn_generate.configure(state="disabled")
        self.status_lbl.configure(text="L'AI sta analizzando il testo...", fg=DARK_THEME["fg_muted"])
        
        # Esegui l'API in un thread separato per non bloccare la UI
        threading.Thread(target=self._run_ai, args=(prompt, api_key), daemon=True).start()
        
    def _run_ai(self, prompt, api_key):
        try:
            parsed_data = parse_product_with_ai(prompt, api_key)
            self.after(0, lambda: self._on_ai_success(parsed_data))
        except Exception as e:
            self.after(0, lambda: self._on_ai_error(str(e)))
            
    def _on_ai_success(self, parsed_list):
        count = len(parsed_list)
        label = "prodotto estratto" if count == 1 else f"{count} prodotti estratti"
        self.status_lbl.configure(text=f"{label.capitalize()} con successo!", fg=DARK_THEME["fg_main"])

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
                "name": parsed_data.get("name", ""),
                "size": parsed_data.get("size", ""),
                "quantity": qty,
                "purchased_price": pp,
                "purchased_place": parsed_data.get("purchased_place", ""),
                "selling_place": "",
                "selling_price": None,
                "sold_price": None,
                "fees": 0.0,
                "status": parsed_data.get("status", STATUS_STOCK),
                "release_date": parsed_data.get("release_date", ""),
                "notes": "Generato automaticamente tramite AI."
            })

        self.result = records
        self.destroy()
        
    def _on_ai_error(self, error_msg):
        self.btn_generate.configure(state="normal")
        self.status_lbl.configure(text="Errore durante l'analisi.", fg="red")
        messagebox.showerror("Errore AI", error_msg, parent=self)

    def _start_listening(self):
        if getattr(self, 'is_listening', False): return
        self.is_listening = True
        
        # Non modifichiamo più il bottone visto che ora è solo un'icona
        self.status_lbl.configure(text="Inizializzazione microfono...", fg=DARK_THEME["fg_muted"])
        
        from ..speech_helper import transcribe_from_microphone
        transcribe_from_microphone(
            on_result=self._on_speech_result,
            on_error=self._on_speech_error,
            on_listening=self._on_listening
        )
        
    def _on_listening(self):
        def update_ui():
            self.status_lbl.configure(text="🔴 Parla ora (max 6s)...", fg=DARK_THEME["fg_main"])
        self.after(0, update_ui)
        
    def _on_speech_result(self, text):
        def update_ui():
            self.is_listening = False
            self.status_lbl.configure(text="Trascrizione completata.", fg=DARK_THEME["fg_main"])
            current = self.prompt_text.get("1.0", tk.END).strip()
            if current:
                self.prompt_text.insert(tk.END, " " + text)
            else:
                self.prompt_text.insert(tk.END, text)
        self.after(0, update_ui)
        
    def _on_speech_error(self, error_msg):
        def update_ui():
            self.is_listening = False
            self.status_lbl.configure(text="Errore microfono.", fg="red")
            messagebox.showerror("Errore Microfono", error_msg, parent=self)
        self.after(0, update_ui)
