"""Strict cross-OS loader for the pinned Keras 2.15 HDF5 weight layout.

Keras uses tf.io.gfile.join for HDF5 group names; Windows writes backslashes,
Linux writes slashes. File paths and HDF5 object paths are different concepts.
"""
from pathlib import Path


def group_path(saved, path):
    for candidate in dict.fromkeys((path,path.replace('\\','/'),path.replace('/','\\'))):
        if candidate in saved:
            return candidate
    return path


def load_weights(model, checkpoint):
    import h5py
    import numpy as np
    from keras.src.saving import saving_lib

    class PortableStore(saving_lib.H5IOStore):
        def __init__(self, path):
            super().__init__(str(path),mode='r')
            self.read_tensors=set()

        def get(self, path):
            value=super().get(group_path(self.h5_file,path) if path else path)
            if isinstance(value,h5py.Group):
                self.read_tensors.update(value[key].name for key in value if isinstance(value[key],h5py.Dataset))
            return value

    store=PortableStore(checkpoint)
    expected=set()
    try:
        def validate(name,value):
            if isinstance(value,h5py.Dataset):
                if value.dtype.kind in 'fc' and not np.isfinite(value[()]).all():
                    raise ValueError('Nonfinite checkpoint tensor: '+name)
                if name.replace('\\','/').startswith('layers/'):
                    expected.add(value.name)
        store.h5_file.visititems(validate)
        if not expected:
            raise ValueError('Checkpoint contains no prediction-network variables')
        saving_lib._load_state(model,weights_store=store,assets_store=None,inner_path='',
                               skip_mismatch=False,visited_trackables=set())
        if expected-store.read_tensors:
            raise ValueError('Prediction-network checkpoint tensors were not all consumed')
        return dict(prediction_tensors=len(expected),strict=True,normalized_hdf5_group_separators=True)
    finally:
        store.close()
