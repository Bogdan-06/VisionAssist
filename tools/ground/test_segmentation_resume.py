"""Tiny synthetic Keras smoke: full state recovery, never real dataset training."""
import csv
from pathlib import Path
import tempfile
import shutil
import unittest

import numpy as np
import tensorflow as tf
from tensorflow import keras

from experiment_store import atomic_json
from segmentation_resume import callback, inspect_checkpoint


class SegmentationResumeTests(unittest.TestCase):
    def test_optimizer_callbacks_and_committed_checkpoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            config = dict(epochs=3, batch_size=2)
            atomic_json(output/'resume-config.json', config)
            inputs=keras.Input((2,))
            model=keras.Model(inputs,keras.layers.Dense(1)(inputs))
            model.compile(optimizer=keras.optimizers.Adam(.001),loss='mse')
            early=keras.callbacks.EarlyStopping(monitor='val_loss',patience=4)
            reduce=keras.callbacks.ReduceLROnPlateau(monitor='val_loss',patience=2)
            best=keras.callbacks.ModelCheckpoint(output/'decoder.weights.h5',save_weights_only=True,
                                               monitor='val_loss',save_best_only=True)
            csv_log=keras.callbacks.CSVLogger(output/'history.csv')
            saver=callback(keras,output,early,reduce)
            callbacks=[best,early,reduce,csv_log,saver]
            for item in callbacks:
                item.set_model(model)
                item.on_train_begin()
            model.train_on_batch(np.ones((2,2),np.float32), np.zeros((2,1),np.float32))
            for item in callbacks:
                item.on_epoch_end(0,{'loss':1.,'val_loss':2.})
            for item in callbacks:
                item.on_train_end()
            path,state=inspect_checkpoint(output,config)
            restored=keras.models.load_model(path/'last.keras')
            self.assertEqual(int(restored.optimizer.iterations.numpy()),1)
            for a,b in zip(model.optimizer.variables,restored.optimizer.variables):
                np.testing.assert_array_equal(a.numpy(),b.numpy())
            self.assertEqual(state['early']['best'],2.)
            continued=output/'continued'
            continued.mkdir()
            for name in ('decoder.weights.h5','history.csv'):
                shutil.copyfile(path/name,continued/name)
            next_early=keras.callbacks.EarlyStopping(monitor='val_loss',patience=4)
            next_reduce=keras.callbacks.ReduceLROnPlateau(monitor='val_loss',patience=2)
            next_logger=keras.callbacks.CSVLogger(continued/'history.csv',append=True)
            next_saver=callback(keras,continued,next_early,next_reduce,state)
            resumed_callbacks=[next_early,next_reduce,next_logger,next_saver]
            for item in resumed_callbacks:
                item.set_model(restored)
                item.on_train_begin()
            self.assertEqual(next_early.best,2.)
            restored.train_on_batch(np.ones((2,2),np.float32),np.zeros((2,1),np.float32))
            for item in resumed_callbacks:
                item.on_epoch_end(1,{'loss':.9,'val_loss':2.1})
            for item in resumed_callbacks:
                item.on_train_end()
            self.assertEqual(int(restored.optimizer.iterations.numpy()),2)
            self.assertEqual(next_early.wait,1)
            self.assertTrue((continued/'checkpoints/epoch-0002/committed.json').is_file())
            # An interrupted write must not displace the prior complete epoch.
            (output/'checkpoints/epoch-0002').mkdir()
            self.assertEqual(inspect_checkpoint(output,config)[0],path)
            with self.assertRaisesRegex(ValueError,'configuration differs'):
                inspect_checkpoint(output,dict(epochs=4,batch_size=2))
            (path/'last.keras').write_bytes(b'corrupted')
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):
                inspect_checkpoint(output,config)


if __name__=='__main__':
    unittest.main()
