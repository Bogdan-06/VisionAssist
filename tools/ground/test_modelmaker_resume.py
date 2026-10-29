"""Checkpoint consistency tests; tiny HDF5 fixtures are never trained model data."""
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import h5py
import numpy as np
from modelmaker_resume import capture_snapshot, inspect_source


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.source=self.root/'training'
        (self.source/'source').mkdir(parents=True)
        code=b'# synthetic checkpoint test source\n'
        (self.source/'source'/'trainer.py').write_bytes(code)
        self.provenance=dict(counts=dict(train=dict(images=8)))
        self.settings=dict(epochs=20,batch_size=8,class_profile='barriers',classes=['stairs','curb','step'],
                           data_provenance=self.provenance,hardware=dict(selected='gpu'),
                           versions=dict(h5py=importlib.metadata.version('h5py')),
                           source_sha256={'trainer.py':hashlib.sha256(code).hexdigest()})
        self.save_settings()
        with (self.source/'history.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=['epoch','total_loss','val_total_loss'])
            writer.writeheader()
            writer.writerows([dict(epoch=0,total_loss=2,val_total_loss=1),
                              dict(epoch=1,total_loss=1.5,val_total_loss=2),
                              dict(epoch=2,total_loss=1.2,val_total_loss=1.3)])
        for name,step in [('best.weights.h5',1),('last.weights.h5',3)]:
            with h5py.File(self.source/name,'w') as target:
                target.create_dataset('optimizer/vars/0',data=np.int64(step))
                target.create_dataset('optimizer/vars/1',data=np.array([.1,.2],dtype=np.float32))

    def save_settings(self):
        (self.source/'run.json').write_text(json.dumps(self.settings))

    def inspect(self):
        return inspect_source(self.source,self.provenance,20,8,'gpu')

    def test_latest_state_and_best_state_remain_distinct(self):
        info=self.inspect()
        snapshot=capture_snapshot(info,self.root/'snapshot')
        self.assertEqual(snapshot['selected_epoch'],3)
        self.assertEqual(snapshot['best_selected_epoch'],1)
        self.assertEqual(snapshot['resume_weights_filename'],'last.weights.h5')
        self.assertNotEqual(snapshot['weights_sha256'],snapshot['best_weights_sha256'])
        for name in ('last.weights.h5','best.weights.h5','history.csv'):
            self.assertEqual((self.root/'snapshot'/name).read_bytes(),(self.source/name).read_bytes())

    def test_checkpoint_history_mismatch_or_nonfinite_state_is_rejected(self):
        with h5py.File(self.source/'last.weights.h5','r+') as target:
            target['optimizer/vars/0'][...]=4
        with self.assertRaisesRegex(ValueError,'iteration disagrees'):
            self.inspect()
        with h5py.File(self.source/'last.weights.h5','r+') as target:
            target['optimizer/vars/0'][...]=3
            target['optimizer/vars/1'][...]=[np.nan,.2]
        with self.assertRaisesRegex(ValueError,'Nonfinite checkpoint'):
            self.inspect()

    def test_modified_source_or_data_is_rejected(self):
        info=self.inspect()
        with (self.source/'history.csv').open('a') as stream: stream.write('3,1,1\n')
        with self.assertRaisesRegex(ValueError,'changed after inspection'):
            capture_snapshot(info,self.root/'snapshot')
        self.settings['data_provenance']={'different':True}
        self.save_settings()
        with self.assertRaisesRegex(ValueError,'Source data'):
            self.inspect()

    def test_live_source_and_changed_schedule_are_rejected(self):
        live=SimpleNamespace(info=dict(cmdline=['python','train_modelmaker.py','--output',str(self.source)]))
        with patch('modelmaker_resume.psutil.process_iter',return_value=[live]):
            with self.assertRaisesRegex(RuntimeError,'still running'):
                self.inspect()
        with self.assertRaisesRegex(ValueError,'original 20-epoch'):
            inspect_source(self.source,self.provenance,30,8,'gpu')


if __name__=='__main__': unittest.main()
