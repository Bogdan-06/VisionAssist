"""Bookkeeping tests: real process locks and immutable files, no training."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import experiment_store

from experiment_store import atomic_json, comparison, completed_history, job_lock, new_run


class StoreTests(unittest.TestCase):
    def test_windows_venv_parent_is_not_another_job_but_sibling_is(self):
        command='python visionassist_training.py --action evaluate'
        rows=[dict(ProcessId=100,ParentProcessId=99,CommandLine=command),
              dict(ProcessId=99,ParentProcessId=88,CommandLine=command)]
        with patch.object(experiment_store.os,'name','nt'),patch.object(experiment_store.os,'getpid',return_value=100), \
             patch.object(experiment_store.subprocess,'run') as run:
            run.return_value=SimpleNamespace(returncode=0,stdout=json.dumps(rows))
            experiment_store.ensure_no_trainer()
            rows.append(dict(ProcessId=101,ParentProcessId=88,CommandLine=command))
            run.return_value=SimpleNamespace(returncode=0,stdout=json.dumps(rows))
            with self.assertRaisesRegex(RuntimeError,'Windows trainer'):
                experiment_store.ensure_no_trainer()
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_lock_rejects_competing_process_and_releases(self):
        lock = self.root / 'job.lock'
        code = 'from experiment_store import job_lock; import sys;\nwith job_lock(sys.argv[1]): print("acquired")'
        def child():
            return subprocess.run([sys.executable, '-B', '-c', code, str(lock)],
                                  cwd=Path(__file__).parent, capture_output=True)
        with job_lock(lock):
            self.assertNotEqual(child().returncode, 0)
        self.assertEqual(child().returncode, 0)

    def test_run_snapshot_does_not_overwrite_source(self):
        scripts = self.root / 'scripts'
        scripts.mkdir()
        (scripts / 'train.py').write_text('original')
        runs = self.root / 'runs'
        a = new_run(runs, 'pothole', {}, scripts)
        b = new_run(runs, 'pothole', {}, scripts)
        self.assertNotEqual(a, b)
        (scripts / 'train.py').write_text('changed')
        self.assertEqual((a / 'source/train.py').read_text(), 'original')
        self.assertFalse(json.loads((a / 'experiment.json').read_text())['warning_eligible'])

    def test_partial_history_is_not_completed(self):
        (self.root / 'history.csv').write_text('epoch,loss,val_loss\n0,1,2\n1,0.5,\n')
        self.assertEqual(len(completed_history(self.root)), 1)

    def test_comparison_calculates_scoped_f1_and_refuses_overwrite(self):
        evidence = self.root / 'runs/one'
        evidence.mkdir(parents=True)
        atomic_json(evidence / 'evaluation.json', {'pixel_metrics': {'0.5': {'tp': 2, 'fp': 1, 'fn': 3}}})
        report = comparison(self.root / 'runs', self.root / 'report.md')
        self.assertIn('0.5000', report.read_text())
        self.assertIn('/pixel_metrics/0.5', report.read_text())
        with self.assertRaises(FileExistsError):
            comparison(self.root / 'runs', report)


if __name__ == '__main__':
    unittest.main()
