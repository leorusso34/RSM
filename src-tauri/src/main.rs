// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::thread;
use std::time::Duration;
use tauri::Manager;

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

fn is_bridge_running() -> bool {
    TcpStream::connect("127.0.0.1:28472").is_ok()
}

fn find_bridge_script() -> Option<(PathBuf, PathBuf)> {
    let mut bases = vec![PathBuf::from(".")];

    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(p) = exe_path.parent() {
            bases.push(p.to_path_buf());
            if let Some(p2) = p.parent() {
                bases.push(p2.to_path_buf());
                if let Some(p3) = p2.parent() {
                    bases.push(p3.to_path_buf());
                    if let Some(p4) = p3.parent() {
                        bases.push(p4.to_path_buf());
                    }
                }
            }
        }
    }

    for base in &bases {
        let script = base.join("src").join("services").join("bridge_server.py");
        if script.exists() {
            return Some((script, base.clone()));
        }
        let script_flat = base.join("bridge_server.py");
        if script_flat.exists() {
            return Some((script_flat, base.clone()));
        }
    }
    None
}

fn find_python_executable(work_dir: &Path) -> PathBuf {
    let mut check_dirs = vec![work_dir.to_path_buf()];
    let mut curr = work_dir.parent();
    while let Some(p) = curr {
        check_dirs.push(p.to_path_buf());
        curr = p.parent();
    }

    if let Ok(exe_path) = std::env::current_exe() {
        let mut curr_exe = exe_path.parent();
        while let Some(p) = curr_exe {
            check_dirs.push(p.to_path_buf());
            curr_exe = p.parent();
        }
    }

    for dir in &check_dirs {
        let venv_py = dir.join(".venv").join("Scripts").join("python.exe");
        if venv_py.exists() {
            return venv_py;
        }
        let local_py = dir.join("python.exe");
        if local_py.exists() {
            return local_py;
        }
    }

    if let Ok(local_app_data) = std::env::var("LOCALAPPDATA") {
        let p1 = PathBuf::from(&local_app_data).join("Python").join("bin").join("python.exe");
        if p1.exists() {
            return p1;
        }
    }

    #[cfg(target_os = "windows")]
    return PathBuf::from("python.exe");

    #[cfg(not(target_os = "windows"))]
    return PathBuf::from("python3");
}

fn ensure_bridge_server() {
    if is_bridge_running() {
        return;
    }

    if let Some((script, work_dir)) = find_bridge_script() {
        let py_bin = find_python_executable(&work_dir);
        thread::spawn(move || {
            let mut cmd = Command::new(py_bin);
            cmd.arg(&script);
            cmd.current_dir(&work_dir);

            #[cfg(target_os = "windows")]
            cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW

            if let Ok(mut child) = cmd.spawn() {
                let _ = child.wait();
            }
        });
    } else {
        // Fallback generico
        let py_bin = find_python_executable(Path::new("."));
        thread::spawn(move || {
            let mut cmd = Command::new(py_bin);
            cmd.arg("src/services/bridge_server.py");

            #[cfg(target_os = "windows")]
            cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW

            if let Ok(mut child) = cmd.spawn() {
                let _ = child.wait();
            }
        });
    }

    // Attendi fino a 2 secondi per l'avvio del server
    for _ in 0..20 {
        thread::sleep(Duration::from_millis(100));
        if is_bridge_running() {
            break;
        }
    }
}

fn main() {
    ensure_bridge_server();

    tauri::Builder::default()
        .setup(|app| {
            if let Some(window) = app.get_window("main") {
                let _ = window.maximize();
                let _ = window.show();
                let _ = window.set_focus();
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Errore durante l'esecuzione dell'applicazione Tauri");
}
