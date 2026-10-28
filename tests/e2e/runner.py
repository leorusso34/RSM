"""Orchestratore a Cascata (Gated Runner) per la Suite E2E di RSM.

Regole operative tassative:
1. Zero-Code-Touch: nessun file dell'applicazione viene modificato durante il test.
2. Fail-Fast per Livello:
   Livello 1 (Smoke) -> se verde -> Livello 2 (CRUD) -> se verde -> Livello 3 (Ciclo Vendita) -> se verde -> Livello 4 (Avanzato).
   Se un livello fallisce, il runner si arresta immediatamente e genera il report HTML.
3. Isolamento Sandbox: server effimero su porta 28475 con DB in %TEMP%.
4. Reportistica Multimediale: C:\\Users\\<user>\\Desktop\\E2E_REPORT_RSM.html con video e screenshot in Base64.
"""

import argparse
import os
import sys
import time
import traceback
from pathlib import Path

# Assicura che la root del progetto sia nel PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from playwright.sync_api import sync_playwright

from tests.e2e.conftest import VIDEOS_DIR, E2EContextManager, SandboxServer
from tests.e2e.report_generator import LevelResult, generate_e2e_html_report
from tests.e2e.test_level1_smoke import run_level1_smoke_checks
from tests.e2e.test_level2_crud import run_level2_crud_checks
from tests.e2e.test_level3_flow import run_level3_flow_checks
from tests.e2e.test_level4_advanced import run_level4_advanced_checks


def extract_error_info(exc: Exception) -> tuple[str, str | None, int | None]:
    """Estrae messaggio, file e riga dell'errore per il report."""
    msg = str(exc)
    tb = traceback.extract_tb(exc.__traceback__)
    if tb:
        last_frame = tb[-1]
        return msg, last_frame.filename, last_frame.lineno
    return msg, None, None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001, S110
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001, S110
            pass

    parser = argparse.ArgumentParser(description="RSM End-to-End Cascading Test Runner")
    parser.add_argument(
        "--level",
        "-l",
        type=int,
        choices=[1, 2, 3, 4],
        help="Esegue esclusivamente il livello indicato (1: Smoke, 2: CRUD, 3: Ciclo Vendita, 4: Avanzato)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Percorso personalizzato per il report HTML (default: Desktop/E2E_REPORT_RSM.html)",
    )
    args = parser.parse_args()

    desktop_dir = Path(os.environ.get("USERPROFILE", ".")) / "Desktop"
    report_target = args.output if args.output else desktop_dir / "E2E_REPORT_RSM.html"

    print("================================================================================")
    print("🚀 [RSM E2E] AVVIO SUITE DI COLLAUDO AUTOMATIZZATA (CHROMIUM HEADLESS)")
    print(
        f"📍 Modalità: {'Cascata Completa (Livelli 1 -> 2 -> 3 -> 4)' if not args.level else f'Livello Singolo ({args.level})'}"
    )
    print("🛡️  Regole: Zero-Code-Touch | Isolamento Sandbox :28475 | Fail-Fast per Livello")
    print(f"📄 Report Target: {report_target}")
    print("================================================================================\n")

    # 1. Avvio Server Sandbox Isolato
    print("[1/3] Avvio del server Sandbox effimero su 127.0.0.1:28475...")
    server = SandboxServer(28475)
    try:
        server.start()
        print("   ✅ Server Sandbox attivo con database effimero in %TEMP%\n")
    except Exception as e:  # noqa: BLE001
        print(f"   ❌ Errore critico avvio server sandbox: {e}")
        return 1

    results: list[LevelResult] = []
    has_failed = False

    try:
        with sync_playwright() as playwright:
            # ------------------------------------------------------------------
            # LIVELLO 1: SMOKE TEST & LAYOUT INTEGRITY
            # ------------------------------------------------------------------
            if args.level is None or args.level == 1:
                print("🟢 [LIVELLO 1] Esecuzione: Smoke Test, Layout Integrity & Audit Console...")
                start_t = time.time()
                mgr1 = E2EContextManager(playwright, "level1_smoke")
                try:
                    with mgr1 as (page, console_errors):
                        chk1 = run_level1_smoke_checks(page, console_errors)

                    elapsed = time.time() - start_t
                    res1 = LevelResult(
                        level_id=1,
                        name="Smoke Test & Layout Integrity",
                        status="PASSED",
                        duration=elapsed,
                        screenshot_path=chk1["screenshot_path"],
                        video_path=mgr1.final_video_path or VIDEOS_DIR / "level1_smoke.webm",
                        details=chk1["details"],
                    )
                    results.append(res1)
                    print(f"   ✅ LIVELLO 1 SUPERATO in {elapsed:.2f}s (0 errori console)\n")
                except Exception as exc:  # noqa: BLE001
                    elapsed = time.time() - start_t
                    err_msg, f_path, line_no = extract_error_info(exc)
                    res1 = LevelResult(
                        level_id=1,
                        name="Smoke Test & Layout Integrity",
                        status="FAILED",
                        duration=elapsed,
                        error_message=err_msg,
                        file_path=f_path,
                        line_number=line_no,
                        video_path=mgr1.final_video_path or VIDEOS_DIR / "level1_smoke.webm",
                        details=["Fallimento durante i controlli di integrità di base del Livello 1."],
                    )
                    results.append(res1)
                    has_failed = True
                    print(f"   ❌ LIVELLO 1 FALLITO in {elapsed:.2f}s:")
                    print(f"      {err_msg}\n")

            # ------------------------------------------------------------------
            # LIVELLO 2: CRUD PRODOTTO IN STOCK
            # ------------------------------------------------------------------
            if (args.level is None and not has_failed) or args.level == 2:
                print("🟡 [LIVELLO 2] Esecuzione: Creazione Prodotto In Stock (CRUD) & Consistenza Metriche...")
                start_t = time.time()
                mgr2 = E2EContextManager(playwright, "level2_crud")
                try:
                    with mgr2 as (page, console_errors):
                        chk2 = run_level2_crud_checks(page, console_errors)

                    elapsed = time.time() - start_t
                    res2 = LevelResult(
                        level_id=2,
                        name="Creazione Prodotto & Consistenza Dati (CRUD)",
                        status="PASSED",
                        duration=elapsed,
                        screenshot_path=chk2["screenshot_path"],
                        video_path=mgr2.final_video_path or VIDEOS_DIR / "level2_crud.webm",
                        details=chk2["details"],
                    )
                    results.append(res2)
                    print(f"   ✅ LIVELLO 2 SUPERATO in {elapsed:.2f}s (prodotto creato e verificato)\n")
                except Exception as exc:  # noqa: BLE001
                    elapsed = time.time() - start_t
                    err_msg, f_path, line_no = extract_error_info(exc)
                    res2 = LevelResult(
                        level_id=2,
                        name="Creazione Prodotto & Consistenza Dati (CRUD)",
                        status="FAILED",
                        duration=elapsed,
                        error_message=err_msg,
                        file_path=f_path,
                        line_number=line_no,
                        video_path=mgr2.final_video_path or VIDEOS_DIR / "level2_crud.webm",
                        details=["Fallimento durante l'aggiunta o la verifica del prodotto nel Livello 2."],
                    )
                    results.append(res2)
                    has_failed = True
                    print(f"   ❌ LIVELLO 2 FALLITO in {elapsed:.2f}s:")
                    print(f"      {err_msg}\n")
            elif args.level is None and has_failed:
                results.append(
                    LevelResult(
                        level_id=2,
                        name="Creazione Prodotto & Consistenza Dati (CRUD)",
                        status="SKIPPED",
                        details=["Livello saltato automaticamente a causa del fallimento del Livello 1 (Fail-Fast)."],
                    )
                )

            # ------------------------------------------------------------------
            # LIVELLO 3: CICLO VENDITA REALISTICO, TRANSIZIONI & CALCOLO PROFITTI
            # ------------------------------------------------------------------
            if (args.level is None and not has_failed) or args.level == 3:
                print("🔴 [LIVELLO 3] Esecuzione: Ciclo Vendita Realistico, Transizioni di Stato & Utile Netto...")
                start_t = time.time()
                mgr3 = E2EContextManager(playwright, "level3_flow")
                try:
                    with mgr3 as (page, console_errors):
                        chk3 = run_level3_flow_checks(page, console_errors)

                    elapsed = time.time() - start_t
                    res3 = LevelResult(
                        level_id=3,
                        name="Ciclo Vendita Realistico, Transizioni di Stato & Profitti",
                        status="PASSED",
                        duration=elapsed,
                        screenshot_path=chk3["screenshot_path"],
                        video_path=mgr3.final_video_path or VIDEOS_DIR / "level3_flow.webm",
                        details=chk3["details"],
                    )
                    results.append(res3)
                    print(
                        f"   ✅ LIVELLO 3 SUPERATO in {elapsed:.2f}s (transizioni stato, lock campi e utile validati)\n"
                    )
                except Exception as exc:  # noqa: BLE001
                    elapsed = time.time() - start_t
                    err_msg, f_path, line_no = extract_error_info(exc)
                    res3 = LevelResult(
                        level_id=3,
                        name="Ciclo Vendita Realistico, Transizioni di Stato & Profitti",
                        status="FAILED",
                        duration=elapsed,
                        error_message=err_msg,
                        file_path=f_path,
                        line_number=line_no,
                        video_path=mgr3.final_video_path or VIDEOS_DIR / "level3_flow.webm",
                        details=["Fallimento durante il ciclo di vendita o asserzione matematica nel Livello 3."],
                    )
                    results.append(res3)
                    has_failed = True
                    print(f"   ❌ LIVELLO 3 FALLITO in {elapsed:.2f}s:")
                    print(f"      {err_msg}\n")
            elif args.level is None and has_failed:
                results.append(
                    LevelResult(
                        level_id=3,
                        name="Ciclo Vendita Realistico, Transizioni di Stato & Profitti",
                        status="SKIPPED",
                        details=[
                            "Livello saltato automaticamente a causa del fallimento di un livello precedente (Fail-Fast)."
                        ],
                    )
                )

            # ------------------------------------------------------------------
            # LIVELLO 4: INTERAZIONI AVANZATE, SELEZIONE MULTIPLA & ELIMINAZIONE
            # ------------------------------------------------------------------
            if (args.level is None and not has_failed) or args.level == 4:
                print("🟣 [LIVELLO 4] Esecuzione: Selezione Multipla, Pillola Flottante, Filtri & Eliminazione...")
                start_t = time.time()
                mgr4 = E2EContextManager(playwright, "level4_advanced")
                try:
                    with mgr4 as (page, console_errors):
                        chk4 = run_level4_advanced_checks(page, console_errors)

                    elapsed = time.time() - start_t
                    res4 = LevelResult(
                        level_id=4,
                        name="Selezione Multipla, Pillola Flottante, Filtri & Eliminazione",
                        status="PASSED",
                        duration=elapsed,
                        screenshot_path=chk4["screenshot_path"],
                        video_path=mgr4.final_video_path or VIDEOS_DIR / "level4_advanced.webm",
                        details=chk4["details"],
                    )
                    results.append(res4)
                    print(
                        f"   ✅ LIVELLO 4 SUPERATO in {elapsed:.2f}s (pillola flottante, filtri ed eliminazione 100% validati)\n"
                    )
                except Exception as exc:  # noqa: BLE001
                    elapsed = time.time() - start_t
                    err_msg, f_path, line_no = extract_error_info(exc)
                    res4 = LevelResult(
                        level_id=4,
                        name="Selezione Multipla, Pillola Flottante, Filtri & Eliminazione",
                        status="FAILED",
                        duration=elapsed,
                        error_message=err_msg,
                        file_path=f_path,
                        line_number=line_no,
                        video_path=mgr4.final_video_path or VIDEOS_DIR / "level4_advanced.webm",
                        details=["Fallimento durante i collaudi avanzati del Livello 4."],
                    )
                    results.append(res4)
                    has_failed = True
                    print(f"   ❌ LIVELLO 4 FALLITO in {elapsed:.2f}s:")
                    print(f"      {err_msg}\n")
            elif args.level is None and has_failed:
                results.append(
                    LevelResult(
                        level_id=4,
                        name="Selezione Multipla, Pillola Flottante, Filtri & Eliminazione",
                        status="SKIPPED",
                        details=[
                            "Livello saltato automaticamente a causa del fallimento di un livello precedente (Fail-Fast)."
                        ],
                    )
                )

    finally:
        print("[2/3] Chiusura sicura del server Sandbox e distruzione del database effimero...")
        server.stop()
        print("   ✅ Sandbox ripulito al 100% (nessun residuo su rsm_inventory.db)\n")

    # 3. Generazione Report HTML sul Desktop
    print("[3/3] Compilazione report multimediale sul Desktop in corso...")
    try:
        report_path = generate_e2e_html_report(results, report_target)
        print("================================================================================")
        if not has_failed:
            print("🏆 [ESITO FINALE: SUCCESSO 100%]")
            print(f"📄 Report HTML Standalone pronto sul Desktop: {report_path}")
            print("   👉 Doppio click sul file per aprire la dashboard, riprodurre i video e vedere gli screenshot.")
        else:
            print("⚠️  [ESITO FINALE: REGISTRATI ERRORI]")
            print(f"📄 Report HTML diagnostico generato sul Desktop: {report_path}")
            print("   👉 Consulta il report per l'analisi visiva e le proposte di soluzione.")
        print("================================================================================\n")
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ Impossibile generare il report HTML: {e}")

    return 1 if has_failed else 0


if __name__ == "__main__":
    sys.exit(main())
