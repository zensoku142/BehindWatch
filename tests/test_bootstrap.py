import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap


class BootstrapTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'win32', 'Windows event test')
    def test_duplicate_launch_requests_existing_window(self):
        with patch.object(bootstrap, 'ACTIVATION_EVENT', f'Local\\BehindWatch.Test.{uuid.uuid4()}'):
            handle = bootstrap.create_activation_event()
            try:
                self.assertFalse(bootstrap.activation_requested(handle))
                self.assertTrue(bootstrap.signal_existing_instance())
                self.assertTrue(bootstrap.activation_requested(handle))
                self.assertFalse(bootstrap.activation_requested(handle))
            finally:
                bootstrap.release_single_instance(handle)

    def test_missing_dependencies_waits_for_project_interpreter(self):
        with patch.object(bootstrap.sys, 'executable', 'E:/github/myth984/.venv/Scripts/python.exe'), \
             patch.object(bootstrap.sys, 'argv', ['app.py', '--smoke-test']), \
             patch.object(bootstrap.importlib.util, 'find_spec', return_value=None), \
             patch.object(bootstrap.Path, 'is_file', return_value=True), \
             patch.object(bootstrap.subprocess, 'run', return_value=SimpleNamespace(returncode=7)) as run:
            with self.assertRaises(SystemExit) as result:
                bootstrap.ensure_runtime()
            self.assertEqual(result.exception.code, 7)
            args = run.call_args.args[0]
            self.assertEqual(Path(args[0]).parent.parent.name, '.venv')
            self.assertEqual(Path(args[1]).name, 'app.py')
            self.assertEqual(args[2:], ['--smoke-test'])

    def test_ide_interpreter_stays_in_current_process(self):
        with patch.object(bootstrap.sys, 'executable', 'E:/other-project/python.exe'), \
             patch.object(bootstrap.importlib.util, 'find_spec', return_value=object()), \
             patch.object(bootstrap.Path, 'mkdir'):
            self.assertIsNone(bootstrap.ensure_runtime())


if __name__ == '__main__':
    unittest.main()
