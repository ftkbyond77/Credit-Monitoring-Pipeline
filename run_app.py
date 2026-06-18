import os
import sys
import subprocess

def main():
    # หาที่อยู่ของไฟล์ app.py ไม่ว่าจะรันแบบสคริปต์ปกติ หรือรันผ่าน .exe
    if getattr(sys, 'frozen', False):
        # ถ้ารันจาก .exe
        application_path = sys._MEIPASS
    else:
        # ถ้ารันจาก Python ปกติ
        application_path = os.path.dirname(os.path.abspath(__name__))
    
    script_path = os.path.join(application_path, 'app.py')
    
    # สั่งรัน Streamlit แบบซ่อนการตั้งค่าต่างๆ ไว้
    subprocess.run([sys.executable, "-m", "streamlit", "run", script_path, "--global.developmentMode=false"])

if __name__ == '__main__':
    main()