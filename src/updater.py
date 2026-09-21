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

        # Individua in modo robusto la cartella sorgente contenente l'applicazione:
        # Se 'RSM.exe' si trova direttamente in extract_dir, usiamo quella.
        # Altrimenti cerchiamo la cartella che contiene 'RSM.exe' (es. dentro 'RSM/').
        if (extract_dir / "RSM.exe").exists():
            source_root = extract_dir
        else:
            exe_candidates = list(extract_dir.rglob("RSM.exe"))
            if exe_candidates:
                source_root = exe_candidates[0].parent
            else:
                subfolders = [f for f in extract_dir.iterdir() if f.is_dir()]
                source_root = subfolders[0] if len(subfolders) == 1 else extract_dir

        # Determina la directory di destinazione corretta:
        # - Se gira come exe compilato (PyInstaller): è la cartella dell'eseguibile stesso
        # - Se gira come script Python (sviluppo/testing): è dist/RSM/ nella root del progetto
        if getattr(sys, "frozen", False):
            target_app_dir = Path(sys.executable).resolve().parent
        else:
            target_app_dir = (PROJECT_DIR / "dist" / "RSM").resolve()

        if status_callback:
            status_callback("Avvio aggiornamento in background...")

        # Genera un batch script helper nella directory temp di sistema.
        # Si usa .bat invece di uno script Python perché nell'eseguibile
        # PyInstaller frozen sys.executable è RSM.exe e non un interprete Python:
        # lanciare "RSM.exe script.py" riaprirebbe solo l'applicazione ignorando
        # l'argomento, senza mai eseguire la logica di aggiornamento.
        # Un batch file viene eseguito direttamente da cmd.exe senza alcuna dipendenza.
        system_temp = Path(tempfile.gettempdir())
        helper_script = system_temp / "rsm_apply_update.bat"
        log_path = system_temp / "rsm_update.log"

        # Stringhe pulite senza barre finali per evitare escape non voluti in cmd.exe
        src = str(source_root).rstrip(r"\/")
        tgt = str(target_app_dir).rstrip(r"\/")
        tmp = str(temp_dir).rstrip(r"\/")
        log = str(log_path).rstrip(r"\/")

        helper_code = (
            "@echo off\r\n"
            "setlocal EnableDelayedExpansion\r\n"
            "\r\n"
            f'set "LOG={log}"\r\n'
            f'set "SOURCE={src}"\r\n'
            f'set "TARGET={tgt}"\r\n'
            f'set "TMPDIR={tmp}"\r\n'
            "\r\n"
            'echo === RSM Update Helper avviato === >> "!LOG!"\r\n'
            'echo source_root  = !SOURCE! >> "!LOG!"\r\n'
            'echo target_dir   = !TARGET! >> "!LOG!"\r\n'
            "\r\n"
            ":: Attende che RSM rilasci i file (4 secondi in modo totalmente silenzioso)\r\n"
            'echo Attesa chiusura RSM... >> "!LOG!"\r\n'
            "ping 127.0.0.1 -n 5 > nul\r\n"
            "\r\n"
            ":: Chiude eventuali processi residui bloccati prima della copia\r\n"
            "taskkill /F /IM RSM.exe > nul 2>&1\r\n"
            "\r\n"
            ":: Copia tutti i file aggiornati preservando config.json e data/\r\n"
            ":: robocopy exit code 0-7 = successo, 8+ = errori\r\n"
            'echo Copia file aggiornati ^(robocopy^)... >> "!LOG!"\r\n'
            'robocopy "!SOURCE!" "!TARGET!" /E /XD data /XF config.json /IS /IT /IM /R:5 /W:2 >> "!LOG!" 2>&1\r\n'
            'set "RC=!ERRORLEVEL!"\r\n'
            'echo Robocopy exit code: !RC! >> "!LOG!"\r\n'
            "\r\n"
            "if !RC! LSS 8 (\r\n"
            '    echo Copia completata con successo. >> "!LOG!"\r\n'
            ") else (\r\n"
            '    echo ATTENZIONE: Robocopy ha riportato errori ^(codice !RC!^). >> "!LOG!"\r\n'
            ")\r\n"
            "\r\n"
            ":: Riavvia RSM impostando esplicitamente la cartella di lavoro corretta\r\n"
            'if exist "!TARGET!\\RSM.exe" (\r\n'
            '    echo Riavvio RSM: !TARGET!\\RSM.exe >> "!LOG!"\r\n'
            '    start "" /d "!TARGET!" "!TARGET!\\RSM.exe"\r\n'
            '    echo RSM riavviato con successo. >> "!LOG!"\r\n'
            ") else (\r\n"
            '    echo ERRORE: RSM.exe non trovato in !TARGET! >> "!LOG!"\r\n'
            ")\r\n"
            "\r\n"
            ":: Pulizia cartella temporanea\r\n"
            'echo Pulizia cartella temporanea... >> "!LOG!"\r\n'
            'rmdir /s /q "!TMPDIR!" 2>> "!LOG!"\r\n'
            "\r\n"
            'echo === Fine Update Helper === >> "!LOG!"\r\n'
            "\r\n"
            'del "%~f0"\r\n'
        )

        # newline="" per evitare che Python aggiunga \r extra ai \r\n manuali
        with open(helper_script, "w", encoding="utf-8", newline="") as f:
            f.write(helper_code)

        CREATE_NO_WINDOW = 0x08000000
        CREATE_NEW_PROCESS_GROUP = 0x00000200

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE: nasconde completamente qualsiasi finestra di console

        subprocess.Popen(
            ["cmd.exe", "/c", str(helper_script)],
            creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
            startupinfo=startupinfo,
            close_fds=True,
            shell=False,
        )

        # Chiude l'intero processo immediatamente per rilasciare tutti i file
        os._exit(0)

    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise exc
