"""Windows current-user startup shortcut for BehindWatch."""
import os
from pathlib import Path
import subprocess
import sys


def _shortcut_path():
    return (Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'Microsoft' / 'Windows' / 'Start Menu' /
            'Programs' / 'Startup' / 'BehindWatch.lnk')


def sync_autostart(enabled):
    path = _shortcut_path()
    if not enabled:
        path.unlink(missing_ok=True)
        if path.exists():
            raise OSError('开机自启快捷方式未删除。')
        return
    # 与 TokenMeter 一样保留现有入口，避免开发运行覆盖已安装版的启动快捷方式。
    if path.is_file():
        return
    executable = Path(sys.executable).resolve()
    script = Path(__file__).resolve().parents[1] / 'app.py'
    if getattr(sys, 'frozen', False):
        arguments = ''
        working_dir = executable.parent
    else:
        # 源码版沿用当前解释器，与 TokenMeter 的开发运行入口一致。
        arguments = subprocess.list2cmdline([str(script)])
        working_dir = script.parent
    path.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(BEHINDWATCH_STARTUP_LINK=str(path), BEHINDWATCH_STARTUP_EXE=str(executable),
                       BEHINDWATCH_STARTUP_ARGS=arguments, BEHINDWATCH_STARTUP_DIR=str(working_dir))
    command = ('$link = (New-Object -ComObject WScript.Shell).CreateShortcut($env:BEHINDWATCH_STARTUP_LINK); '
               '$link.TargetPath = $env:BEHINDWATCH_STARTUP_EXE; '
               '$link.Arguments = $env:BEHINDWATCH_STARTUP_ARGS; '
               '$link.WorkingDirectory = $env:BEHINDWATCH_STARTUP_DIR; '
               '$link.IconLocation = $env:BEHINDWATCH_STARTUP_EXE; $link.Save()')
    powershell = Path(os.environ.get('SYSTEMROOT', r'C:\Windows')) / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'
    subprocess.run([str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', command],
                   check=True, capture_output=True, timeout=15, env=environment,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if not path.is_file():
        raise OSError('开机自启快捷方式未创建。')
