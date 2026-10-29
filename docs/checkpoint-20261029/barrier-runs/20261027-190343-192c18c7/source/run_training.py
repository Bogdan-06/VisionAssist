"""One-command local pothole training and evaluation; never installs Android assets."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

SCRIPTS = Path(__file__).resolve().parent
BACKBONE_SHA = '279052de2cfa801003aa6cc25cc4d007d35dd0b76f06935268c79788b7642d05'


def save_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf8')
    temporary.replace(path)


def require_file(path):
    if not path.is_file():
        raise FileNotFoundError(f'Required file is missing: {path}')


def preflight(data, backbone, device='auto'):
    for name in ('train_masked_segmentation.py', 'verify_segmentation_runtime.py',
                 'evaluate_segmentation_rdd.py', 'evaluate_segmentation_videos.py',
                 'evaluate_segmentation_external.py', 'uk-reviewed-conditions.json'):
        require_file(SCRIPTS / name)
    for relative in ('RDD2022_India.zip', 'training-v3/manifest.json',
                     'external-uk/Potholes.zip'):
        require_file(data / relative)
    for name in ('masked-segmentation-v1', 'segmentation-negatives-v1', 'masked-videos-test'):
        root = data / name
        require_file(root / 'manifest.json')
        manifest = json.loads((root / 'manifest.json').read_text(encoding='utf8'))
        for record in manifest['records']:
            entries = ([record['training_arrays']] if record.get('training_arrays') else
                       list(record['files'].values()) if name == 'masked-videos-test' else [])
            for entry in entries:
                path = (root / entry['path']).resolve()
                if not path.is_relative_to(root.resolve()):
                    raise ValueError(f'Data path escapes its dataset: {path}')
                require_file(path)
    require_file(backbone)
    with backbone.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != BACKBONE_SHA:
            raise ValueError('Backbone checksum differs from the reviewed Keras weights')
    # Import the actual runtime, not merely check that its packages are listed.
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
    import tensorflow as tf
    import cv2
    import numpy as np
    from PIL import Image
    gpus = tf.config.list_physical_devices('GPU')
    if device == 'gpu' and not gpus:
        raise RuntimeError('GPU requested but TensorFlow sees no GPU. Run Setup-GpuTraining.ps1 or choose -Device Cpu.')
    return dict(python=sys.version, executable=sys.executable, tensorflow=tf.__version__,
                opencv=cv2.__version__, numpy=np.__version__, pillow=Image.__version__,
                requested_device=device, available_gpus=[g.name for g in gpus])


def run_step(command, log, environment):
    """Stream both output channels, retain diagnostics, and propagate native failure."""
    with log.open('x', encoding='utf8') as output:
        output.write(subprocess.list2cmdline(command) + '\n\n')
        output.flush()
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding='utf8', errors='replace', env=environment)
        try:
            for line in process.stdout:
                print(line, end='', flush=True)
                output.write(line)
                output.flush()
            code = process.wait()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            process.stdout.close()
        if code:
            raise RuntimeError(f'Process exited with code {code}. See {log}')


def pipeline(data, backbone, run, epochs, threads, device='auto', batch_size=16, cache_batch_size=32):
    training = run / 'training'
    model = training / 'segmentation.tflite'
    return [
        ('train', ['train_masked_segmentation.py', '--data', data / 'masked-segmentation-v1',
                   '--negative-data', data / 'segmentation-negatives-v1', '--backbone', backbone,
                   '--output', training, '--epochs', epochs, '--threads', threads,
                   '--device', device, '--batch-size', batch_size, '--cache-batch-size', cache_batch_size]),
        ('verify-runtime', ['verify_segmentation_runtime.py', '--data', data / 'masked-segmentation-v1',
                            '--training', training, '--output', run / 'runtime-verification.json']),
        ('evaluate-rdd', ['evaluate_segmentation_rdd.py', '--dataset', data / 'RDD2022_India.zip',
                          '--manifest', data / 'training-v3/manifest.json', '--model', model,
                          '--output', run / 'rdd']),
        ('evaluate-videos', ['evaluate_segmentation_videos.py', '--data', data / 'masked-videos-test',
                             '--model', model, '--output', run / 'videos']),
        ('evaluate-uk', ['evaluate_segmentation_external.py', '--dataset', data / 'external-uk/Potholes.zip',
                         '--conditions', SCRIPTS / 'uk-reviewed-conditions.json', '--model', model,
                         '--output', run / 'uk']),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('data-root', 'backbone', 'output-root'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--epochs', type=int, default=12)
    parser.add_argument('--threads', type=int, default=8)
    parser.add_argument('--device', choices=['auto', 'cpu', 'gpu'], default='auto')
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--cache-batch-size', type=int, default=32)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.epochs <= 1000 or not 1 <= args.threads <= 64:
        parser.error('epochs must be 1..1000 and threads 1..64')
    if not 1 <= args.batch_size <= 128 or not 1 <= args.cache_batch_size <= 128:
        parser.error('batch sizes must be 1..128')
    if args.device == 'cpu':
        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
    data, backbone, output = (p.resolve() for p in (args.data_root, args.backbone, args.output_root))
    print('Checking Python, prepared datasets and the pinned backbone...', flush=True)
    versions = preflight(data, backbone, args.device)
    ancestor = output
    while not ancestor.exists():
        ancestor = ancestor.parent
    if not ancestor.is_dir():
        raise ValueError(f'Output parent is not a directory: {ancestor}')
    if shutil.disk_usage(ancestor).free < 4 * 1024**3:
        raise ValueError('Allow at least 4 GiB of free disk space for a new run.')
    print(f'Checks passed. TensorFlow {versions["tensorflow"]}; CPU threads: {args.threads}.')
    print(f'Device: {args.device}; visible GPUs: {versions["available_gpus"]}; '
          f'training batch: {args.batch_size}; feature-cache batch: {args.cache_batch_size}.')
    print(f'Data: {data}\nResults: {output}')
    print('Stages: train, verify exported runtime, evaluate RDD, videos, UK.')
    print('Fresh run from the original backbone: this does not continue a previous trained model.')
    print('Pothole research candidate only. No Android installation or warning activation.')
    if args.check_only:
        print('Check-only finished. No training started or output folder created.\n'
              'Array/archive content hashes are checked by the training/evaluation stages.')
        return 0

    run = output / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
    run.mkdir(parents=True, exist_ok=False)
    (run / 'logs').mkdir()
    # Preserve the scripts and arguments used for this run, including helper modules.
    source = run / 'source'
    source.mkdir()
    for path in SCRIPTS.glob('*.py'):
        shutil.copy2(path, source / path.name)
    shutil.copy2(SCRIPTS / 'uk-reviewed-conditions.json', source / 'uk-reviewed-conditions.json')
    steps = pipeline(data, backbone, run, args.epochs, args.threads, args.device, args.batch_size, args.cache_batch_size)
    commands = [(name, [sys.executable, '-u', str(source / argv[0])] +
                 [str(source / 'uk-reviewed-conditions.json') if item == SCRIPTS / 'uk-reviewed-conditions.json'
                  else str(item) for item in argv[1:]]) for name, argv in steps]
    save_json(run / 'run.json', dict(started_utc=datetime.now(timezone.utc).isoformat(),
              epochs=args.epochs, threads=args.threads, data_root=str(data), backbone=str(backbone),
              device=args.device, batch_size=args.batch_size, cache_batch_size=args.cache_batch_size,
              versions=versions, commands=commands, installs_android_model=False))
    environment = os.environ.copy()
    environment.update(PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8', TF_CPP_MIN_LOG_LEVEL='2',
                       TF_NUM_INTRAOP_THREADS=str(args.threads), TF_NUM_INTEROP_THREADS='1',
                       OMP_NUM_THREADS=str(args.threads))
    started = time.monotonic()
    completed = []
    stage = 'starting'
    print(f'Run folder: {run}\nKeep this window open. Press Ctrl+C to stop.', flush=True)
    try:
        for stage, command in commands:
            save_json(run / 'status.json', dict(state='running', stage=stage, completed=completed,
                      pid=os.getpid(), elapsed_seconds=time.monotonic() - started))
            print(f'\nStarting {stage}...', flush=True)
            stage_environment = environment.copy()
            if stage != 'train':
                # LiteRT evaluation is CPU work; don't let desktop TF reserve GPU memory.
                stage_environment['CUDA_VISIBLE_DEVICES'] = '-1'
            run_step(command, run / 'logs' / (stage + '.log'), stage_environment)
            completed.append(stage)
    except BaseException as error:
        save_json(run / 'status.json', dict(state='interrupted' if isinstance(error, KeyboardInterrupt)
                  else 'failed', stage=stage, completed=completed, error=str(error),
                  elapsed_seconds=time.monotonic() - started))
        print(f'\nStopped at {stage}. Saved diagnostics: {run}', file=sys.stderr)
        if isinstance(error, KeyboardInterrupt):
            return 130
        raise
    save_json(run / 'status.json', dict(state='completed', completed=completed,
              elapsed_seconds=time.monotonic() - started, quality_approved=False))
    print(f'\nTraining and evaluations completed.\nModel: {run / "training/segmentation.tflite"}\n'
          f'Results and logs: {run}\nCompletion does not mean the model passed a quality gate.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
