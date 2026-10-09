@echo off
title RSM Next-Gen (Tauri)
cd /d "c:\Users\Leonardo Russo\Desktop\RUSSO STOCK"

:: 1. Avvia il micro-server bridge Python in background (invisibile) se non attivo
powershell -Command "if (!(Test-NetConnection -ComputerName 127.0.0.1 -Port 28472 -InformationLevel Quiet)) { Start-Process -FilePath '.venv\Scripts\python.exe' -ArgumentList 'src\services\bridge_server.py' -WindowStyle Hidden }"

:: 2. Avvia l'interfaccia nativa Tauri (Release ottimizzata)
start "" "c:\Users\Leonardo Russo\Desktop\RUSSO STOCK\src-tauri\target\release\rsm-desktop.exe"
exit
