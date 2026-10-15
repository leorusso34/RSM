"""RSM - Reseller Stock & Sales Manager.

Entry point principale di avvio.
Avvia la nuova interfaccia grafica nativa Tauri (Zero-Lag).
Per avviare la vecchia interfaccia CustomTkinter di fallback: python RSM.py --legacy
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def kill_stale_bridge(port: int = 28472) -> None:
    """Termina eventuali processi bridge orfani o obsoleti sulla porta specificata."""
    if sys.platform != "win32":
        return
    try:
        cmd = f'powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"'
        subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
    except Exception:
        pass


def needs_rebuild(root_dir: Path, target_exe: Path) -> bool:
    """Verifica se i file sorgente dell'interfaccia sono più recenti dell'eseguibile compilato."""
    if not target_exe.exists():
        return True
    exe_mtime = target_exe.stat().st_mtime

    watch_files = [
        root_dir / "src-tauri" / "tauri.conf.json",
        root_dir / "src-tauri" / "src" / "main.rs",
    ]
    for wf in watch_files:
        if wf.exists() and wf.stat().st_mtime > exe_mtime:
            return True

    web_dir = root_dir / "web"
    if web_dir.exists():
        for f in web_dir.rglob("*"):
            if f.is_file() and f.stat().st_mtime > exe_mtime:
                return True

    return False


def main() -> None:
    root_dir = Path(__file__).resolve().parent

    # Flag per accedere alla vecchia interfaccia CustomTkinter di riferimento
    if "--legacy" in sys.argv:
        from src.main import main as legacy_main
        legacy_main()
        return

    # 1. Termina eventuali bridge precedenti per garantire che le nuove API siano attive
    kill_stale_bridge(28472)

    # 2. Cerca l'eseguibile nativo compilato di Tauri
    dist_exe = root_dir / "dist" / "RSM" / ("RSM.exe" if sys.platform == "win32" else "RSM")

    # 3. Controllo modifiche all'interfaccia: se ci sono novità, ricompila prima di avviare
    if needs_rebuild(root_dir, dist_exe):
        print("[RSM] Nuove modifiche rilevate. Aggiornamento automatico della build nativa Tauri...")
        try:
            import build
            build.main()
        except Exception as err:
            print(f"[RSM] Avviso durante la compilazione: {err}")

    # Sincronizza il backend in dist/RSM
    dist_bridge = root_dir / "dist" / "RSM" / "src" / "services" / "bridge_server.py"
    src_bridge = root_dir / "src" / "services" / "bridge_server.py"
    if src_bridge.exists() and dist_bridge.parent.exists():
        try:
            shutil.copy2(src_bridge, dist_bridge)
        except Exception:
            pass

    if dist_exe.exists():
        print(f"[RSM] Avvio interfaccia nativa Tauri ({dist_exe.name})...")
        try:
            if sys.platform == "win32":
                os.startfile(str(dist_exe))
            else:
                subprocess.Popen([str(dist_exe)])
            return
        except Exception as err:
            print(f"[RSM] Errore nell'avvio di {dist_exe}: {err}")

    print("Esegui 'python build.py' per compilare la versione Tauri.")


if __name__ == "__main__":
    main()

