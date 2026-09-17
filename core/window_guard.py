"""Selected-window hiding and mouse-dependent opacity using Windows APIs."""
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Window:
    hwnd: int
    pid: int
    thread: int
    title: str
    class_name: str


class WindowGuard:
    def __init__(self):
        self.api = ctypes.WinDLL('user32', use_last_error=True)
        self.callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        signatures = {
            'EnumWindows': ([self.callback_type, wintypes.LPARAM], wintypes.BOOL),
            'IsWindow': ([wintypes.HWND], wintypes.BOOL),
            'IsWindowVisible': ([wintypes.HWND], wintypes.BOOL),
            'GetWindowTextLengthW': ([wintypes.HWND], ctypes.c_int),
            'GetWindowTextW': ([wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
            'GetClassNameW': ([wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
            'GetWindowThreadProcessId': ([wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
            'ShowWindowAsync': ([wintypes.HWND, ctypes.c_int], wintypes.BOOL),
            'PostMessageW': ([wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM], wintypes.BOOL),
            'GetWindowLongW': ([wintypes.HWND, ctypes.c_int], wintypes.LONG),
            'SetWindowLongW': ([wintypes.HWND, ctypes.c_int, wintypes.LONG], wintypes.LONG),
            'GetWindowRect': ([wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
            'GetCursorPos': ([ctypes.POINTER(wintypes.POINT)], wintypes.BOOL),
            'GetLayeredWindowAttributes': ([wintypes.HWND, ctypes.POINTER(wintypes.DWORD),
                                            ctypes.POINTER(wintypes.BYTE), ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            'SetLayeredWindowAttributes': ([wintypes.HWND, wintypes.DWORD, wintypes.BYTE, wintypes.DWORD], wintypes.BOOL),
        }
        # HWND 必须按指针宽度传递，否则 64 位系统上可能操作错误的窗口。
        for name, (args, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, result
        self.selected = None
        self.hidden = False
        self.original_opacity = None
        self.browser_crop = None

    def describe(self, hwnd):
        if not self.api.IsWindow(hwnd):
            return None
        pid = wintypes.DWORD()
        thread = self.api.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        title = ctypes.create_unicode_buffer(self.api.GetWindowTextLengthW(hwnd) + 1)
        self.api.GetWindowTextW(hwnd, title, len(title))
        class_name = ctypes.create_unicode_buffer(256)
        self.api.GetClassNameW(hwnd, class_name, len(class_name))
        return Window(hwnd, pid.value, thread, title.value, class_name.value)

    def windows(self):
        windows = []

        @self.callback_type
        def collect(hwnd, _):
            if self.api.IsWindowVisible(hwnd):
                window = self.describe(hwnd)
                # 排除监测面板和桌面外壳，防止把恢复入口或任务栏隐藏。
                if (window and window.title and window.pid != os.getpid()
                        and window.class_name not in ('Progman', 'WorkerW', 'Shell_TrayWnd', 'Shell_SecondaryTrayWnd')):
                    windows.append(window)
            return True

        if not self.api.EnumWindows(collect, 0):
            raise OSError('无法读取窗口列表，请重试。')
        return windows

    def valid(self):
        current = self.describe(self.selected.hwnd) if self.selected else None
        # 标题会随网页导航变化；用进程、线程和窗口类检查明显的句柄复用。
        return bool(current and (current.pid, current.thread, current.class_name) ==
                    (self.selected.pid, self.selected.thread, self.selected.class_name))

    def select(self, window):
        self.restore_crop()
        self.restore_opacity()
        self.restore()
        self.selected = window

    def update_crop(self, hide_top, hide_scrollbar):
        if self.browser_crop is None:
            if not (hide_top or hide_scrollbar):
                return '浏览器裁剪已关闭。'
            from core.browser_crop import BrowserCrop
            self.browser_crop = BrowserCrop(self)
        import pywintypes
        try:
            return self.browser_crop.update(hide_top, hide_scrollbar)
        except pywintypes.error as exc:
            # 窗口可能在有效性检查后被关闭；向界面返回可恢复错误，不中断监测轮询。
            raise OSError('浏览器裁剪失败，请关闭开关后重试。') from exc

    def restore_crop(self):
        if self.browser_crop is not None:
            self.browser_crop.reset()

    def set_styles(self, styles):
        # 返回零也可能是成功（原样式为零），必须结合 GetLastError 判断。
        ctypes.set_last_error(0)
        previous = self.api.SetWindowLongW(self.selected.hwnd, -20, styles)
        if previous == 0 and ctypes.get_last_error():
            raise OSError('无法设置窗口透明度样式，请检查目标程序权限。')

    def update_opacity(self, entry_alpha, exit_alpha):
        if not self.valid():
            raise OSError('目标窗口已关闭，请刷新并重新选择。')
        hwnd = self.selected.hwnd
        # 隐藏优先；鼠标进入原窗口区域也不能把监测隐藏的窗口重新显示。
        if self.hidden or not self.api.IsWindowVisible(hwnd):
            return
        rect, point = wintypes.RECT(), wintypes.POINT()
        if not self.api.GetWindowRect(hwnd, ctypes.byref(rect)) or not self.api.GetCursorPos(ctypes.byref(point)):
            raise OSError('无法读取鼠标或窗口位置，请重试。')
        inside = rect.left <= point.x < rect.right and rect.top <= point.y < rect.bottom
        if inside and self.browser_crop is not None:
            inside = self.browser_crop.contains(rect, point)
        alpha = max(0, min(255, int(entry_alpha if inside else exit_alpha)))
        styles = self.api.GetWindowLongW(hwnd, -20)
        if self.original_opacity is None:
            color, original_alpha, flags = wintypes.DWORD(), wintypes.BYTE(), wintypes.DWORD()
            if styles & 0x80000:
                # 逐像素透明窗口不一定能读取透明参数；不能保存时不覆盖，确保退出可恢复。
                if not self.api.GetLayeredWindowAttributes(hwnd, ctypes.byref(color), ctypes.byref(original_alpha), ctypes.byref(flags)):
                    raise OSError('该窗口的原透明度无法读取，未修改；请选择其他窗口。')
            self.original_opacity = (bool(styles & 0x80000), color.value, original_alpha.value, flags.value)
        # 只在缺少 WS_EX_LAYERED 时设置，避免反复重建浏览器外观。
        if not styles & 0x80000:
            self.set_styles(styles | 0x80000)
        _, color, _, flags = self.original_opacity
        if not self.api.SetLayeredWindowAttributes(hwnd, color, alpha, flags | 2):
            raise OSError('无法设置透明度，请关闭透明度开关重试。')

    def restore_opacity(self):
        if self.original_opacity is None:
            return
        if self.valid():
            layered, color, alpha, flags = self.original_opacity
            if layered:
                if not self.api.SetLayeredWindowAttributes(self.selected.hwnd, color, alpha, flags):
                    raise OSError('无法恢复原透明度，请重试。')
            else:
                # 只移除本工具添加的透明样式，保留目标程序期间修改的其他样式位。
                self.set_styles(self.api.GetWindowLongW(self.selected.hwnd, -20) & ~0x80000)
        self.original_opacity = None

    def hide(self):
        if not self.valid():
            self.selected = None
            self.hidden = False
            raise OSError('目标窗口已关闭，请刷新并重新选择。')
        if not self.api.IsWindowVisible(self.selected.hwnd):
            return False
        # 外部程序可能无响应；异步请求避免阻塞摄像头轮询和恢复按钮。
        if not self.api.ShowWindowAsync(self.selected.hwnd, 0):
            raise OSError('无法隐藏窗口，请检查目标程序权限后重试。')
        self.hidden = True
        return True

    def restore(self):
        if not self.hidden:
            return
        if self.valid():
            # SW_SHOWNA 保留窗口当前大小和状态，不抢走用户正在输入的焦点。
            if not self.api.ShowWindowAsync(self.selected.hwnd, 8):
                raise OSError('无法恢复窗口，请重试；必要时重启目标程序。')
        self.hidden = False

    def close_selected(self):
        if not self.valid():
            return
        # 仅向仍匹配的所选窗口发送正常关闭请求，保留目标程序的未保存提示，不终止其进程。
        if not self.api.PostMessageW(self.selected.hwnd, 0x0010, 0, 0):
            raise OSError('无法关闭所选窗口，请重试或关闭“退出时关闭所选窗口”开关。')
