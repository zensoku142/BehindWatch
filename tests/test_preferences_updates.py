"""Preferences and stable-release boundaries (no live network)."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import preferences
from core import autostart
from updater import updates
from updater import main as updater_main


class PreferencesTests(unittest.TestCase):
    def test_exit_close_defaults_on_and_saves_disabled(self):
        self.assertTrue(preferences.validated({})['close_window_on_exit'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            preferences.save_preferences({'close_window_on_exit': False}, path)
            self.assertFalse(preferences.load_preferences(path)['close_window_on_exit'])
        self.assertTrue(preferences.validated({'close_window_on_exit': 'false'})['close_window_on_exit'])

    def test_invalid_missing_and_atomic_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'settings.json'
            self.assertEqual(preferences.load_preferences(path), preferences.DEFAULTS)
            path.write_text('{broken', encoding='utf-8')
            self.assertEqual(preferences.load_preferences(path), preferences.DEFAULTS)
            values = dict(theme='system', language='ko', auto_start=True, auto_update=True, last_check=123,
                          monitor_hotkey='Ctrl+Alt+M')
            preferences.save_preferences(values, path)
            self.assertEqual(preferences.load_preferences(path), {**preferences.DEFAULTS, **values})
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_invalid_values_never_enable_updates(self):
        result = preferences.validated({'theme':'invalid','language':'invalid','auto_update':'true','last_check':float('nan')})
        self.assertEqual(result, preferences.DEFAULTS)
        self.assertEqual(preferences.validated({'monitor_hotkey': 'Ctrl+Alt+Delete'})['monitor_hotkey'], '')

    def test_window_size_roundtrip_and_invalid_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'settings.json'
            preferences.save_preferences({'window_size': [900, 700]}, path)
            self.assertEqual(preferences.load_preferences(path)['window_size'], [900, 700])
        for size in (None, '900x700', [900], [900, 700, 600], [True, 700], [900.5, 700], [0, 700], [900, 32768]):
            with self.subTest(size=size):
                self.assertNotIn('window_size', preferences.validated({'window_size': size}))

    def test_monitoring_settings_roundtrip_and_invalid_values(self):
        values = {**preferences.DEFAULTS, 'camera_name': 'USB Camera', 'camera_mode': 'idle',
                  'idle_threshold': 45, 'recheck_interval': 120, 'lock_enabled': True,
                  'presence_mode': 'owner', 'reminder_mode': 'dot', 'auto_hide': True,
                  'hide_browser_top': True, 'hide_browser_scrollbar': True,
                  'mouse_opacity': True, 'entry_alpha': 180, 'exit_alpha': 80,
                  'target_window': ['Browser', 'Chrome_WidgetWin_1']}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            preferences.save_preferences(values, path)
            self.assertEqual(preferences.load_preferences(path), {**preferences.DEFAULTS, **values})
        invalid = preferences.validated({'camera_mode': 'other', 'idle_threshold': True,
                                         'lock_enabled': 'true', 'target_window': ['Browser', '']})
        self.assertEqual(invalid, preferences.DEFAULTS)

    def test_autostart_creates_and_removes_current_user_shortcut(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict('os.environ', {'APPDATA': directory}), \
             patch.object(autostart.subprocess, 'run') as run:
            path = autostart._shortcut_path()
            run.side_effect = lambda *args, **kwargs: path.write_bytes(b'shortcut')
            autostart.sync_autostart(True)
            self.assertTrue(path.is_file())
            self.assertEqual(run.call_args.kwargs['env']['BEHINDWATCH_STARTUP_LINK'], str(path))
            autostart.sync_autostart(False)
            self.assertFalse(path.exists())


class UpdateTests(unittest.TestCase):
    def test_stable_versions_and_fixed_repository_url(self):
        release = updates.parse_release({'tag_name':'v1.2.3', 'body':'Notes', 'html_url':'https://untrusted.invalid'}, '1.2.2')
        self.assertTrue(release['available'])
        self.assertEqual(release['url'], updates.RELEASES_URL+'/tag/v1.2.3')
        self.assertFalse(updates.parse_release({'tag_name':'v1.2.3'}, '1.2.3')['available'])
        for tag in ('v1.2.3-beta', 'v01.2.3', '../other', 'v1.2', ''):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                updates.parse_release({'tag_name':tag})
        for field in ('draft','prerelease'):
            with self.assertRaises(ValueError):
                updates.parse_release({'tag_name':'v1.2.3',field:True})

    def test_no_release_and_network_error(self):
        for code in (404, 403):
            with patch('updater.updates.urlopen', side_effect=HTTPError(updates.API_URL,code,'error',{},None)):
                if code == 404:
                    self.assertIsNone(updates.check_release())
                else:
                    with self.assertRaises(HTTPError):
                        updates.check_release()

    def test_response_size_and_notes_limit(self):
        with patch('updater.updates.urlopen', return_value=io.BytesIO(b'x'*(updates.MAX_METADATA_BYTES+1))):
            with self.assertRaises(ValueError):
                updates.check_release()
        payload = json.dumps({'tag_name':'v1.2.3','body':'x'*60000}).encode()
        with patch('updater.updates.urlopen', return_value=io.BytesIO(payload)):
            self.assertEqual(len(updates.check_release()['notes']),50000)

    def test_installer_requires_release_assets_and_valid_checksum(self):
        release = updates.parse_release({'tag_name':'v1.2.3', 'assets':[
            {'name':'BehindWatch-Setup-v1.2.3-x64.exe'}, {'name':'SHA256SUMS.txt'}]}, '1.0.0')
        self.assertTrue(release['installable'])
        self.assertFalse(updates.parse_release({'tag_name':'v1.2.3'}, '1.0.0')['installable'])

        class Download(io.BytesIO):
            def geturl(self):
                return 'https://release-assets.githubusercontent.com/asset'

        name = 'BehindWatch-Setup-v1.2.3-x64.exe'
        checksum = ('0'*64 + ' *' + name + '\n').encode()
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(updates, 'APP_VERSION', '1.0.0'), \
             patch.dict('os.environ', {'LOCALAPPDATA':directory}), \
             patch('updater.updates.urlopen', side_effect=[Download(checksum), Download(b'installer')]):
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                updates.download_installer(release)
            self.assertEqual(list((Path(directory)/'BehindWatch'/'updates').iterdir()), [])

    def test_updater_runs_outside_installed_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installed = root / 'installed'
            installed.mkdir()
            executable = installed / 'BehindWatch.exe'
            executable.touch()
            (installed / 'BehindWatchUpdater.exe').write_bytes(b'helper')
            cache = root / 'updates'
            cache.mkdir()
            installer = cache / 'BehindWatch-Setup-v1.2.3-x64.exe'
            installer.touch()
            with patch.object(updates.sys, 'frozen', True, create=True), \
                 patch.object(updates.sys, 'executable', str(executable)), \
                 patch('updater.updates.subprocess.Popen') as launch:
                updates.launch_installer(installer)
            detached = cache / 'BehindWatchUpdater.exe'
            self.assertEqual(detached.read_bytes(), b'helper')
            self.assertEqual(launch.call_args.args[0][0], str(detached))
            self.assertEqual(launch.call_args.args[0][-2:], ['--installer', str(installer)])

    def test_update_installer_shows_progress_and_records_log(self):
        with tempfile.TemporaryDirectory() as directory:
            installer = Path(directory) / 'BehindWatch-Setup-v1.2.3-x64.exe'
            installer.touch()
            with patch('updater.main.ctypes.windll') as windll, \
                 patch('updater.main.subprocess.call', return_value=0) as launch:
                windll.kernel32.OpenProcess.return_value = 0
                self.assertEqual(updater_main.main(['--wait-pid', '123', '--installer', str(installer)]), 0)
            command = launch.call_args.args[0]
            self.assertIn('/SILENT', command)
            self.assertIn('/BEHINDWATCHUPDATE', command)
            self.assertIn(f'/LOG={installer.with_suffix(".log")}', command)

    def test_translation_placeholders_and_system_resolution(self):
        from string import Formatter
        from ui.translations import MESSAGES
        from ui.i18n import resolve_language
        fields = lambda value: {field for _,field,_,_ in Formatter().parse(value) if field}
        for source, translations in MESSAGES.items():
            self.assertEqual(len(translations),4,source)
            for translated in translations:
                self.assertEqual(fields(source),fields(translated),source)
        self.assertEqual(resolve_language('system',['zh-Hant-HK']), 'zh-tw')
        self.assertEqual(resolve_language('system',['zh-Hans-CN']), 'zh-cn')
        self.assertEqual(resolve_language('system',['de-DE']), 'en')


if __name__ == '__main__':
    unittest.main()
