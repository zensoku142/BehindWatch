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
    handle = kernel.OpenProcess(0x00100000, False, args.wait_pid)
    if handle:
        try:
            if kernel.WaitForSingleObject(handle, 120000) != 0:
                return 1
        finally:
            kernel.CloseHandle(handle)
    # 安装器负责覆盖文件并只启动一次新程序；数据在用户目录，不参与替换。
    return subprocess.call([str(args.installer), '/VERYSILENT', '/SUPPRESSMSGBOXES',
                            '/NORESTART', '/BEHINDWATCHUPDATE'])


if __name__ == '__main__':
    sys.exit(main())
