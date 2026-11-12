"""Generatore di report HTML multimediale interattivo su Desktop per RSM E2E.

Caratteristiche:
- Salvataggio automatico sul Desktop: C:\\Users\\<user>\\Desktop\\E2E_REPORT_RSM.html
- Singolo file 100% autosufficiente (video .webm e screenshot .png incorporati in Base64)
- Dashboard con pillole di stato per ogni livello
- Player video interattivo con navigazione a schede tra i livelli
- Galleria screenshot ingrandibile (modal lightbox)
- Sezione diagnosi errori con spiegazione in parole semplici e proposta di fix
- Design Dark Slate ad alto contrasto coerente con RSM
"""

import base64
import html
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class LevelResult:
    level_id: int
    name: str
    status: str  # "PASSED", "FAILED", "SKIPPED"
    duration: float = 0.0
    error_message: str | None = None
    file_path: str | None = None
    line_number: int | None = None
    code_fix: str | None = None
    screenshot_path: Path | None = None
    video_path: Path | None = None
    details: list[str] = field(default_factory=list)


def file_to_base64(path: Path | None, mime: str) -> str | None:
    """Converte un file su disco in stringa Data URI Base64 per garantire l'autosufficienza dell'HTML."""
    if not path or not path.is_file():
        return None
    try:
        raw = path.read_bytes()
        encoded = base64.b64encode(raw).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    except OSError:
        return None


def generate_e2e_html_report(
    results: list[LevelResult],
    output_path: Path | None = None,
) -> Path:
    """Compone ed esporta il report HTML standalone sul Desktop."""
    if output_path is None:
        desktop_dir = Path(os.environ.get("USERPROFILE", ".")) / "Desktop"
        output_path = desktop_dir / "E2E_REPORT_RSM.html"

    now_str = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M:%S")
    all_passed = all(r.status == "PASSED" for r in results)
    has_failed = any(r.status == "FAILED" for r in results)

    overall_status_text = (
        "TUTTI I LIVELLI SUPERATI (100% VERDE)" if all_passed else ("FALLITO" if has_failed else "PARZIALE")
    )
    overall_badge_class = "badge-passed" if all_passed else ("badge-failed" if has_failed else "badge-skipped")

    # Mappatura Base64 dei media
    videos_b64: dict[int, str] = {}
    for r in results:
        if r.video_path:
            v_b64 = file_to_base64(r.video_path, "video/webm")
            if v_b64:
                videos_b64[r.level_id] = v_b64

    # Generazione markup schede livelli
    level_cards_html = []
    for r in results:
        status_class = f"status-{r.status.lower()}"
        status_label = "SUPERATO" if r.status == "PASSED" else ("FALLITO" if r.status == "FAILED" else "SALTATO")
        badge_style = "bg-green" if r.status == "PASSED" else ("bg-red" if r.status == "FAILED" else "bg-gray")

        details_li = "".join(f"<li>{html.escape(d)}</li>" for d in r.details)
        level_cards_html.append(f"""
        <div class="level-card {status_class}">
          <div class="level-header">
            <div>
              <div class="level-num">LIVELLO {r.level_id}</div>
              <div class="level-name">{html.escape(r.name)}</div>
            </div>
            <div class="level-badge {badge_style}">{status_label}</div>
          </div>
          <div class="level-meta">
            <span>⏱ Durata: <strong>{r.duration:.2f}s</strong></span>
          </div>
          <ul class="level-details">
            {details_li}
          </ul>
        </div>
        """)

    # Generazione markup player video
    video_tabs_html = []
    video_players_html = []
    first_active_tab = True

    for r in results:
        vid_src = videos_b64.get(r.level_id)
        active_class = "active" if first_active_tab and vid_src else ""
        btn_active = "active" if first_active_tab and vid_src else ""

        if vid_src:
            video_tabs_html.append(f"""
              <button class="video-tab-btn {btn_active}" onclick="switchVideoTab({r.level_id})">
                Livello {r.level_id}: {html.escape(r.name)}
              </button>
            """)
            video_players_html.append(f"""
              <div id="video-tab-{r.level_id}" class="video-container {active_class}">
                <video controls playsinline preload="metadata">
                  <source src="{vid_src}" type="video/webm">
                  Il tuo browser non supporta la riproduzione video HTML5.
                </video>
              </div>
            """)
            if first_active_tab:
                first_active_tab = False

    video_section_html = ""
    if video_tabs_html:
        video_section_html = f"""
        <section class="report-section">
          <div class="section-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/></svg>
            <h2>Registrazione Video di Collaudo (Chromium Headless)</h2>
          </div>
          <div class="video-tabs-bar">
            {"".join(video_tabs_html)}
          </div>
          <div class="video-wrapper-box">
            {"".join(video_players_html)}
          </div>
        </section>
        """

    # Sezione Errori e Diagnosi
    error_cards_html = []
    for r in results:
        if r.status == "FAILED" and r.error_message:
            fix_box = ""
            if r.code_fix:
                fix_box = f"""
                <div class="code-fix-wrap">
                  <div class="code-fix-title">💡 Soluzione / Proposta di Fix Suggerita:</div>
                  <pre><code>{html.escape(r.code_fix)}</code></pre>
                </div>
                """
            loc_str = ""
            if r.file_path:
                loc_str = (
                    f"<div class='error-loc'>📍 File: <code>{html.escape(r.file_path)}</code>"
                    + (f" : riga <code>{r.line_number}</code>" if r.line_number else "")
                    + "</div>"
                )

            error_cards_html.append(f"""
            <div class="error-card">
              <div class="error-header">
                <div class="error-title">🚨 Errore nel Livello {r.level_id}: {html.escape(r.name)}</div>
              </div>
              {loc_str}
              <div class="error-desc">{html.escape(r.error_message)}</div>
              {fix_box}
            </div>
            """)

    errors_section_html = ""
    if error_cards_html:
        errors_section_html = f"""
        <section class="report-section">
          <div class="section-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <h2 style="color: #ef4444;">Diagnosi Errori & Soluzioni Proposte</h2>
          </div>
          <div class="errors-list">
            {"".join(error_cards_html)}
          </div>
        </section>
        """

    full_html = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RSM E2E Test Report</title>
  <style>
    :root {{
      --bg-main: #07090e;
      --bg-card: #0e131f;
      --bg-card-hover: #151b2b;
      --border: #1e293b;
      --border-accent: #3b82f6;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --accent-blue: #2563eb;
      --green: #10b981;
      --red: #ef4444;
      --gray: #64748b;
      --radius: 12px;
      --radius-sm: 8px;
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}
    body {{
      background: var(--bg-main);
      color: var(--text-main);
      padding: 32px 24px;
      line-height: 1.6;
    }}
    .report-container {{
      max-width: 1200px;
      margin: 0 auto;
    }}
    header {{
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 24px 28px;
      margin-bottom: 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
    }}
    .brand-title {{
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.5px;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .brand-pill {{
      font-size: 11px;
      padding: 3px 9px;
      background: rgba(37, 99, 235, 0.2);
      border: 1px solid rgba(59, 130, 246, 0.4);
      color: #93c5fd;
      border-radius: 999px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .header-meta {{
      font-size: 12.5px;
      color: var(--text-muted);
      margin-top: 4px;
    }}
    .overall-badge {{
      font-size: 13px;
      font-weight: 700;
      padding: 8px 16px;
      border-radius: 999px;
      letter-spacing: 0.5px;
    }}
    .badge-passed {{
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #34d399;
    }}
    .badge-failed {{
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid rgba(239, 68, 68, 0.4);
      color: #f87171;
    }}
    .badge-skipped {{
      background: rgba(100, 116, 139, 0.15);
      border: 1px solid rgba(100, 116, 139, 0.4);
      color: #94a3b8;
    }}
    .levels-track-wrapper {{
      position: relative;
      margin-bottom: 28px;
    }}
    .levels-track-hint {{
      display: flex;
      justify-content: flex-end;
      align-items: center;
      gap: 6px;
      font-size: 11.5px;
      color: #60a5fa;
      margin-bottom: 8px;
      font-weight: 500;
    }}
    .levels-grid {{
      display: flex;
      flex-direction: row;
      flex-wrap: nowrap;
      gap: 16px;
      overflow-x: auto;
      padding-bottom: 14px;
      padding-top: 4px;
      padding-left: 2px;
      padding-right: 2px;
      scroll-snap-type: x mandatory;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: thin;
      scrollbar-color: #3b82f6 rgba(14, 19, 31, 0.85);
    }}
    .levels-grid::-webkit-scrollbar {{
      height: 8px;
    }}
    .levels-grid::-webkit-scrollbar-track {{
      background: rgba(14, 19, 31, 0.9);
      border-radius: 999px;
      border: 1px solid rgba(30, 41, 59, 0.8);
      margin: 0 4px;
    }}
    .levels-grid::-webkit-scrollbar-thumb {{
      background: linear-gradient(90deg, #2563eb, #3b82f6);
      border-radius: 999px;
      box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
      cursor: pointer;
    }}
    .levels-grid::-webkit-scrollbar-thumb:hover {{
      background: linear-gradient(90deg, #3b82f6, #60a5fa);
    }}
    .level-card {{
      flex: 0 0 340px;
      width: 340px;
      scroll-snap-align: start;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 20px;
      transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
      display: flex;
      flex-direction: column;
    }}
    .level-card:hover {{
      border-color: rgba(59, 130, 246, 0.45);
      transform: translateY(-2px);
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
    }}
    .level-card.status-passed {{
      border-left: 4px solid var(--green);
    }}
    .level-card.status-failed {{
      border-left: 4px solid var(--red);
    }}
    .level-card.status-skipped {{
      border-left: 4px solid var(--gray);
      opacity: 0.65;
    }}
    .level-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 10px;
    }}
    .level-num {{
      font-size: 11px;
      font-weight: 700;
      color: var(--text-dim);
      letter-spacing: 0.5px;
    }}
    .level-name {{
      font-size: 15px;
      font-weight: 700;
      color: #fff;
    }}
    .level-badge {{
      font-size: 11px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 6px;
      letter-spacing: 0.5px;
    }}
    .bg-green {{ background: rgba(16, 185, 129, 0.2); color: #34d399; }}
    .bg-red {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
    .bg-gray {{ background: rgba(100, 116, 139, 0.2); color: #94a3b8; }}
    .level-meta {{
      font-size: 12px;
      color: var(--text-muted);
      margin-bottom: 12px;
    }}
    .level-details {{
      list-style: none;
      font-size: 12px;
      color: var(--text-muted);
      border-top: 1px solid rgba(255, 255, 255, 0.05);
      padding-top: 10px;
    }}
    .level-details li {{
      margin-bottom: 5px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .level-details li::before {{
      content: "•";
      color: var(--accent-blue);
      font-weight: bold;
    }}
    .report-section {{
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 24px;
      margin-bottom: 28px;
    }}
    .section-title {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 18px;
    }}
    .section-title h2 {{
      font-size: 17px;
      font-weight: 700;
      color: #fff;
    }}
    .video-tabs-bar {{
      display: flex;
      gap: 8px;
      margin-bottom: 14px;
      flex-wrap: wrap;
    }}
    .video-tab-btn {{
      background: #090d16;
      border: 1px solid var(--border);
      color: var(--text-muted);
      font-size: 12px;
      font-weight: 600;
      padding: 8px 14px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      transition: all 0.2s ease;
    }}
    .video-tab-btn:hover {{
      color: #fff;
      border-color: var(--border-accent);
    }}
    .video-tab-btn.active {{
      background: rgba(37, 99, 235, 0.15);
      border-color: var(--border-accent);
      color: #93c5fd;
    }}
    .video-wrapper-box {{
      background: #05070c;
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      overflow: hidden;
      display: flex;
      justify-content: center;
      align-items: center;
    }}
    .video-container {{
      display: none;
      width: 100%;
    }}
    .video-container.active {{
      display: block;
    }}
    video {{
      width: 100%;
      max-height: 580px;
      display: block;
      outline: none;
    }}
    .error-card {{
      background: rgba(239, 68, 68, 0.05);
      border: 1px solid rgba(239, 68, 68, 0.25);
      border-radius: var(--radius-sm);
      padding: 18px;
      margin-bottom: 14px;
    }}
    .error-title {{
      font-size: 14px;
      font-weight: 700;
      color: #f87171;
      margin-bottom: 6px;
    }}
    .error-loc {{
      font-size: 12px;
      color: var(--text-dim);
      margin-bottom: 8px;
    }}
    .error-loc code {{
      background: #0b101c;
      padding: 2px 6px;
      border-radius: 4px;
      color: #93c5fd;
    }}
    .error-desc {{
      font-size: 13px;
      color: #cbd5e1;
      margin-bottom: 12px;
      white-space: pre-wrap;
    }}
    .code-fix-wrap {{
      background: #090d16;
      border: 1px solid #1e293b;
      border-radius: 6px;
      padding: 12px;
      margin-top: 8px;
    }}
    .code-fix-title {{
      font-size: 11px;
      font-weight: 700;
      color: #38bdf8;
      text-transform: uppercase;
      margin-bottom: 6px;
      letter-spacing: 0.5px;
    }}
    pre code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      color: #e2e8f0;
      display: block;
      overflow-x: auto;
    }}
  </style>
</head>
<body>
  <div class="report-container">
    <header>
      <div>
        <div class="brand-title">
          <span>RSM UI Automation</span>
          <span class="brand-pill">E2E Suite</span>
        </div>
        <div class="header-meta">
          Esecuzione completata il: <strong>{now_str}</strong> &bull; Motore: <strong>Chromium Headless</strong> &bull; Porta Sandbox: <strong>28475</strong>
        </div>
      </div>
      <div>
        <span class="overall-badge {overall_badge_class}">{overall_status_text}</span>
      </div>
    </header>

    <div class="levels-track-wrapper">
      <div class="levels-track-hint">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="13 17 18 12 13 7"></polyline><polyline points="6 17 11 12 6 7"></polyline></svg>
        <span>Scorri orizzontalmente per visualizzare tutti i test</span>
      </div>
      <div class="levels-grid">
        {"".join(level_cards_html)}
      </div>
    </div>

    {video_section_html}
    {errors_section_html}
  </div>

  <script>
    function switchVideoTab(levelId) {{
      document.querySelectorAll(".video-tab-btn").forEach(function(b) {{ b.classList.remove("active"); }});
      document.querySelectorAll(".video-container").forEach(function(c) {{ c.classList.remove("active"); }});
      
      const tabBtn = Array.from(document.querySelectorAll(".video-tab-btn")).find(function(b) {{ return b.textContent.includes("Livello " + levelId); }});
      if (tabBtn) tabBtn.classList.add("active");

      const target = document.getElementById("video-tab-" + levelId);
      if (target) {{
        target.classList.add("active");
        const video = target.querySelector("video");
        if (video) video.play().catch(function() {{}});
      }}
    }}

    const track = document.querySelector(".levels-grid");
    if (track) {{
      track.addEventListener("wheel", function(e) {{
        if (e.deltaY !== 0 && !e.shiftKey) {{
          e.preventDefault();
          track.scrollLeft += e.deltaY * 1.2;
        }}
      }}, {{ passive: false }});
    }}
  </script>
</body>
</html>
"""
    output_path.write_text(full_html, encoding="utf-8")
    return output_path
