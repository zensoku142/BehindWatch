"""BehindWatch Qt interface; capture and protection remain in their existing modules."""
import multiprocessing as mp

if __name__ == '__main__':
    # 冻结版采集子进程先进入 worker，避免重复加载 Qt、通知和整个设置界面。
    mp.freeze_support()
    from bootstrap import ensure_runtime
    ensure_runtime()

import ctypes
import queue
import subprocess
import sys
import threading
import time
import uuid
from ctypes import wintypes
from PySide6.QtCore import QEvent, QRectF, QSignalBlocker, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPen, QShortcut, QKeySequence
from PySide6.QtWidgets import (QApplication, QButtonGroup, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QMenu, QPlainTextEdit, QPushButton, QScrollArea, QSizeGrip, QSizePolicy, QSlider,
    QSpinBox, QStackedWidget, QStyle, QSystemTrayIcon, QToolButton, QVBoxLayout, QWidget)
from core.vision import worker
from core.face_identity import delete_template, load_template
from core.window_guard import WindowGuard
from core.preferences import DEFAULTS, load_preferences, save_preferences
from core.autostart import sync_autostart
from core.seat_lock import LockDecision, input_idle_seconds, lock_workstation
from core.news import NEWS_APP_ID, fetch_headlines, news_notifications_enabled, register_news_app
from updater.updates import APP_VERSION, CHECK_INTERVAL, RELEASES_URL, check_release, download_installer, launch_installer
from win11toast import notify as send_news_toast
from ui.qt_theme import configure_theme, current_theme, fluent_icon
from ui.i18n import LANGUAGES, add_item, bind_text, configure_language, startup_running_message, tr
from ui.ui_widgets import SettingsComboBox, SettingsSwitch, SettingsTabBar, Preview, app_icon


WM_WTSSESSION_CHANGE = 0x02B1
WM_POWERBROADCAST = 0x0218
WM_HOTKEY = 0x0312
MONITOR_HOTKEY_ID = 0xB17
MONITOR_HOTKEYS = {'Ctrl+Alt+M': (0x0003, ord('M')), 'Ctrl+Alt+S': (0x0003, ord('S')),
                   'Ctrl+Shift+M': (0x0006, ord('M')), 'Alt+Shift+M': (0x0005, ord('M'))}
PBT_POWERSETTINGCHANGE = 0x8013
WTS_SESSION_LOCK, WTS_SESSION_UNLOCK = 7, 8
SESSION_DISPLAY_STATUS = uuid.UUID('2b84c20e-ad23-4ddf-93db-05ffbd7efca5').bytes_le


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.root = self
        self.process = None
        self.stopping = self.failed = self.closed = False
        self._quitting = False
        self.session_locked = self.display_off = self.auto_resume = False
        self.session_notifications = False
        self.display_notification = None
        self.last_frame = None
        self.selection_mode = None
        self.last_received = 0
        self.started = time.monotonic()
        self.lock_decision = LockDecision()
        self.camera_active = True
        self.camera_pending = False
        self.presence_since = None
        self.recheck_at = 0
        self.tray = self.toast = None
        self.toasts = []
        self.ui_commands = queue.Queue()
        self.update_results = queue.Queue()
        self.install_results = queue.Queue()
        self.news_results = queue.Queue()
        self.news_headlines = []
        self.news_index = 0
        self.news_fetching = False
        self.news_identity_ready = False
        self.update_busy = False
        self.latest_release = None
        self.window_guard = WindowGuard()
        self.windows, self.cameras = [], []
        # 自检不恢复用户目标窗口，避免自动应用透明度、裁剪或退出关闭选项。
        self.preferences = DEFAULTS.copy() if '--smoke-test' in sys.argv else load_preferences()
        self.face_registered = load_template() is not None
        self.theme = configure_theme(QApplication.instance(), self.preferences['theme'])
        self.language = configure_language(QApplication.instance(), self.preferences['language'])
        self.setWindowTitle('BehindWatch')
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(640, 520)
        self.resize(*self.preferences.get('window_size', [760, 600]))
        self.setWindowIcon(app_icon())
        self.build()
        # 连续拖动只在停下后写入，避免每个 resize 事件都访问磁盘。
        self.size_save_timer = QTimer(self)
        self.size_save_timer.setSingleShot(True)
        self.size_save_timer.setInterval(300)
        self.size_save_timer.timeout.connect(self.save_preferences)
        self.settings_save_timer = QTimer(self)
        self.settings_save_timer.setSingleShot(True)
        self.settings_save_timer.setInterval(300)
        self.settings_save_timer.timeout.connect(self.save_preferences)
        self.connect_settings_autosave()
        # 自检只验证界面，不能读写当前用户的登录启动项。
        if '--smoke-test' not in sys.argv:
            try:
                sync_autostart(self.preferences['auto_start'])
            except (OSError, KeyError, subprocess.SubprocessError) as exc:
                bind_text(self.preference_status, lambda error=str(exc): tr('开机自启设置失败：{error}', error=error))
                self.settings_page.layout().addWidget(self.preference_status)
                self.preference_status.show()
        self.lock_warning = QLabel()
        self.lock_warning.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.lock_warning.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lock_warning.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.lock_warning.setStyleSheet('background: rgba(20, 24, 32, 180); color: white; padding: 14px 28px; border-radius: 12px; font-size: 18px;')
        self.lock_warning.hide()
        self.theme.changed.connect(self.refresh_theme)
        self.language.changed.connect(self.refresh_language)
        self.refresh_theme()
        self.refresh_windows()
        self.setup_tray()
        self.refresh_cameras()
        # Qt 定时器只在 GUI 线程消费进程/网络结果，后台线程不接触控件。
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(100)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.maybe_check_updates)
        self.update_timer.start(60000)
        QTimer.singleShot(1500, self.maybe_check_updates)
        self.news_timer = QTimer(self)
        self.news_timer.timeout.connect(self.refresh_news)
        self.news_timer.start(60 * 60 * 1000)
        QTimer.singleShot(1000, self.refresh_news)
        self.register_system_notifications()
        self.monitor_hotkey = ''
        self.monitor_hotkey_hwnd = None
        if not self.set_monitor_hotkey(self.preferences['monitor_hotkey']):
            bind_text(self.preference_status, '快捷键不可用，可能已被其他程序占用。')
            self.preference_status.show()

    def event(self, event):
        if event.type() == QEvent.Type.WinIdChange and getattr(self, 'monitor_hotkey', ''):
            # Qt 可能重建原生窗口；旧 HWND 上的全局热键不会自动转到新窗口。
            QTimer.singleShot(0, self.refresh_monitor_hotkey_binding)
        return super().event(event)

    def refresh_monitor_hotkey_binding(self):
        if not self.closed and self.monitor_hotkey and self.monitor_hotkey_hwnd != int(self.winId()):
            if not self.set_monitor_hotkey(self.monitor_hotkey):
                bind_text(self.preference_status, '快捷键不可用，可能已被其他程序占用。')
                self.preference_status.show()

    def register_system_notifications(self):
        hwnd = wintypes.HWND(int(self.winId()))
        self._wts = ctypes.WinDLL('wtsapi32', use_last_error=True)
        self._user32 = ctypes.WinDLL('user32', use_last_error=True)
        self._wts.WTSRegisterSessionNotification.argtypes = (wintypes.HWND, wintypes.DWORD)
        self._wts.WTSRegisterSessionNotification.restype = wintypes.BOOL
        self._wts.WTSUnRegisterSessionNotification.argtypes = (wintypes.HWND,)
        self._user32.RegisterPowerSettingNotification.argtypes = (wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD)
        self._user32.RegisterPowerSettingNotification.restype = wintypes.HANDLE
        self._user32.UnregisterPowerSettingNotification.argtypes = (wintypes.HANDLE,)
        self.session_notifications = bool(self._wts.WTSRegisterSessionNotification(hwnd, 0))
        # Interactive apps receive the current session's display state through this GUID.
        display_guid = ctypes.create_string_buffer(SESSION_DISPLAY_STATUS)
        self.display_notification = self._user32.RegisterPowerSettingNotification(hwnd, display_guid, 0)

    def nativeEvent(self, event_type, message):
        if event_type == b'windows_generic_MSG':
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == MONITOR_HOTKEY_ID:
                self.pause_monitoring_from_hotkey()
                return True, 0
            if msg.message == WM_WTSSESSION_CHANGE:
                if msg.wParam in (WTS_SESSION_LOCK, WTS_SESSION_UNLOCK):
                    self.system_state_changed(locked=msg.wParam == WTS_SESSION_LOCK)
                    return False, 0
            elif msg.message == WM_POWERBROADCAST and msg.wParam == PBT_POWERSETTINGCHANGE and msg.lParam:
                setting = ctypes.string_at(msg.lParam, 20)
                if setting[:16] == SESSION_DISPLAY_STATUS and int.from_bytes(setting[16:20], 'little') >= 4:
                    # 0=off, 1=on, 2=dimmed; dimming still leaves the desktop usable.
                    state = int.from_bytes(ctypes.string_at(msg.lParam + 20, 4), 'little')
                    if state in (0, 1, 2):
                        self.system_state_changed(display_off=state == 0)
                        return False, 0
        return super().nativeEvent(event_type, message)

    def pause_monitoring_from_hotkey(self):
        # 启动需要用户在预览中选择本人，因此快捷键只负责暂停。
        if self.process is not None and not self.stopping and not self.closed:
            self.stop()

    def set_monitor_hotkey(self, hotkey):
        previous = self.monitor_hotkey
        if previous:
            self._user32.UnregisterHotKey(wintypes.HWND(self.monitor_hotkey_hwnd), MONITOR_HOTKEY_ID)
        self.monitor_hotkey = ''
        self.monitor_hotkey_hwnd = None
        if hotkey:
            modifiers, key = MONITOR_HOTKEYS[hotkey]
            hwnd = int(self.winId())
            # 系统注册使托盘隐藏时仍可操作；失败时恢复先前的快捷键。
            if not self._user32.RegisterHotKey(wintypes.HWND(hwnd), MONITOR_HOTKEY_ID,
                                                modifiers | 0x4000, key):
                if previous:
                    old_modifiers, old_key = MONITOR_HOTKEYS[previous]
                    if self._user32.RegisterHotKey(wintypes.HWND(hwnd), MONITOR_HOTKEY_ID,
                                                    old_modifiers | 0x4000, old_key):
                        self.monitor_hotkey = previous
                        self.monitor_hotkey_hwnd = hwnd
                return False
            self.monitor_hotkey = hotkey
            self.monitor_hotkey_hwnd = hwnd
        return True

    def system_state_changed(self, *, locked=None, display_off=None):
        if locked is not None:
            self.session_locked = locked
        if display_off is not None:
            self.display_off = display_off
        if self.session_locked or self.display_off:
            if self.process is not None and not self.stopping:
                # Resume only a session interrupted by Windows, never a user-paused session.
                self.auto_resume = True
                self.stop(auto=True)
        elif self.auto_resume and self.process is None and not self.closed:
            self.auto_resume = False
            self.start()

    def label(self, text='', role='muted'):
        label = QLabel()
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setObjectName(role)
        label.setWordWrap(True)
        return bind_text(label, text)

    def button(self, text, callback, primary=False):
        button = bind_text(QPushButton(), text)
        if primary:
            button.setObjectName('primaryButton')
        button.clicked.connect(lambda: callback())
        return button

    def tool(self, text, icon, callback):
        button = QToolButton()
        button.setObjectName('panelToolButton')
        button.setIconSize(QSize(18, 18))
        button.setFixedSize(32, 32)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        button.setProperty('iconName', icon)
        bind_text(button, text, method='setToolTip')
        bind_text(button, text, method='setAccessibleName')
        button.clicked.connect(lambda: callback())
        return button

    def row(self, layout, title, *controls):
        frame = QFrame()
        frame.setObjectName('settingsSwitchRow')
        row = QHBoxLayout(frame)
        row.setContentsMargins(0, 12, 0, 12)
        row.setSpacing(12)
        label = self.label(title, 'settingsRowTitle')
        label.setFixedWidth(100)
        row.addWidget(label)
        for control in controls:
            row.addWidget(control, 1 if isinstance(control, (SettingsComboBox, QSlider, QLabel)) else 0)
        layout.addWidget(frame)
        return row

    def build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        self.header = QWidget()
        self.header.setFixedHeight(42)
        self.header.setObjectName('panelHeader')
        self.header.installEventFilter(self)
        header = QHBoxLayout(self.header)
        header.setContentsMargins(14, 5, 12, 5)
        header.setSpacing(8)
        self.brand = QLabel()
        self.brand.setFixedSize(28, 28)
        self.brand.installEventFilter(self)
        header.addWidget(self.brand)
        title = self.label('BehindWatch', 'panelTitle')
        title.setWordWrap(False)
        title.installEventFilter(self)
        header.addWidget(title)
        # 直接沿用 TokenMeter 的标题栏返回入口，不使用带边框的普通按钮。
        self.back_button = bind_text(QToolButton(), '返回面板')
        self.back_button.setObjectName('settingsBackButton')
        self.back_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        self.back_button.setIconSize(QSize(14, 14))
        self.back_button.setFixedSize(132, 28)
        self.back_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.back_button.clicked.connect(self.close_settings)
        header.addWidget(self.back_button)
        self.back_button.hide()
        self.quick_window_choice = SettingsComboBox()
        self.quick_window_choice.setObjectName('headerProviderCombo')
        self.quick_window_choice.setMinimumContentsLength(8)
        self.quick_window_choice.setMaximumWidth(210)
        bind_text(self.quick_window_choice, '选择目标窗口', method='setPlaceholderText')
        header.addWidget(self.quick_window_choice, 1)
        header.addStretch()
        self.settings_save_status = self.label('已自动保存', 'settingsSaveStatus')
        self.settings_save_status.setWordWrap(False)
        bind_text(self.settings_save_status, '设置已自动保存；监测仍需手动启动并选择本人。', method='setToolTip')
        header.addWidget(self.settings_save_status)
        self.settings_save_status.hide()
        self.recovery_button = self.button('恢复窗口', self.restore_window)
        header.addWidget(self.recovery_button)
        self.recovery_button.hide()
        self.theme_segment = QFrame()
        self.theme_segment.setObjectName('themeSegment')
        self.theme_segment.setFixedHeight(30)
        theme_layout = QHBoxLayout(self.theme_segment)
        theme_layout.setContentsMargins(2, 2, 2, 2)
        theme_layout.setSpacing(0)
        self.theme_group = QButtonGroup(self)
        self.theme_group.setExclusive(True)
        for mode, icon, tooltip in (('light', 'sun', '切换到浅色主题'), ('dark', 'moon', '切换到深色主题')):
            button = QToolButton()
            button.setObjectName('themeButton')
            button.setProperty('iconName', icon)
            button.setProperty('themeValue', mode)
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setFixedSize(24, 24)
            button.setIconSize(QSize(14, 14))
            bind_text(button, tooltip, method='setToolTip')
            bind_text(button, tooltip, method='setAccessibleName')
            button.clicked.connect(lambda checked=False, value=mode: self.set_theme_mode(value))
            setattr(self, mode + '_theme_button', button)
            self.theme_group.addButton(button)
            theme_layout.addWidget(button)
        header.addWidget(self.theme_segment)
        divider = QFrame()
        divider.setObjectName('divider')
        divider.setFixedSize(1, 22)
        header.addWidget(divider)
        self.settings_button = self.tool('设置', 'settings', self.show_settings)
        header.addWidget(self.settings_button)
        self.header_refresh_button = self.tool('刷新', 'refresh', self.refresh_current_page)
        header.addWidget(self.header_refresh_button)
        close = self.tool('收起到后台', 'close', self.hide_to_tray)
        close.setProperty('role', 'close')
        header.addWidget(close)
        outer.addWidget(self.header)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self.main_page = QWidget()
        self.main_page.setObjectName('monitorPage')
        main = QVBoxLayout(self.main_page)
        main.setContentsMargins(22, 18, 22, 18)
        main.setSpacing(12)
        main.addWidget(self.label('摄像头预览', 'sectionTitle'))
        content = QHBoxLayout()
        content.setSpacing(20)
        preview_column = QVBoxLayout()
        self.selection_hint = self.label('点同事框直接忽略 · 选择本人请点按钮')
        hint_policy = self.selection_hint.sizePolicy()
        hint_policy.setRetainSizeWhenHidden(True)
        self.selection_hint.setSizePolicy(hint_policy)
        self.owner_select_button = self.button('选择本人', lambda: self.set_selection_mode('owner'))
        self.owner_select_button.setObjectName('selectionModeButton')
        self.owner_select_button.setCheckable(True)
        self.canvas = Preview()
        self.canvas.selected.connect(self.calibrate)
        self.canvas.ignore_selected.connect(self.toggle_ignored_person)
        preview_column.addWidget(self.canvas)
        preview_column.addWidget(self.selection_hint)
        preview_column.addStretch()
        content.addLayout(preview_column, 5)
        divider = QFrame()
        divider.setObjectName('divider')
        divider.setFixedWidth(1)
        content.addWidget(divider)
        sidebar = QVBoxLayout()
        sidebar.setSpacing(14)
        sidebar.addSpacing(18)
        content.addLayout(sidebar, 2)
        main.addLayout(content, 1)
        self.status_bar = QWidget()
        self.status_bar.setObjectName('statusBar')
        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(0, 12, 0, 0)
        status_line = QHBoxLayout()
        self.status_dot = QLabel('●')
        self.status = self.label('尚未开始监测', 'sectionTitle')
        status_line.addWidget(self.status_dot)
        status_line.addWidget(self.status, 1)
        sidebar.addLayout(status_line)
        self.owner_status = self.label('尚未选择本人')
        sidebar.addWidget(self.owner_status)
        self.detail = self.label()
        self.detail.hide()
        sidebar.addWidget(self.detail)
        sidebar.addSpacing(14)
        sidebar.addWidget(self.owner_select_button)
        self.preview_toggle = self.button('隐藏画面', self.toggle_preview)
        sidebar.addWidget(self.preview_toggle)
        self.owner_row = QWidget()
        owners = QVBoxLayout(self.owner_row)
        owners.setContentsMargins(0, 0, 0, 0)
        self.owner_choice = SettingsComboBox()
        self.owner_choice.setMinimumContentsLength(6)
        owners.addWidget(self.owner_choice)
        self.owner_confirm = self.button('这是我', self.select_from_list)
        owners.addWidget(self.owner_confirm)
        sidebar.addWidget(self.owner_row)
        self.owner_row.hide()
        sidebar.addStretch()
        status_layout.addWidget(self.label('本机处理 · 不录制 · 不上传'), 1)
        self.start_button = self.button('开始监测', self.start, True)
        self.stop_button = self.button('暂停监测', self.stop)
        status_layout.addWidget(self.start_button)
        status_layout.addWidget(self.stop_button)
        self.background_button = self.button('收起到后台', self.hide_to_tray, True)
        status_layout.addWidget(self.background_button)
        self.stop_button.hide()
        main.addWidget(self.status_bar)
        self.stack.addWidget(self.main_page)
        self.build_settings()
        self.resize_grip = QSizeGrip(self)
        QShortcut(QKeySequence('Ctrl+,'), self, activated=self.show_settings)
        QShortcut(QKeySequence('Escape'), self, activated=self.quit)
        self.settings_open = False
        self.current_settings_page = '摄像头'

    def build_settings(self):
        self.settings_page = QDialog(self)
        self.settings_page.setWindowFlags(Qt.WindowType.Widget)
        self.settings_page.setObjectName('settingsPage')
        layout = QVBoxLayout(self.settings_page)
        self.settings_page.setStyleSheet('QDialog#settingsPage { background: transparent; }')
        layout.setContentsMargins(24, 14, 24, 18)
        layout.setSpacing(0)
        self.tabs = SettingsTabBar()
        self.tabs.setStyleSheet('font-size: 13px;')
        self.settings_stack = QStackedWidget()
        self.settings_pages = {}
        self.page_names = ('摄像头', '锁屏与本人', '窗口保护', '提醒', '常规', '更新与关于')
        for name in self.page_names:
            index = self.tabs.addTab('')
            bind_text(self.tabs, name, method='setTabText', index=index)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            body = QWidget()
            body.setObjectName('settingsBody')
            page = QVBoxLayout(body)
            page.setContentsMargins(0, 20, 0, 8)
            page.setSpacing(12)
            scroll.setWidget(body)
            self.settings_stack.addWidget(scroll)
            self.settings_pages[name] = page
        self.tabs.currentChanged.connect(self.settings_stack.setCurrentIndex)
        self.tabs.currentChanged.connect(lambda i: setattr(self, 'current_settings_page', self.page_names[i]))
        layout.addWidget(self.tabs)
        layout.addWidget(self.settings_stack, 1)
        self.preference_status = self.label('设置已自动保存；监测仍需手动启动并选择本人。')
        self.preference_status.hide()
        self.stack.addWidget(self.settings_page)
        page = self.settings_pages['摄像头']
        page.addWidget(self.label('摄像头仅在开启监测时使用。'))
        self.camera = SettingsComboBox()
        self.refresh_button = self.tool('刷新设备', 'refresh', self.refresh_cameras)
        self.row(page, '摄像头', self.camera, self.refresh_button)
        self.camera_mode = SettingsComboBox()
        add_item(self.camera_mode, '持续监测', 'continuous')
        add_item(self.camera_mode, '键鼠空闲后监测', 'idle')
        self.camera_mode.setCurrentIndex(self.camera_mode.findData(self.preferences['camera_mode']))
        self.row(page, '摄像头工作模式', self.camera_mode)
        self.idle_settings = QWidget()
        idle_layout = QVBoxLayout(self.idle_settings)
        idle_layout.setContentsMargins(0, 0, 0, 0)
        idle_layout.setSpacing(12)
        self.idle_threshold = QSpinBox()
        self.idle_threshold.setRange(5, 300)
        self.idle_threshold.setValue(self.preferences['idle_threshold'])
        self.idle_threshold.setSuffix(' 秒')
        self.row(idle_layout, '空闲后开启', self.idle_threshold)
        self.recheck_interval = QSpinBox()
        self.recheck_interval.setRange(10, 600)
        self.recheck_interval.setValue(self.preferences['recheck_interval'])
        self.recheck_interval.setSuffix(' 秒')
        self.row(idle_layout, '在场复查间隔', self.recheck_interval)
        idle_layout.addWidget(self.label('空闲模式会在连续确认有人在场 10 秒后关闭摄像头；恢复键鼠操作时立即关闭。'))
        page.addWidget(self.idle_settings)
        # 持续监测不使用空闲参数；隐藏时保留用户数值，切回即可继续使用。
        self.camera_mode.currentIndexChanged.connect(
            lambda: self.idle_settings.setVisible(self.camera_mode.currentData() == 'idle'))
        self.idle_settings.setVisible(self.camera_mode.currentData() == 'idle')
        self.meta = self.label()
        page.addWidget(self.meta)
        page.addStretch()
        page = self.settings_pages['锁屏与本人']
        page.addWidget(self.label('离席锁屏', 'sectionTitle'))
        self.lock_enabled = SettingsSwitch('自动锁屏')
        self.lock_enabled.setChecked(self.preferences['lock_enabled'])
        row = self.row(page, '自动锁屏', self.label('连续离席且键鼠空闲 60 秒后，先提示 5 秒。'))
        row.addWidget(self.lock_enabled)
        self.presence_mode = SettingsComboBox()
        add_item(self.presence_mode, '任意人脸', 'any')
        add_item(self.presence_mode, '仅本人', 'owner')
        self.presence_mode.setCurrentIndex(self.presence_mode.findData(self.preferences['presence_mode']))
        self.row(page, '在场判断', self.presence_mode)
        self.owner_settings = QWidget()
        owner_layout = QVBoxLayout(self.owner_settings)
        owner_layout.setContentsMargins(0, 0, 0, 0)
        owner_layout.setSpacing(12)
        owner_layout.addWidget(self.label('本人面容', 'sectionTitle'))
        self.row(owner_layout, '本人校准', self.label('先点选择本人，再点预览中自己的检测框。'), self.button('返回校准', self.close_settings))
        self.registration_status = self.label('已注册本人面容。' if self.face_registered else '尚未注册本人面容。')
        self.row(owner_layout, '人脸注册', self.registration_status, self.button('注册当前本人', self.register_face))
        self.delete_face_button = self.button('删除注册', self.delete_face)
        self.row(owner_layout, '注册管理', self.label('人脸特征仅保存在本机当前用户目录。'), self.delete_face_button)
        self.delete_face_button.setEnabled(self.face_registered)
        page.addWidget(self.owner_settings)
        # 注册也用于监测开始后的本人恢复，且删除入口不能被在场判断选项隐藏。
        page.addStretch()
        page = self.settings_pages['窗口保护']
        page.addWidget(self.label('只保护所选窗口，恢复后关闭自动隐藏。'))
        self.window_choice = SettingsComboBox()
        bind_text(self.window_choice, '选择目标窗口', method='setPlaceholderText')
        self.row(page, '目标窗口', self.window_choice, self.tool('刷新窗口', 'refresh', self.refresh_windows))
        for combo in (self.window_choice, self.quick_window_choice):
            combo.opening.connect(self.refresh_windows)
            combo.activated.connect(lambda index, c=combo: self.select_window(index))
        self.auto_hide = SettingsSwitch('自动隐藏')
        self.auto_hide.setChecked(self.preferences['auto_hide'])
        self.auto_hide.clicked.connect(self.toggle_window_guard)
        page.addWidget(self.label('走动保护', 'sectionTitle'))
        row = self.row(page, '自动隐藏', self.label('其他人员走动时隐藏窗口'))
        row.addWidget(self.auto_hide)
        self.window_status = self.label('选择目标窗口后开启；人员离开不会自动恢复。')
        page.addWidget(self.window_status)
        self.restore_window_button = self.button('恢复并关闭自动隐藏', self.restore_window)
        page.addWidget(self.restore_window_button, 0, Qt.AlignmentFlag.AlignRight)
        page.addWidget(self.label('浏览器裁剪', 'sectionTitle'))
        self.hide_browser_top = SettingsSwitch('隐藏浏览器顶部')
        self.hide_browser_scrollbar = SettingsSwitch('隐藏右侧滚动条')
        self.hide_browser_top.setChecked(self.preferences['hide_browser_top'])
        self.hide_browser_scrollbar.setChecked(self.preferences['hide_browser_scrollbar'])
        for title, switch in (('隐藏浏览器顶部', self.hide_browser_top),
                              ('隐藏右侧滚动条', self.hide_browser_scrollbar)):
            row = self.row(page, title)
            row.addStretch()
            row.addWidget(switch)
            switch.clicked.connect(self.update_browser_crop)
        page.addWidget(self.label('自动识别标签栏、地址栏和书签栏高度；滚轮仍可滚动。'))
        self.browser_crop_status = self.label('浏览器裁剪已关闭。')
        page.addWidget(self.browser_crop_status)
        page.addWidget(self.label('鼠标透明度', 'sectionTitle'))
        self.mouse_opacity = SettingsSwitch('鼠标透明度')
        self.mouse_opacity.setChecked(self.preferences['mouse_opacity'])
        self.mouse_opacity.clicked.connect(self.toggle_opacity)
        row = self.row(page, '鼠标透明度', self.label('范围 0–255，0 为完全透明'))
        row.addWidget(self.mouse_opacity)
        self.opacity_scales = []
        for title, value in (('移入', self.preferences['entry_alpha']),
                             ('移出', self.preferences['exit_alpha'])):
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 255)
            slider.setValue(value)
            bind_text(slider, title, method='setAccessibleName')
            number = QLabel(str(value))
            number.setFixedWidth(28)
            slider.valueChanged.connect(lambda v, label=number: label.setText(str(v)))
            slider.valueChanged.connect(self.update_window_opacity)
            self.row(page, title, slider, number)
            self.opacity_scales.append(slider)
        self.entry_alpha, self.exit_alpha = self.opacity_scales
        self.close_window_on_exit = SettingsSwitch('退出时关闭所选窗口')
        self.close_window_on_exit.setChecked(self.preferences['close_window_on_exit'])
        row = self.row(page, '退出时关闭所选窗口', self.label('仅真正退出时生效，收起到托盘不会关闭。'))
        row.addWidget(self.close_window_on_exit)
        page.addStretch()
        page = self.settings_pages['提醒']
        self.reminder_mode = SettingsComboBox()
        add_item(self.reminder_mode, '角落提示点', 'dot')
        add_item(self.reminder_mode, '系统通知', 'text')
        self.reminder_mode.setCurrentIndex(self.reminder_mode.findData(self.preferences['reminder_mode']))
        self.test_reminder_button = self.button('测试提醒', lambda: self.notify('测试提醒：检测到人员走动'))
        self.row(page, '提醒方式', self.reminder_mode, self.test_reminder_button)
        page.addWidget(self.label('两种方式均保持静音，不抢占焦点。'))
        page.addWidget(self.label('头部朝向仅供参考，不能确认阅读行为；遮挡或视野外可能漏检。'))
        page.addStretch()
        page = self.settings_pages['常规']
        page.addWidget(self.label('启动与快捷键', 'sectionTitle'))
        self.auto_start = SettingsSwitch('开机自启')
        self.auto_start.setChecked(self.preferences['auto_start'])
        self.auto_start.clicked.connect(self.change_auto_start)
        self.row(page, '开机自启', self.label('登录 Windows 后自动运行 BehindWatch。'), self.auto_start)
        self.monitor_hotkey_choice = SettingsComboBox()
        add_item(self.monitor_hotkey_choice, '不启用', '')
        for hotkey in MONITOR_HOTKEYS:
            self.monitor_hotkey_choice.addItem(hotkey, hotkey)
        self.monitor_hotkey_choice.setCurrentIndex(
            self.monitor_hotkey_choice.findData(self.preferences['monitor_hotkey']))
        self.monitor_hotkey_choice.currentIndexChanged.connect(self.change_monitor_hotkey)
        self.row(page, '暂停监测快捷键', self.label('按组合键暂停监测；开启监测后仍需手动选择本人。'),
                 self.monitor_hotkey_choice)
        page.addWidget(self.label('外观', 'sectionTitle'))
        page.addWidget(self.label('调整主题与面板外观，修改立即应用并保存。'))
        appearance_card = QFrame()
        appearance_card.setObjectName('settingsSection')
        form = QFormLayout(appearance_card)
        form.setContentsMargins(18, 14, 18, 14)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        self.language_choice = SettingsComboBox()
        for key, title in LANGUAGES:
            if key == 'system':
                add_item(self.language_choice, title, key)
            else:
                self.language_choice.addItem(title, key)
        self.language_choice.setCurrentIndex(self.language_choice.findData(self.preferences['language']))
        self.language_choice.currentIndexChanged.connect(self.change_language)
        form.addRow('Language / 语言', self.language_choice)
        self.theme_choice = SettingsComboBox()
        for key, title in (('system', '跟随系统'), ('light', '浅色'), ('dark', '深色')):
            add_item(self.theme_choice, title, key)
        self.theme_choice.setCurrentIndex(self.theme_choice.findData(self.preferences['theme']))
        self.theme_choice.currentIndexChanged.connect(self.change_theme)
        form.addRow(self.label('外观主题', ''), self.theme_choice)
        page.addWidget(appearance_card)
        page.addStretch()

        page = self.settings_pages['更新与关于']
        page.addWidget(self.label('管理版本更新，查看项目主页与反馈入口。'))
        update_card = QFrame()
        update_card.setObjectName('settingsSection')
        update_layout = QVBoxLayout(update_card)
        update_layout.setContentsMargins(18, 14, 18, 14)
        update_layout.setSpacing(10)
        update_layout.addWidget(self.label('软件更新', 'sectionTitle'))
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        form.addRow(self.label('当前版本', ''), self.label(APP_VERSION or '开发版本', ''))
        self.auto_update = SettingsSwitch('自动检查更新')
        self.auto_update.setChecked(self.preferences['auto_update'])
        bind_text(self.auto_update, '每天检查一次正式版本', method='setToolTip')
        self.auto_update.clicked.connect(self.change_auto_update)
        form.addRow(self.label('自动检查', ''), self.auto_update)
        self.update_channel = SettingsComboBox()
        add_item(self.update_channel, '正式版', 'stable')
        form.addRow(self.label('更新通道', ''), self.update_channel)
        self.update_status = self.label('尚未检查更新')
        form.addRow(self.label('检查状态', ''), self.update_status)
        update_layout.addLayout(form)
        self.release_notes = QPlainTextEdit()
        self.release_notes.setReadOnly(True)
        self.release_notes.setMinimumHeight(110)
        self.release_notes.hide()
        update_layout.addWidget(self.release_notes)
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        self.check_button = self.button('检查更新', self.check_updates)
        actions.addWidget(self.check_button)
        self.download_button = self.button('下载并安装', self.install_update)
        self.download_button.setEnabled(False)
        actions.addWidget(self.download_button)
        actions.addWidget(self.button('打开下载页', self.open_download))
        actions.addWidget(self.button('GitHub 项目主页', lambda: QDesktopServices.openUrl(QUrl('https://github.com/zensoku142/BehindWatch'))))
        actions.addStretch()
        update_layout.addLayout(actions)
        update_layout.addWidget(self.label('安装版可校验并安装正式版本；源码版请使用下载页。'))
        page.addWidget(update_card)
        page.addStretch()

    def paintEvent(self, event):
        tokens = current_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(tokens.border), 1))
        painter.setBrush(QColor(tokens.window))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 18, 18)

    def resizeEvent(self, event):
        self.resize_grip.move(self.width()-22, self.height()-22)
        self.resize_grip.raise_()
        if hasattr(self, 'settings_open'):
            self.settings_save_status.setVisible(self.settings_open and self.width() >= 720)
        super().resizeEvent(event)
        # 最大化、最小化的临时尺寸不能覆盖用户调整的普通窗口尺寸；自检不写偏好。
        if (hasattr(self, 'size_save_timer') and not self.isMaximized() and not self.isMinimized()
                and '--smoke-test' not in sys.argv):
            size = [self.width(), self.height()]
            if size != self.preferences.get('window_size', [760, 600]):
                self.preferences['window_size'] = size
                self.size_save_timer.start()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if self.windowHandle():
                self.windowHandle().startSystemMove()
        return super().eventFilter(watched, event)

    def refresh_theme(self, *_):
        t = current_theme()
        self.setStyleSheet(f'''
            QWidget#settingsBody {{ background: {t.window}; }}
            QComboBox#headerProviderCombo {{ background: transparent; border: 0; }}
            QSlider::groove:horizontal {{ height: 4px; background: {t.disabled}; border-radius: 2px; }}
            QSlider::handle:horizontal {{ width: 12px; margin: -5px 0; border-radius: 3px; background: {t.border}; }}
            QSlider::handle:horizontal:focus {{ background: {t.accent}; }}
        ''')
        self.brand.setPixmap(app_icon(28).pixmap(28, 28))
        for button in (self.light_theme_button, self.dark_theme_button):
            selected = button.property('themeValue') == self.theme.resolved
            button.setChecked(selected)
            button.setProperty('selected', selected)
            button.style().unpolish(button)
            button.style().polish(button)
        blocker = QSignalBlocker(self.theme_choice)
        self.theme_choice.setCurrentIndex(self.theme_choice.findData(self.theme.mode))
        del blocker
        for button in self.findChildren(QToolButton):
            name = button.property('iconName')
            if name:
                button.setIcon(fluent_icon(name))
        for widget in self.findChildren(QWidget):
            widget.update()
        self.update()

    def refresh_language(self, *_):
        self.canvas.update()
        self.tabs.update()

    def connect_settings_autosave(self):
        for combo in (self.camera, self.camera_mode, self.presence_mode, self.reminder_mode):
            combo.currentIndexChanged.connect(self.schedule_settings_save)
        for control in (self.idle_threshold, self.recheck_interval, self.entry_alpha, self.exit_alpha):
            control.valueChanged.connect(self.schedule_settings_save)
        for switch in (self.lock_enabled, self.auto_hide, self.hide_browser_top,
                       self.hide_browser_scrollbar, self.mouse_opacity, self.close_window_on_exit):
            switch.clicked.connect(self.schedule_settings_save)

    def schedule_settings_save(self, *_):
        if '--smoke-test' not in sys.argv:
            self.settings_save_timer.start()

    def save_preferences(self):
        self.settings_save_timer.stop()
        self.preferences.update(camera_mode=self.camera_mode.currentData(),
                                idle_threshold=self.idle_threshold.value(),
                                recheck_interval=self.recheck_interval.value(),
                                lock_enabled=self.lock_enabled.isChecked(),
                                presence_mode=self.presence_mode.currentData(),
                                reminder_mode=self.reminder_mode.currentData(),
                                auto_hide=self.auto_hide.isChecked(),
                                hide_browser_top=self.hide_browser_top.isChecked(),
                                hide_browser_scrollbar=self.hide_browser_scrollbar.isChecked(),
                                mouse_opacity=self.mouse_opacity.isChecked(),
                                close_window_on_exit=self.close_window_on_exit.isChecked(),
                                entry_alpha=self.entry_alpha.value(), exit_alpha=self.exit_alpha.value())
        index = self.camera.currentIndex()
        if 0 <= index < len(self.cameras):
            self.preferences['camera_name'] = self.cameras[index].name
        try:
            save_preferences(self.preferences)
            bind_text(self.preference_status, '设置已自动保存；监测仍需手动启动并选择本人。')
            bind_text(self.settings_save_status, '已自动保存')
            bind_text(self.settings_save_status, '设置已自动保存；监测仍需手动启动并选择本人。', method='setToolTip')
            self.preference_status.hide()
            return True
        except OSError as exc:
            bind_text(self.preference_status, lambda error=str(exc): tr('偏好保存失败：{error}', error=error))
            bind_text(self.settings_save_status, '未保存')
            bind_text(self.settings_save_status, lambda error=str(exc): tr('偏好保存失败：{error}', error=error), method='setToolTip')
            self.preference_status.setParent(self.settings_page)
            if self.settings_page.layout().indexOf(self.preference_status) < 0:
                self.settings_page.layout().addWidget(self.preference_status)
            self.preference_status.show()
            return False

    def change_theme(self):
        self.set_theme_mode(self.theme_choice.currentData())

    def set_theme_mode(self, mode):
        self.theme.set_mode(mode)
        self.preferences['theme'] = mode
        self.save_preferences()

    def refresh_current_page(self):
        if self.settings_open and self.current_settings_page == '更新与关于':
            self.check_updates()
        else:
            self.refresh_windows()
            if self.process is None:
                self.refresh_cameras()

    def change_language(self):
        preference = self.language_choice.currentData()
        self.language.set_language(preference)
        self.preferences['language'] = preference
        self.save_preferences()

    def change_auto_update(self):
        self.preferences['auto_update'] = self.auto_update.isChecked()
        self.save_preferences()
        self.maybe_check_updates()

    def change_monitor_hotkey(self):
        selected = self.monitor_hotkey_choice.currentData()
        previous = self.preferences['monitor_hotkey']
        if not self.set_monitor_hotkey(selected):
            with QSignalBlocker(self.monitor_hotkey_choice):
                self.monitor_hotkey_choice.setCurrentIndex(self.monitor_hotkey_choice.findData(previous))
            bind_text(self.preference_status, '快捷键不可用，可能已被其他程序占用。')
            self.preference_status.show()
            return
        self.preferences['monitor_hotkey'] = selected
        if not self.save_preferences():
            self.preferences['monitor_hotkey'] = previous
            self.set_monitor_hotkey(previous)
            with QSignalBlocker(self.monitor_hotkey_choice):
                self.monitor_hotkey_choice.setCurrentIndex(self.monitor_hotkey_choice.findData(previous))

    def change_auto_start(self):
        enabled = self.auto_start.isChecked()
        try:
            sync_autostart(enabled)
        except (OSError, KeyError, subprocess.SubprocessError) as exc:
            self.auto_start.setChecked(not enabled)
            bind_text(self.preference_status, lambda error=str(exc): tr('开机自启设置失败：{error}', error=error))
            if self.settings_page.layout().indexOf(self.preference_status) < 0:
                self.settings_page.layout().addWidget(self.preference_status)
            self.preference_status.show()
            return
        self.preferences['auto_start'] = enabled
        if not self.save_preferences():
            self.preferences['auto_start'] = not enabled
            self.auto_start.setChecked(not enabled)
            try:
                sync_autostart(not enabled)
            except (OSError, KeyError, subprocess.SubprocessError) as exc:
                bind_text(self.preference_status, lambda error=str(exc): tr('开机自启设置失败：{error}', error=error))

    def maybe_check_updates(self):
        if not self.closed and self.preferences['auto_update'] and time.time()-self.preferences['last_check'] >= CHECK_INTERVAL:
            self.check_updates()

    def refresh_news(self):
        if self.closed or self.news_fetching or self.tray is None:
            return
        self.news_fetching = True
        results = self.news_results

        # 网络抓取只写入队列，界面线程在 poll 中更新缓存；失败后下个整点再试。
        def fetch():
            try:
                results.put(fetch_headlines())
            except Exception:
                results.put([])
        threading.Thread(target=fetch, daemon=True).start()

    def check_updates(self):
        if self.closed or self.update_busy:
            return
        self.update_busy = True
        self.check_button.setEnabled(False)
        bind_text(self.update_status, '正在检查更新…')
        # daemon 线程仅持有结果队列；关闭窗口时不等待网络，也不回调已销毁的 Qt 对象。
        results = self.update_results
        def check():
            try:
                results.put((check_release(), None))
            except Exception as exc:
                results.put((None, str(exc)))
        threading.Thread(target=check, daemon=True).start()

    def finish_update(self, release, error):
        self.update_busy = False
        self.check_button.setEnabled(True)
        self.preferences['last_check'] = time.time()
        self.save_preferences()
        self.latest_release = release
        self.download_button.setEnabled(bool(release and release['available'] and release.get('installable') and APP_VERSION))
        self.release_notes.setVisible(bool(release))
        self.release_notes.setPlainText(release['notes'] if release else '')
        if error:
            bind_text(self.update_status, lambda: tr('检查失败：{error}', error=error))
        elif release is None:
            bind_text(self.update_status, '暂无正式版本')
        elif release['available']:
            bind_text(self.update_status, lambda: tr('可用版本：{version}', version=release['version']))
        else:
            bind_text(self.update_status, '已是最新版本')

    def open_download(self):
        QDesktopServices.openUrl(QUrl(self.latest_release['url'] if self.latest_release else RELEASES_URL))

    def install_update(self):
        if self.update_busy or not self.latest_release or not self.download_button.isEnabled():
            return
        self.update_busy = True
        self.download_button.setEnabled(False)
        bind_text(self.update_status, '正在下载并校验安装包…')
        release = self.latest_release
        results = self.install_results

        # 下载在后台完成；主线程只处理结果，避免 Qt 对象跨线程访问。
        def download():
            try:
                results.put((download_installer(release), None))
            except Exception as exc:
                results.put((None, str(exc)))
        threading.Thread(target=download, daemon=True).start()

    def show_settings(self, page=None):
        self.select_settings_page(page or self.current_settings_page)
        self.settings_open = True
        self.stack.setCurrentWidget(self.settings_page)
        self.quick_window_choice.hide()
        self.back_button.show()
        self.settings_button.hide()
        self.settings_save_status.setVisible(self.width() >= 720)
        self.tabs.setFocus()

    def select_settings_page(self, name):
        # 旧入口名称继续指向同一页，避免内部快捷入口因页签改名失效。
        name = {'监测': '摄像头', '监测与提醒': '摄像头', '监测与锁屏': '摄像头',
                '锁屏与运行': '锁屏与本人', '提醒与记录': '提醒', '提醒与启动': '提醒',
                '最近事件': '提醒', '通用': '常规', '外观': '常规'}.get(name, name)
        self.current_settings_page = name
        self.tabs.setCurrentIndex(self.page_names.index(name))

    def close_settings(self):
        self.settings_open = False
        self.stack.setCurrentWidget(self.main_page)
        self.quick_window_choice.show()
        self.back_button.hide()
        self.settings_button.show()
        self.settings_save_status.hide()
        self.settings_button.setFocus()
        self.render()

    def show_opacity_settings(self):
        self.show_settings('窗口保护')
        self.entry_alpha.setFocus()

    def set_window_status(self, text, tone='muted'):
        bind_text(self.window_status, text)
        self.window_status.setProperty('tone', tone)
        self.window_status.style().unpolish(self.window_status)
        self.window_status.style().polish(self.window_status)

    def set_status(self, title, detail='', tone='success'):
        bind_text(self.status, title)
        self.status_dot.setProperty('tone', tone)
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)
        bind_text(self.detail, detail)
        routine = title in ('尚未开始监测', '需要本人校准', '请重新选择本人', '监测运行中', '正在启动', '正在暂停', '已暂停') or title.startswith('检测到 ')
        self.detail.setVisible(bool(detail) and not routine)

    def render(self):
        self.owner_row.setVisible(bool(self.last_frame and self.last_frame.get('owner') is None))
        self.owner_select_button.setEnabled(bool(self.last_frame))
        bind_text(self.owner_status, '本人已确认' if self.last_frame and self.last_frame.get('owner') is not None else '尚未选择本人')
        if self.selection_mode is None:
            bind_text(self.owner_select_button, '重新选择本人' if self.last_frame and self.last_frame.get('owner') is not None else '选择本人')
        # 隐藏提示时保留占位，避免切换画面导致预览和侧栏跳动。
        self.selection_hint.setVisible(not self.canvas.preview_hidden)
        if self.selection_mode is None:
            bind_text(self.selection_hint, '点同事框直接忽略 · 选择本人请点按钮' if not self.last_frame or self.last_frame.get('owner') is None
                      else '点击同事框直接忽略或取消忽略')
        # 后台或设置页不解码 JPEG；仍保留最新监测状态，返回面板时再恢复画面。
        self.canvas.set_frame(self.last_frame if self.canvas.isVisible() and not self.canvas.preview_hidden else None)

    def toggle_preview(self):
        # 只遮挡显示，不停止采集或保护；隐藏时退出选择模式，避免盲点误选。
        if not self.canvas.preview_hidden and self.selection_mode is not None:
            self.set_selection_mode(self.selection_mode)
        self.canvas.preview_hidden = not self.canvas.preview_hidden
        bind_text(self.preview_toggle, '显示画面' if self.canvas.preview_hidden else '隐藏画面')
        self.render()

    def set_selection_mode(self, mode):
        if mode == 'owner' and self.canvas.preview_hidden:
            self.toggle_preview()
        # Owner selection is explicit; ordinary preview clicks only toggle a coworker's ignore state.
        self.selection_mode = None if self.selection_mode == mode else mode
        self.canvas.selection_mode = self.selection_mode
        self.owner_select_button.setChecked(self.selection_mode == 'owner')
        bind_text(self.owner_select_button, '取消选择本人' if self.selection_mode == 'owner' else '选择本人')
        if self.selection_mode is None:
            self.render()
        else:
            bind_text(self.selection_hint, '请点击预览中的自己')

    def toggle_ignored_person(self, identity):
        if not self.last_frame or not self.process or self.stopping:
            return
        if identity == self.last_frame['owner']:
            return
        self.commands.put(('toggle_ignore', identity))

    def select_from_list(self):
        identity = self.owner_choice.currentData()
        if identity is not None:
            self.calibrate(identity)

    def show_panel(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.render()

    def hide_to_tray(self):
        self.close_settings()
        if self.tray and self.tray.isVisible():
            self.hide()
        else:
            self.showMinimized()

    def setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip('BehindWatch')
        menu = QMenu(self)
        for title, callback in (('打开监测面板', self.show_panel), ('暂停监测', self.stop),
                                ('恢复窗口并关闭自动隐藏', self.restore_window), ('退出', self.quit)):
            action = menu.addAction('')
            bind_text(action, title)
            action.triggered.connect(lambda checked=False, cb=callback: cb())
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_panel() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()
        try:
            register_news_app()
            self.news_identity_ready = True
        except OSError:
            self.news_identity_ready = False

    def notify(self, message):
        self.dismiss_toast()
        is_danger = '看向屏幕' in message
        # 屏幕上的文案只传达约定信号；真实事件仅保留在应用内，避免旁人看到监测内容。
        discreet_message = '有一项后台任务需要关注' if is_danger else '后台状态已更新'
        system_sent = False
        if self.reminder_mode.currentData() == 'text' and self.tray and self.tray.isVisible() and QSystemTrayIcon.supportsMessages():
            notifications_enabled = True
            if self.news_identity_ready:
                try:
                    # Windows 可在应用级关闭通知；Qt 的 supportsMessages 仍会返回 True。
                    notifications_enabled = news_notifications_enabled()
                except Exception:
                    notifications_enabled = False
            if notifications_enabled:
                if self.news_headlines and self.news_identity_ready:
                    title, url = self.news_headlines[self.news_index % len(self.news_headlines)]
                    self.news_index += 1
                    try:
                        # 每条 WinRT 通知独立绑定正文链接，通知中心里旧消息也能打开对应文章。
                        send_news_toast('中国新闻网 · 国内新闻', title, on_click=url,
                                        audio={'silent': 'true'}, app_id=NEWS_APP_ID)
                        system_sent = True
                    except Exception:
                        pass
                if not system_sent:
                    # 抓取或 WinRT 不可用时保持中性提醒，不把过期新闻冒充当前热点。
                    self.tray.showMessage(tr('系统状态'), tr(discreet_message), QSystemTrayIcon.MessageIcon.NoIcon, 7000)
                    system_sent = True
        # 系统通知由 Windows 放在主屏；副屏补提示点。系统通知不可用时每块屏幕都显示。
        for screen in QApplication.screens():
            if system_sent and screen == QApplication.primaryScreen():
                continue
            toast = QWidget(self, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
            # 静音提示不激活工作窗口；定时器跟随提示窗口销毁，旧提示不能关闭新提示。
            toast.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            toast.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            area = screen.availableGeometry()
            toast.resize(28, 28)
            dot = QPushButton(toast)
            dot.setGeometry(7, 7, 14, 14)
            color = '#f38383' if is_danger else '#ffd18a'
            dot.setStyleSheet(f'min-height:0; padding:0; border:1px solid #17252d; border-radius:7px; background:{color};')
            bind_text(dot, '系统状态', method='setAccessibleName')
            toast.move(area.right()-44, area.bottom()-44)
            timer = QTimer(toast)
            timer.setSingleShot(True)
            timer.timeout.connect(self.dismiss_toast)
            timer.start(7000)
            self.toasts.append(toast)
            toast.show()
        self.toast = self.toasts[0] if self.toasts else None

    def show_events(self):
        self.dismiss_toast()
        self.show_panel()
        self.show_settings('提醒与启动')

    def dismiss_toast(self):
        for toast in self.toasts:
            toast.close()
            toast.deleteLater()
        self.toasts.clear()
        self.toast = None

    def quit(self):
        self.lock_warning.hide()
        self._quitting = True
        try:
            self.close()
        finally:
            self._quitting = False

    def closeEvent(self, event):
        if self.closed:
            event.accept()
            return
        # 拖动后立即关闭时，不能等事件循环结束后再写入尺寸。
        if self.size_save_timer.isActive():
            self.size_save_timer.stop()
            self.save_preferences()
        if not self._quitting:
            # 系统关闭事件与标题栏 X 一样只收起；托盘“退出”和 Esc 才执行清理。
            event.ignore()
            self.hide_to_tray()
            return
        # 退出清理会临时关闭保护开关；先保存用户的选择，避免覆盖下次启动的设置。
        if self.settings_save_timer.isActive():
            self.save_preferences()
        self.mouse_opacity.setChecked(False)
        try:
            self.window_guard.restore_crop()
            self.window_guard.restore_opacity()
        except OSError as exc:
            self.set_window_status(str(exc), 'warning')
            self.show_panel()
            self.show_settings('窗口保护')
            event.ignore()
            return
        if not self.restore_window():
            # 恢复失败时保留控制面板，避免退出后丢失唯一的恢复入口。
            event.ignore()
            return
        try:
            # 先还原窗口，确保应用的保存确认可见；自检退出不能关闭用户窗口。
            if self.close_window_on_exit.isChecked() and '--smoke-test' not in sys.argv:
                self.window_guard.close_selected()
        except OSError as exc:
            self.set_window_status(str(exc), 'warning')
            self.show_panel()
            self.show_settings('窗口保护')
            event.ignore()
            return
        self.auto_resume = False
        if self.process is not None:
            self.commands.put(('stop', None))
            self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=1)
            self.cleanup()
        self.closed = True
        if self.window_guard.browser_crop is not None:
            self.window_guard.browser_crop.close()
        hwnd = wintypes.HWND(int(self.winId()))
        if self.session_notifications:
            self._wts.WTSUnRegisterSessionNotification(hwnd)
        if self.display_notification:
            self._user32.UnregisterPowerSettingNotification(self.display_notification)
        if self.monitor_hotkey:
            self._user32.UnregisterHotKey(wintypes.HWND(self.monitor_hotkey_hwnd), MONITOR_HOTKEY_ID)
            self.monitor_hotkey = ''
            self.monitor_hotkey_hwnd = None
        self.timer.stop()
        self.update_timer.stop()
        self.news_timer.stop()
        self.dismiss_toast()
        if self.tray:
            self.tray.hide()
        event.accept()


    def toggle_opacity(self):
        if self.mouse_opacity.isChecked():
            if not self.window_guard.valid():
                self.set_window_status('鼠标透明度已开启，等待选择目标窗口。', 'warning')
                return
            self.update_window_opacity()
            if self.mouse_opacity.isChecked():
                self.set_window_status('鼠标透明度已启用；可与人员自动隐藏同时使用。', 'success')
        else:
            try:
                self.window_guard.restore_opacity()
                self.set_window_status('鼠标透明度已关闭，原透明度已还原。', 'muted')
            except OSError as exc:
                self.set_window_status(str(exc), 'warning')

    def update_browser_crop(self):
        try:
            message = self.window_guard.update_crop(self.hide_browser_top.isChecked(),
                                                   self.hide_browser_scrollbar.isChecked())
        except (OSError, ImportError) as exc:
            self.hide_browser_top.setChecked(False)
            self.hide_browser_scrollbar.setChecked(False)
            message = str(exc)
            try:
                self.window_guard.restore_crop()
            except OSError as restore_error:
                message += ' ' + str(restore_error)
        bind_text(self.browser_crop_status, message)

    def refresh_windows(self):
        try:
            self.windows = self.window_guard.windows()
            selected = self.window_guard.selected
            # 隐藏的目标不在可见窗口枚举里，保留它才能继续恢复和查看选择状态。
            if selected and self.window_guard.valid() and not any(w.hwnd == selected.hwnd for w in self.windows):
                self.windows.insert(0, selected)
            index = next((i + 1 for i, w in enumerate(self.windows) if selected and w.hwnd == selected.hwnd), -1)
            for combo in (self.window_choice, self.quick_window_choice):
                blocker = QSignalBlocker(combo)
                combo.clear()
                add_item(combo, '取消选择')
                combo.addItems([f'{w.title} [0x{w.hwnd:X}]' for w in self.windows])
                combo.setCurrentIndex(index)
                del blocker
            if selected is None and self.preferences.get('target_window'):
                title, class_name = self.preferences['target_window']
                matches = [i for i, window in enumerate(self.windows)
                           if (window.title, window.class_name) == (title, class_name)]
                # 同名窗口不能凭标题猜测目标，避免把保护作用到错误的程序。
                if len(matches) == 1:
                    self.select_window(matches[0] + 1)
        except OSError as exc:
            self.set_window_status(str(exc), 'warning')

    def select_window(self, index=None):
        index = self.window_choice.currentIndex() if index is None else index
        if index == 0:
            try:
                # 清除目标前先恢复显隐和透明度，避免取消后失去恢复入口。
                self.window_guard.select(None)
                self.update_browser_crop()
                self.auto_hide.setChecked(False)
                self.recovery_button.hide()
                for combo in (self.window_choice, self.quick_window_choice):
                    combo.setCurrentIndex(-1)
                self.set_window_status('已取消选择目标窗口。')
                self.preferences.pop('target_window', None)
                self.schedule_settings_save()
            except OSError as exc:
                self.set_window_status(str(exc), 'warning')
                self.refresh_windows()
            return
        # 首项用于取消选择，窗口列表索引比下拉框索引小一位。
        window_index = index - 1
        if not 0 <= window_index < len(self.windows):
            return
        # 尚未选目标时保留预先开启的意图；切换已有目标仍关闭自动隐藏。
        waiting = self.auto_hide.isChecked() and self.window_guard.selected is None
        self.auto_hide.setChecked(waiting)
        try:
            self.window_guard.select(self.windows[window_index])
            for combo in (self.window_choice, self.quick_window_choice):
                combo.setCurrentIndex(index)
            self.set_window_status('已选择窗口，勾选上方开关启用。')
            self.update_window_opacity()
            self.update_browser_crop()
            if waiting:
                self.toggle_window_guard()
            self.preferences['target_window'] = [self.windows[window_index].title,
                                                 getattr(self.windows[window_index], 'class_name', '')]
            self.schedule_settings_save()
        except OSError as exc:
            self.set_window_status(str(exc), 'warning')
            self.refresh_windows()

    def update_window_opacity(self):
        if not self.mouse_opacity.isChecked():
            return
        # 未选目标或旧目标已关闭时保留开启意图，选定新窗口后首次应用。
        if not self.window_guard.valid():
            return
        try:
            self.window_guard.update_opacity(self.entry_alpha.value(), self.exit_alpha.value())
        except OSError as exc:
            self.mouse_opacity.setChecked(False)
            message = str(exc)
            # 设置失败可能发生在添加透明样式之后；回滚，避免留下半完成的修改。
            try:
                self.window_guard.restore_opacity()
            except OSError as restore_error:
                message += ' ' + str(restore_error)
            self.set_window_status(message, 'warning')

    def toggle_window_guard(self):
        if not self.auto_hide.isChecked():
            self.restore_window()
        elif not self.window_guard.valid():
            self.set_window_status('自动隐藏已开启，等待选择目标窗口。', 'warning')
        else:
            self.set_window_status('已开启；开始监测并校准本人后生效。', 'success')
            self.protect_window()

    def protect_window(self):
        frame = self.last_frame
        # 使用当前画面而非有冷却时间的提醒事件，确保中途开启也能立即保护。
        if (not self.auto_hide.isChecked() or self.stopping or self.failed or not frame
                or time.monotonic()-frame['at'] > 1 or frame['owner'] is None):
            return
        # 等待配置时不调用隐藏接口，否则它会把未选窗口当成失败并关闭开关。
        if self.window_guard.selected is None:
            return
        if any(t['id'] != frame['owner'] and t.get('moving') for t in frame['tracks']):
            try:
                if self.window_guard.hide():
                    self.set_window_status('已请求隐藏；可通过主界面或托盘恢复。', 'warning')
                    self.recovery_button.show()
            except OSError as exc:
                self.auto_hide.setChecked(False)
                self.set_window_status(str(exc), 'warning')

    def restore_window(self):
        # 手动恢复同时关闭保护，避免下一帧立即再次隐藏。
        self.auto_hide.setChecked(False)
        try:
            self.window_guard.restore()
        except OSError as exc:
            self.set_window_status(str(exc), 'warning')
            # 恢复入口可能来自主界面或托盘，错误不能只留在已隐藏的设置页。
            self.show_panel()
            self.show_settings('窗口保护')
            return False
        self.set_window_status('自动隐藏已关闭；已请求恢复本次隐藏的窗口。', 'muted')
        self.recovery_button.hide()
        if not self._quitting:
            self.schedule_settings_save()
        return True

    def refresh_cameras(self):
        try:
            import cv2
            from cv2_enumerate_cameras import enumerate_cameras
            previous = self.camera.currentIndex()
            selected_name = (self.cameras[previous].name if 0 <= previous < len(self.cameras)
                             else self.preferences['camera_name'])
            self.cameras = list(enumerate_cameras(cv2.CAP_DSHOW))
            with QSignalBlocker(self.camera):
                self.camera.clear()
                self.camera.addItems([f'{c.index} · {c.name}' for c in self.cameras])
                if self.cameras:
                    index = next((i for i, camera in enumerate(self.cameras) if camera.name == selected_name), 0)
                    self.camera.setCurrentIndex(index)
            if not self.cameras:
                self.set_status('未发现摄像头', '请连接摄像头，在设置中刷新设备。', 'warning')
        except ImportError as exc:
            self.cameras = []
            self.set_status('运行依赖缺失', f'{exc}。请运行 launch.cmd 修复环境。', 'warning')
        except Exception as exc:
            self.cameras = []
            self.set_status('设备枚举失败', str(exc), 'warning')

    def start(self):
        if self.process is not None:
            return
        if self.session_locked or self.display_off:
            return
        if self.camera.currentIndex() < 0 or not self.cameras:
            self.set_status('请选择摄像头', '在设置中连接并选择摄像头后再启动。', 'warning')
            self.show_settings('监测与提醒')
            return
        self.commands, self.frames, self.events = mp.Queue(), mp.Queue(maxsize=1), mp.Queue()
        self.failed = self.stopping = False
        self.last_frame = None
        self.last_received = time.monotonic()
        self.started = self.last_received
        idle_camera = self.camera_mode.currentData() == 'idle'
        self.camera_active = not idle_camera
        self.camera_pending = False
        self.presence_since = None
        self.recheck_at = 0
        self.lock_decision = LockDecision()
        self.process = mp.Process(target=worker, args=(self.cameras[self.camera.currentIndex()].index, self.commands, self.frames, self.events, idle_camera), daemon=True)
        self.process.start()
        self.start_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.camera.setEnabled(False)
        self.camera_mode.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.start_button.hide()
        self.stop_button.show()
        self.set_status('正在启动', '加载本地模型并连接摄像头…', 'warning')

    def stop(self, *, auto=False):
        self.lock_warning.hide()
        self.lock_decision.reset()
        if not auto:
            self.auto_resume = False
        if self.process is not None and not self.stopping:
            self.stopping = True
            self.commands.put(('stop', None))
            self.stop_at = time.monotonic()
            self.set_status('正在暂停', '正在释放摄像头…', 'warning')
            self.stop_button.setEnabled(False)
        self.last_frame = None
        self.render()

    def cleanup(self):
        if self.process is not None:
            self.process.join(timeout=0.1)
            self.process.close()
            self.process = None
            for q in (self.commands, self.frames, self.events):
                q.close()
                q.cancel_join_thread()
        self.last_frame = None
        self.owner_choice.clear()
        self.selection_mode = None
        self.canvas.selection_mode = None
        self.owner_select_button.setChecked(False)
        bind_text(self.owner_select_button, '选择本人')
        self.owner_choice._language_bindings = {}
        self.start_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.camera.setEnabled(True)
        self.camera_mode.setEnabled(True)
        self.lock_warning.hide()
        self.stop_button.setEnabled(False)
        self.stop_button.hide()
        self.start_button.show()
        bind_text(self.meta, '摄像头已释放 · 画面不保留')
        if not self.failed:
            self.set_status('已暂停', '摄像头已释放，重新启动后需要校准。', 'warning')
        self.render()
        if self.failed:
            self.auto_resume = False
        elif self.auto_resume and not self.session_locked and not self.display_off and not self.closed:
            self.auto_resume = False
            self.start()

    def calibrate(self, identity):
        if self.process and not self.stopping and self.last_frame and time.monotonic()-self.last_frame['at'] < 1:
            self.commands.put(('owner', identity))
            self.set_selection_mode(None)

    def register_face(self):
        if not self.process or self.stopping or not self.last_frame or self.last_frame['owner'] is None:
            bind_text(self.registration_status, '请先开始监测并在预览中选择本人。')
            return
        self.commands.put(('register', None))
        bind_text(self.registration_status, '正在采集本人面容，请正对摄像头…')

    def delete_face(self):
        delete_template()
        if self.process and not self.stopping:
            self.commands.put(('delete_identity', None))
        self.face_registered = False
        self.delete_face_button.setEnabled(False)
        bind_text(self.registration_status, '尚未注册本人面容。')

    def set_camera_active(self, active):
        if self.camera_active == active or self.process is None or self.stopping:
            return
        self.camera_active = active
        self.camera_pending = active
        self.commands.put(('camera', active))
        self.last_frame = None
        self.presence_since = None
        self.lock_decision.reset()
        self.lock_warning.hide()
        self.render()
        if active:
            self.last_received = time.monotonic()
        else:
            bind_text(self.meta, '摄像头已释放 · 画面不保留')

    def check_seat_lock(self, now, idle):
        frame = self.last_frame
        safe = (self.lock_enabled.isChecked() and self.session_notifications and self.display_notification
                and not self.session_locked and not self.display_off and not self.failed and not self.stopping
                and self.camera_active and not self.camera_pending and frame is not None
                and now - frame['at'] <= 1 and
                ('owner_present' in frame if self.presence_mode.currentData() == 'owner' else 'face_count' in frame) and
                (self.presence_mode.currentData() != 'owner' or self.face_registered))
        present = None if not safe else (frame.get('owner_present', False) if self.presence_mode.currentData() == 'owner'
                                         else frame.get('face_count', 0) > 0)
        remaining = self.lock_decision.update(now, present, idle, self.started, safe)
        if remaining is None:
            self.lock_warning.hide()
        elif remaining:
            self.lock_warning.setText(tr('即将锁屏 · {seconds} 秒', seconds=remaining))
            self.lock_warning.adjustSize()
            screen = QApplication.primaryScreen()
            if screen:
                rect = screen.availableGeometry()
                self.lock_warning.move(rect.center().x() - self.lock_warning.width() // 2, rect.top() + 24)
                self.lock_warning.show()
        else:
            # 再读一次输入状态，避免倒计时最后一次轮询与用户操作同时发生。
            fresh_idle = input_idle_seconds()
            if fresh_idle is not None and fresh_idle >= 60 and safe and not self.session_locked and not self.display_off:
                self.lock_decision.locked = lock_workstation()
            self.lock_warning.hide()
            self.lock_decision.reset()

    def check_idle_camera(self, now, idle):
        if self.camera_mode.currentData() != 'idle' or self.stopping or self.failed:
            return
        if idle is None or idle < self.idle_threshold.value():
            self.set_camera_active(False)
            self.recheck_at = 0
            return
        if not self.camera_active and now >= self.recheck_at:
            self.set_camera_active(True)
            return
        frame = self.last_frame
        if not self.camera_active or self.camera_pending or not frame or now - frame['at'] > 1:
            # A capture gap cannot count toward uninterrupted presence before releasing the device.
            self.presence_since = None
            return
        if self.camera_active:
            present = frame.get('owner_present', False) if self.presence_mode.currentData() == 'owner' else frame.get('face_count', 0) > 0
            if present:
                if self.presence_since is None:
                    self.presence_since = now
                elif now - self.presence_since >= 10:
                    self.recheck_at = now + self.recheck_interval.value()
                    self.set_camera_active(False)
            else:
                self.presence_since = None

    def poll(self):
        if self.closed:
            return
        try:
            headlines = self.news_results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.news_fetching = False
            self.news_headlines = headlines
            self.news_index = 0
        try:
            release, error = self.update_results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.finish_update(release, error)
        try:
            installer, error = self.install_results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.update_busy = False
            if error:
                bind_text(self.update_status, lambda: tr('安装失败：{error}', error=error))
                self.download_button.setEnabled(True)
            else:
                try:
                    launch_installer(installer)
                    self.quit()
                except Exception as exc:
                    bind_text(self.update_status, lambda: tr('安装失败：{error}', error=exc))
                    self.download_button.setEnabled(True)
        while True:
            try:
                action = self.ui_commands.get_nowait()
            except queue.Empty:
                break
            if action == 'show':
                self.show_panel()
                self.raise_()
            elif action == 'stop':
                self.stop()
            elif action == 'restore':
                self.restore_window()
            elif action == 'quit':
                self.quit()
                return
        self.update_window_opacity()
        # 透明样式可能重建浏览器背景；裁剪和 Mica 修正必须在透明度更新之后。
        if self.hide_browser_top.isChecked() or self.hide_browser_scrollbar.isChecked():
            self.update_browser_crop()
        if self.process is not None:
            while True:
                try:
                    kind, data = self.events.get_nowait()
                except queue.Empty:
                    break
                if kind == 'status' and not self.stopping:
                    bind_text(self.detail, data)
                elif kind == 'error':
                    self.failed = True
                    self.set_status('监测不可用', data, 'warning')
                    self.notify('监测已中断，请检查摄像头或模型。')
                elif kind == 'alert' and not self.stopping:
                    self.notify(f"{tr(data['message'])} · {tr('人员 #{id}', id=data['id'])}")
                elif kind == 'calibration' and not data:
                    self.set_status('请重新选择本人', '目标已离开画面。', 'warning')
                elif kind == 'identity':
                    self.face_registered = data
                    self.delete_face_button.setEnabled(data)
                    bind_text(self.registration_status, '已注册本人面容。' if data else '尚未注册本人面容。')
                elif kind == 'registration':
                    bind_text(self.registration_status, data)
                elif kind == 'camera':
                    self.camera_pending = False
            try:
                frame = self.frames.get_nowait()
            except queue.Empty:
                frame = None
            if frame and not self.stopping and not self.failed and self.camera_active:
                self.last_frame = frame
                self.last_received = frame['at']
                self.protect_window()
                tracks, owner = frame['tracks'], frame['owner']
                selected_id = self.owner_choice.currentData()
                self.owner_choice.clear()
                self.owner_choice._language_bindings = {}
                for track in tracks:
                    add_item(self.owner_choice, f"人员 #{track['id']}", track['id'])
                index = self.owner_choice.findData(selected_id)
                if index >= 0:
                    self.owner_choice.setCurrentIndex(index)
                if owner is None:
                    self.set_status('请先选择本人', '先点选择本人，再点自己的检测框；已注册可等待自动识别。', 'warning')
                elif frame.get('moving_count', 0):
                    self.set_status('检测到人员走动', '画面中有其他人员持续移动。', 'warning')
                else:
                    self.set_status('监测运行中', '固定位置的同事不会触发提醒。')
                bind_text(self.meta, f"{frame['fps']} 帧/秒  ·  镜像预览  ·  {len(tracks)} 个可见目标")
                self.render()
            now = time.monotonic()
            idle = input_idle_seconds()
            self.check_idle_camera(now, idle)
            self.check_seat_lock(now, idle)
            if self.stopping and now-self.stop_at > 3 and self.process.is_alive():
                # Drivers may block inside read(); terminate only this owned capture process.
                self.process.terminate()
            elif not self.stopping and self.camera_active and now-self.last_received > (30 if self.last_frame is None else 8):
                self.failed = True
                self.stop()
                self.set_status('监测已超时', '长时间未收到新画面，请重新启动。', 'warning')
                self.notify('监测超时，当前无法判断身后情况。')
            if not self.process.is_alive():
                if not self.failed and not self.stopping:
                    self.failed = True
                    self.set_status('监测异常退出', '检测进程已结束，请重新启动。', 'warning')
                self.cleanup()



if __name__ == '__main__':
    import sys
    mp.freeze_support()
    if '--smoke-test' in sys.argv:
        # 自检要验证本次启动，不能被已经运行的实例短路。
        application = QApplication(sys.argv)
        from scripts.smoke_runtime import verify_runtime
        verify_runtime()
        window = App()
        window.quit()
        sys.exit(0)
    from bootstrap import (acquire_single_instance, activation_requested, create_activation_event,
                           release_single_instance, signal_existing_instance)
    instance_handle = acquire_single_instance()
    if instance_handle is None:
        # 已隐藏的实例仍持有互斥量；重复启动时请求它显示面板，事件尚未就绪才提示。
        if not signal_existing_instance():
            message = startup_running_message('BehindWatch', load_preferences()['language'])
            ctypes.windll.user32.MessageBoxW(None, message, 'BehindWatch', 0x40)
        sys.exit(0)
    activation_handle = None
    try:
        activation_handle = create_activation_event()
        application = QApplication(sys.argv)
        # 与 TokenMeter 一样保留 Windows 原生 Qt 风格，包括圆角下拉菜单和选中指示。
        window = App()
        window.show()
        # Windows 事件可在界面初始化期间收到请求；由 GUI 线程轮询并操作窗口。
        activation_timer = QTimer(window)
        activation_timer.timeout.connect(lambda: window.show_panel() if activation_requested(activation_handle) else None)
        activation_timer.start(150)
        sys.exit(application.exec())
    finally:
        release_single_instance(activation_handle)
        release_single_instance(instance_handle)
