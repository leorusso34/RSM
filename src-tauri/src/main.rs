// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::process::Command;
use std::thread;
use std::time::Duration;

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

fn is_bridge_running() -> bool {
    TcpStream::connect("127.0.0.1:28472").is_ok()
}

fn ensure_bridge_server() {
    if is_bridge_running() {
        return;
    }

    thread::spawn(|| {
        let mut cmd = Command::new("python");
        cmd.arg("src/services/bridge_server.py");

        #[cfg(target_os = "windows")]
        cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW

        match cmd.spawn() {
            Ok(mut child) => {
                let _ = child.wait();
            }
            Err(e) => {
                eprintln!("Impossibile avviare il bridge Python: {}", e);
            }
        }
    });

    // Attendi fino a 2 secondi per l'avvio del server
    for _ in 0..20 {
        thread::sleep(Duration::from_millis(100));
        if is_bridge_running() {
            break;
        }
    }
}

use tauri::Manager;

fn main() {
    ensure_bridge_server();

    tauri::Builder::default()
        .setup(|app| {
            if let Some(window) = app.get_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Errore durante l'esecuzione dell'applicazione Tauri");
}
