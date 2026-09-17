"""Conservative Windows input and absence checks for optional screen locking."""
import ctypes
from ctypes import wintypes


class LastInputInfo(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.UINT), ('dwTime', wintypes.DWORD)]


def input_idle_seconds():
    try:
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        info = LastInputInfo(ctypes.sizeof(LastInputInfo), 0)
        user32.GetLastInputInfo.argtypes = (ctypes.POINTER(LastInputInfo),)
        user32.GetLastInputInfo.restype = wintypes.BOOL
        kernel32.GetTickCount.restype = wintypes.DWORD
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        return ((kernel32.GetTickCount() - info.dwTime) & 0xffffffff) / 1000
    except (AttributeError, OSError):
        return None


def lock_workstation():
    try:
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        user32.LockWorkStation.restype = wintypes.BOOL
        return bool(user32.LockWorkStation())
    except (AttributeError, OSError):
        return False


class LockDecision:
    def __init__(self):
        self.absent_since = None
        self.warning_since = None
        self.locked = False

    def reset(self):
        self.absent_since = self.warning_since = None

    def update(self, now, present, idle, started, safe):
        if self.locked or not safe or idle is None or present is None:
            self.reset()
            return None
        if present:
            self.reset()
            return None
        if self.absent_since is None:
            self.absent_since = now
        if idle < 60 or now - started < 30 or now - self.absent_since < 60:
            self.warning_since = None
            return None
        if self.warning_since is None:
            self.warning_since = now
        if now - self.warning_since >= 5:
            return 0
        return max(1, 5 - int(now - self.warning_since))
