"""Browser detection and native clipping tests; only test-owned windows are changed."""
import sys
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pywintypes
import win32gui
from core.browser_top import detect_browser_top
from core.browser_crop import BrowserCrop, get_window_backdrop, set_window_backdrop, get_scrollbar_crop_width
from core.window_guard import WindowGuard


class DetectionTests(unittest.TestCase):
    def test_dynamic_container_height_and_electron_exclusion(self):
        uia = SimpleNamespace(TreeScope_Descendants=4, UIA_ClassNamePropertyId=1)
        automation = Mock()
        container = Mock(CurrentBoundingRectangle=SimpleNamespace(top=140, bottom=227))
        browser = Mock()
        browser.FindFirst.return_value = container
        window = automation.ElementFromHandle.return_value
        window.FindFirst.return_value = browser
        with patch('core.browser_top.win32gui.IsWindow', return_value=True), \
             patch('core.browser_top.win32gui.IsIconic', return_value=False), \
             patch('core.browser_top.win32gui.GetWindowRect', return_value=(10, 100, 900, 800)), \
             patch('core.browser_top.win32gui.GetClassName', return_value='Chrome_WidgetWin_1'):
            self.assertEqual(detect_browser_top(automation, uia, 1)[1], 127)
            container.CurrentBoundingRectangle.bottom = 260
            self.assertEqual(detect_browser_top(automation, uia, 1)[1], 160)
            window.FindFirst.return_value = None
            self.assertIsNone(detect_browser_top(automation, uia, 1)[1])

    def test_scrollbar_width_includes_dpi_and_border(self):
        with patch('core.browser_crop.ctypes.windll.user32.GetDpiForWindow', return_value=144), \
             patch('core.browser_crop.ctypes.windll.user32.GetSystemMetricsForDpi', return_value=26), \
             patch('core.browser_crop.win32gui.GetWindowRect', return_value=(10, 100, 900, 800)), \
             patch('core.browser_crop.win32gui.GetClientRect', return_value=(0, 0, 874, 680)), \
             patch('core.browser_crop.win32gui.ClientToScreen', return_value=(892, 792)):
            self.assertEqual(get_scrollbar_crop_width(1), 34)


class NativeCropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qt = QApplication.instance() or QApplication([])
        cls.qt.setQuitOnLastWindowClosed(False)

    def setUp(self):
        from PySide6.QtWidgets import QWidget
        self.window = QWidget()
        self.window.resize(400, 300)
        self.window.show()
        self.qt.processEvents()
        self.hwnd = int(self.window.winId())
        self.guard = WindowGuard()
        self.guard.select(self.guard.describe(self.hwnd))
        self.crop = self.guard.browser_crop = BrowserCrop(self.guard)
        self.crop.rect = win32gui.GetWindowRect(self.hwnd)
        self.crop.height = 80

    def tearDown(self):
        self.crop.close()
        self.guard.restore_opacity()
        self.guard.restore()
        self.window.close()
        self.window.deleteLater()
        self.qt.processEvents()

    def contains(self, x, y):
        region = win32gui.CreateRectRgnIndirect((0, 0, 0, 0))
        try:
            try:
                import ctypes
                ctypes.windll.kernel32.SetLastError(0)
                if not win32gui.GetWindowRgn(self.hwnd, region):
                    return True
            except pywintypes.error as exc:
                if exc.winerror == 0:
                    return True
                raise
            return win32gui.PtInRegion(region, x, y)
        finally:
            win32gui.DeleteObject(region)

    def test_top_scrollbar_independent_and_restore(self):
        width = self.crop.rect[2]-self.crop.rect[0]
        with patch('core.browser_crop.get_scrollbar_crop_width', return_value=20):
            self.crop.apply(True, True)
            self.assertFalse(self.contains(20, 20))
            self.assertFalse(self.contains(width-5, 100))
            self.assertTrue(self.contains(20, 100))
            self.crop.apply(False, True)
            self.assertTrue(self.contains(width-5, 20))
            self.assertFalse(self.contains(width-5, 100))
            self.crop.apply(True, False)
            self.assertFalse(self.contains(20, 20))
            self.assertTrue(self.contains(width-5, 100))
            self.crop.reset()
            self.assertTrue(self.contains(20, 20))

    def test_original_region_and_backdrop_restored_on_selection_clear(self):
        win32gui.SetWindowRgn(self.hwnd, win32gui.CreateRectRgnIndirect((10, 10, 250, 250)), True)
        backdrop = get_window_backdrop(self.hwnd)
        if backdrop is not None:
            set_window_backdrop(self.hwnd, 2)
        self.crop.apply(True, False)
        self.assertFalse(self.contains(20, 20))
        if backdrop is not None:
            self.assertEqual(get_window_backdrop(self.hwnd), 1)
            set_window_backdrop(self.hwnd, 2)
            self.crop.apply(True, False)
            self.assertEqual(get_window_backdrop(self.hwnd), 1)
        self.guard.select(None)
        self.assertTrue(self.contains(20, 20))
        self.assertFalse(self.contains(5, 5))
        if backdrop is not None:
            self.assertEqual(get_window_backdrop(self.hwnd), 2)

    def test_stale_bounds_restore_instead_of_cropping_content(self):
        self.crop.apply(True, False)
        self.crop.rect = (0, 0, 1, 1)
        self.crop.apply(True, False)
        self.assertTrue(self.contains(20, 20))

    def test_cropped_area_uses_mouse_outside_opacity(self):
        import ctypes
        from ctypes import wintypes
        self.crop.apply(True, False)
        left, top, _, _ = self.crop.rect
        def cursor(output):
            output._obj.x, output._obj.y = left+20, top+20
            return True
        with patch.object(self.guard.api, 'GetCursorPos', side_effect=cursor):
            self.guard.update_opacity(255, 90)
        color, alpha, flags = wintypes.DWORD(), wintypes.BYTE(), wintypes.DWORD()
        self.assertTrue(self.guard.api.GetLayeredWindowAttributes(self.hwnd, ctypes.byref(color), ctypes.byref(alpha), ctypes.byref(flags)))
        self.assertEqual(alpha.value, 90)
        self.guard.hide()
        self.qt.processEvents()
        self.guard.update_opacity(255, 255)
        self.assertFalse(win32gui.IsWindowVisible(self.hwnd))
        self.guard.restore()
        self.qt.processEvents()
        self.assertFalse(self.contains(20, 20))

    def test_closed_or_reused_target_is_never_restored(self):
        self.crop.apply(True, False)
        with patch.object(self.guard, 'describe', return_value=None), \
             patch('core.browser_crop.win32gui.SetWindowRgn') as restore:
            self.crop.restore()
            restore.assert_not_called()

    def test_restore_failure_keeps_original_region_for_retry(self):
        self.crop.apply(True, False)
        with patch('core.browser_crop.win32gui.SetWindowRgn', side_effect=pywintypes.error(5, 'SetWindowRgn', 'Denied')):
            with self.assertRaises(OSError):
                self.guard.select(None)
        self.assertIsNotNone(self.crop.target)
        self.assertIsNotNone(self.guard.selected)
        self.crop.restore()
        self.assertTrue(self.contains(20, 20))

    def test_old_async_result_cannot_reapply_after_toggle(self):
        self.guard.selected = replace(self.guard.selected, class_name='Chrome_WidgetWin_1')
        self.crop.options = (self.guard.selected, True, False)
        self.crop.thread = Mock(ident=1)
        self.crop.pending = (self.crop.generation, time.monotonic())
        self.crop.results.put((self.crop.generation, self.crop.rect, 80))
        self.crop.reset()
        with patch.object(self.guard, 'valid', return_value=True):
            self.crop.update(True, False)
        self.assertIsNone(self.crop.height)
        self.assertTrue(self.contains(20, 20))

    def test_timeout_restores_and_late_result_is_discarded(self):
        self.crop.apply(True, False)
        self.guard.selected = replace(self.guard.selected, class_name='Chrome_WidgetWin_1')
        self.crop.options = (self.guard.selected, True, False)
        self.crop.thread = Mock(ident=1)
        self.crop.pending = (self.crop.generation, time.monotonic()-5)
        with patch.object(self.guard, 'valid', return_value=True):
            message = self.crop.update(True, False)
            self.assertIn('暂未响应', message)
            self.assertTrue(self.contains(20, 20))
            self.crop.results.put((self.crop.generation, win32gui.GetWindowRect(self.hwnd), 80))
            self.crop.update(True, False)
        self.assertIsNone(self.crop.height)
        self.assertTrue(self.contains(20, 20))


if __name__ == '__main__':
    unittest.main()
