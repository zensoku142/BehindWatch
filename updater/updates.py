"""Read stable BehindWatch releases without modifying the running checkout."""
import json
import re
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# 安装版以构建时写入的版本为准；源码仍标记为开发版本。
def installed_version():
    if not getattr(sys, 'frozen', False):
        return None
    try:
        value = (Path(sys._MEIPASS) / 'version.txt').read_text(encoding='ascii').strip()
        if not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value):
            return None
        return value
    except (OSError, ValueError):
        return None


APP_VERSION = installed_version()
REPOSITORY = 'zensoku142/BehindWatch'
RELEASES_URL = f'https://github.com/{REPOSITORY}/releases'
API_URL = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
MAX_METADATA_BYTES = 2 * 1024 * 1024
CHECK_INTERVAL = 24 * 60 * 60
SETUP_NAME = 'BehindWatch-Setup-v{version}-x64.exe'
MAX_INSTALLER_BYTES = 2 * 1024**3


def version_tuple(value):
    match = re.fullmatch(r'v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value)
    if not match:
        raise ValueError('Invalid stable release version')
    return tuple(map(int, match.groups()))


def parse_release(data, current_version=APP_VERSION):
    if not isinstance(data, dict) or data.get('draft') or data.get('prerelease'):
        raise ValueError('Invalid stable release metadata')
    tag = data.get('tag_name', '')
    version = version_tuple(tag)
    # URL 根据固定仓库和已校验的版本生成，不打开响应提供的任意外部地址。
    assets = {item.get('name') for item in data.get('assets', []) if isinstance(item, dict)}
    installer = SETUP_NAME.format(version=tag.removeprefix('v'))
    return {'version': tag.removeprefix('v'), 'url': f'{RELEASES_URL}/tag/{tag}',
            'notes': str(data.get('body') or '')[:50000],
            'available': current_version is None or version > version_tuple(current_version),
            'installable': installer in assets and 'SHA256SUMS.txt' in assets}


def _release_asset_url(release, name):
    version_tuple(release['version'])
    if name not in (SETUP_NAME.format(version=release['version']), 'SHA256SUMS.txt'):
        raise ValueError('Unexpected release asset')
    return f"{RELEASES_URL}/download/v{release['version']}/{name}"


def _read_asset(url, limit):
    request = Request(url, headers={'User-Agent': 'BehindWatch-Updater'})
    with urlopen(request, timeout=60) as response:
        # GitHub release downloads redirect to its asset CDN; reject other destinations.
        if urlparse(response.geturl()).hostname not in {
                'github.com', 'objects.githubusercontent.com', 'release-assets.githubusercontent.com'}:
            raise ValueError('Unexpected download host')
        content = response.read(limit + 1)
    if len(content) > limit:
        raise ValueError('Release asset exceeds size limit')
    return content


def download_installer(release):
    if not release['available'] or not release['installable'] or APP_VERSION is None:
        raise ValueError('No installable update is available')
    name = SETUP_NAME.format(version=release['version'])
    checksum = _read_asset(_release_asset_url(release, 'SHA256SUMS.txt'), 64 * 1024).decode('utf-8')
    match = next((re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?' + re.escape(name), line.strip())
                  for line in checksum.splitlines() if name in line), None)
    if match is None:
        raise ValueError('Installer checksum missing')
    cache = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'BehindWatch' / 'updates'
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / name
    temporary = target.with_suffix('.download')
    try:
        request = Request(_release_asset_url(release, name), headers={'User-Agent': 'BehindWatch-Updater'})
        digest = hashlib.sha256()
        size = 0
        with urlopen(request, timeout=60) as response, temporary.open('wb') as output:
            if urlparse(response.geturl()).hostname not in {
                    'github.com', 'objects.githubusercontent.com', 'release-assets.githubusercontent.com'}:
                raise ValueError('Unexpected download host')
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_INSTALLER_BYTES:
                    raise ValueError('Installer exceeds size limit')
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest().lower() != match.group(1).lower():
            raise ValueError('Installer checksum mismatch')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def launch_installer(path):
    if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
        raise RuntimeError('Automatic installation is available in the packaged Windows app')
    helper = Path(sys.executable).with_name('BehindWatchUpdater.exe')
    if not helper.is_file():
        raise FileNotFoundError(helper)
    subprocess.Popen([str(helper), '--wait-pid', str(os.getpid()), '--installer', str(path)],
                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def check_release():
    request = Request(API_URL, headers={'Accept': 'application/vnd.github+json',
                                       'User-Agent': 'BehindWatch-UpdateCheck'})
    try:
        with urlopen(request, timeout=10) as response:
            payload = response.read(MAX_METADATA_BYTES + 1)
        if len(payload) > MAX_METADATA_BYTES:
            raise ValueError('Release metadata exceeds size limit')
        return parse_release(json.loads(payload))
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise
