# -*- coding: utf-8 -*-
"""Starts Uvicorn, Cloudflared, and Telegram live as detached Windows processes."""
import os, sys, subprocess, time, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

PYTHON_EXE = sys.executable
CLOUDFLARED_EXE = str(ROOT / "cloudflared.exe")

def is_port_in_use(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def start_services():
    # 1. Kill any stale cloudflared
    subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], capture_output=True)

    # 2. Check if Uvicorn is already listening on 8000
    if not is_port_in_use(8000):
        print("Starting persistent Uvicorn...")
        DETACHED_FLAG = 0x00000008  # DETACHED_PROCESS
        subprocess.Popen(
            [PYTHON_EXE, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd=str(ROOT),
            creationflags=DETACHED_FLAG,
            close_fds=True
        )
        time.sleep(2)
    else:
        print("Uvicorn already listening on port 8000.")

    # 3. Clean tunnel.log
    tunnel_log = ROOT / "tunnel.log"
    if tunnel_log.exists():
        try:
            tunnel_log.unlink()
        except Exception:
            pass

    # 4. Start Cloudflared detached
    print("Starting persistent Cloudflared tunnel...")
    DETACHED_FLAG = 0x00000008
    subprocess.Popen(
        [CLOUDFLARED_EXE, "tunnel", "--url", "http://localhost:8000", "--logfile", str(tunnel_log)],
        cwd=str(ROOT),
        creationflags=DETACHED_FLAG,
        close_fds=True
    )

    # 5. Extract URL from tunnel.log
    url = None
    for _ in range(15):
        time.sleep(1)
        if tunnel_log.exists():
            try:
                with open(tunnel_log, "r", encoding="utf-8", errors="ignore") as f:
                    txt = f.read()
                m = re.findall(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", txt)
                if m:
                    url = m[-1]
                    break
            except Exception:
                pass

    if url:
        print(f"ACTIVE_URL: {url}")
        with open("CURRENT_TUNNEL_URL.txt", "w", encoding="utf-8") as f:
            f.write(url)
    else:
        print("WARNING: Could not parse tunnel URL in time.")

    # 6. Start Telegram live listener detached
    print("Starting persistent Telegram live ingestion...")
    subprocess.Popen(
        [PYTHON_EXE, "-m", "app.ingestion.telegram_live"],
        cwd=str(ROOT),
        creationflags=DETACHED_FLAG,
        close_fds=True
    )

if __name__ == "__main__":
    start_services()
