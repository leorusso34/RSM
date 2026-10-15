"""RSM - Reseller Stock & Sales Manager.

Entry point principale di avvio.
Avvia la nuova interfaccia grafica nativa Tauri (Zero-Lag).
Per avviare la vecchia interfaccia CustomTkinter di fallback: python RSM.py --legacy
"""

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root_dir = Path(__file__).resolve().parent

    # Flag per accedere alla vecchia interfaccia CustomTkinter di riferimento
    if "--legacy" in sys.argv:
        from src.main import main as legacy_main
        legacy_main()
        return

    # 1. Cerca l'eseguibile nativo compilato di Tauri
    dist_exe = root_dir / "dist" / "RSM" / ("RSM.exe" if sys.platform == "win32" else "RSM")
    release_exe = root_dir / "src-tauri" / "target" / "release" / ("rsm-desktop.exe" if sys.platform == "win32" else "rsm-desktop")

    target_exe = None
    if dist_exe.exists():
        target_exe = dist_exe
    elif release_exe.exists():
        target_exe = release_exe

    if target_exe:
        print(f"[RSM] Avvio interfaccia nativa Tauri ({target_exe.name})...")
        try:
            if sys.platform == "win32":
                os.startfile(str(target_exe))
            else:
                subprocess.Popen([str(target_exe)])
            return
        except Exception as err:
            print(f"[RSM] Errore nell'avvio di {target_exe}: {err}")

    # 2. Se l'eseguibile non è presente, avvia la compilazione
    print("[RSM] Eseguibile Tauri non trovato. Compilazione in corso...")
    try:
        import build
        build.main()
        if dist_exe.exists():
            if sys.platform == "win32":
                os.startfile(str(dist_exe))
            else:
                subprocess.Popen([str(dist_exe)])
            return
    except Exception as err:
        print(f"[RSM] Impossibile compilare automaticamente: {err}")
        print("Esegui 'python build.py' per compilare la versione Tauri.")


if __name__ == "__main__":
    main()
