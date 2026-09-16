"""Keep IDE launches and double-click launches on the same project interpreter."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys


def ensure_runtime():
    root = Path(__file__).resolve().parent
    expected = root / '.venv' / 'Scripts' / 'python.exe'
    if expected.is_file() and Path(sys.executable).resolve() != expected.resolve():
        # IDEs may inherit an unrelated project's interpreter; multiprocessing must use ours too.
        subprocess.Popen([str(expected), str(root/'app.py'), *sys.argv[1:]], cwd=str(root),
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        raise SystemExit(0)
    missing = [name for name in ('cv2', 'mediapipe', 'PIL', 'pystray', 'cv2_enumerate_cameras')
               if importlib.util.find_spec(name) is None]
    if missing:
        import tkinter as tk
        from tkinter import messagebox
        window = tk.Tk()
        window.withdraw()
        messagebox.showerror('BehindWatch · 运行环境未就绪',
                             '缺少运行依赖：' + ', '.join(missing) + '\n\n请运行项目目录中的 launch.cmd 完成安装。\n这不是摄像头设备故障。\n\n当前 Python：' + sys.executable)
        window.destroy()
        raise SystemExit(1)
    cache = root/'.runtime'/'matplotlib'
    cache.mkdir(parents=True, exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(cache)


if __name__ == '__main__':
    ensure_runtime()
