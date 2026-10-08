"""Script per la build dell'eseguibile Windows tramite PyInstaller per RSM."""

import json
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    print("Preparazione per la build di RSM...")

    # Assicurati che PyInstaller sia installato
    try:
        import PyInstaller  # noqa: F401
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
    dist_config = dist_dir / "config.json"

    # 1. Salvataggio sicuro del database prima della ricompilazione
    target_existing_data = dist_data if dist_data.exists() else (old_dist_data if old_dist_data.exists() else None)
    if target_existing_data and target_existing_data.exists():
        print("Salvataggio del database attuale in corso...")
        if backup_data.exists():
            shutil.rmtree(backup_data)
        shutil.copytree(target_existing_data, backup_data)

    # Rimuovi la vecchia cartella legacy se ancora presente
    if old_dist_dir.exists():
        shutil.rmtree(old_dist_dir, ignore_errors=True)
    old_build_dir = build_root / "Russo Stock Manager"
    if old_build_dir.exists():
        shutil.rmtree(old_build_dir, ignore_errors=True)

    # Costruisci il comando PyInstaller con tutte le inclusioni per CustomTkinter
    data_sep = ";" if sys.platform == "win32" else ":"
    icon_arg = "--icon=assets/app_icon.ico"
    if sys.platform == "darwin" and (project_root / "assets" / "app_icon.icns").exists():
        icon_arg = "--icon=assets/app_icon.icns"

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=RSM",
        "--clean",
        icon_arg,
        f"--add-data=assets{data_sep}assets",
        "--hidden-import=customtkinter",
        "--hidden-import=darkdetect",
        "--hidden-import=PIL",
        "--collect-all=customtkinter",
        "--copy-metadata=customtkinter",
        str(main_script)
    ]

    print(f"Esecuzione comando: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=project_root)

    # Su macOS PyInstaller può generare dist/RSM.app: organizziamo la cartella di rilascio dist/RSM
    if sys.platform == "darwin" and (dist_root / "RSM.app").exists():
        dist_dir.mkdir(parents=True, exist_ok=True)
        target_app = dist_dir / "RSM.app"
        if target_app.exists():
            shutil.rmtree(target_app)
        shutil.move(str(dist_root / "RSM.app"), str(target_app))

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

    # 3. Copia esatta di config.json dalla cartella principale in dist/RSM/config.json
    source_config = project_root / "config.json"
    if source_config.exists():
        print("Copia di config.json da cartella principale in dist/RSM/...")
        shutil.copy2(source_config, dist_config)
    elif not dist_config.exists():
        with open(dist_config, "w", encoding="utf-8") as f:
            json.dump({
                "email_sync_address": "",
                "email_sync_app_password": "",
                "dashboard_layout": "[\"monthly\", \"top_products\", \"platform_pie\"]"
            }, f, indent=2, ensure_ascii=False)

    # 4. Copia del README.md nella cartella di rilascio dist/RSM
    source_readme = project_root / "README.md"
    if source_readme.exists():
        shutil.copy(source_readme, dist_dir / "README.md")

    # Pulizia finale cartella legacy se ricreata
    if old_dist_dir.exists():
        shutil.rmtree(old_dist_dir, ignore_errors=True)

    print("\nBuild completata con successo!")
    print("Cartella di rilascio: 'dist/RSM/'")
    print("Eseguibile: 'dist/RSM/RSM.exe'")


if __name__ == "__main__":
    main()
