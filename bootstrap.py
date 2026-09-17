"""Use the source runtime while keeping IDE launches attached to a live process."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys


def acquire_single_instance():
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.CreateMutexW(None, False, 'Local\\BehindWatch.SingleInstance')
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        return None
    # 保留句柄直到进程结束，退出或崩溃后 Windows 会自动释放互斥量。
    return handle


def release_single_instance(handle):
    if handle:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL('kernel32')
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle(handle)


def ensure_runtime():
    if getattr(sys, 'frozen', False):
        # 安装版自带解释器和依赖，不能重启到开发目录的虚拟环境。
        return
    root = Path(__file__).resolve().parent
    missing = [name for name in ('cv2', 'mediapipe', 'supervision', 'PIL', 'PySide6', 'cv2_enumerate_cameras', 'win11toast', 'win32gui', 'comtypes')
               if importlib.util.find_spec(name) is None]
    if missing:
        expected = root / '.venv' / 'Scripts' / 'python.exe'
        if expected.is_file() and Path(sys.executable).resolve() != expected.resolve():
            # IDE 使用了其他项目的解释器时等待子进程退出，避免运行按钮立刻显示结束。
            result = subprocess.run([str(expected), str(root / 'app.py'), *sys.argv[1:]], cwd=str(root))
            raise SystemExit(result.returncode)
        # 依赖缺失时使用系统对话框，不依赖 Tk 或尚未安装的 Qt。
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,
            '缺少运行依赖：' + ', '.join(missing) + '\n\n请运行项目目录中的 launch.cmd 完成安装。\n这不是摄像头设备故障。\n\n当前 Python：' + sys.executable,
            'BehindWatch · 运行环境未就绪', 0x10)
        raise SystemExit(1)
    cache = root/'.runtime'/'matplotlib'
    cache.mkdir(parents=True, exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(cache)


if __name__ == '__main__':
    ensure_runtime()
