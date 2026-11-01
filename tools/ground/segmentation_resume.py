"""Transactional Keras epoch checkpoints, including optimizer and callback state."""
import csv
import math
from pathlib import Path
import shutil

from experiment_store import atomic_json, digest, read_json


def inspect_checkpoint(source, configuration):
    source = Path(source).resolve()
    # Never assume a status file proves that the owning process has stopped.
    # Unified controller holds the global lock and rejects live legacy trainers
    # before spawning us. Verify the specific source PID if it recorded one.
    status_path = source / 'status.json'
    if status_path.exists():
        status = read_json(status_path)
        if status.get('pid'):
            from experiment_store import process_identity
            import os
            try:
                if status['pid'] != os.getpid() and process_identity(status['pid']) == status.get('process_created'):
                    raise RuntimeError('Source trainer is still running')
            except (ProcessLookupError, FileNotFoundError):
                pass
    if read_json(source / 'resume-config.json') != configuration:
        raise ValueError('Resume data, code, runtime, device, epochs or batch configuration differs')
    checkpoints = sorted((source / 'checkpoints').glob('epoch-*'))
    valid = [p for p in checkpoints if (p / 'committed.json').is_file()]
    if not valid:
        raise ValueError('No committed full-state epoch checkpoint; legacy best weights cannot safely resume')
    latest = valid[-1]
    state = read_json(latest / 'committed.json')
    if not 0 < state['completed_epochs'] < configuration['epochs']:
        raise ValueError('No remaining epochs')
    if state.get('stopped_early'):
        raise ValueError('Early stopping completed this experiment; use train for a fresh experiment')
    for name, expected in state['sha256'].items():
        if Path(name).name != name or digest(latest / name) != expected:
            raise ValueError('Epoch checkpoint checksum mismatch')
    return latest, state


def callback(keras, output, early, reduce_lr, restore=None):
    """Placed after CSVLogger and stateful callbacks, so commit means epoch complete."""
    class EpochCheckpoint(keras.callbacks.Callback):
        def on_train_begin(self, logs=None):
            if restore:
                for name, target in [('early', early), ('reduce_lr', reduce_lr)]:
                    for key, value in restore[name].items():
                        setattr(target, key, value)

        def on_epoch_end(self, epoch, logs=None):
            if any(not math.isfinite(float(value)) for value in (logs or {}).values()):
                raise FloatingPointError('Nonfinite epoch metrics; refusing checkpoint')
            folder = Path(output) / 'checkpoints' / f'epoch-{epoch+1:04d}'
            folder.mkdir(parents=True, exist_ok=False)
            # Save the last optimizer/model state, separate from selected best weights.
            self.model.save(folder / 'last.keras')
            for name in ('decoder.weights.h5', 'history.csv'):
                shutil.copyfile(Path(output) / name, folder / name)
            state = dict(completed_epochs=epoch+1, stopped_early=bool(self.model.stop_training),
                         optimizer_step=int(self.model.optimizer.iterations.numpy()),
                         early={key: float(getattr(early, key)) if key == 'best' else int(getattr(early, key))
                                for key in ('best', 'wait', 'stopped_epoch', 'best_epoch')},
                         reduce_lr={key: float(getattr(reduce_lr, key)) if key == 'best' else int(getattr(reduce_lr, key))
                                    for key in ('best', 'wait', 'cooldown_counter')},
                         sha256={name: digest(folder / name) for name in ('last.keras', 'decoder.weights.h5', 'history.csv')})
            atomic_json(folder / 'committed.json', state)
            print(f'CHECKPOINT epoch={epoch+1} optimizer_step={state["optimizer_step"]} path={folder}', flush=True)
    return EpochCheckpoint()
