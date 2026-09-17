"""Persist user settings between launches."""
import json
import os
from pathlib import Path
import tempfile

HOTKEYS = {'', 'Ctrl+Alt+M', 'Ctrl+Alt+S', 'Ctrl+Shift+M', 'Alt+Shift+M'}
DEFAULTS = {'theme': 'dark', 'language': 'zh-cn', 'auto_start': False, 'auto_update': False,
            'last_check': 0, 'monitor_hotkey': '', 'camera_name': '', 'camera_mode': 'continuous',
            'idle_threshold': 20, 'recheck_interval': 60, 'lock_enabled': False,
            'presence_mode': 'any', 'reminder_mode': 'text', 'auto_hide': False,
            'hide_browser_top': False, 'hide_browser_scrollbar': False, 'mouse_opacity': False,
            'entry_alpha': 255, 'exit_alpha': 0, 'close_window_on_exit': True}
LANGUAGES = ('system', 'zh-cn', 'zh-tw', 'en', 'ja', 'ko')


def preferences_path():
    return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'BehindWatch' / 'preferences.json'


def validated(data):
    result = DEFAULTS.copy()
    if not isinstance(data, dict):
        return result
    if data.get('theme') in ('dark', 'light', 'system'):
        result['theme'] = data['theme']
    if data.get('language') in LANGUAGES:
        result['language'] = data['language']
    if isinstance(data.get('auto_update'), bool):
        result['auto_update'] = data['auto_update']
    if isinstance(data.get('auto_start'), bool):
        result['auto_start'] = data['auto_start']
    if isinstance(data.get('monitor_hotkey'), str) and data['monitor_hotkey'] in HOTKEYS:
        result['monitor_hotkey'] = data['monitor_hotkey']
    if isinstance(data.get('camera_name'), str) and len(data['camera_name']) <= 256:
        result['camera_name'] = data['camera_name']
    for key, choices in (('camera_mode', ('continuous', 'idle')),
                         ('presence_mode', ('any', 'owner')), ('reminder_mode', ('dot', 'text'))):
        if data.get(key) in choices:
            result[key] = data[key]
    for key, minimum, maximum in (('idle_threshold', 5, 300), ('recheck_interval', 10, 600),
                                  ('entry_alpha', 0, 255), ('exit_alpha', 0, 255)):
        value = data.get(key)
        if type(value) is int and minimum <= value <= maximum:
            result[key] = value
    for key in ('lock_enabled', 'auto_hide', 'hide_browser_top', 'hide_browser_scrollbar', 'mouse_opacity', 'close_window_on_exit'):
        if isinstance(data.get(key), bool):
            result[key] = data[key]
    target = data.get('target_window')
    # HWND 和 PID 重启后会变化；仅保存可用于唯一匹配的窗口描述。
    if (isinstance(target, list) and len(target) == 2 and
            all(isinstance(part, str) and 0 < len(part) <= 256 for part in target)):
        result['target_window'] = target.copy()
    size = data.get('window_size')
    # 旧配置没有尺寸；损坏或非整数尺寸交给界面使用原来的默认值。
    if isinstance(size, list) and len(size) == 2 and all(type(value) is int and 0 < value <= 32767 for value in size):
        result['window_size'] = size.copy()
    timestamp = data.get('last_check')
    if type(timestamp) in (int, float) and 0 <= timestamp < 1e12:
        result['last_check'] = timestamp
    return result


def load_preferences(path=None):
    try:
        return validated(json.loads((path or preferences_path()).read_text(encoding='utf-8')))
    except (OSError, ValueError):
        return DEFAULTS.copy()


def save_preferences(data, path=None):
    path = path or preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        # 同目录原子替换，避免退出或写入失败留下半截 JSON。
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(validated(data), stream, ensure_ascii=False, indent=2)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def system_theme():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
            return 'light' if winreg.QueryValueEx(key, 'AppsUseLightTheme')[0] else 'dark'
    except OSError:
        return 'dark'


# 复用 TokenMeter 的深浅色语义配色；保持 BehindWatch 默认深色与提醒语义。
DARK = {'BG': '#151515', 'CARD': '#1d1d1d', 'ELEVATED': '#242424', 'TEXT': '#e6e6e6',
        'MUTED': '#a8a8ad', 'BORDER': '#6a6a6a', 'DIVIDER': '#303030', 'ACCENT': '#3478f6',
        'ACCENT_SOFT': '#20304a', 'VALUE': '#fafafa', 'ACCENT_HOVER': '#5a93fa',
        'GREEN': '#18c77a', 'AMBER': '#ffd18a', 'TRACK': '#55555b'}
LIGHT = {'BG': '#f7f7f8', 'CARD': '#ffffff', 'ELEVATED': '#ffffff', 'TEXT': '#25272b',
         'MUTED': '#5e6571', 'BORDER': '#90949b', 'DIVIDER': '#d9dadd', 'ACCENT': '#2f72e8',
         'ACCENT_SOFT': '#e9f1ff', 'VALUE': '#111318', 'ACCENT_HOVER': '#1e61d2',
         'GREEN': '#087a4a', 'AMBER': '#946000', 'TRACK': '#a8adb5'}
