import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap


class BootstrapTests(unittest.TestCase):
    def test_wrong_ide_interpreter_relaunches_project_python(self):
        with patch.object(bootstrap.sys, 'executable', 'E:/other-project/python.exe'), \
             patch.object(bootstrap.Path, 'is_file', return_value=True), \
             patch.object(bootstrap.subprocess, 'Popen') as launch:
            with self.assertRaises(SystemExit) as result:
                bootstrap.ensure_runtime()
            self.assertEqual(result.exception.code, 0)
            args = launch.call_args.args[0]
            self.assertEqual(Path(args[0]).name, 'python.exe')
            self.assertEqual(Path(args[0]).parent.parent.name, '.venv')
            self.assertEqual(Path(args[1]).name, 'app.py')


if __name__ == '__main__':
    unittest.main()
