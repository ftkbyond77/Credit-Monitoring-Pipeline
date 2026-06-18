# desktop.py

import threading
import subprocess
import webview

def run_streamlit():

    subprocess.run([
        "streamlit",
        "run",
        "app.py",
        "--server.headless=true"
    ])

threading.Thread(
    target=run_streamlit,
    daemon=True
).start()

window = webview.create_window(
    "Customer Debt Dashboard",
    "http://localhost:8501"
)

webview.start()