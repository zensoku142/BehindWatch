"""Qt integration checks without camera access or real update requests."""
import importlib.util
import io
import queue
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@unittest.skipUnless(sys.platform == 'win32' and importlib.util.find_spec('PySide6'), 'Windows Qt test')
class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qt = QApplication.instance() or QApplication([])
        cls.qt.setQuitOnLastWindowClosed(False)

    def setUp(self):
        from app import App
        from core.preferences import DEFAULTS
        self.prefs = patch('app.load_preferences', return_value=DEFAULTS.copy())
        self.prefs.start()
        self.save = patch('app.save_preferences').start()
        self.autostart = patch('app.sync_autostart').start()
        with patch.object(App, 'setup_tray'), patch.object(App, 'refresh_cameras'):
            self.app = App()
        self.app.timer.stop()
        self.app.update_timer.stop()
        self.app.show()
        self.qt.processEvents()
        # CI or a late-night desktop session may report the display as off;
        # interaction tests set their own power state when exercising that behavior.
        self.app.session_locked = False
        self.app.display_off = False

    def tearDown(self):
        self.app.process = None
        self.app.last_frame = None
        self.app.quit()
        self.app.deleteLater()
        self.qt.processEvents()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        patch.stopall()

    def frame(self, owner=1, tracks=None):
        from PIL import Image
        data = io.BytesIO()
        Image.new('RGB', (640, 360), '#233446').save(data, format='JPEG')
        return {'at': time.monotonic(), 'jpeg': data.getvalue(), 'owner': owner,
                'tracks': tracks or [], 'fps': 10}

    def test_window_size_saves_after_resize_and_restores(self):
        from PySide6.QtTest import QTest
        from app import App
        self.save.reset_mock()
        self.app.resize(900, 700)
        self.qt.processEvents()
        self.save.assert_not_called()
        QTest.qWait(400)
        self.assertEqual(self.save.call_args.args[0]['window_size'], [900, 700])
        with patch('app.load_preferences', return_value=self.app.preferences.copy()), \
             patch.object(App, 'setup_tray'), patch.object(App, 'refresh_cameras'):
            restored = App()
        try:
            self.assertEqual((restored.width(), restored.height()), (900, 700))
        finally:
            restored.quit()
            restored.deleteLater()

    def test_smoke_uses_defaults_without_restoring_user_target(self):
        from app import App
        from core.preferences import DEFAULTS
        with patch('app.sys.argv', ['app.py', '--smoke-test']), \
             patch('app.load_preferences') as load, \
             patch.object(App, 'setup_tray'), patch.object(App, 'refresh_cameras'):
            window = App()
            try:
                load.assert_not_called()
                self.assertEqual(window.preferences, DEFAULTS)
                self.assertIsNone(window.window_guard.selected)
            finally:
                window.quit()
                window.deleteLater()

    def test_monitoring_settings_autosave_and_restore(self):
        from PySide6.QtTest import QTest
        from app import App
        self.app.camera_mode.setCurrentIndex(self.app.camera_mode.findData('idle'))
        self.app.idle_threshold.setValue(45)
        self.app.lock_enabled.click()
        self.app.presence_mode.setCurrentIndex(self.app.presence_mode.findData('owner'))
        self.app.reminder_mode.setCurrentIndex(self.app.reminder_mode.findData('dot'))
        self.app.entry_alpha.setValue(180)
        QTest.qWait(400)
        saved = self.save.call_args.args[0].copy()
        self.assertEqual(saved['camera_mode'], 'idle')
        self.assertTrue(saved['lock_enabled'])
        with patch('app.load_preferences', return_value=saved), \
             patch.object(App, 'setup_tray'), patch.object(App, 'refresh_cameras'):
            restored = App()
        try:
            self.assertEqual(restored.camera_mode.currentData(), 'idle')
            self.assertEqual(restored.idle_threshold.value(), 45)
            self.assertTrue(restored.lock_enabled.isChecked())
            self.assertEqual(restored.presence_mode.currentData(), 'owner')
            self.assertEqual(restored.reminder_mode.currentData(), 'dot')
            self.assertEqual(restored.entry_alpha.value(), 180)
        finally:
            restored.quit()
            restored.deleteLater()

    def test_camera_selection_restores_by_name_after_device_order_changes(self):
        cameras = [SimpleNamespace(index=0, name='Built-in'), SimpleNamespace(index=2, name='USB')]
        with patch('cv2_enumerate_cameras.enumerate_cameras', return_value=cameras):
            self.app.refresh_cameras()
        self.app.camera.setCurrentIndex(1)
        self.app.save_preferences()
        self.assertEqual(self.save.call_args.args[0]['camera_name'], 'USB')
        self.app.cameras = []
        self.app.preferences['camera_name'] = 'USB'
        with patch('cv2_enumerate_cameras.enumerate_cameras', return_value=list(reversed(cameras))):
            self.app.refresh_cameras()
        self.assertEqual(self.app.cameras[self.app.camera.currentIndex()].name, 'USB')

    def test_window_target_restores_only_when_unique(self):
        target = SimpleNamespace(hwnd=123, title='Browser', class_name='BrowserWindow')
        self.app.preferences['target_window'] = ['Browser', 'BrowserWindow']
        with patch.object(self.app.window_guard, 'windows', return_value=[target, target]), \
             patch.object(self.app.window_guard, 'select') as select:
            self.app.refresh_windows()
            select.assert_not_called()
        with patch.object(self.app.window_guard, 'windows', return_value=[target]), \
             patch.object(self.app.window_guard, 'select', side_effect=lambda window: setattr(self.app.window_guard, 'selected', window)) as select:
            self.app.refresh_windows()
            select.assert_called_once_with(target)

    def test_browser_crop_switches_share_target_and_are_off_by_default(self):
        self.assertFalse(self.app.hide_browser_top.isChecked())
        self.assertFalse(self.app.hide_browser_scrollbar.isChecked())
        self.app.update_browser_crop()
        self.assertIsNone(self.app.window_guard.browser_crop)
        with patch.object(self.app.window_guard, 'update_crop', return_value='浏览器区域裁剪已生效。') as update:
            self.app.hide_browser_top.click()
            update.assert_called_with(True, False)
            self.app.hide_browser_scrollbar.click()
            update.assert_called_with(True, True)
            self.app.hide_browser_top.click()
            update.assert_called_with(False, True)

    def test_failed_crop_restore_blocks_exit(self):
        with patch.object(self.app.window_guard, 'restore_crop', side_effect=OSError('恢复浏览器裁剪失败，请重试。')):
            self.app.quit()
        self.assertFalse(self.app.closed)
        self.assertTrue(self.app.isVisible())

    def test_exit_closes_native_selected_window_but_tray_does_not(self):
        from PySide6.QtWidgets import QWidget
        from PySide6.QtTest import QTest
        target = QWidget()
        target.show()
        self.qt.processEvents()
        guard = self.app.window_guard
        guard.select(guard.describe(int(target.winId())))
        try:
            self.assertTrue(self.app.close_window_on_exit.isChecked())
            self.app.close()
            QTest.qWait(50)
            self.assertTrue(target.isVisible())
            self.assertFalse(self.app.closed)
            self.app.quit()
            QTest.qWait(50)
            self.assertFalse(target.isVisible())
            self.assertTrue(self.app.closed)
        finally:
            target.close()
            target.deleteLater()

    def test_exit_close_setting_autosaves_and_request_failure_blocks_exit(self):
        self.app.close_window_on_exit.click()
        self.assertTrue(self.app.settings_save_timer.isActive())
        self.app.save_preferences()
        self.assertFalse(self.save.call_args.args[0]['close_window_on_exit'])
        self.app.close_window_on_exit.setChecked(True)
        with patch.object(self.app.window_guard, 'close_selected', side_effect=OSError('关闭失败')):
            self.app.quit()
        self.assertFalse(self.app.closed)

    def test_smoke_exit_does_not_close_selected_window(self):
        with patch.object(sys, 'argv', ['app.py', '--smoke-test']), \
             patch.object(self.app.window_guard, 'close_selected') as close:
            self.app.quit()
            close.assert_not_called()

    def test_crop_error_disables_switches_and_restores_region(self):
        self.app.hide_browser_top.setChecked(True)
        self.app.hide_browser_scrollbar.setChecked(True)
        with patch.object(self.app.window_guard, 'update_crop', side_effect=OSError('浏览器裁剪失败，请关闭开关后重试。')), \
             patch.object(self.app.window_guard, 'restore_crop') as restore:
            self.app.update_browser_crop()
            restore.assert_called_once()
        self.assertFalse(self.app.hide_browser_top.isChecked())
        self.assertFalse(self.app.hide_browser_scrollbar.isChecked())

    def test_immediate_close_flushes_pending_window_size(self):
        self.app.resize(880, 680)
        self.qt.processEvents()
        self.assertTrue(self.app.size_save_timer.isActive())
        self.app.close()
        self.assertFalse(self.app.size_save_timer.isActive())
        self.assertEqual(self.save.call_args.args[0]['window_size'], [880, 680])

    def test_face_registration_and_deletion_commands(self):
        self.app.process = Mock()
        self.app.commands = queue.Queue()
        self.app.last_frame = self.frame(owner=1)
        self.app.register_face()
        self.assertEqual(self.app.commands.get_nowait(), ('register', None))
        with patch('app.delete_template') as delete:
            self.app.delete_face()
        delete.assert_called_once()
        self.assertEqual(self.app.commands.get_nowait(), ('delete_identity', None))

    def test_manual_ignore_targets_selected_person_only(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        self.app.process = Mock()
        self.app.commands = queue.Queue()
        self.app.last_frame = self.frame(owner=1, tracks=[
            {'id': 1, 'box': (.1, .1, .4, .9), 'facing': False},
            {'id': 2, 'box': (.6, .1, .9, .9), 'facing': False}])
        self.app.render()
        self.qt.processEvents()
        rect = self.app.canvas.image_rect
        point = lambda x: QPoint(int(rect.x() + rect.width()*x), int(rect.y() + rect.height()*.5))
        self.assertIsNone(self.app.canvas.selection_mode)
        QTest.mouseClick(self.app.canvas, Qt.MouseButton.LeftButton, pos=point(.25))
        self.assertTrue(self.app.commands.empty())
        QTest.mouseClick(self.app.canvas, Qt.MouseButton.LeftButton, pos=point(.75))
        self.assertEqual(self.app.commands.get_nowait(), ('toggle_ignore', 2))
        QTest.mouseClick(self.app.canvas, Qt.MouseButton.LeftButton, pos=point(.75))
        self.assertEqual(self.app.commands.get_nowait(), ('toggle_ignore', 2))
        self.assertFalse(self.app.owner_select_button.isChecked())
        self.app.owner_select_button.click()
        self.assertEqual(self.app.canvas.selection_mode, 'owner')
        self.assertTrue(self.app.owner_select_button.isChecked())
        QTest.mouseClick(self.app.canvas, Qt.MouseButton.LeftButton, pos=point(.25))
        self.assertEqual(self.app.commands.get_nowait(), ('owner', 1))
        self.assertIsNone(self.app.canvas.selection_mode)
        self.assertFalse(self.app.owner_select_button.isChecked())

    def test_main_controls_and_settings_preserve_state(self):
        self.assertGreater(self.app.canvas.height(), 200)
        self.assertTrue(self.app.start_button.isVisible())
        self.assertFalse(self.app.camera.isVisible())
        self.assertFalse(self.app.owner_choice.isVisible())
        self.app.show_settings('监测与提醒')
        self.qt.processEvents()
        self.assertTrue(self.app.camera.isVisible())
        self.assertIs(self.app.camera.window(), self.app)
        self.app.reminder_mode.setCurrentIndex(1)
        self.app.close_settings()
        self.app.notify('检测到其他人员')
        self.app.show_settings('提醒与启动')
        self.assertEqual(self.app.reminder_mode.currentData(), 'text')
        self.app.show_settings('常规')
        self.assertTrue(self.app.auto_start.isVisible())
        self.assertFalse(hasattr(self.app, 'log'))

    def test_preview_visibility_preserves_monitoring_and_blocks_selection(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        self.app.last_frame = self.frame(None, [{'id': 2, 'box': (0, 0, 1, 1)}])
        self.app.render()
        self.qt.processEvents()
        self.app.owner_select_button.click()
        preview_height = self.app.canvas.heightForWidth(480)
        self.app.preview_toggle.click()
        self.qt.processEvents()
        self.assertTrue(self.app.canvas.preview_hidden)
        self.assertEqual(self.app.canvas.heightForWidth(480), preview_height)
        self.assertIsNone(self.app.selection_mode)
        self.assertIsNotNone(self.app.last_frame)
        selected = []
        self.app.canvas.selected.connect(selected.append)
        QTest.mouseClick(self.app.canvas, Qt.MouseButton.LeftButton, pos=self.app.canvas.rect().center())
        self.assertEqual(selected, [])
        self.app.owner_select_button.click()
        self.qt.processEvents()
        self.assertFalse(self.app.canvas.preview_hidden)
        self.assertEqual(self.app.selection_mode, 'owner')

    def test_preview_aspect_and_clicks_after_resize(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PIL import Image
        for dimensions in ((640, 480), (1280, 720), (480, 640)):
            data = io.BytesIO()
            Image.new('RGB', dimensions).save(data, format='JPEG')
            frame = self.frame(None, [{'id': 7, 'box': (.4, .4, .6, .6)}])
            frame['jpeg'] = data.getvalue()
            self.app.last_frame = frame
            self.app.render()
            self.app.canvas.selection_mode = 'owner'
            selected = []
            self.app.canvas.selected.connect(selected.append)
            for window in ((640, 520), (900, 700)):
                self.app.resize(*window)
                self.qt.processEvents()
                rect = self.app.canvas.image_rect
                self.assertAlmostEqual(rect.width() / rect.height(), dimensions[0] / dimensions[1], delta=.01)
                QTest.mouseClick(self.app.canvas, Qt.MouseButton.LeftButton, pos=rect.center().toPoint())
                self.assertEqual(selected[-1], 7)
                self.assertTrue(self.app.rect().contains(self.app.background_button.mapTo(self.app, self.app.background_button.rect().bottomRight())))
            self.app.canvas.selected.disconnect(selected.append)

    def test_owner_management_remains_accessible_in_all_presence_modes(self):
        self.assertEqual(self.app.page_names, ('摄像头', '锁屏与本人', '窗口保护', '提醒', '常规', '更新与关于'))
        camera_body = self.app.settings_stack.widget(self.app.page_names.index('摄像头')).widget()
        lock_body = self.app.settings_stack.widget(self.app.page_names.index('锁屏与本人')).widget()
        general_body = self.app.settings_stack.widget(self.app.page_names.index('常规')).widget()
        for control in (self.app.camera, self.app.camera_mode, self.app.idle_threshold,
                        self.app.recheck_interval, self.app.meta):
            self.assertTrue(camera_body.isAncestorOf(control), control)
        for control in (self.app.lock_enabled, self.app.presence_mode, self.app.owner_settings):
            self.assertTrue(lock_body.isAncestorOf(control), control)
        self.assertTrue(general_body.isAncestorOf(self.app.auto_start))
        self.assertFalse(hasattr(self.app, 'hide_button'))
        self.app.show_settings('监测')
        self.assertEqual(self.app.current_settings_page, '摄像头')
        self.app.show_settings('锁屏与本人')
        self.qt.processEvents()
        self.assertTrue(self.app.owner_settings.isVisible())
        self.app.presence_mode.setCurrentIndex(self.app.presence_mode.findData('owner'))
        self.assertTrue(self.app.owner_settings.isVisible())
        self.assertTrue(self.app.registration_status.isVisible())
        self.app.lock_enabled.setChecked(True)
        self.app.presence_mode.setCurrentIndex(self.app.presence_mode.findData('any'))
        self.assertTrue(self.app.owner_settings.isVisible())
        self.app.presence_mode.setCurrentIndex(self.app.presence_mode.findData('owner'))
        self.assertTrue(self.app.owner_settings.isVisible())
        self.assertTrue(self.app.lock_enabled.isChecked())
        self.app.show_settings('摄像头')
        self.app.show_settings('锁屏与本人')
        self.assertTrue(self.app.owner_settings.isVisible())

    def test_idle_controls_keep_values_when_switching_modes(self):
        self.app.show_settings('摄像头')
        self.qt.processEvents()
        self.assertFalse(self.app.idle_settings.isVisible())
        self.app.camera_mode.setCurrentIndex(self.app.camera_mode.findData('idle'))
        self.assertTrue(self.app.idle_settings.isVisible())
        self.app.idle_threshold.setValue(45)
        self.app.camera_mode.setCurrentIndex(self.app.camera_mode.findData('continuous'))
        self.assertFalse(self.app.idle_settings.isVisible())
        self.app.camera_mode.setCurrentIndex(self.app.camera_mode.findData('idle'))
        self.assertEqual(self.app.idle_threshold.value(), 45)

    def test_background_preview_releases_decoded_image_and_restores_latest(self):
        self.app.last_frame = self.frame()
        self.app.render()
        self.assertFalse(self.app.canvas.picture.isNull())
        self.app.show_settings('常规')
        self.app.render()
        self.assertTrue(self.app.canvas.picture.isNull())
        self.assertIsNotNone(self.app.last_frame)
        self.app.close_settings()
        self.assertFalse(self.app.canvas.picture.isNull())
        self.app.hide()
        self.app.render()
        self.assertTrue(self.app.canvas.picture.isNull())
        self.app.show_panel()
        self.assertFalse(self.app.canvas.picture.isNull())

    def test_family_header_theme_buttons_back_and_settings_state(self):
        from PySide6.QtWidgets import QToolButton
        self.assertIsInstance(self.app.back_button, QToolButton)
        self.assertEqual(self.app.back_button.objectName(), 'settingsBackButton')
        self.assertEqual(self.app.theme_segment.height(), 30)
        self.assertTrue(self.app.light_theme_button.isVisible())
        self.assertTrue(self.app.dark_theme_button.isChecked())
        self.app.light_theme_button.click()
        self.assertEqual(self.app.theme.resolved, 'light')
        self.assertEqual(self.app.theme_choice.currentData(), 'light')
        self.assertEqual(self.app.preferences['theme'], 'light')
        self.assertTrue(self.app.light_theme_button.property('selected'))
        self.app.show_settings('外观')
        self.assertFalse(self.app.settings_button.isVisible())
        self.assertTrue(self.app.settings_save_status.isVisible())
        self.app.dark_theme_button.click()
        self.assertEqual(self.app.theme_choice.currentData(), 'dark')
        self.assertTrue(self.app.back_button.icon().isNull() is False)
        self.app.back_button.click()
        self.assertFalse(self.app.settings_save_status.isVisible())
        self.assertTrue(self.app.settings_button.isVisible())

    def test_autostart_switch_saves_only_after_shortcut_succeeds(self):
        self.autostart.reset_mock()
        self.app.auto_start.click()
        self.autostart.assert_called_once_with(True)
        self.assertTrue(self.app.preferences['auto_start'])
        self.assertTrue(self.save.called)
        self.autostart.reset_mock()
        self.autostart.side_effect = OSError('shortcut unavailable')
        self.app.auto_start.click()
        self.assertTrue(self.app.auto_start.isChecked())
        self.assertTrue(self.app.preferences['auto_start'])

    def test_monitor_hotkey_selection_and_pause_only(self):
        choice = self.app.monitor_hotkey_choice
        with patch.object(self.app, 'set_monitor_hotkey', return_value=False):
            choice.setCurrentIndex(choice.findData('Ctrl+Alt+M'))
        self.assertEqual(choice.currentData(), '')
        self.assertEqual(self.app.preferences['monitor_hotkey'], '')
        with patch.object(self.app, 'set_monitor_hotkey', return_value=True):
            choice.setCurrentIndex(choice.findData('Ctrl+Alt+M'))
        self.assertEqual(self.app.preferences['monitor_hotkey'], 'Ctrl+Alt+M')
        self.assertTrue(self.save.called)
        with patch.object(self.app, 'start') as start, patch.object(self.app, 'stop') as stop:
            self.app.pause_monitoring_from_hotkey()
            start.assert_not_called()
            stop.assert_not_called()
            self.app.process = Mock()
            self.app.pause_monitoring_from_hotkey()
            stop.assert_called_once_with()
            self.app.stopping = True
            self.app.pause_monitoring_from_hotkey()
            stop.assert_called_once_with()
        self.app.process = None

    def test_monitor_hotkey_message_only_pauses_when_panel_is_hidden(self):
        import ctypes
        from ctypes import wintypes
        from app import MONITOR_HOTKEY_ID, WM_HOTKEY
        from PySide6.QtTest import QTest

        user32 = ctypes.WinDLL('user32', use_last_error=True)
        hwnd = wintypes.HWND(int(self.app.winId()))
        self.app.hide()
        self.app.commands = queue.Queue()
        self.app.stopping = False

        with patch.object(self.app, 'start') as start:
            self.assertTrue(user32.PostMessageW(hwnd, WM_HOTKEY, MONITOR_HOTKEY_ID, 0))
            QTest.qWait(50)
            start.assert_not_called()
            self.assertIsNone(self.app.process)
        self.app.process = Mock()
        self.assertTrue(user32.PostMessageW(hwnd, WM_HOTKEY, MONITOR_HOTKEY_ID, 0))
        QTest.qWait(50)
        self.assertTrue(self.app.stopping)
        self.assertEqual(self.app.commands.get_nowait(), ('stop', None))
        self.app.process = None

    def test_monitor_hotkey_rebinds_after_window_handle_changes(self):
        old_user32 = self.app._user32
        register = Mock(return_value=True)
        unregister = Mock(return_value=True)
        self.app._user32 = SimpleNamespace(RegisterHotKey=register, UnregisterHotKey=unregister)
        self.app.monitor_hotkey = 'Ctrl+Alt+M'
        self.app.monitor_hotkey_hwnd = 123
        try:
            self.app.refresh_monitor_hotkey_binding()
            self.assertEqual(self.app.monitor_hotkey_hwnd, int(self.app.winId()))
            self.assertEqual(unregister.call_args.args[0].value, 123)
            self.assertEqual(register.call_count, 1)
        finally:
            self.app.monitor_hotkey = ''
            self.app.monitor_hotkey_hwnd = None
            self.app._user32 = old_user32

    def test_settings_language_popup_row_height_matches_native_menu(self):
        self.app.show_settings('外观')
        self.app.language_choice.showPopup()
        self.qt.processEvents()
        view = self.app.language_choice.view()
        self.assertTrue(view.isVisible())
        self.assertGreaterEqual(view.sizeHintForRow(0), 36)
        self.app.language_choice.hidePopup()

    def test_monitoring_continues_in_settings_and_languages(self):
        self.app.show_settings('通用')
        frame = self.frame()
        process = self.app.process = Mock()
        process.is_alive.return_value = True
        self.app.frames, self.app.events, self.app.commands = queue.Queue(), queue.Queue(), queue.Queue()
        self.app.frames.put(frame)
        self.app.poll()
        self.assertIs(self.app.last_frame, frame)
        self.assertEqual(self.app.status.text(), '监测运行中')
        self.app.language_choice.setCurrentIndex(self.app.language_choice.findData('en'))
        self.app.theme_choice.setCurrentIndex(self.app.theme_choice.findData('light'))
        self.assertIs(self.app.process, process)
        self.assertIs(self.app.last_frame, frame)
        self.assertEqual(self.app.status.text(), 'Monitoring active')
        self.assertEqual(self.app.theme.resolved, 'light')
        self.app.close_settings()
        self.assertFalse(self.app.canvas.picture.isNull())
        self.assertEqual(self.app.commands.qsize(), 0)

    def test_minimum_width_all_languages_and_pages(self):
        from PySide6.QtCore import QPoint
        self.app.resize(640, 520)
        for language in ('zh-cn', 'zh-tw', 'en', 'ja', 'ko'):
            self.app.language.set_language(language)
            for page in self.app.page_names:
                self.app.show_settings(page)
                self.qt.processEvents()
                self.assertLessEqual(self.app.tabs.tabRect(self.app.tabs.count() - 1).right(),
                                     self.app.tabs.width(), language)
                scroll = self.app.settings_stack.currentWidget()
                self.assertEqual(scroll.horizontalScrollBar().maximum(), 0, (language, page))
                self.assertLessEqual(self.app.width(), 640, (language, page))
                for button in (self.app.header_refresh_button, self.app.back_button):
                    self.assertLessEqual(button.mapTo(self.app, QPoint(button.width(), 0)).x(), 640)

    def test_start_without_camera_opens_settings(self):
        self.app.start_button.click()
        self.assertIsNone(self.app.process)
        self.assertEqual(self.app.status.text(), '请选择摄像头')
        self.assertTrue(self.app.camera.isVisible())

    def test_long_restore_error_remains_scrollable(self):
        from PySide6.QtCore import QPoint
        self.app.resize(640, 520)
        self.app.show_settings('窗口保护')
        self.app.set_window_status('恢复错误详情。'*150, 'warning')
        self.qt.processEvents()
        scroll = self.app.settings_stack.currentWidget()
        self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
        scroll.ensureWidgetVisible(self.app.restore_window_button)
        self.qt.processEvents()
        button = self.app.restore_window_button
        bottom = button.mapTo(scroll.viewport(), QPoint(0, button.height())).y()
        self.assertLessEqual(bottom, scroll.viewport().height())

    def test_cleanup_releases_queues_and_restores_controls(self):
        process = self.app.process = Mock()
        queues = self.app.commands, self.app.frames, self.app.events = Mock(), Mock(), Mock()
        self.app.last_frame = self.frame()
        self.app.cleanup()
        process.join.assert_called_once()
        process.close.assert_called_once()
        for channel in queues:
            channel.close.assert_called_once()
            channel.cancel_join_thread.assert_called_once()
        self.assertIsNone(self.app.process)
        self.assertIsNone(self.app.last_frame)
        self.assertTrue(self.app.camera.isEnabled())
        self.assertTrue(self.app.start_button.isVisible())
        self.assertFalse(self.app.stop_button.isVisible())

    def test_tray_actions_use_qt_and_hidden_panel_can_be_restored(self):
        from PySide6.QtWidgets import QSystemTrayIcon
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.skipTest('System tray unavailable in this desktop session')
        self.app.setup_tray()
        self.assertIsInstance(self.app.tray, QSystemTrayIcon)
        self.app.hide_to_tray()
        self.assertFalse(self.app.isVisible())
        actions = self.app.tray.contextMenu().actions()
        actions[0].trigger()
        self.assertTrue(self.app.isVisible())
        with patch.object(self.app.window_guard, 'restore') as restore:
            actions[2].trigger()
            restore.assert_called_once()
        self.app.hide_to_tray()
        actions[3].trigger()
        self.assertTrue(self.app.closed)

    def test_close_hides_but_escape_exits(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        self.app.tray = Mock()
        self.app.tray.isVisible.return_value = True
        self.app.close()
        self.assertFalse(self.app.isVisible())
        self.assertFalse(self.app.closed)
        self.app.show_panel()
        self.qt.processEvents()
        from PySide6.QtWidgets import QToolButton
        next(button for button in self.app.findChildren(QToolButton)
             if button.property('role') == 'close').click()
        self.assertFalse(self.app.isVisible())
        self.assertFalse(self.app.closed)
        self.app.show_panel()
        self.qt.processEvents()
        QTest.keyClick(self.app, Qt.Key.Key_Escape)
        self.assertTrue(self.app.closed)

    def test_start_pause_calibrate_commands(self):
        # 退出会保存设备名；模拟设备也必须提供枚举接口的 name，避免 Qt 回调异常。
        self.app.cameras = [SimpleNamespace(index=3, name='Camera')]
        self.app.camera.addItem('Camera', 3)
        process = Mock()
        with patch('app.mp.Process', return_value=process), patch('app.mp.Queue', side_effect=queue.Queue):
            self.app.start_button.click()
        process.start.assert_called_once()
        self.assertFalse(self.app.camera.isEnabled())
        self.assertFalse(self.app.start_button.isVisible())
        self.assertTrue(self.app.stop_button.isVisible())
        self.app.last_frame = self.frame()
        self.app.owner_choice.addItem('Person #7', 7)
        self.app.select_from_list()
        self.assertEqual(self.app.commands.get_nowait(), ('owner', 7))
        self.app.stop_button.click()
        self.assertEqual(self.app.commands.get_nowait(), ('stop', None))
        self.assertIsNone(self.app.last_frame)
        self.assertFalse(self.app.owner_choice.isVisible())

    def test_system_pause_waits_for_unlock_and_display_then_resumes(self):
        self.app.process = Mock()
        self.app.commands, self.app.frames, self.app.events = Mock(), Mock(), Mock()
        self.app.system_state_changed(locked=True)
        self.app.system_state_changed(display_off=True)
        self.assertTrue(self.app.auto_resume)
        self.app.commands.put.assert_called_once_with(('stop', None))
        with patch.object(self.app, 'start') as start:
            self.app.system_state_changed(display_off=False)
            self.app.cleanup()
            start.assert_not_called()
            self.app.system_state_changed(locked=False)
            start.assert_called_once_with()
        self.assertFalse(self.app.auto_resume)

    def test_manual_pause_cancels_system_resume(self):
        self.app.process = Mock()
        self.app.commands, self.app.frames, self.app.events = Mock(), Mock(), Mock()
        self.app.system_state_changed(locked=True)
        self.app.stop()
        self.app.cleanup()
        with patch.object(self.app, 'start') as start:
            self.app.system_state_changed(locked=False)
            start.assert_not_called()

    def test_system_events_do_not_start_manually_paused_monitoring(self):
        with patch.object(self.app, 'start') as start:
            self.app.system_state_changed(display_off=True)
            self.app.system_state_changed(display_off=False)
            self.app.system_state_changed(locked=True)
            self.app.system_state_changed(locked=False)
            start.assert_not_called()

    def test_native_windows_messages_update_system_state(self):
        import ctypes
        from ctypes import wintypes
        from app import WM_POWERBROADCAST, WM_WTSSESSION_CHANGE, PBT_POWERSETTINGCHANGE, SESSION_DISPLAY_STATUS

        message = wintypes.MSG()
        message.message, message.wParam = WM_WTSSESSION_CHANGE, 7
        with patch.object(self.app, 'system_state_changed') as changed:
            self.app.nativeEvent(b'windows_generic_MSG', ctypes.addressof(message))
            changed.assert_called_once_with(locked=True)
            changed.reset_mock()
            setting = ctypes.create_string_buffer(SESSION_DISPLAY_STATUS + (4).to_bytes(4, 'little') + (0).to_bytes(4, 'little'))
            message.message, message.wParam = WM_POWERBROADCAST, PBT_POWERSETTINGCHANGE
            message.lParam = ctypes.addressof(setting)
            self.app.nativeEvent(b'windows_generic_MSG', ctypes.addressof(message))
            changed.assert_called_once_with(display_off=True)

    def test_calibration_click_maps_letterbox_and_smallest_box(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        tracks = [{'id': 2, 'box': (.1, .1, .9, .9), 'facing': False},
                  {'id': 3, 'box': (.4, .4, .6, .6), 'facing': True}]
        self.app.last_frame = self.frame(None, tracks)
        self.app.render()
        self.qt.processEvents()
        self.assertTrue(self.app.owner_choice.isVisible())
        rect = self.app.canvas.image_rect
        with patch.object(self.app, 'calibrate') as calibrate:
            # Signal was connected to the original bound method; inspect emitted IDs directly.
            selected = []
            self.app.canvas.selected.connect(selected.append)
            QTest.mouseClick(self.app.canvas, Qt.MouseButton.LeftButton, pos=rect.center().toPoint())
            self.assertEqual(selected, [])
            self.app.owner_select_button.click()
            QTest.mouseClick(self.app.canvas, Qt.MouseButton.LeftButton, pos=rect.center().toPoint())
            self.assertEqual(selected, [3])
            QTest.mouseClick(self.app.canvas, Qt.MouseButton.LeftButton, pos=QPoint(1, 1))
            self.assertEqual(selected, [3])
        self.app.last_frame['owner'] = 3
        self.app.render()
        self.assertFalse(self.app.owner_choice.isVisible())

    def test_quick_selector_refresh_and_sync(self):
        targets = [SimpleNamespace(hwnd=123, title='First'), SimpleNamespace(hwnd=456, title='Second')]
        with patch.object(self.app.window_guard, 'windows', return_value=targets):
            self.app.quick_window_choice.opening.emit()
        with patch.object(self.app.window_guard, 'select') as select:
            self.app.quick_window_choice.activated.emit(2)
            select.assert_called_once_with(targets[1])
        self.assertEqual(self.app.window_choice.currentIndex(), 2)
        self.assertEqual(self.app.quick_window_choice.currentIndex(), 2)

    def test_target_window_can_be_cleared_from_either_selector(self):
        target = SimpleNamespace(hwnd=123, title='First')
        guard = self.app.window_guard
        guard.selected = target
        with patch.object(guard, 'windows', return_value=[target]), patch.object(guard, 'valid', return_value=True):
            self.app.refresh_windows()
        self.assertEqual(self.app.window_choice.itemText(0), '取消选择')
        self.assertEqual(self.app.quick_window_choice.itemText(0), '取消选择')
        self.app.auto_hide.setChecked(True)
        with patch.object(guard, 'select', side_effect=lambda window: setattr(guard, 'selected', window)) as select:
            self.app.quick_window_choice.activated.emit(0)
            select.assert_called_once_with(None)
        self.assertIsNone(guard.selected)
        self.assertFalse(self.app.auto_hide.isChecked())
        self.assertEqual(self.app.window_choice.currentIndex(), -1)
        self.assertEqual(self.app.quick_window_choice.currentIndex(), -1)

    def test_failed_target_clear_keeps_selection(self):
        target = SimpleNamespace(hwnd=123, title='First')
        guard = self.app.window_guard
        guard.selected = target
        with patch.object(guard, 'windows', return_value=[target]), patch.object(guard, 'valid', return_value=True):
            self.app.refresh_windows()
            with patch.object(guard, 'select', side_effect=OSError('恢复失败')):
                self.app.window_choice.activated.emit(0)
        self.assertIs(guard.selected, target)
        self.assertEqual(self.app.window_choice.currentIndex(), 1)
        self.assertEqual(self.app.quick_window_choice.currentIndex(), 1)
        self.assertEqual(self.app.window_status.text(), '恢复失败')

    def test_combo_keyboard_and_slider_actions(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        self.app.show_settings('监测')
        self.app.camera.addItems(['First', 'Second'])
        self.app.camera.showPopup()
        self.qt.processEvents()
        self.assertTrue(self.app.camera.view().isVisible())
        QTest.keyClick(self.app.camera, Qt.Key.Key_Down)
        QTest.keyClick(self.app.camera, Qt.Key.Key_Enter)
        self.app.camera.hidePopup()
        self.assertEqual(self.app.camera.currentIndex(), 1)
        self.app.show_opacity_settings()
        self.app.entry_alpha.setValue(100)
        QTest.keyClick(self.app.entry_alpha, Qt.Key.Key_Right)
        self.assertEqual(self.app.entry_alpha.value(), 101)

    def test_silent_corner_notification_replacement(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication, QSystemTrayIcon
        self.assertEqual(self.app.news_timer.interval(), 60 * 60 * 1000)
        self.assertEqual(self.app.reminder_mode.currentData(), 'text')
        self.app.tray = Mock()
        self.app.tray.isVisible.return_value = True
        self.app.news_identity_ready = True
        self.app.news_headlines = [('国内新闻标题', 'https://www.chinanews.com.cn/gn/2026/09-16/1.shtml')]
        with patch.object(QApplication, 'screens', return_value=[QApplication.primaryScreen()]), \
             patch.object(QSystemTrayIcon, 'supportsMessages', return_value=True), \
             patch('app.news_notifications_enabled', return_value=True):
            with patch('app.send_news_toast') as send_news:
                self.app.test_reminder_button.click()
            send_news.assert_called_once_with(
                '中国新闻网 · 国内新闻', '国内新闻标题',
                on_click='https://www.chinanews.com.cn/gn/2026/09-16/1.shtml',
                audio={'silent': 'true'}, app_id='BehindWatch.News')
            self.app.news_headlines = []
            self.app.notify('有人可能看向屏幕')
            self.app.tray.showMessage.assert_called_with(
                '系统状态', '有一项后台任务需要关注', QSystemTrayIcon.MessageIcon.NoIcon, 7000)
        self.assertIsNone(self.app.toast)
        self.app.news_identity_ready = True
        with patch.object(QSystemTrayIcon, 'supportsMessages', return_value=True), \
             patch('app.news_notifications_enabled', return_value=False):
            self.app.test_reminder_button.click()
        self.assertIsNotNone(self.app.toast)
        self.app.dismiss_toast()
        self.app.tray = None
        self.app.reminder_mode.setCurrentIndex(0)
        self.app.test_reminder_button.click()
        self.assertEqual(self.app.toast.width(), 28)
        self.app.notify('有人可能看向屏幕')
        self.assertEqual(self.app.toast.width(), 28)
        self.assertTrue(self.app.toast.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
        self.assertTrue(self.app.toast.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus)
        self.app.dismiss_toast()
        self.assertIsNone(self.app.toast)

    def test_notification_appears_on_each_screen(self):
        from PySide6.QtCore import QRect
        from PySide6.QtWidgets import QApplication
        self.app.reminder_mode.setCurrentIndex(0)
        screens = [SimpleNamespace(availableGeometry=lambda: QRect(0, 0, 1920, 1080)),
                   SimpleNamespace(availableGeometry=lambda: QRect(1920, 0, 1920, 1080))]
        with patch.object(QApplication, 'screens', return_value=screens):
            self.app.test_reminder_button.click()
        self.assertEqual(len(self.app.toasts), 2)
        self.assertEqual([toast.x() for toast in self.app.toasts], [1875, 3795])
        self.app.dismiss_toast()
        self.assertFalse(self.app.toasts)

    def test_system_notification_adds_corner_dot_only_on_secondary_screen(self):
        from PySide6.QtCore import QRect
        from PySide6.QtWidgets import QApplication, QSystemTrayIcon

        self.app.tray = Mock()
        self.app.tray.isVisible.return_value = True
        self.app.news_identity_ready = True
        self.app.news_headlines = [('国内新闻标题', 'https://www.chinanews.com.cn/gn/2026/09-16/1.shtml')]
        primary = SimpleNamespace(availableGeometry=lambda: QRect(0, 0, 1920, 1080))
        secondary = SimpleNamespace(availableGeometry=lambda: QRect(1920, 0, 1920, 1080))
        with patch.object(QApplication, 'screens', return_value=[primary, secondary]), \
             patch.object(QApplication, 'primaryScreen', return_value=primary), \
             patch.object(QSystemTrayIcon, 'supportsMessages', return_value=True), \
             patch('app.news_notifications_enabled', return_value=True), \
             patch('app.send_news_toast') as send_news:
            self.app.test_reminder_button.click()
        send_news.assert_called_once()
        self.assertEqual(len(self.app.toasts), 1)
        self.assertEqual(self.app.toast.x(), 3795)
        self.app.dismiss_toast()

    def test_failed_restore_keeps_window_and_shows_error(self):
        with patch.object(self.app.window_guard, 'restore', side_effect=OSError('恢复失败')):
            self.assertFalse(self.app.restore_window())
            self.app.quit()
        self.assertFalse(self.app.closed)
        self.assertTrue(self.app.isVisible())
        self.assertTrue(self.app.window_status.isVisible())
        self.assertEqual(self.app.window_status.text(), '恢复失败')

    def test_failed_opacity_restore_blocks_exit(self):
        with patch.object(self.app.window_guard, 'restore_opacity', side_effect=OSError('opacity failure')):
            self.app.quit()
        self.assertFalse(self.app.closed)
        self.assertEqual(self.app.current_settings_page, '窗口保护')

    def test_hiding_requires_fresh_calibrated_other_person(self):
        guard = self.app.window_guard
        with patch.object(guard, 'selected', object()), patch.object(guard, 'hide', return_value=True) as hide:
            self.app.last_frame = self.frame(1, [{'id': 2, 'moving': True}])
            self.app.protect_window()
            hide.assert_not_called()
            self.app.auto_hide.setChecked(True)
            for changes in ({'owner': None}, {'tracks': [{'id': 1}]}, {'at': time.monotonic()-2}):
                original = self.app.last_frame.copy()
                self.app.last_frame.update(changes)
                self.app.protect_window()
                hide.assert_not_called()
                self.app.last_frame = original
            for state in ('stopping', 'failed'):
                setattr(self.app, state, True)
                self.app.protect_window()
                hide.assert_not_called()
                setattr(self.app, state, False)
            self.app.protect_window()
            hide.assert_called_once()
            self.assertTrue(self.app.recovery_button.isVisible())

    def test_auto_hide_waits_for_target_and_cancel_is_preserved(self):
        target = SimpleNamespace(hwnd=123, title='Test')
        guard = self.app.window_guard
        self.app.auto_hide.setChecked(True)
        self.app.toggle_window_guard()
        self.assertIn('等待选择目标窗口', self.app.window_status.text())
        self.app.last_frame = self.frame(1, [{'id': 2, 'moving': True}])
        with patch.object(guard, 'hide', return_value=True) as hide:
            self.app.protect_window()
            hide.assert_not_called()
            self.app.windows = [target]
            self.app.window_choice.addItem('Test')
            with patch.object(guard, 'select', side_effect=lambda w: setattr(guard, 'selected', w)), patch.object(guard, 'valid', return_value=True):
                self.app.select_window(1)
            hide.assert_called_once()
            self.assertTrue(self.app.auto_hide.isChecked())
        guard.selected = None
        self.app.auto_hide.setChecked(False)
        self.app.toggle_window_guard()
        with patch.object(guard, 'select'), patch.object(self.app, 'protect_window') as protect:
            self.app.select_window(1)
            protect.assert_not_called()

    def test_hide_and_opacity_failures_disable_retries(self):
        self.app.auto_hide.setChecked(True)
        self.app.last_frame = self.frame(1, [{'id': 2, 'moving': True}])
        with patch.object(self.app.window_guard, 'selected', object()), patch.object(self.app.window_guard, 'hide', side_effect=OSError('hide failed')):
            self.app.protect_window()
        self.assertFalse(self.app.auto_hide.isChecked())
        self.app.mouse_opacity.setChecked(True)
        with patch.object(self.app.window_guard, 'valid', return_value=True), patch.object(self.app.window_guard, 'update_opacity', side_effect=OSError('opacity failed')), patch.object(self.app.window_guard, 'restore_opacity') as restore:
            self.app.update_window_opacity()
            restore.assert_called_once()
        self.assertFalse(self.app.mouse_opacity.isChecked())

    def test_opacity_can_be_enabled_before_selecting_window(self):
        target = SimpleNamespace(hwnd=123, title='Test')
        guard = self.app.window_guard
        self.app.mouse_opacity.setChecked(True)
        with patch.object(guard, 'update_opacity') as update:
            self.app.toggle_opacity()
            self.app.exit_alpha.setValue(80)
            update.assert_not_called()
            self.assertTrue(self.app.mouse_opacity.isChecked())
            self.assertIn('等待选择目标窗口', self.app.window_status.text())
            self.app.windows = [target]
            self.app.window_choice.addItem('Test')
            with patch.object(guard, 'select', side_effect=lambda w: setattr(guard, 'selected', w)), patch.object(guard, 'valid', return_value=True):
                self.app.select_window(1)
            update.assert_called_once_with(255, 80)
            self.assertTrue(self.app.mouse_opacity.isChecked())

    def test_opacity_waits_when_previous_target_closed(self):
        guard = self.app.window_guard
        guard.selected = SimpleNamespace(hwnd=123)
        self.app.mouse_opacity.setChecked(True)
        with patch.object(guard, 'valid', return_value=False), patch.object(guard, 'update_opacity') as update:
            self.app.toggle_opacity()
            self.app.exit_alpha.setValue(80)
        update.assert_not_called()
        self.assertTrue(self.app.mouse_opacity.isChecked())
        self.assertIn('等待选择目标窗口', self.app.window_status.text())

    def test_native_window_hide_refresh_restore_and_opacity(self):
        import ctypes
        from ctypes import wintypes
        from PySide6.QtWidgets import QWidget
        from PySide6.QtTest import QTest
        target = QWidget()
        target.setWindowTitle('BehindWatch isolated protection test')
        target.show()
        self.qt.processEvents()
        guard = self.app.window_guard
        hwnd = int(target.winId())
        guard.select(guard.describe(hwnd))
        original = guard.api.GetWindowLongW(hwnd, -20)
        # 沙箱会话可能无法读取桌面鼠标位置；固定光标只隔离输入，透明度和显隐仍调用真实 HWND。
        cursor = patch.object(guard.api, 'GetCursorPos', return_value=True)
        cursor.start()
        try:
            self.app.entry_alpha.setValue(80)
            self.app.exit_alpha.setValue(80)
            self.app.mouse_opacity.setChecked(True)
            self.app.toggle_opacity()
            color, value, flags = wintypes.DWORD(), wintypes.BYTE(), wintypes.DWORD()
            self.assertTrue(guard.api.GetLayeredWindowAttributes(hwnd, ctypes.byref(color), ctypes.byref(value), ctypes.byref(flags)))
            self.assertEqual(value.value, 80)
            self.app.auto_hide.setChecked(True)
            self.app.last_frame = self.frame(1, [{'id': 2, 'moving': True}])
            self.app.protect_window()
            QTest.qWait(50)
            self.assertFalse(guard.api.IsWindowVisible(hwnd))
            self.app.refresh_windows()
            self.assertEqual(self.app.windows[self.app.window_choice.currentIndex() - 1].hwnd, hwnd)
            self.app.stop()
            self.assertFalse(guard.api.IsWindowVisible(hwnd))
            self.app.restore_window()
            QTest.qWait(50)
            self.assertTrue(guard.api.IsWindowVisible(hwnd))
            self.assertFalse(self.app.auto_hide.isChecked())
            self.app.mouse_opacity.setChecked(False)
            self.app.toggle_opacity()
            self.assertEqual(guard.api.GetWindowLongW(hwnd, -20) & 0x80000, original & 0x80000)
            guard.hide()
            QTest.qWait(50)
            self.app.close_window_on_exit.setChecked(False)
            self.app.quit()
            QTest.qWait(50)
            self.assertTrue(guard.api.IsWindowVisible(hwnd))
            self.assertTrue(self.app.closed)
        finally:
            guard.restore_opacity()
            guard.restore()
            target.close()
            target.deleteLater()
            cursor.stop()

    def test_dependency_failure_is_distinct(self):
        with patch.dict(sys.modules, {'cv2': None}):
            self.app.refresh_cameras()
        self.assertEqual(self.app.status.text(), '运行依赖缺失')

    def test_update_success_error_no_release_and_busy(self):
        release = {'version': '1.2.3', 'notes': '<script>plain text</script>', 'url': 'https://github.com/zensoku142/BehindWatch/releases/tag/v1.2.3', 'available': True}
        with patch('app.threading.Thread') as thread:
            self.app.check_updates()
            self.app.check_updates()
            thread.assert_called_once()
        self.assertFalse(self.app.check_button.isEnabled())
        self.app.update_results.put((release, None))
        self.app.poll()
        self.assertTrue(self.app.check_button.isEnabled())
        self.assertIn('1.2.3', self.app.update_status.text())
        self.assertEqual(self.app.release_notes.toPlainText(), release['notes'])
        with patch('app.QDesktopServices.openUrl') as open_url:
            self.app.open_download()
            self.assertEqual(open_url.call_args.args[0].toString(), release['url'])
        self.app.finish_update(None, 'offline')
        self.assertIn('offline', self.app.update_status.text())
        self.app.finish_update(None, None)
        self.assertEqual(self.app.update_status.text(), '暂无正式版本')
        self.assertFalse(self.app.release_notes.isVisible())

    def test_auto_update_interval_and_preference_failure(self):
        with patch.object(self.app, 'check_updates') as check:
            self.app.maybe_check_updates()
            check.assert_not_called()
            self.app.preferences.update(auto_update=True, last_check=time.time())
            self.app.maybe_check_updates()
            check.assert_not_called()
            self.app.preferences['last_check'] = 0
            self.app.maybe_check_updates()
            check.assert_called_once()
        with patch('app.save_preferences', side_effect=OSError('read only')):
            self.app.save_preferences()
        self.app.language.set_language('en')
        self.assertIn('read only', self.app.preference_status.text())

    def test_translated_person_selection_keeps_ids_after_track_count_changes(self):
        self.app.process = Mock()
        self.app.process.is_alive.return_value = True
        self.app.frames, self.app.events, self.app.commands = queue.Queue(), queue.Queue(), queue.Queue()
        for identities in ([1, 2, 3], [8]):
            tracks = [{'id': i, 'box': (.1,.1,.3,.3), 'facing': False} for i in identities]
            self.app.frames.put(self.frame(None, tracks))
            self.app.poll()
        self.app.language.set_language('ja')
        self.assertEqual(self.app.owner_choice.count(), 1)
        self.assertEqual(self.app.owner_choice.currentData(), 8)
        self.app.select_from_list()
        self.assertEqual(self.app.commands.get_nowait(), ('owner', 8))

    def test_timeout_and_stuck_stop_terminate_only_owned_process(self):
        self.app.process = process = Mock()
        process.is_alive.return_value = True
        self.app.frames, self.app.events, self.app.commands = queue.Queue(), queue.Queue(), queue.Queue()
        self.app.last_received = time.monotonic()-31
        self.app.poll()
        self.assertTrue(self.app.failed)
        self.assertTrue(self.app.stopping)
        self.assertEqual(self.app.commands.get_nowait(), ('stop', None))
        self.app.stop_at = time.monotonic()-4
        self.app.poll()
        process.terminate.assert_called_once()


if __name__ == '__main__':
    unittest.main()
