import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap


class BootstrapTests(unittest.TestCase):
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
