#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script per la build dell'eseguibile Windows tramite PyInstaller per RSM."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    print("Preparazione per la build di RSM...")

    # Assicurati che PyInstaller sia installato
    try:
        import PyInstaller
    except ImportError:
        print("Installazione di PyInstaller in corso...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    project_root = Path(__file__).resolve().parent
    main_script = project_root / "rsm.py"

    if not main_script.exists():
        print(f"Errore: {main_script} non trovato.")
        sys.exit(1)

    dist_root = project_root / "dist"
    build_root = project_root / "build"
    dist_dir = dist_root / "RSM"
    dist_data = dist_dir / "data"
    old_dist_dir = dist_root / "Russo Stock Manager"
    old_dist_data = old_dist_dir / "data"
    backup_data = project_root / "data_backup_temp"
    backup_config = project_root / "config_backup_temp.json"
    dist_config = dist_dir / "config.json"

    # 1. Salvataggio sicuro di database e config.json prima della ricompilazione
    target_existing_data = dist_data if dist_data.exists() else (old_dist_data if old_dist_data.exists() else None)
    if target_existing_data and target_existing_data.exists():
        print("Salvataggio del database attuale in corso...")
        if backup_data.exists():
            shutil.rmtree(backup_data)
        shutil.copytree(target_existing_data, backup_data)

    if dist_config.exists():
        shutil.copy(dist_config, backup_config)

    # Rimuovi la vecchia cartella legacy se ancora presente
    if old_dist_dir.exists():
        shutil.rmtree(old_dist_dir, ignore_errors=True)
    old_build_dir = build_root / "Russo Stock Manager"
    if old_build_dir.exists():
        shutil.rmtree(old_build_dir, ignore_errors=True)

    # Costruisci il comando PyInstaller con tutte le inclusioni per CustomTkinter
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=RSM",
        "--clean",
        "--icon=assets/app_icon.ico",
        "--add-data=assets;assets",
        "--hidden-import=customtkinter",
        "--hidden-import=darkdetect",
        "--hidden-import=PIL",
        "--collect-all=customtkinter",
        "--copy-metadata=customtkinter",
        str(main_script)
    ]

    print(f"Esecuzione comando: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=project_root)

    # 2. Ripristino del database di produzione in dist/RSM/data
    if not dist_data.exists():
        dist_data.mkdir(parents=True, exist_ok=True)

    source_data = project_root / "data"
    if backup_data.exists():
        print("Ripristino del database di produzione in dist/RSM/data...")
        shutil.rmtree(dist_data, ignore_errors=True)
        shutil.copytree(backup_data, dist_data)
        shutil.rmtree(backup_data, ignore_errors=True)
    elif source_data.exists():
        print("Copia del database iniziale in dist/RSM/data...")
        shutil.rmtree(dist_data, ignore_errors=True)
        shutil.copytree(source_data, dist_data)

    # 3. Ripristino o creazione di config.json in dist/RSM/config.json
    source_config = project_root / "config.json"
    if backup_config.exists():
        shutil.copy(backup_config, dist_config)
        backup_config.unlink(missing_ok=True)
    elif source_config.exists():
        shutil.copy(source_config, dist_config)
    elif not dist_config.exists():
        with open(dist_config, "w", encoding="utf-8") as f:
            json.dump({"gemini_api_key": "", "email_sync_address": "", "email_sync_app_password": ""}, f, indent=2)

    # Pulizia finale cartella legacy se ricreata
    if old_dist_dir.exists():
        shutil.rmtree(old_dist_dir, ignore_errors=True)

    print("\nBuild completata con successo!")
    print("Cartella di rilascio: 'dist/RSM/'")
    print("Eseguibile: 'dist/RSM/RSM.exe'")


if __name__ == "__main__":
    main()
