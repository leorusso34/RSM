# RSM

Applicazione desktop moderna in **CustomTkinter** per la gestione di inventario, pre-ordini, vendite attive e storiche, con cruscotto KPI, grafici statistici e inserimento intelligente con AI (testuale e vocale).

---

## 🚀 Caratteristiche Principali

- **📦 Magazzino & Pre-ordini**: Tracciamento completo di prodotti, taglie, quantità, luoghi di acquisto e date di rilascio.
- **🏷️ Gestione Vendite & Vendite Multiple**: Conversione rapida, supporto per vendite in blocco (bundle) e drag & drop tra schede.
- **✅ Storico Vendite Completate**: Archiviazione permanente delle vendite concluse con calcolo esatto di ricavi, commissioni, profitto netto e ROI reale.
- **📊 Dashboard & Grafici**: Indicatori KPI in tempo reale, andamento del profitto mensile (€) e ripartizione volumi inventario per stato.
- **📬 Sincronizzazione Email Ordini (Gmail + Gemini AI)**: Scansione automatica delle conferme d'ordine da Gmail tramite IMAP e inserimento istantaneo nei Pre-ordini con intelligenza artificiale.
- **✨ Assistente AI con Riconoscimento Vocale**: Estrazione rapida e strutturata dei prodotti tramite Google Gemini e trascrizione vocale in italiano.
- **🔑 Configurazione Rapida via `config.json`**: Possibilità di impostare API key e credenziali direttamente dal file esterno `config.json` nella cartella principale (con precedenza sui dati salvati in app).
- **📁 Import / Export & Backup**:
  - Importazione automatica da fogli **Excel** (`.xlsx`).
  - Esportazione **CSV** formattata per Excel italiano.
  - Backup istantaneo e sicuro del database SQLite.
- **🎨 Interfaccia Dark Professionale**: Supporto nativo High-DPI su Windows, titlebar scura integrata, pill-navigation e finestre sempre perfettamente centrate.

---

## ⚙️ Configurazione Credenziali (`config.json`)

Nella cartella principale dell'applicazione puoi modificare o inserire direttamente i tuoi parametri nel file `config.json`:

```json
{
  "gemini_api_key": "LA_TUA_CHIAVE_API_GEMINI",
  "email_sync_address": "tuo_indirizzo@gmail.com",
  "email_sync_app_password": "abcd efgh ijkl mnop"
}
```

> **Nota**: I valori inseriti in `config.json` hanno la **precedenza assoluta** su qualsiasi dato salvato in-app. Se modifichi i parametri all'interno dell'applicazione, anche `config.json` verrà sincronizzato automaticamente.

---

## 💻 Requisiti e Avvio in Sviluppo

```powershell
# 1. Installa le dipendenze
python -m pip install -r requirements.txt

# 2. Avvia l'applicazione
python russo_stock_manager.py
```

---

## 📦 Compilazione Eseguibile (.exe) Standalone

Per compilare l'applicazione in una cartella autonoma per Windows (senza bisogno di Python sul PC di destinazione):

```powershell
python build.py
```

L'eseguibile completo e pronto all'uso verrà generato nella cartella `dist/RSM/`.

---

## 🧪 Esecuzione dei Test

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

---

## 🗂️ Struttura del Progetto

```text
RUSSO STOCK/
├── assets/                  # Icone, logo trasparente e risorse grafiche
├── data/                    # Database SQLite locale (russo_stock.db)
├── src/                     # Codice sorgente modulare
│   ├── ai_agent.py          # Integrazione API Gemini
│   ├── config.py            # Costanti di configurazione e tema colori
│   ├── database.py          # Database SQLite, query e migrazioni
│   ├── main.py              # Entry point e DPI scaling
│   ├── speech_helper.py     # Riconoscimento vocale
│   ├── types.py             # Type annotations
│   ├── utils.py             # Calcoli matematici, formattazioni, I/O
│   └── ui/                  # Componenti grafici CustomTkinter
│       ├── ai_dialog.py     # Dialogo inserimento rapido AI / Voce
│       ├── dashboard_view.py# Grafici e statistiche KPI
│       ├── dialogs.py       # Finestre di creazione, modifica e luoghi
│       ├── main_window.py   # Finestra principale
│       └── theme.py         # Tema e stili grafici
├── tests/                   # Test suite automatica
├── build.py                 # Script di packaging PyInstaller
└── russo_stock_manager.py   # Launcher principale
```