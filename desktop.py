# desktop.py ✅ Final Version

import os
import sys
import time
import socket
import threading
import subprocess
import multiprocessing
import webview


def _get_base_path() -> str:
    """รองรับทั้ง .exe (PyInstaller) และ script ปกติ"""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _wait_for_server(host: str = "127.0.0.1", port: int = 8501,
                     timeout: int = 60) -> bool:
    """รอจน Streamlit bind port สำเร็จ — ป้องกันหน้าขาว"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _run_streamlit(app_path: str) -> None:
    """รัน Streamlit ใน background thread ด้วย sys.executable (รองรับ .exe)"""
    cmd = [
        sys.executable,          # ✅ ไม่ใช้ "streamlit" command ตรงๆ
        "-m", "streamlit",
        "run", app_path,
        "--server.headless=true",
        "--server.port=8501",
        "--server.address=127.0.0.1",
        "--global.developmentMode=false",
        "--browser.gatherUsageStats=false",
    ]
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NO_WINDOW  # ✅ ซ่อน console popup

    subprocess.run(cmd, creationflags=creation_flags)


def main() -> None:
    base_path = _get_base_path()
    app_path  = os.path.join(base_path, "app.py")

    # 1) เริ่ม Streamlit ใน background
    t = threading.Thread(target=_run_streamlit, args=(app_path,), daemon=True)
    t.start()

    # 2) รอ server พร้อมก่อนเปิด window ✅ ป้องกันหน้าขาว
    ready = _wait_for_server(port=8501, timeout=60)
    if not ready:
        sys.exit(1)

    # 3) เปิด PyWebView window
    window = webview.create_window(
        title="Customer Debt Dashboard — Credit Monitoring",
        url="http://127.0.0.1:8501",
        width=1440,
        height=860,
        min_size=(1024, 600),
        resizable=True,
    )
    webview.start(gui="edgechromium", debug=False)


# ✅ guard บรรทัดนี้คือตัวหยุด recursive loop ทั้งหมด
if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()