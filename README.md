# Russo Stock Manager

Applicazione desktop moderna in **CustomTkinter** per la gestione di inventario, pre-ordini, vendite attive e storiche, con cruscotto KPI, grafici statistici e inserimento intelligente con AI (testuale e vocale).

---

## 🚀 Caratteristiche Principali

- **📦 Magazzino & Pre-ordini**: Tracciamento completo di prodotti, taglie, quantità, luoghi di acquisto e date di rilascio.
- **🏷️ Gestione Vendite & Vendite Multiple**: Conversione rapida, supporto per vendite in blocco (bundle) e drag & drop tra schede.
- **✅ Storico Vendite Completate**: Archiviazione permanente delle vendite concluse con calcolo esatto di ricavi, commissioni, profitto netto e ROI reale.
- **📊 Dashboard & Grafici**: Indicatori KPI in tempo reale, andamento del profitto mensile (€) e ripartizione volumi inventario per stato.
- **✨ Assistente AI con Riconoscimento Vocale**: Estrazione rapida e strutturata dei prodotti tramite Google Gemini e trascrizione vocale in italiano.
- **📁 Import / Export & Backup**:
  - Importazione automatica da fogli **Excel** (`.xlsx`).
  - Esportazione **CSV** formattata per Excel italiano.
  - Backup istantaneo e sicuro del database SQLite.
- **🎨 Interfaccia Dark Professionale**: Supporto nativo High-DPI su Windows, titlebar scura integrata, pill-navigation e finestre sempre perfettamente centrate.

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

L'eseguibile completo e pronto all'uso verrà generato nella cartella `dist/Russo Stock Manager/`.

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