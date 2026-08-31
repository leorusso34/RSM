#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script per la build dell'eseguibile Windows tramite PyInstaller."""

import os
import subprocess
import sys
from pathlib import Path

def main():
    print("Preparazione per la build di Russo Stock Manager...")
    
    # Assicurati che PyInstaller sia installato
    try:
        import PyInstaller
    except ImportError:
        print("Installazione di PyInstaller in corso...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        
    project_root = Path(__file__).resolve().parent
    main_script = project_root / "russo_stock_manager.py"
    
    if not main_script.exists():
        print(f"Errore: {main_script} non trovato.")
        sys.exit(1)
        
    import shutil
    source_data = project_root / "data"
    dist_dir = project_root / "dist" / "Russo Stock Manager"
    dist_data = dist_dir / "data"
    backup_data = project_root / "data_backup_temp"
    
    # 1. Salvataggio del database di produzione (se esiste in dist) prima della build
    if dist_data.exists():
        print("Salvataggio del database attuale in corso...")
        if backup_data.exists():
            shutil.rmtree(backup_data)
        shutil.copytree(dist_data, backup_data)
        
    # Costruisci il comando PyInstaller
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=Russo Stock Manager",
        "--clean",
        "--icon=assets/app_icon.ico",
        "--add-data=assets;assets",
        "--collect-all=customtkinter",
        str(main_script)
    ]
    
    print(f"Esecuzione comando: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=project_root)
    
    # 2. Ripristino o copia iniziale
    if not dist_data.exists():
        dist_data.mkdir(parents=True, exist_ok=True)
        
    if backup_data.exists():
        print("Ripristino del database di produzione in dist...")
        shutil.rmtree(dist_data)
        shutil.copytree(backup_data, dist_data)
        shutil.rmtree(backup_data)
    elif source_data.exists():
        print("Cartella 'data' iniziale copiata con successo nella build.")
        shutil.rmtree(dist_data, ignore_errors=True)
        shutil.copytree(source_data, dist_data)
    
    # 3. Copia o creazione di config.json nella cartella dist
    dist_config = dist_folder / "config.json"
    source_config = project_root / "config.json"
    if source_config.exists():
        shutil.copy(source_config, dist_config)
    elif not dist_config.exists():
        with open(dist_config, "w", encoding="utf-8") as f:
            json.dump({"gemini_api_key": "", "email_sync_address": "", "email_sync_app_password": ""}, f, indent=2)
    
    print("Build completata con successo! Troverai l'eseguibile nella cartella 'dist/Russo Stock Manager/'.")

if __name__ == "__main__":
    main()
