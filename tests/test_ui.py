"""Windows-only UI checks; does not open the camera or play audio."""
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@unittest.skipUnless(sys.platform == 'win32' and importlib.util.find_spec('PIL'), 'Windows GUI test')
class UITests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from app import App
        self.root = tk.Tk()
        self.root.withdraw()
        with patch.object(App, 'setup_tray'), patch.object(App, 'refresh_cameras'):
            self.app = App(self.root)
        self.root.update_idletasks()

    def tearDown(self):
        self.app.quit()

    def test_event_history_and_boundary_remain_visible_at_minimum_size(self):
        self.root.geometry('980x720')
        self.root.deiconify()
        # Windows finishes mapping a previously withdrawn window through the event queue.
        self.root.update()
        footer = self.app.log.master
        self.assertLessEqual(footer.winfo_y()+footer.winfo_height(), 720)
        self.assertGreater(self.app.canvas.winfo_height(), 200)
        controls = self.app.hide_button.master
        self.assertLessEqual(controls.winfo_y()+controls.winfo_height(), controls.master.winfo_height())

    def test_dismissed_notification_can_be_replaced(self):
        self.app.reminder_mode.set('文字提示')
        self.app.notify('测试提醒一')
        first = self.app.toast
        button = next(w for w in first.winfo_children() if w.winfo_class() == 'Button')
        button.invoke()
        self.assertIsNone(self.app.toast)
        self.app.notify('测试提醒二')
        self.assertTrue(self.app.toast.winfo_exists())
        self.assertEqual(self.app.log.size(), 2)

    def test_default_reminder_is_a_silent_unlabelled_corner_dot(self):
        self.assertEqual(self.app.reminder_mode.get(), '角落提示点')
        self.app.notify('检测到其他人员')
        self.root.update()
        self.assertEqual(self.app.toast.winfo_width(), 28)
        self.assertTrue(self.app.toast.overrideredirect())
        self.assertEqual([w.winfo_class() for w in self.app.toast.winfo_children()], ['Canvas'])
        dot = self.app.toast.winfo_children()[0]
        self.assertEqual(dot.itemcget(dot.find_all()[0], 'fill'), '#ffd18a')
        self.app.notify('有人可能看向屏幕')
        dot = self.app.toast.winfo_children()[0]
        self.assertEqual(dot.itemcget(dot.find_all()[0], 'fill'), '#f38383')

    def test_dependency_failure_is_not_reported_as_camera_failure(self):
        from app import App
        with patch.dict(sys.modules, {'cv2': None}):
            App.refresh_cameras(self.app)
        self.assertEqual(self.app.status.cget('text'), '运行依赖缺失')


if __name__ == '__main__':
    unittest.main()
