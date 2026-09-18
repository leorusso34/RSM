#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modulo per la verifica, download e applicazione automatica degli aggiornamenti di RSM.
"""

import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from .config import APP_VERSION, GITHUB_REPO, PROJECT_DIR


def parse_version_tuple(version_str: str) -> Tuple[int, ...]:
    """
    Estrae una tupla di interi da una stringa di versione (es. 'v1.2.0' -> (1, 2, 0)).
    Consente confronti semantici corretti (es. (1, 10, 0) > (1, 2, 0)).
    """
    if not version_str:
        return (0,)
    # Rimuove prefissi 'v' o 'V' e spazi
    cleaned = version_str.strip().lstrip("vV")
    # Estrae tutti i blocchi numerici
    numbers = re.findall(r"\d+", cleaned)
    if not numbers:
        return (0,)
    return tuple(int(n) for n in numbers)


def check_for_updates(
    current_version: str = APP_VERSION,
    repo: str = GITHUB_REPO,
    github_token: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Controlla in modo sicuro se è disponibile una nuova versione su GitHub Releases.

    Returns:
        Dizionario con i dettagli dell'aggiornamento o None se l'app è già aggiornata.
    """
    if not repo or "/" not in repo:
        return None

    owner, repo_name = repo.split("/", 1)
    headers = {
        "User-Agent": "RSM-App-Updater",
        "Accept": "application/vnd.github.v3+json",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token.strip()}"

    try:
        conn = http.client.HTTPSConnection("api.github.com", timeout=8)
        conn.request("GET", f"/repos/{owner}/{repo_name}/releases/latest", headers=headers)
        resp = conn.getresponse()
        raw_data = resp.read().decode("utf-8")
        conn.close()

        if resp.status != 200:
            return None

        data = json.loads(raw_data)
        tag_name = data.get("tag_name", "").strip()
        if not tag_name:
            return None

        # Confronto versioni
        if parse_version_tuple(tag_name) <= parse_version_tuple(current_version):
            return None

        # Cerca un asset .zip (preferibilmente contenente 'RSM' o il primo zip)
        assets = data.get("assets", [])
        zip_asset = None
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(".zip"):
                if "rsm" in name:
                    zip_asset = asset
                    break
                if not zip_asset:
                    zip_asset = asset

        if not zip_asset:
            return None

        # Per repository privati usiamo l'endpoint API dell'asset (zip_asset["url"]) con token
        download_url = (zip_asset.get("url") if github_token else zip_asset.get("browser_download_url")) or zip_asset.get("url")
        is_api_asset = bool(github_token or (zip_asset.get("url") and not zip_asset.get("browser_download_url")))

        return {
            "version": tag_name,
            "title": data.get("name") or tag_name,
            "changelog": (data.get("body") or "").strip() or "Nessun dettaglio specificato.",
            "download_url": download_url,
            "asset_name": zip_asset.get("name", "RSM-update.zip"),
            "size_bytes": zip_asset.get("size", 0),
            "is_api_asset": is_api_asset,
        }
    except Exception:
        return None


def download_file_with_redirects(
    url: str,
    dest_path: Path,
    headers: Optional[Dict[str, str]] = None,
    progress_callback: Optional[Callable[[float], None]] = None,
    max_redirects: int = 5,
) -> None:
    """
    Scarica un file gestendo automaticamente i redirect HTTP/HTTPS (es. GitHub S3 storage)
    e notificando l'avanzamento tramite callback (da 0.0 a 1.0).
    """
    current_url = url
    req_headers = dict(headers or {})
    if "User-Agent" not in req_headers:
        req_headers["User-Agent"] = "RSM-App-Updater"

    for _ in range(max_redirects):
        parsed = urllib.parse.urlparse(current_url)
        is_https = parsed.scheme == "https"
        host = parsed.netloc
        path = parsed.path
        if parsed.query:
            path += f"?{parsed.query}"

        conn_cls = http.client.HTTPSConnection if is_https else http.client.HTTPConnection
        conn = conn_cls(host, timeout=30)
        conn.request("GET", path, headers=req_headers)
        resp = conn.getresponse()

        # Gestione redirect 301, 302, 303, 307, 308
        if resp.status in (301, 302, 303, 307, 308):
            location = resp.getheader("Location")
            conn.close()
            if not location:
                raise RuntimeError(f"Redirect HTTP {resp.status} senza header Location")
            current_url = location
            # Se reindirizzato ad AWS S3 (objects.githubusercontent.com), rimuoviamo l'header Authorization di GitHub
            if "githubusercontent.com" in location:
                req_headers.pop("Authorization", None)
            continue

        if resp.status != 200:
            conn.close()
            raise RuntimeError(f"Errore download HTTP {resp.status}: {resp.reason}")

        total_length = int(resp.getheader("Content-Length", "0"))
        downloaded = 0
        chunk_size = 64 * 1024  # 64 KB

        with open(dest_path, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total_length > 0 and progress_callback:
                    progress_callback(min(1.0, downloaded / total_length))

        conn.close()
        if progress_callback:
            progress_callback(1.0)
        return

    raise RuntimeError("Superato il limite massimo di redirect HTTP")


def apply_update_and_restart(
    download_url: str,
    github_token: str = "",
    progress_callback: Optional[Callable[[float], None]] = None,
    status_callback: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Esegue il download dello zip di aggiornamento, estrae i file e avvia uno script
    Python di sostituzione che gira in background garantendo la preservazione del
    database locale e del config.json.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="rsm_update_"))
    zip_dest = temp_dir / "update.zip"

    try:
        if status_callback:
            status_callback("Download dell'aggiornamento in corso...")

        headers = {}
        if github_token:
            headers["Authorization"] = f"Bearer {github_token.strip()}"
            headers["Accept"] = "application/octet-stream"

        download_file_with_redirects(
            download_url,
            zip_dest,
            headers=headers,
            progress_callback=progress_callback,
        )

        if status_callback:
            status_callback("Estrazione file in corso...")

        extract_dir = temp_dir / "extracted"
        extract_dir.mkdir(exist_ok=True)

        with zipfile.ZipFile(zip_dest, "r") as z:
            z.extractall(extract_dir)

        # Se lo zip contiene una cartella radice (es. 'RSM/'), usiamo quella
        source_root = extract_dir
        subfolders = [f for f in extract_dir.iterdir() if f.is_dir()]
        if len(subfolders) == 1 and not any(f.is_file() for f in extract_dir.iterdir()):
            source_root = subfolders[0]

        # Determina la directory di destinazione corretta:
        # - Se gira come exe compilato (PyInstaller): è la cartella dell'eseguibile stesso
        # - Se gira come script Python (sviluppo/testing): è dist/RSM/ nella root del progetto
        if getattr(sys, "frozen", False):
            target_app_dir = Path(sys.executable).resolve().parent
        else:
            target_app_dir = (PROJECT_DIR / "dist" / "RSM").resolve()

        if status_callback:
            status_callback("Avvio aggiornamento in background...")

        # Percorso dell'interprete Python da usare nello script helper
        python_exe = Path(sys.executable).resolve()

        # Genera lo script Python helper nella directory temp di sistema.
        # subprocess.Popen con lista di argomenti e shell=False passa i percorsi
        # direttamente a CreateProcess, gestendo correttamente gli spazi senza quoting manuale.
        system_temp = Path(tempfile.gettempdir())
        helper_script = system_temp / "rsm_apply_update.py"

        helper_code = f"""\
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

LOG = Path(r"{system_temp}") / "rsm_update.log"

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\\n")

log("=== RSM Update Helper avviato ===")

source_root = Path(r"{source_root}")
target_app_dir = Path(r"{target_app_dir}")
temp_dir = Path(r"{temp_dir}")
exe_path = target_app_dir / "RSM.exe"

log(f"source_root  = {{source_root}}")
log(f"target_dir   = {{target_app_dir}}")
log(f"exe_path     = {{exe_path}}")

# Attende che RSM si chiuda (max 10 secondi)
log("Attesa chiusura RSM...")
time.sleep(3)

# Copia i file aggiornati, preservando config.json e data/
log("Copia file aggiornati...")
for item in source_root.iterdir():
    name = item.name
    if name in ("config.json", "data"):
        log(f"  Saltato (preservato): {{name}}")
        continue
    dest = target_app_dir / name
    try:
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
        log(f"  Copiato: {{name}}")
    except Exception as e:
        log(f"  ERRORE copia {{name}}: {{e}}")

# Pulizia cartella temporanea
log("Pulizia temp...")
try:
    shutil.rmtree(temp_dir, ignore_errors=True)
except Exception as e:
    log(f"  ERRORE pulizia: {{e}}")

# Rilancio applicazione
log(f"Riavvio RSM: {{exe_path}}")
if exe_path.exists():
    try:
        subprocess.Popen(
            [str(exe_path)],
            cwd=str(target_app_dir),
            close_fds=True,
        )
        log("RSM riavviato con successo.")
    except Exception as e:
        log(f"ERRORE riavvio: {{e}}")
else:
    log(f"ERRORE: RSM.exe non trovato in {{target_app_dir}}")

# Auto-eliminazione di questo script
try:
    os.remove(__file__)
except Exception:
    pass
"""

        with open(helper_script, "w", encoding="utf-8") as f:
            f.write(helper_code)

        # Lancia lo script helper con pythonw.exe (no finestra console) se disponibile,
        # altrimenti con python.exe + CREATE_NO_WINDOW
        pythonw_exe = python_exe.parent / "pythonw.exe"
        launcher = pythonw_exe if pythonw_exe.exists() else python_exe

        CREATE_NO_WINDOW = 0x08000000
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        flags = CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

        subprocess.Popen(
            [str(launcher), str(helper_script)],
            creationflags=flags,
            close_fds=True,
            shell=False,
        )

        # Chiude l'intero processo Python immediatamente per rilasciare tutti i file
        os._exit(0)

    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise exc
