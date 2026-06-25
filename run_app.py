# run_app.py ✅ Fixed

import os
import sys
import subprocess

def main():
    if getattr(sys, 'frozen', False):
        application_path = sys._MEIPASS
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))

    script_path = os.path.join(application_path, 'app.py')

    subprocess.run([
        sys.executable, "-m", "streamlit", "run", script_path,
        "--global.developmentMode=false"
    ])

if __name__ == '__main__':
    main()