"""RSM - Reseller Stock & Sales Manager.

Entry point principale di avvio.
Avvia la nuova interfaccia grafica nativa Tauri (Zero-Lag).
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
        subprocess.run(cmd, shell=True, capture_output=True, timeout=5, check=False)
    except (subprocess.SubprocessError, OSError) as err:
        print(f"[RSM] Avviso chiusura bridge obsoleto: {err}")


def start_bridge_server(root_dir: Path, port: int = 28472) -> None:
    """Avvia il server bridge locale con l'interprete Python corrente."""
    import socket
    import time

    script = root_dir / "src" / "services" / "bridge_server.py"
    if not script.exists():
        return

    flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
    try:
        subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(root_dir),
            creationflags=flags,
            close_fds=True,
        )
        for _ in range(15):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.settimeout(0.1)
                s.connect(("127.0.0.1", port))
                s.close()
                break
            except OSError:
                time.sleep(0.1)
    except (OSError, RuntimeError) as err:
        print(f"[RSM] Avviso avvio bridge: {err}")


def main() -> None:
    root_dir = Path(__file__).resolve().parent

    # 1. Termina eventuali bridge precedenti per garantire che le nuove API siano attive
    kill_stale_bridge(28472)

    # 2. Sincronizza il backend in dist/RSM
    dist_bridge = root_dir / "dist" / "RSM" / "src" / "services" / "bridge_server.py"
    src_bridge = root_dir / "src" / "services" / "bridge_server.py"
    if src_bridge.exists() and dist_bridge.parent.exists():
        try:
            shutil.copy2(src_bridge, dist_bridge)
        except OSError as err:
            print(f"[RSM] Avviso copia bridge_server: {err}")

    # 3. Avvia il server bridge con il Python attivo
    start_bridge_server(root_dir, 28472)

    # 3. Cerca l'eseguibile nativo di Tauri
    dist_exe = root_dir / "dist" / "RSM" / ("RSM.exe" if sys.platform == "win32" else "RSM")
    release_exe = root_dir / "src-tauri" / "target" / "release" / ("rsm-desktop.exe" if sys.platform == "win32" else "rsm-desktop")

    target_exe = None
    if dist_exe.exists():
        target_exe = dist_exe
    elif release_exe.exists():
        target_exe = release_exe

    if target_exe:
        print(f"[RSM] Avvio applicazione ({target_exe.name})...")
        try:
            if sys.platform == "win32":
                os.startfile(str(target_exe), show_cmd=3)
            else:
                subprocess.Popen([str(target_exe)])
            return
        except OSError as err:
            print(f"[RSM] Errore nell'avvio di {target_exe}: {err}")

    print("Eseguibile non trovato. Esegui 'python build.py' per compilare la versione Tauri.")


if __name__ == "__main__":
    main()
