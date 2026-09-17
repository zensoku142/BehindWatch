"""Build the Windows onedir app and matching Inno Setup installer."""
import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DIST = ROOT / 'dist' / 'BehindWatch'
OUT = ROOT / 'dist-installer'


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def build_onedir(version):
    from scripts.download_models import download
    download()
    marker = ROOT / 'build' / 'version.txt'
    marker.parent.mkdir(exist_ok=True)
    if version:
        marker.write_text(version, encoding='ascii')
    else:
        marker.unlink(missing_ok=True)
    run(sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm',
        str(ROOT / 'packaging' / 'pyinstaller' / 'BehindWatch.spec'))
    run(sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', '--onefile',
        '--windowed', '--name', 'BehindWatchUpdater', '--specpath', str(ROOT / 'build'), '--icon',
        str(ROOT / 'assets' / 'BehindWatch.ico'), str(ROOT / 'updater' / 'main.py'))
    shutil.copy2(ROOT / 'dist' / 'BehindWatchUpdater.exe', DIST / 'BehindWatchUpdater.exe')
    if not (DIST / 'BehindWatch.exe').is_file():
        raise FileNotFoundError('Main executable was not built')
    for name in ('person_yolox.onnx', 'face.task', 'sface.onnx'):
        if not (DIST / '_internal' / 'models' / name).is_file():
            raise FileNotFoundError(f'Packaged model missing: {name}')
    for path in ('PySide6/Qt6Core.dll', 'PySide6/plugins/platforms/qwindows.dll'):
        if not (DIST / '_internal' / path).is_file():
            raise FileNotFoundError(f'Packaged Qt file missing: {path}')
    if version and not (DIST / '_internal' / 'version.txt').is_file():
        raise FileNotFoundError('Packaged version missing')


def build_installer(version, compiler=None):
    compiler = compiler or shutil.which('ISCC.exe') or shutil.which('iscc')
    if compiler is None:
        candidates = [Path('C:/Program Files (x86)/Inno Setup 6/ISCC.exe'),
                      Path.home() / 'AppData/Local/Programs/Inno Setup 6/ISCC.exe']
        for path in candidates:
            try:
                if path.is_file():
                    compiler = str(path)
                    break
            except OSError:
                continue
    if compiler is None:
        raise FileNotFoundError('Inno Setup 6 compiler not found')
    OUT.mkdir(exist_ok=True)
    run(compiler, f'/DMyAppVersion={version}',
        str(ROOT / 'packaging' / 'installer' / 'BehindWatch.iss'))
    installer = OUT / f'BehindWatch-Setup-v{version}-x64.exe'
    if not installer.is_file():
        raise FileNotFoundError(installer)
    with installer.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    (OUT / 'SHA256SUMS.txt').write_text(f'{digest} *{installer.name}\n', encoding='ascii')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=('all', 'onedir', 'installer'), default='all')
    parser.add_argument('--version', help='Stable release version, for example 1.0.0')
    parser.add_argument('--iscc', help='Path to the Inno Setup compiler')
    args = parser.parse_args(argv)
    if args.version and not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', args.version):
        parser.error('Version must be a stable X.Y.Z value')
    if args.stage in ('all', 'onedir'):
        build_onedir(args.version)
    if args.stage in ('all', 'installer'):
        if not args.version:
            parser.error('--version is required for an installer')
        build_installer(args.version, args.iscc)


if __name__ == '__main__':
    main()
