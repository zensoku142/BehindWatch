"""Measure isolated Windows inference memory without opening a camera."""
import argparse
import ctypes
import json
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class MemoryCounters(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
            'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage',
            'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]


def memory_mib():
    counters = MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL('kernel32')
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    api = ctypes.WinDLL('psapi')
    api.GetProcessMemoryInfo.argtypes = (wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD)
    if not api.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError()
    return {name: round(getattr(counters, name) / 1024**2, 1)
            for name in ('WorkingSetSize', 'PrivateUsage', 'PeakWorkingSetSize')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-ui', action='store_true', help='Simulate the old worker import overhead')
    parser.add_argument('--threads-2', action='store_true', help='Compare a two-thread OpenCV experiment')
    args = parser.parse_args()
    if args.with_ui:
        import app  # 仅导入，不创建界面；模拟冻结版优化前的子进程入口。
    import cv2
    import numpy as np
    from core.vision import Detector
    from core.person_detection import PersonTracker
    if args.threads_2:
        cv2.setNumThreads(2)
    started = time.perf_counter()
    detector = Detector()
    try:
        tracker = PersonTracker()
        for _ in range(5):
            tracker.update(detector.detect(np.zeros((480, 640, 3), dtype=np.uint8)))
        print(json.dumps({'ui_imported': args.with_ui, 'threads': cv2.getNumThreads(),
                          'elapsed_seconds': round(time.perf_counter() - started, 2), **memory_mib()}))
    finally:
        detector.close()


if __name__ == '__main__':
    main()
