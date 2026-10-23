"""
Modulo per la verifica, download e applicazione automatica degli aggiornamenti di RSM.
Utilizza direttamente le API pubbliche di GitHub Releases con supporto opzionale al Worker proxy.
"""

import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import APP_VERSION, GITHUB_REPO, PROJECT_DIR, RSM_AUTH_KEY, WORKER_URL


def parse_version_tuple(version_str: str) -> tuple[int, int, int]:
    """
    Estrae una tupla semantica a 3 elementi (major, minor, patch) da una stringa.
    Esempi:
        'update_1.6.1' -> (1, 6, 1)
        'v1.6'         -> (1, 6, 0)
        '2.0.0-rc1'    -> (2, 0, 0)
    """
    if not version_str:
        return (0, 0, 0)
    cleaned = version_str.strip().lstrip("vV")
    numbers = [int(n) for n in re.findall(r"\d+", cleaned)]
    if not numbers:
        return (0, 0, 0)
    while len(numbers) < 3:
        numbers.append(0)
    return (numbers[0], numbers[1], numbers[2])


def _fetch_release_info_github() -> dict[str, Any] | None:
    """Interroga direttamente le API pubbliche di GitHub Releases (nessun token necessario)."""
    if not GITHUB_REPO:
        return None
    try:
        conn = http.client.HTTPSConnection("api.github.com", timeout=10)
        headers = {
            "User-Agent": "RSM-App-Updater",
            "Accept": "application/vnd.github+json",
        }
        conn.request("GET", f"/repos/{GITHUB_REPO}/releases/latest", headers=headers)
        resp = conn.getresponse()
        if resp.status != 200:
            conn.close()
            return None
        raw = resp.read().decode("utf-8")
        conn.close()
        return json.loads(raw)
    except (OSError, http.client.HTTPException, json.JSONDecodeError, TimeoutError, ValueError):
        return None


def _fetch_release_info_worker() -> dict[str, Any] | None:
    """Fallback sul Cloudflare Worker proxy in caso di indisponibilità o rate-limit di GitHub API."""
    if not WORKER_URL:
        return None
    try:
        parsed_w = urllib.parse.urlparse(WORKER_URL.strip())
        w_host = parsed_w.netloc
        w_path = parsed_w.path.rstrip("/") + "/api/updates/latest"
        w_headers = {"User-Agent": "RSM-App-Updater", "Accept": "application/json"}
        if RSM_AUTH_KEY:
            w_headers["X-RSM-Auth"] = RSM_AUTH_KEY.strip()
        conn_cls = http.client.HTTPSConnection if parsed_w.scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(w_host, timeout=10)
        conn.request("GET", w_path, headers=w_headers)
        resp = conn.getresponse()
        if resp.status != 200:
            conn.close()
            return None
        raw = resp.read().decode("utf-8")
        conn.close()
        return json.loads(raw)
    except (OSError, http.client.HTTPException, json.JSONDecodeError, TimeoutError, ValueError):
        return None


def check_for_updates(current_version: str = APP_VERSION) -> dict[str, Any] | None:
    """
    Controlla se è disponibile un aggiornamento interrogando prima GitHub e poi il Worker di fallback.
    """
    data = _fetch_release_info_github() or _fetch_release_info_worker()
    if not data:
        return None

    tag_name = data.get("tag_name", "").strip()
    if not tag_name or parse_version_tuple(tag_name) <= parse_version_tuple(current_version):
        return None

    assets = data.get("assets", [])
    zip_asset = None
    target_keyword = "mac" if sys.platform == "darwin" else "win"

    # 1. Cerca lo zip dedicato al sistema operativo corrente
    for asset in assets:
        name = asset.get("name", "").lower()
        if name.endswith(".zip") and target_keyword in name:
            zip_asset = asset
            break

    # 2. Fallback su zip generico evitando l'altro OS
    if not zip_asset:
        other_keyword = "win" if sys.platform == "darwin" else "mac"
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(".zip") and other_keyword not in name:
                if "rsm" in name:
                    zip_asset = asset
                    break
                if not zip_asset:
                    zip_asset = asset

    # 3. Fallback finale su qualsiasi zip
    if not zip_asset:
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(".zip"):
                zip_asset = asset
                break

    if not zip_asset:
        return None

    # URL di download: preferisci il browser_download_url diretto pubblico di GitHub
    download_url = zip_asset.get("browser_download_url")
    if not download_url and WORKER_URL:
        download_url = f"{WORKER_URL.strip().rstrip('/')}/api/updates/download/{zip_asset.get('id')}"

    return {
        "version": tag_name,
        "title": data.get("name") or tag_name,
        "changelog": (data.get("body") or "").strip() or "Nessun dettaglio specificato.",
        "download_url": download_url,
        "asset_name": zip_asset.get("name", "RSM-update.zip"),
        "size_bytes": zip_asset.get("size", 0),
    }


def download_file_with_redirects(
    url: str,
    dest_path: Path,
    headers: dict[str, str] | None = None,
    progress_callback: Callable[[float], None] | None = None,
    max_redirects: int = 5,
) -> None:
    """Scarica il file seguendo i redirect HTTP (GitHub -> AWS S3 / Azure CDN)."""
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

        if resp.status in (301, 302, 303, 307, 308):
            location = resp.getheader("Location")
            conn.close()
            if not location:
                raise RuntimeError(f"Redirect HTTP {resp.status} senza Location")
            current_url = location
            if "githubusercontent.com" in location:
                req_headers.pop("Authorization", None)
                req_headers.pop("X-RSM-Auth", None)
            continue

        if resp.status != 200:
            conn.close()
            raise RuntimeError(f"Errore download HTTP {resp.status}: {resp.reason}")

        total_length = int(resp.getheader("Content-Length", "0"))
        downloaded = 0
        chunk_size = 64 * 1024

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
    progress_callback: Callable[[float], None] | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> None:
    """Scarica lo zip, estrae i contenuti e lancia lo script di aggiornamento preservando dati e configurazioni."""
    temp_dir = Path(tempfile.mkdtemp(prefix="rsm_update_"))
    zip_dest = temp_dir / "update.zip"

    try:
        if status_callback:
            status_callback("Download dell'aggiornamento in corso...")

        headers = {}
        if RSM_AUTH_KEY and "workers.dev" in download_url:
            headers["X-RSM-Auth"] = RSM_AUTH_KEY.strip()

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

        nested_zips = list(extract_dir.glob("*.zip"))
        if len(nested_zips) == 1 and not (extract_dir / "RSM.exe").is_file() and not (extract_dir / "src").is_dir():
            with zipfile.ZipFile(nested_zips[0], "r") as nz:
                nz.extractall(extract_dir)
            nested_zips[0].unlink(missing_ok=True)

        source_root = None
        if (extract_dir / "RSM.exe").is_file() or (extract_dir / "RSM.app").is_dir() or (extract_dir / "RSM").is_file():
            source_root = extract_dir
        else:
            candidates = (
                [p for p in extract_dir.rglob("RSM.exe") if p.is_file()]
                + [p for p in extract_dir.rglob("RSM.app") if p.is_dir()]
                + [p for p in extract_dir.rglob("RSM") if p.is_file()]
            )
            if candidates:
                cand = candidates[0]
                if cand.name == "RSM.app":
                    source_root = cand.parent
                elif ".app/Contents/MacOS" in cand.as_posix():
                    source_root = cand.parents[2].parent
                else:
                    source_root = cand.parent
            else:
                subfolders = [f for f in extract_dir.iterdir() if f.is_dir()]
                source_root = subfolders[0] if len(subfolders) == 1 else extract_dir

        if not source_root or not source_root.exists():
            source_root = extract_dir

        target_env = os.environ.get("RSM_APP_DIR")
        if target_env and Path(target_env).is_dir():
            target_app_dir = Path(target_env).resolve()
        elif (
            (PROJECT_DIR / "RSM.exe").is_file() or (PROJECT_DIR / "RSM.app").is_dir() or (PROJECT_DIR / "RSM").is_file()
        ):
            target_app_dir = PROJECT_DIR.resolve()
        elif (PROJECT_DIR / "dist" / "RSM" / "RSM.exe").is_file():
            target_app_dir = (PROJECT_DIR / "dist" / "RSM").resolve()
        elif getattr(sys, "frozen", False):
            exe_path = Path(sys.executable).resolve()
            if sys.platform == "darwin" and ".app/Contents/MacOS" in exe_path.as_posix():
                target_app_dir = exe_path.parents[2].parent
            else:
                target_app_dir = exe_path.parent
        else:
            target_app_dir = (PROJECT_DIR / "dist" / "RSM").resolve()

        if status_callback:
            status_callback("Avvio aggiornamento in background...")

        system_temp = Path(tempfile.gettempdir())
        log_path = system_temp / "rsm_update.log"

        src = str(source_root).rstrip(r"\/")
        tgt = str(target_app_dir).rstrip(r"\/")
        tmp = str(temp_dir).rstrip(r"\/")
        log = str(log_path).rstrip(r"\/")

        if sys.platform == "win32":
            helper_script = system_temp / "rsm_apply_update.bat"
            helper_code = (
                "@echo off\r\n"
                "setlocal EnableDelayedExpansion\r\n\r\n"
                f'set "LOG={log}"\r\n'
                f'set "SOURCE={src}"\r\n'
                f'set "TARGET={tgt}"\r\n'
                f'set "TMPDIR={tmp}"\r\n\r\n'
                'echo === RSM Update Helper avviato === >> "!LOG!"\r\n'
                'echo SOURCE = !SOURCE! >> "!LOG!"\r\n'
                'echo TARGET = !TARGET! >> "!LOG!"\r\n\r\n'
                'echo Attesa rilascio file... >> "!LOG!"\r\n'
                "ping 127.0.0.1 -n 4 > nul\r\n\r\n"
                ":: Termina l'albero di processi completo di RSM e WebView2\r\n"
                "taskkill /F /T /IM RSM.exe > nul 2>&1\r\n\r\n"
                ":: Copia file escludendo in modo assoluto data/, config.json e .env\r\n"
                'echo Copia file in corso... >> "!LOG!"\r\n'
                'robocopy "!SOURCE!" "!TARGET!" /E /XD "!SOURCE!\\data" "!TARGET!\\data" /XF "!SOURCE!\\config.json" "!TARGET!\\config.json" "!SOURCE!\\.env" "!TARGET!\\.env" /IS /IT /IM /R:5 /W:2 >> "!LOG!" 2>&1\r\n'
                'set "RC=!ERRORLEVEL!"\r\n'
                'echo Robocopy exit code: !RC! >> "!LOG!"\r\n\r\n'
                "if !RC! LSS 8 (\r\n"
                '    echo Aggiornamento riuscito. Riavvio RSM... >> "!LOG!"\r\n'
                '    if exist "!TARGET!\\RSM.exe" (\r\n'
                '        start "" /d "!TARGET!" "!TARGET!\\RSM.exe"\r\n'
                "    )\r\n"
                ") else (\r\n"
                '    echo ERRORE: Fallimento Robocopy con codice !RC! >> "!LOG!"\r\n'
                "    mshta \"javascript:alert('Impossibile completare l aggiornamento automatico. Controlla il file di log: %TEMP%\\\\rsm_update.log');close();\"\r\n"
                ")\r\n\r\n"
                'rmdir /s /q "!TMPDIR!" 2>> "!LOG!"\r\n'
                'echo === Fine Update Helper === >> "!LOG!"\r\n'
                'del "%~f0"\r\n'
            )
            with open(helper_script, "w", encoding="utf-8", newline="") as f:
                f.write(helper_code)

            CREATE_NO_WINDOW = 0x08000000
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

            subprocess.Popen(
                ["cmd.exe", "/c", str(helper_script)],
                creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
                startupinfo=startupinfo,
                close_fds=True,
                shell=False,
            )
        else:
            helper_script = system_temp / "rsm_apply_update.sh"
            helper_code = (
                "#!/bin/bash\n"
                f'LOG="{log}"\n'
                f'SOURCE="{src}"\n'
                f'TARGET="{tgt}"\n'
                f'TMPDIR="{tmp}"\n\n'
                'echo "=== RSM Update Helper avviato ===" >> "$LOG"\n'
                'echo "SOURCE = $SOURCE" >> "$LOG"\n'
                'echo "TARGET = $TARGET" >> "$LOG"\n\n'
                "sleep 3\n"
                'pkill -x "RSM" 2>/dev/null || true\n\n'
                "if command -v rsync >/dev/null 2>&1; then\n"
                '    rsync -a --exclude="/data" --exclude="/config.json" --exclude="/.env" "$SOURCE/" "$TARGET/" >> "$LOG" 2>&1\n'
                "else\n"
                '    for item in "$SOURCE"/*; do\n'
                '        base=$(basename "$item")\n'
                '        if [ "$base" != "data" ] && [ "$base" != "config.json" ] && [ "$base" != ".env" ]; then\n'
                '            cp -R "$item" "$TARGET/" >> "$LOG" 2>&1\n'
                "        fi\n"
                "    done\n"
                "fi\n\n"
                "# Ripristino fondamentale permessi di esecuzione POSIX\n"
                'if [ -d "$TARGET/RSM.app" ]; then\n'
                '    chmod -R +x "$TARGET/RSM.app/Contents/MacOS" 2>/dev/null || true\n'
                '    chmod -R +x "$TARGET/python/bin" 2>/dev/null || true\n'
                '    echo "Riavvio RSM.app..." >> "$LOG"\n'
                '    open "$TARGET/RSM.app" >> "$LOG" 2>&1\n'
                'elif [ -f "$TARGET/RSM" ]; then\n'
                '    chmod +x "$TARGET/RSM" 2>/dev/null || true\n'
                '    echo "Riavvio RSM..." >> "$LOG"\n'
                '    "$TARGET/RSM" &\n'
                "fi\n\n"
                'rm -rf "$TMPDIR" 2>> "$LOG"\n'
                'echo "=== Fine Update Helper ===" >> "$LOG"\n'
                'rm -- "$0"\n'
            )
            with open(helper_script, "w", encoding="utf-8", newline="\n") as f:
                f.write(helper_code)
            os.chmod(helper_script, 0o755)

            subprocess.Popen(
                ["/bin/bash", str(helper_script)],
                close_fds=True,
                start_new_session=True,
            )

        # Pausa per permettere al server bridge di inviare l'ultimo stato HTTP al frontend prima dell'uscita
        time.sleep(0.6)
        os._exit(0)

    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
