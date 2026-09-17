"""Wait for the running app to exit, then install a verified release."""
import argparse
import ctypes
import subprocess
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description='BehindWatch updater')
    parser.add_argument('--wait-pid', type=int, required=True)
    parser.add_argument('--installer', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.wait_pid <= 0 or not args.installer.is_file():
        return 1
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
    kernel.WaitForSingleObject.restype = ctypes.c_ulong
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    handle = kernel.OpenProcess(0x00100000, False, args.wait_pid)
    if handle:
        try:
            if kernel.WaitForSingleObject(handle, 120000) != 0:
                return 1
        finally:
            kernel.CloseHandle(handle)
    # 保留进度和错误窗口；旧版完全静默安装失败时，用户只会看到主程序关闭。
    log = args.installer.with_suffix('.log')
    return subprocess.call([str(args.installer), '/SILENT', '/NORESTART',
                            '/BEHINDWATCHUPDATE', f'/LOG={log}'])


if __name__ == '__main__':
    try:
        result = main()
    except OSError as exc:
        result = 1
        detail = str(exc)
    else:
        detail = f'错误代码：{result}'
    if result:
        ctypes.windll.user32.MessageBoxW(None,
            f'更新未完成：{detail}\n请从发布页手动下载安装包。', 'BehindWatch 更新', 0x10)
    sys.exit(result)
