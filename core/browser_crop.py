"""Browser clipping ported from myth984, with cancellable background detection."""
import ctypes
from ctypes import wintypes
import queue
import threading
import time

import pywintypes
import win32con
import win32gui

from core.browser_top import browser_detection_worker


def get_window_backdrop(hwnd):
    value = ctypes.c_int()
    result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd), 38, ctypes.byref(value), ctypes.sizeof(value))
    # Windows 10 不支持 Mica；此时仍可使用普通窗口区域裁剪。
    return value.value if result >= 0 else None


def set_window_backdrop(hwnd, backdrop):
    value = ctypes.c_int(backdrop)
    result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
        wintypes.HWND(hwnd), 38, ctypes.byref(value), ctypes.sizeof(value))
    if result < 0:
        raise OSError('无法恢复或调整浏览器背景。')


def get_scrollbar_crop_width(hwnd):
    dpi = ctypes.windll.user32.GetDpiForWindow(wintypes.HWND(hwnd)) or 96
    scrollbar = ctypes.windll.user32.GetSystemMetricsForDpi(win32con.SM_CXVSCROLL, dpi)
    _, _, right, _ = win32gui.GetWindowRect(hwnd)
    client = win32gui.GetClientRect(hwnd)
    client_right, _ = win32gui.ClientToScreen(hwnd, (client[2], client[3]))
    # 把不可见边框也计入，避免高 DPI 或最大化时在右侧留下一条残边。
    return scrollbar + max(0, right - client_right)


class BrowserCrop:
    def __init__(self, guard):
        self.guard = guard
        self.target = None
        self.original_region = None
        self.original_backdrop = None
        self.crop_size = None
        self.rect, self.height = None, None
        self.options = None
        self.generation = 0
        self.pending = None
        self.next_detection = 0
        self.requests, self.results = queue.Queue(), queue.Queue()
        # UI Automation 可能等待浏览器响应；后台线程不接触界面，也不直接修改窗口。
        self.thread = threading.Thread(target=browser_detection_worker,
                                       args=(self.requests, self.results), daemon=True)

    def restore(self):
        if self.target is None:
            return
        current = self.guard.describe(self.target.hwnd)
        valid = current and (current.pid, current.thread, current.class_name) == (
            self.target.pid, self.target.thread, self.target.class_name)
        try:
            if valid:
                if self.original_backdrop is not None:
                    set_window_backdrop(self.target.hwnd, self.original_backdrop)
                # 成功后区域句柄归 Windows 所有；失败时保留恢复记录供下一次重试。
                win32gui.SetWindowRgn(self.target.hwnd, self.original_region or 0, True)
            elif self.original_region:
                win32gui.DeleteObject(self.original_region)
        except (OSError, pywintypes.error) as exc:
            raise OSError('恢复浏览器裁剪失败，请重试。') from exc
        self.target = None
        self.original_region = self.original_backdrop = self.crop_size = None

    def reset(self):
        self.restore()
        # 即使切回同一 HWND，之前排队的识别结果也不能重新启用旧设置。
        self.generation += 1
        self.rect = self.height = self.options = None
        self.next_detection = 0

    def close(self):
        self.reset()
        self.requests.put(None)

    def update(self, hide_top, hide_scrollbar):
        options = (self.guard.selected, hide_top, hide_scrollbar)
        if options != self.options:
            self.reset()
            self.options = options
        if not (hide_top or hide_scrollbar):
            return '浏览器裁剪已关闭。'
        if not self.guard.valid():
            self.reset()
            return '请选择浏览器窗口。'
        hwnd = self.guard.selected.hwnd
        if self.guard.selected.class_name not in ('Chrome_WidgetWin_1', 'MozillaWindowClass'):
            return '未识别到浏览器区域，保留原窗口。'
        now = time.monotonic()
        try:
            token, rect, height = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            pending, self.pending = self.pending, None
            if pending and token == self.generation and now-pending[1] <= 3:
                self.rect, self.height = rect, height
        if self.pending and now-self.pending[1] > 3:
            # 超时不继续使用旧高度，也不无限增生识别线程；等待现有请求返回。
            self.restore()
            self.rect = self.height = None
            return '浏览器识别暂未响应，保留原窗口。'
        if not self.guard.hidden and win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd):
            if not self.pending and now >= self.next_detection:
                if self.thread.ident is None:
                    self.thread.start()
                if not self.thread.is_alive():
                    self.restore()
                    return '浏览器自动识别不可用，请重启程序。'
                self.pending = (self.generation, now)
                self.requests.put((self.generation, hwnd))
                self.next_detection = now + 1
            self.apply(hide_top, hide_scrollbar)
        if self.crop_size:
            return '浏览器区域裁剪已生效。'
        return '未识别到浏览器区域，保留原窗口。'

    def apply(self, hide_top, hide_scrollbar):
        hwnd = self.guard.selected.hwnd
        if not self.height or self.rect != win32gui.GetWindowRect(hwnd):
            # 移动、缩放或识别失败时还原，等待匹配当前物理坐标的新结果。
            self.restore()
            return
        left, top, right, bottom = self.rect
        width, height = right-left, bottom-top
        content_top = min(self.height, max(0, height-1))
        hidden = content_top if hide_top else 0
        right_hidden = min(get_scrollbar_crop_width(hwnd), max(0, width-1)) if hide_scrollbar else 0
        size = (width, height, hidden, right_hidden, content_top)
        region = None
        try:
            if self.target is None:
                original = win32gui.CreateRectRgnIndirect((0, 0, 0, 0))
                try:
                    try:
                        # 未设置区域时 GetWindowRgn 不保证更新错误码，先清掉线程上残留的错误。
                        ctypes.windll.kernel32.SetLastError(0)
                        has_region = win32gui.GetWindowRgn(hwnd, original)
                    except pywintypes.error as exc:
                        # 普通窗口未定义区域时 pywin32 报错误码 0，并非操作失败。
                        if exc.winerror != 0:
                            raise
                        has_region = False
                except Exception:
                    win32gui.DeleteObject(original)
                    raise
                if not has_region:
                    win32gui.DeleteObject(original)
                    original = None
                self.original_region = original
                self.target = self.guard.selected
                self.original_backdrop = get_window_backdrop(hwnd)
            # Mica 独立合成，单纯裁剪会残留白条；浏览器重设背景后也要再次关闭。
            if self.original_backdrop is not None and get_window_backdrop(hwnd) != 1:
                set_window_backdrop(hwnd, 1)
            if self.crop_size == size:
                return
            region = win32gui.CreateRectRgnIndirect((0, hidden, width, height))
            if right_hidden:
                scrollbar = win32gui.CreateRectRgnIndirect((width-right_hidden, content_top, width, height))
                try:
                    win32gui.CombineRgn(region, region, scrollbar, win32con.RGN_DIFF)
                finally:
                    win32gui.DeleteObject(scrollbar)
            if self.original_region:
                win32gui.CombineRgn(region, region, self.original_region, win32con.RGN_AND)
            win32gui.SetWindowRgn(hwnd, region, True)
            region = None
            self.crop_size = size
        except (OSError, pywintypes.error) as exc:
            raise OSError('浏览器裁剪失败，请关闭开关后重试。') from exc
        finally:
            if region is not None:
                win32gui.DeleteObject(region)

    def contains(self, rect, point):
        if not self.crop_size:
            return True
        # 被裁掉的顶部和滚动条按“鼠标移出”处理，不能因进入空白区域变回不透明。
        _, _, hidden, right_hidden, content_top = self.crop_size
        return (point.y >= rect.top+hidden and not (
            point.x >= rect.right-right_hidden and point.y >= rect.top+content_top))
