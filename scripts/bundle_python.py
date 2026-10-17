"""Script per l'incorporamento del runtime Python isolato e delle dipendenze per RSM (Windows e macOS).

Scarica il runtime ufficiale autonomo (Embeddable per Windows, Standalone per macOS),
configura l'ambiente e installa tutte le librerie necessarie (openpyxl, sounddevice, numpy, scipy, SpeechRecognition)
direttamente nella cartella di distribuzione dist/RSM/python/.
Include un controllo di cache per evitare download e installazioni ripetute se i file sono già presenti e integri.
"""

import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

# Versioni runtime
PYTHON_WIN_VERSION = "3.13.2"
PYTHON_WIN_URL = f"https://www.python.org/ftp/python/{PYTHON_WIN_VERSION}/python-{PYTHON_WIN_VERSION}-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

MAC_PYTHON_TAG = "20261013"
MAC_PYTHON_VERSION = "3.13.16"

# Pacchetti runtime necessari per tutte le funzionalità di RSM
RUNTIME_PACKAGES = [
    "openpyxl>=3.1.0,<4",
    "sounddevice>=0.4.6",
    "numpy>=1.26.0",
    "scipy>=1.11.0",
    "SpeechRecognition>=3.10.0",
]


def is_python_bundle_valid(target_py_dir: Path) -> bool:
    """Verifica se il runtime Python locale esiste già ed è completo di tutte le librerie."""
    if not target_py_dir.exists():
        return False

    py_exe = target_py_dir / ("python.exe" if sys.platform == "win32" else "bin/python3")
    if not py_exe.exists():
        return False

    verify_code = (
        "import sqlite3; "
        "import openpyxl; "
        "import sounddevice as sd; "
        "import numpy as np; "
        "import scipy.io.wavfile as wav; "
        "import speech_recognition as sr; "
        "print('VERIFICA_OK')"
    )
    res = subprocess.run([str(py_exe), "-c", verify_code], capture_output=True, text=True, check=False)
    return res.returncode == 0 and "VERIFICA_OK" in res.stdout


def bundle_python_windows(target_py_dir: Path, tmp_dir: Path) -> None:
    """Scarica e configura Python Embeddable per Windows."""
    zip_path = tmp_dir / f"python-{PYTHON_WIN_VERSION}-embed-amd64.zip"

    print(f"[BUNDLE] Download Python Embeddable per Windows ({PYTHON_WIN_URL})...")
    urllib.request.urlretrieve(PYTHON_WIN_URL, zip_path)
    print(f"[BUNDLE] Download completato ({zip_path.stat().st_size / (1024 * 1024):.1f} MB).")

    print("[BUNDLE] Estrazione runtime...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(target_py_dir)

    # Configurazione ._pth
    pth_files = list(target_py_dir.glob("*._pth"))
    if not pth_files:
        raise RuntimeError("File *._pth non trovato nel pacchetto embeddable estratto.")

    pth_file = pth_files[0]
    content = pth_file.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]

    for entry in ["Lib/site-packages", "..", "import site"]:
        if entry not in lines:
            lines.append(entry)

    pth_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[BUNDLE] Configurato {pth_file.name} con supporto per site-packages e root di progetto.")

    # Installazione pip
    py_exe = target_py_dir / "python.exe"
    get_pip_path = tmp_dir / "get-pip.py"
    print(f"[BUNDLE] Download get-pip.py da {GET_PIP_URL}...")
    urllib.request.urlretrieve(GET_PIP_URL, get_pip_path)

    print("[BUNDLE] Installazione pip nel runtime isolato...")
    res = subprocess.run(
        [str(py_exe), str(get_pip_path), "--no-warn-script-location"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Errore installazione get-pip:\n{res.stderr}")

    # Installazione dipendenze
    print(f"[BUNDLE] Installazione pacchetti runtime: {', '.join(RUNTIME_PACKAGES)}...")
    pip_cmd = [str(py_exe), "-m", "pip", "install", *RUNTIME_PACKAGES, "--no-warn-script-location"]
    res = subprocess.run(pip_cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"Errore durante l'installazione dei pacchetti con pip:\n{res.stderr}")

    # Pulizia cache pip
    subprocess.run([str(py_exe), "-m", "pip", "cache", "purge"], capture_output=True, check=False)


def bundle_python_macos(dist_dir: Path, target_py_dir: Path, tmp_dir: Path) -> None:
    """Scarica e configura il runtime Python Standalone per macOS."""
    arch = "aarch64" if platform.machine() in ("arm64", "aarch64") else "x86_64"
    mac_url = f"https://github.com/astral-sh/python-build-standalone/releases/download/{MAC_PYTHON_TAG}/cpython-{MAC_PYTHON_VERSION}%2B{MAC_PYTHON_TAG}-{arch}-apple-darwin-install_only.tar.gz"

    print(f"[BUNDLE] Download Python Standalone per macOS ({arch}) da {mac_url}...")
    tar_path = tmp_dir / "python-mac.tar.gz"
    urllib.request.urlretrieve(mac_url, tar_path)
    print(f"[BUNDLE] Download completato ({tar_path.stat().st_size / (1024 * 1024):.1f} MB).")

    print("[BUNDLE] Estrazione runtime macOS...")
    with tarfile.open(tar_path, "r:gz") as t:
        t.extractall(dist_dir)

    py_bin = target_py_dir / "bin" / "python3"
    if not py_bin.exists():
        raise RuntimeError(f"Binario {py_bin} non trovato dopo l'estrazione.")

    try:
        py_bin.chmod(0o755)
    except OSError:
        pass

    # Installazione dipendenze
    print(f"[BUNDLE] Installazione pacchetti runtime su macOS: {', '.join(RUNTIME_PACKAGES)}...")
    pip_cmd = [str(py_bin), "-m", "pip", "install", *RUNTIME_PACKAGES, "--no-warn-script-location"]
    res = subprocess.run(pip_cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"Errore durante l'installazione dei pacchetti con pip su macOS:\n{res.stderr}")

    # Pulizia cache pip
    subprocess.run([str(py_bin), "-m", "pip", "cache", "purge"], capture_output=True, check=False)


def bundle_python(project_root: Path) -> None:
    dist_dir = project_root / "dist" / "RSM"
    if not dist_dir.exists():
        raise RuntimeError(f"Cartella di rilascio non trovata: {dist_dir}. Esegui prima build.py.")

    target_py_dir = dist_dir / "python"

    # Controllo cache: se il runtime è già presente e integro, salta il processo
    if is_python_bundle_valid(target_py_dir):
        print(f"[BUNDLE] Runtime Python già presente e integro al 100% in: {target_py_dir}")
        print("[BUNDLE] Salto il download e l'installazione (Cache valida).\n")
        return

    print(f"\n[BUNDLE] Inizio configurazione runtime Python isolato in: {target_py_dir}")
    if target_py_dir.exists():
        print("[BUNDLE] Rimozione cartella python incompleta o obsoleta...")
        shutil.rmtree(target_py_dir, ignore_errors=True)
    target_py_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="rsm_py_embed_") as tmp_str:
        tmp_dir = Path(tmp_str)
        if sys.platform == "win32":
            bundle_python_windows(target_py_dir, tmp_dir)
        elif sys.platform == "darwin":
            bundle_python_macos(dist_dir, target_py_dir, tmp_dir)
        else:
            print(f"[BUNDLE] Piattaforma non supportata per l'embedding: {sys.platform}")
            return

    # Verifica finale di integrità
    print("[BUNDLE] Verifica finale di integrità dei moduli caricati...")
    if not is_python_bundle_valid(target_py_dir):
        raise RuntimeError("Verifica di integrità finale fallita.")

    total_size_mb = sum(f.stat().st_size for f in target_py_dir.rglob("*") if f.is_file()) / (1024 * 1024)
    print(f"[OK] Tutti i moduli verificati con successo! Dimensione runtime: {total_size_mb:.1f} MB in '{target_py_dir}'\n")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    bundle_python(root)
