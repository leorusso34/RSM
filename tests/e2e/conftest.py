"""Fixture e infrastruttura di supporto per i test E2E di RSM.

Fornisce:
1. Server HTTP Sandbox isolato su porta 28475 con database SQLite effimero in %TEMP%.
2. Servizio integrato per file statici web/ e chiamate API bridge /api/.
3. Fixture Playwright headless con intercettazione trasparente delle chiamate :28472 -> :28475.
4. Registrazione video automatica per livello in tests/e2e/artifacts/videos/.
"""

import mimetypes
import os
import shutil
import tempfile
import threading
import time
import urllib.request
from collections.abc import Generator
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright

from src.database import InventoryDatabase
from src.services.bridge_server import RSMBridgeHandler

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = PROJECT_ROOT / "web"
ARTIFACTS_DIR = PROJECT_ROOT / "tests" / "e2e" / "artifacts"
VIDEOS_DIR = ARTIFACTS_DIR / "videos"
SCREENSHOTS_DIR = ARTIFACTS_DIR / "screenshots"

SANDBOX_HOST = "127.0.0.1"
SANDBOX_PORT = 28475
SANDBOX_BASE_URL = f"http://{SANDBOX_HOST}:{SANDBOX_PORT}"

# Assicura l'esistenza delle cartelle artefatti
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


class SandboxBridgeHandler(RSMBridgeHandler):
    """Handler HTTP che serve sia le API REST di RSM sul DB sandbox sia i file statici di web/."""

    sandbox_db_path: Path | None = None
    _thread_local = threading.local()

    @property
    def db(self) -> InventoryDatabase:
        if not hasattr(self._thread_local, "db") or self._thread_local.db is None:
            if not self.sandbox_db_path:
                raise RuntimeError("sandbox_db_path non configurato.")
            self._thread_local.db = InventoryDatabase(self.sandbox_db_path)
        return self._thread_local.db

    def do_GET(self) -> None:
        """Indirizza /api/ al backend RSM e il resto alla cartella web/."""
        if self.path.startswith("/api/"):
            super().do_GET()
            return

        clean_path = self.path.split("?")[0].lstrip("/") or "index.html"
        target_file = (WEB_DIR / clean_path).resolve()

        # Protezione path traversal
        if not str(target_file).startswith(str(WEB_DIR)) or not target_file.is_file():
            self.send_error(404, f"File non trovato: {clean_path}")
            return

        mime_type, _ = mimetypes.guess_type(str(target_file))
        if clean_path.endswith(".js"):
            mime_type = "text/javascript"
        elif clean_path.endswith(".css"):
            mime_type = "text/css"
        elif clean_path.endswith(".html"):
            mime_type = "text/html"

        try:
            content = target_file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(content)
        except OSError as e:
            self.send_error(500, f"Errore lettura file: {e}")

    def log_message(self, format: str, *args: Any) -> None:
        """Silenzia i log HTTP standard per mantenere l'output dei test pulito."""


class SandboxServer:
    """Gestisce il ciclo di vita del server HTTP sandbox su porta 28475."""

    def __init__(self, port: int = SANDBOX_PORT) -> None:
        self.port = port
        self.temp_dir = Path(tempfile.mkdtemp(prefix="rsm_e2e_sandbox_"))
        self.db_path = self.temp_dir / "test_sandbox.db"
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

        # Pre-inizializza lo schema nel thread principale per evitare lock SQLite concorrenti
        init_db = InventoryDatabase(self.db_path)
        init_db.connection.close()

    def start(self) -> None:
        SandboxBridgeHandler.sandbox_db_path = self.db_path
        self.server = ThreadingHTTPServer((SANDBOX_HOST, self.port), SandboxBridgeHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        # Attendi che il server risponda a /api/health
        deadline = time.time() + 5.0
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"{SANDBOX_BASE_URL}/api/health", timeout=1) as resp:
                    if resp.status == 200:
                        return
            except OSError:
                time.sleep(0.05)
        raise TimeoutError(f"Impossibile avviare il server Sandbox su {SANDBOX_BASE_URL}")

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except OSError:
                pass


@pytest.fixture(scope="session")
def sandbox_server() -> Generator[SandboxServer, None, None]:
    """Fixture di sessione che avvia il server sandbox su 127.0.0.1:28475."""
    server = SandboxServer(SANDBOX_PORT)
    server.start()
    yield server
    server.stop()


class E2EContextManager:
    """Crea una pagina Playwright configurata con video, screenshot e routing trasparente."""

    def __init__(self, playwright: Playwright, level_name: str) -> None:
        self.playwright = playwright
        self.level_name = level_name
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.console_errors: list[str] = []
        self.raw_video_dir = Path(tempfile.mkdtemp(prefix=f"rsm_vid_{level_name}_"))
        self.final_video_path: Path | None = None

    def __enter__(self) -> tuple[Page, list[str]]:
        self.browser = self.playwright.chromium.launch(
            headless=True,
            slow_mo=200,  # Ritmo umano naturale per le registrazioni video (200ms per azione)
            args=[
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        self.context = self.browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=str(self.raw_video_dir),
            record_video_size={"width": 1440, "height": 900},
        )
        self.page = self.context.new_page()

        # Intercettazione trasparente delle chiamate API :28472 -> :28475 (Zero-Code-Touch)
        def route_interceptor(route: Any) -> None:
            url = route.request.url
            if "127.0.0.1:28472" in url:
                new_url = url.replace("127.0.0.1:28472", f"127.0.0.1:{SANDBOX_PORT}")
                route.continue_(url=new_url)
            else:
                route.continue_()

        self.page.route("**/*", route_interceptor)

        # Accetta automaticamente popup nativi (confirm / alert)
        self.page.on("dialog", lambda dialog: dialog.accept())

        # Raccoglie errori rossi in console
        def on_console(msg: Any) -> None:
            if msg.type == "error":
                self.console_errors.append(msg.text)

        self.page.on("console", on_console)
        return self.page, self.console_errors

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        video_obj = self.page.video if self.page else None
        video_path = video_obj.path() if video_obj else None

        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()

        # Copia il video nella directory ufficiale
        if video_path and os.path.isfile(video_path):
            target = VIDEOS_DIR / f"{self.level_name}.webm"
            shutil.copy2(video_path, target)
            self.final_video_path = target

        shutil.rmtree(self.raw_video_dir, ignore_errors=True)
