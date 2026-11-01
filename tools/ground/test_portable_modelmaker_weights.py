"""Tiny Keras 2.15 fixtures: cross-OS HDF5 paths, no dataset training."""
import os
os.environ['CUDA_VISIBLE_DEVICES']='-1'
from pathlib import Path
import tempfile
import unittest

import h5py
import numpy as np
import tensorflow as tf

from portable_modelmaker_weights import group_path, load_weights


class PortableWeightsTests(unittest.TestCase):
    def test_group_separator_resolution(self):
        self.assertEqual(group_path({'metrics/mean':True},'metrics\\mean'),'metrics/mean')
        self.assertEqual(group_path({'layers\\dense':True},'layers/dense'),'layers\\dense')

    def test_full_strict_load_of_linux_paths_on_windows(self):
        def model():
            value=tf.keras.Sequential([tf.keras.layers.Dense(2,input_shape=(2,))])
            value.compile(optimizer=tf.keras.optimizers.SGD(momentum=.9))
            value.optimizer.build(value.trainable_variables)
            return value
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            original=model()
            for variable in original.weights:
                variable.assign(tf.ones_like(variable)*2)
            original.save_weights(root/'native.weights.h5')
            with h5py.File(root/'native.weights.h5','r') as source, h5py.File(root/'linux.weights.h5','w') as destination:
                def copy(name,value):
                    name=name.replace('\\','/')
                    if isinstance(value,h5py.Group):
                        destination.require_group(name)
                    else:
                        destination.create_dataset(name,data=value[()])
                source.visititems(copy)
            restored=model()
            report=load_weights(restored,root/'linux.weights.h5')
            self.assertTrue(report['strict'])
            self.assertEqual(report['prediction_tensors'],len(original.weights))
            for a,b in zip(original.weights,restored.weights):
                np.testing.assert_array_equal(a.numpy(),b.numpy())
            with h5py.File(root/'linux.weights.h5','r+') as broken:
                del broken['layers/dense/vars/0']
            with self.assertRaises(ValueError):
                load_weights(model(),root/'linux.weights.h5')


if __name__=='__main__':
    unittest.main()
