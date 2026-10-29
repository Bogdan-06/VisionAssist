"""Capture a stopped barrier run's last optimizer state and separate best model."""
import csv
import hashlib
import importlib.metadata
import io
import json
import math
from pathlib import Path
import shutil

import h5py
import numpy as np
import psutil

PRETRAINED_SHA='73dd229998007e47259b93b00f65aca410ec053a15e67d78519ce5c1779f521f'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def ensure_stopped(source):
    for process in psutil.process_iter(['pid','cmdline']):
        try:
            arguments=process.info['cmdline'] or []
            if not any(Path(a).name=='train_modelmaker.py' for a in arguments) or '--output' not in arguments:
                continue
            output=Path(arguments[arguments.index('--output')+1]).resolve()
            if output==source:
                raise RuntimeError('Source trainer is still running; do not capture changing checkpoints')
        except (psutil.NoSuchProcess,psutil.AccessDenied,IndexError):
            continue


def checkpoint_step(path):
    with h5py.File(path,'r') as saved:
        if 'optimizer/vars/0' not in saved:
            raise ValueError('Checkpoint has no optimizer iteration state')
        step=int(saved['optimizer/vars/0'][()])
        def finite(name,value):
            if isinstance(value,h5py.Dataset) and value.dtype.kind in 'fc' and not np.isfinite(value[()]).all():
                raise ValueError(f'Nonfinite checkpoint tensor: {name}')
        saved.visititems(finite)
    return step


def inspect_source(path, provenance, epochs, batch_size, device):
    source=path.resolve()
    if (source/'training/run.json').is_file():
        source=source/'training'
    ensure_stopped(source)
    settings=json.loads((source/'run.json').read_text(encoding='utf8'))
    if epochs!=20 or batch_size!=8 or settings['epochs']!=epochs or settings['batch_size']!=batch_size:
        raise ValueError('Resume must retain the original 20-epoch, batch-8 schedule')
    if settings['class_profile']!='barriers' or settings['classes']!=['stairs','curb','step']:
        raise ValueError('Only a full three-class barrier run can be resumed here')
    if settings['data_provenance']!=provenance or settings['hardware']['selected']!=device:
        raise ValueError('Source data or training device differs')
    for name,version in settings['versions'].items():
        if importlib.metadata.version(name)!=version:
            raise ValueError(f'Resume environment version differs: {name}')
    history_bytes=(source/'history.csv').read_bytes()
    history=list(csv.DictReader(io.StringIO(history_bytes.decode('utf8'))))
    if not history or not 0<len(history)<epochs or [int(r['epoch']) for r in history]!=list(range(len(history))):
        raise ValueError('History must contain consecutive completed epochs with work remaining')
    for row in history:
        if any(not math.isfinite(float(value)) for key,value in row.items() if key.endswith('_loss')):
            raise ValueError('Completed history contains nonfinite losses')
    steps=provenance['counts']['train']['images']//batch_size
    best_index=min(range(len(history)),key=lambda i:float(history[i]['val_total_loss']))
    if checkpoint_step(source/'last.weights.h5')!=len(history)*steps:
        raise ValueError('Last checkpoint iteration disagrees with completed history')
    if checkpoint_step(source/'best.weights.h5')!=(best_index+1)*steps:
        raise ValueError('Best checkpoint iteration disagrees with validation-selected epoch')
    for name,expected in settings['source_sha256'].items():
        if Path(name).name!=name or digest(source/'source'/name)!=expected:
            raise ValueError('Archived training source changed')
    hashes={name:digest(source/name) for name in ('last.weights.h5','best.weights.h5','history.csv','run.json')}
    return dict(source=str(source),completed_epochs=len(history),best_selected_epoch=best_index+1,
                optimizer_step=len(history)*steps,files_sha256=hashes,settings=settings)


def capture_snapshot(info, destination):
    source=Path(info['source'])
    ensure_stopped(source)
    destination.mkdir(parents=True,exist_ok=False)
    for name,expected in info['files_sha256'].items():
        if digest(source/name)!=expected:
            raise ValueError('Source checkpoint/history changed after inspection')
        shutil.copyfile(source/name,destination/name)
        if digest(destination/name)!=expected or digest(source/name)!=expected:
            raise ValueError('Source changed while taking snapshot')
    settings=info['settings']
    snapshot=dict(data_provenance=settings['data_provenance'],pretrained_checkpoint_sha256=PRETRAINED_SHA,
                  selected_epoch=info['completed_epochs'],best_selected_epoch=info['best_selected_epoch'],
                  resume_weights_filename='last.weights.h5',
                  weights_sha256=info['files_sha256']['last.weights.h5'],
                  best_weights_sha256=info['files_sha256']['best.weights.h5'],
                  history_sha256=info['files_sha256']['history.csv'],source_run=info['source'],
                  optimizer_step=info['optimizer_step'],
                  limitation='Last model/optimizer state is resumed; best validation checkpoint remains separate. Data shuffle/GPU operations after restart are not bitwise equivalent to uninterrupted training.')
    (destination/'snapshot.json').write_text(json.dumps(snapshot,indent=2),encoding='utf8')
    return snapshot
