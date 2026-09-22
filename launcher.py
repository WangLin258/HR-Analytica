# -*- coding: utf-8 -*-
"""Single-process Windows launcher for HR Analytica."""

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    DATA_DIR = Path(sys.executable).resolve().parent
else:
    RESOURCE_DIR = Path(__file__).resolve().parent
    DATA_DIR = RESOURCE_DIR


def _choose_port() -> int:
    for port in (8501, 8502, 8503):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 8501


PORT = int(os.environ.get("HR_ANALYTICA_PORT") or _choose_port())
URL = f"http://127.0.0.1:{PORT}"
LOG_FILE = DATA_DIR / "launcher.log"

SAMPLE_FILES = [
    "薪酬分析样例.csv",
    "薪酬设计全套数据表.xlsx",
    "招聘分析样例.csv",
    "招聘分析样例.xlsx",
]


def _log(message: str) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


def _copy_resources() -> None:
    for name in ["style.css", *SAMPLE_FILES]:
        source = RESOURCE_DIR / name
        target = DATA_DIR / name
        try:
            if source.exists():
                shutil.copy2(source, target)
        except Exception as exc:
            _log(f"copy resource failed: {name}: {exc}")

    source_cfg = RESOURCE_DIR / ".streamlit" / "config.toml"
    target_cfg = DATA_DIR / ".streamlit" / "config.toml"
    try:
        if source_cfg.exists():
            target_cfg.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_cfg, target_cfg)
    except Exception as exc:
        _log(f"copy streamlit config failed: {exc}")


def _run_streamlit_worker() -> None:
    from streamlit.web import cli

    app_path = RESOURCE_DIR / "frontend" / "app.py"
    if not app_path.exists():
        app_path = RESOURCE_DIR / "app.py"

    os.chdir(RESOURCE_DIR)
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.headless=true",
        f"--server.port={PORT}",
        "--global.developmentMode=false",
        "--browser.gatherUsageStats=false",
    ]
    cli.main()


def _wait_ready(process: subprocess.Popen, timeout: int = 90) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(URL, timeout=1):
                return True
        except Exception:
            time.sleep(0.5)
    return process.poll() is None


def _stop_process(process: subprocess.Popen) -> None:
    try:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    except Exception:
        pass


def _show_error(message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("HR数据分析助手", message)
        root.destroy()
    except Exception:
        pass


def _run_control_window(process: subprocess.Popen) -> None:
    try:
        import tkinter as tk
    except Exception:
        process.wait()
        return

    root = tk.Tk()
    root.title("HR数据分析助手")
    root.geometry("430x190")
    root.resizable(False, False)

    tk.Label(
        root,
        text="HR Analytica 正在运行",
        font=("Microsoft YaHei UI", 14, "bold"),
    ).pack(pady=(24, 8))
    tk.Label(root, text=URL, fg="#2563EB").pack()
    tk.Label(root, text="关闭此窗口即可停止服务", fg="#666666").pack(pady=(4, 14))
    tk.Button(
        root,
        text="停止服务",
        width=20,
        height=2,
        command=lambda: (_stop_process(process), root.destroy()),
    ).pack()

    root.protocol("WM_DELETE_WINDOW", lambda: (_stop_process(process), root.destroy()))
    root.mainloop()


def main() -> int:
    if "--streamlit-worker" in sys.argv:
        _run_streamlit_worker()
        return 0

    _copy_resources()
    if FROZEN:
        try:
            sys.stdout = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
            sys.stderr = sys.stdout
        except Exception:
            pass

    _log(f"Starting HR Analytica on port {PORT}")

    if FROZEN:
        command = [sys.executable, "--streamlit-worker"]
    else:
        command = [sys.executable, str(Path(__file__).resolve()), "--streamlit-worker"]

    try:
        process = subprocess.Popen(command, cwd=str(RESOURCE_DIR))
    except Exception as exc:
        _log(f"failed to start Streamlit: {exc}")
        _show_error(f"启动失败：{exc}")
        return 1

    if not _wait_ready(process):
        _log("Streamlit service did not become ready")
        _stop_process(process)
        _show_error("服务启动超时，请查看 launcher.log")
        return 1

    _log("Streamlit service ready")
    try:
        webbrowser.open(URL)
    except Exception:
        pass

    _run_control_window(process)
    _log("Launcher exited")
    return 0


if __name__ == "__main__":
    sys.exit(main())
