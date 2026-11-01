"""Actual subprocess failure/interrupt checks, with no ML work."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from run_training import run_step


class TrainingProcessTests(unittest.TestCase):
    def test_native_failure_is_logged_and_propagated(self):
        with tempfile.TemporaryDirectory() as temporary:
            log=Path(temporary)/'failure.log'
            with self.assertRaisesRegex(RuntimeError,'code 7'):
                run_step([sys.executable,'-u','-c','print("failed-child"); raise SystemExit(7)'],log,os.environ.copy())
            self.assertIn('failed-child',log.read_text())

    def test_interrupt_terminates_the_actual_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            children=[]
            original=subprocess.Popen
            def capture(*args,**kwargs):
                process=original(*args,**kwargs)
                children.append(process)
                return process
            with patch('run_training.subprocess.Popen',side_effect=capture), \
                 patch('builtins.print',side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    run_step([sys.executable,'-u','-c','import time; print("ready"); time.sleep(60)'],
                             Path(temporary)/'interrupt.log',os.environ.copy())
            self.assertEqual(len(children),1)
            self.assertIsNotNone(children[0].poll())


if __name__=='__main__':
    unittest.main()
