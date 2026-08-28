# Russo Stock Manager

Applicazione desktop Tkinter per gestire prodotti in stock, pre-ordini e vendite.

## Avvio

```powershell
python -m pip install -r requirements.txt
python russo_stock_manager.py
```

Il database viene salvato in `data/russo_stock.db`. I file `-wal` e `-shm` sono sidecar temporanei creati da SQLite per il journaling WAL: possono esistere mentre l'app è aperta e ora vengono creati direttamente dentro `data/`. Le versioni precedenti con prezzi `REAL` vengono migrate automaticamente in centesimi interi.

Il codice applicativo è organizzato in `src/`, mentre `russo_stock_manager.py` nella cartella principale resta il punto di avvio.

## Test

```powershell
python -m pytest -q
```

I test coprono calcoli monetari, transizioni di stato, importazione Excel, esportazione CSV, backup e ordinamento.