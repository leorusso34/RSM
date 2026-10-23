"""Script per la build dell'eseguibile Windows nativo tramite Tauri e Rust per RSM."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def find_cargo() -> str:
    """Individua l'eseguibile cargo di Rust nel sistema."""
    cargo_path = shutil.which("cargo")
    if cargo_path:
        return cargo_path

    # Controllo percorso standard cargo su Windows
    home_cargo = Path.home() / ".cargo" / "bin" / ("cargo.exe" if sys.platform == "win32" else "cargo")
    if home_cargo.exists():
        return str(home_cargo)

    raise RuntimeError("Cargo (Rust toolchain) non trovato. Assicurati che Rust sia installato.")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    print("[RSM BUILD] Inizio processo di compilazione RSM (Tauri Native Release)...")

    project_root = Path(__file__).resolve().parent
    tauri_project_dir = project_root / "src-tauri"

    if not tauri_project_dir.exists():
        print(f"Errore: Cartella Tauri {tauri_project_dir} non trovata.")
        sys.exit(1)

    cargo_bin = find_cargo()
    print(f"Toolchain Rust rilevata: {cargo_bin}")

    dist_root = project_root / "dist"
    dist_dir = dist_root / "RSM"
    dist_data = dist_dir / "data"
    dist_config = dist_dir / "config.json"

    # 1. Rilevamento database di produzione
    dist_db = dist_data / "rsm_inventory.db"
    if not dist_db.exists() and (dist_data / "russo_stock.db").exists():
        dist_db = dist_data / "russo_stock.db"
    if dist_db.exists() and dist_db.stat().st_size > 0:
        print(f"Database di produzione rilevato in dist/RSM/data ({dist_db.stat().st_size} byte).")

    # 2. Gestione sicura dei percorsi con spazi per MinGW / windres su Windows
    subst_drive = None
    build_cwd = tauri_project_dir
    if sys.platform == "win32" and " " in str(project_root):
        subst_drive = "R:"
        subprocess.run(["subst", subst_drive, "/D"], capture_output=True, check=False)
        subst_res = subprocess.run(["subst", subst_drive, str(project_root)], capture_output=True, check=False)
        if subst_res.returncode == 0:
            build_cwd = Path(f"{subst_drive}/src-tauri")

    try:
        # 3. Compilazione nativa con Cargo in modalità Release ottimizzata
        print("Compilazione in corso con Cargo Release (Zero-Lag Engine)...")
        cmd = [cargo_bin, "build", "--release"]
        is_ci = os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
        if is_ci:
            subprocess.check_call(cmd, cwd=build_cwd)
        else:
            try:
                # Prova prima con flag offline per massima velocità locale
                subprocess.check_call(cmd + ["--offline"], cwd=build_cwd)
            except subprocess.CalledProcessError:
                # Fallback con accesso rete se necessario
                subprocess.check_call(cmd, cwd=build_cwd)
    finally:
        # Smonta sempre l'unità virtuale temporanea
        if subst_drive:
            subprocess.run(["subst", subst_drive, "/D"], capture_output=True, check=False)

    # 4. Individua il binario compilato
    compiled_exe = (
        tauri_project_dir / "target" / "release" / ("rsm-desktop.exe" if sys.platform == "win32" else "rsm-desktop")
    )
    if not compiled_exe.exists():
        print(f"Errore: Binario compilato non trovato in {compiled_exe}")
        sys.exit(1)

    # 5. Organizzazione cartella di distribuzione dist/RSM
    dist_dir.mkdir(parents=True, exist_ok=True)
    target_exe = dist_dir / ("RSM.exe" if sys.platform == "win32" else "RSM")

    if sys.platform == "win32":
        # Chiude eventuali istanze attive per evitare lock di file su Windows
        subprocess.run(["taskkill", "/F", "/IM", "RSM.exe"], capture_output=True, check=False)
        time.sleep(0.5)

    print(f"Copia dell'eseguibile in {target_exe}...")
    copied = False
    for _ in range(8):
        try:
            shutil.copy2(compiled_exe, target_exe)
            if sys.platform != "win32":
                try:
                    target_exe.chmod(0o755)
                except OSError:
                    pass
            copied = True
            break
        except PermissionError:
            time.sleep(0.4)
    if not copied:
        old_exe = target_exe.with_suffix(".old.exe")
        if old_exe.exists():
            try:
                old_exe.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            target_exe.rename(old_exe)
            shutil.copy2(compiled_exe, target_exe)
        except Exception as e:
            raise PermissionError(
                f"Impossibile accedere a {target_exe}: chiudi l'applicazione prima di compilare."
            ) from e

    # Copia delle librerie dinamiche necessarie (es. WebView2Loader.dll per il runtime WebView2 su Windows)
    for dll in compiled_exe.parent.glob("*.dll"):
        print(f"Copia della libreria runtime {dll.name} in dist/RSM/...")
        shutil.copy2(dll, dist_dir / dll.name)

    webview2_target = dist_dir / "WebView2Loader.dll"
    if sys.platform == "win32" and not webview2_target.exists():
        for candidate in tauri_project_dir.glob("target/**/WebView2Loader.dll"):
            if "x64" in str(candidate) or candidate.parent.name == "release":
                shutil.copy2(candidate, webview2_target)
                print(f"Copia della libreria WebView2Loader.dll da {candidate}...")
                break

    # 6. Copia del backend Python e dei servizi necessari per il micro-server bridge
    src_target = dist_dir / "src"
    if src_target.exists():
        shutil.rmtree(src_target, ignore_errors=True)
    shutil.copytree(project_root / "src", src_target)

    # 7. Garanzia presenza database SQLite in dist/RSM/data
    dist_data.mkdir(parents=True, exist_ok=True)
    dist_db = dist_data / "rsm_inventory.db"
    source_db = project_root / "data" / "rsm_inventory.db"
    if not source_db.exists() and (project_root / "data" / "russo_stock.db").exists():
        source_db = project_root / "data" / "russo_stock.db"

    if not dist_db.exists() or dist_db.stat().st_size == 0:
        if source_db.exists():
            print(f"Copia del database iniziale ({source_db.name}) in dist/RSM/data...")
            shutil.copy2(source_db, dist_db)
    else:
        print(f"Database SQLite di produzione preservato ({dist_db.name}).")

    # 8. Copia file di configurazione config.json
    source_config = project_root / "config.json"
    if source_config.exists():
        shutil.copy2(source_config, dist_config)
    elif not dist_config.exists():
        with open(dist_config, "w", encoding="utf-8") as f:
            json.dump({"email_sync_address": "", "email_sync_app_password": ""}, f, indent=2, ensure_ascii=False)

    # 9. Copia del README.md nella cartella di rilascio
    source_readme = project_root / "README.md"
    if source_readme.exists():
        shutil.copy(source_readme, dist_dir / "README.md")

    size_mb = target_exe.stat().st_size / (1024 * 1024)
    print("\n[OK] Build Tauri completata con successo!")
    print(f"[OK] Cartella di rilascio: '{dist_dir}'")
    print(f"[OK] Eseguibile nativo: '{target_exe}' ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
