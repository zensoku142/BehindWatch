import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.window_guard import Window, WindowGuard


class WindowGuardTests(unittest.TestCase):
    def setUp(self):
        self.guard = WindowGuard.__new__(WindowGuard)
        self.guard.api = Mock()
        self.target = Window(123, 42, 43, '窗口', 'TestWindow')
        self.guard.selected = self.target
        self.guard.hidden = False
        self.guard.original_opacity = None
        self.guard.browser_crop = None
        self.guard.describe = Mock(return_value=self.target)

    def test_hide_and_restore_do_not_change_other_window_attributes(self):
        self.assertTrue(self.guard.hide())
        self.assertTrue(self.guard.hidden)
        self.guard.restore()
        self.assertFalse(self.guard.hidden)
        self.assertEqual([c.args for c in self.guard.api.ShowWindowAsync.call_args_list], [(123, 0), (123, 8)])

    def test_never_restore_window_hidden_by_another_program(self):
        self.guard.api.IsWindowVisible.return_value = False
        self.assertFalse(self.guard.hide())
        self.guard.restore()
        self.guard.api.ShowWindowAsync.assert_not_called()

    def test_changed_title_does_not_invalidate_target(self):
        self.guard.describe.return_value = Window(123, 42, 43, '新标签标题', 'TestWindow')
        self.assertTrue(self.guard.valid())

    def test_closed_or_reused_handle_is_not_touched(self):
        for replacement in (None, Window(123, 99, 43, '其他程序', 'TestWindow')):
            with self.subTest(replacement=replacement):
                self.guard.selected = self.target
                self.guard.hidden = True
                self.guard.describe.return_value = replacement
                self.guard.restore()
                with self.assertRaises(OSError):
                    self.guard.hide()
                self.guard.api.ShowWindowAsync.assert_not_called()

    def test_restore_failure_keeps_recovery_target(self):
        self.guard.hidden = True
        self.guard.api.ShowWindowAsync.return_value = False
        with self.assertRaises(OSError):
            self.guard.select(Window(999, 50, 51, '另一个窗口', 'TestWindow'))
        self.assertEqual(self.guard.selected, self.target)
        self.assertTrue(self.guard.hidden)

    def test_clear_selection_restores_window_and_opacity(self):
        self.guard.hidden = True
        self.guard.original_opacity = (True, 0, 100, 2)
        self.guard.select(None)
        self.guard.api.SetLayeredWindowAttributes.assert_called_once_with(123, 0, 100, 2)
        self.guard.api.ShowWindowAsync.assert_called_once_with(123, 8)
        self.assertIsNone(self.guard.selected)
        self.assertFalse(self.guard.hidden)

    def test_failed_hide_is_not_recorded_as_success(self):
        self.guard.api.ShowWindowAsync.return_value = False
        with self.assertRaises(OSError):
            self.guard.hide()
        self.assertFalse(self.guard.hidden)

    def test_close_only_posts_normal_close_to_selected_window(self):
        self.guard.close_selected()
        self.guard.api.PostMessageW.assert_called_once_with(123, 0x0010, 0, 0)

    def test_close_ignores_missing_or_reused_window(self):
        for current in (None, Window(123, 99, 43, '另一个窗口', 'TestWindow')):
            self.guard.describe.return_value = current
            self.guard.close_selected()
        self.guard.api.PostMessageW.assert_not_called()

    def test_close_failure_is_reported(self):
        self.guard.api.PostMessageW.return_value = False
        with self.assertRaises(OSError):
            self.guard.close_selected()

    def test_mouse_inside_outside_and_zero_alpha(self):
        self.guard.api.GetWindowLongW.return_value = 0

        def rect(_, output):
            output._obj.left, output._obj.top = 10, 20
            output._obj.right, output._obj.bottom = 110, 120
            return True

        def cursor(output):
            output._obj.x, output._obj.y = self.cursor
            return True

        self.guard.api.GetWindowRect.side_effect = rect
        self.guard.api.GetCursorPos.side_effect = cursor
        with unittest.mock.patch.object(self.guard, 'set_styles'):
            for position, expected in (((20, 30), 255), ((110, 30), 0), ((0, 0), 0)):
                self.cursor = position
                self.guard.update_opacity(255, 0)
                self.guard.api.SetLayeredWindowAttributes.assert_called_with(123, 0, expected, 2)

    def test_hidden_window_opacity_cannot_reveal_it(self):
        self.guard.hidden = True
        self.guard.update_opacity(255, 200)
        self.guard.api.SetLayeredWindowAttributes.assert_not_called()
        self.guard.api.ShowWindowAsync.assert_not_called()

    def test_restore_preserves_original_color_key_and_alpha(self):
        self.guard.original_opacity = (True, 0x123456, 130, 3)
        self.guard.restore_opacity()
        self.guard.api.SetLayeredWindowAttributes.assert_called_once_with(123, 0x123456, 130, 3)
        self.assertIsNone(self.guard.original_opacity)

    def test_opacity_restore_failure_retains_original_state(self):
        original = self.guard.original_opacity = (True, 0, 100, 2)
        self.guard.api.SetLayeredWindowAttributes.return_value = False
        with self.assertRaises(OSError):
            self.guard.restore_opacity()
        self.assertEqual(self.guard.original_opacity, original)


if __name__ == '__main__':
    unittest.main()
