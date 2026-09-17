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
    Esegue il download dello zip di aggiornamento, estrae i file e avvia lo script
    di sostituzione Windows garantendo la preservazione del database locale e del config.json.
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

        # Se lo zip contiene una cartella radice (es. 'RSM/' o 'dist/RSM/'), usiamo quella
        source_root = extract_dir
        subfolders = [f for f in extract_dir.iterdir() if f.is_dir()]
        if len(subfolders) == 1 and not any(f.is_file() for f in extract_dir.iterdir()):
            source_root = subfolders[0]

        target_app_dir = PROJECT_DIR.resolve()

        if status_callback:
            status_callback("Riavvio dell'applicazione...")

        # Genera lo script batch Windows per la sostituzione pulita a processo terminato
        bat_script = temp_dir / "apply_update.bat"
        bat_content = f"""@echo off
chcp 65001 >nul
title Aggiornamento RSM in corso...

echo Attesa chiusura di RSM...
timeout /t 2 /nobreak >nul

:: Termina forzatamente il processo se ancora attivo
taskkill /f /im RSM.exe >nul 2>&1
timeout /t 1 /nobreak >nul

echo Applicazione nuovi file...
:: Copia tutti i file aggiornati escludendo tassativamente la cartella dati e il config.json
robocopy "{source_root}" "{target_app_dir}" /E /XF config.json /XD data >nul

echo Pulizia file temporanei...
rd /s /q "{temp_dir}" >nul 2>&1

echo Riavvio di RSM...
start "" "{target_app_dir}\\RSM.exe"
exit
"""
        with open(bat_script, "w", encoding="utf-8") as f:
            f.write(bat_content)

        # Lancia lo script di aggiornamento in un processo separato indipendente
        CREATE_NO_WINDOW = 0x08000000
        DETACHED_PROCESS = 0x00000008
        flags = CREATE_NO_WINDOW | DETACHED_PROCESS if sys.platform == "win32" else 0

        subprocess.Popen(
            ["cmd.exe", "/c", str(bat_script)],
            creationflags=flags,
            close_fds=True,
            shell=False,
        )

        # Chiude l'applicazione corrente in modo pulito
        sys.exit(0)

    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise exc
