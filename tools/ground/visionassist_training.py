"""Unified experiment controller; invoked by Train-VisionAssist.ps1."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import signal

from experiment_store import (atomic_json, comparison, completed_history, digest,
                              job_lock, new_run, read_json, utc_now, process_identity, ensure_no_trainer)
from run_training import run_step

SCRIPTS = Path(__file__).resolve().parent


def output_parent(path):
    while not path.exists():
        if path.parent == path:
            raise FileNotFoundError('Output filesystem/drive is unavailable: ' + str(path))
        path=path.parent
    if not path.is_dir():
        raise ValueError('Output parent is not a directory: ' + str(path))
    return path


def validate_splits(data, task):
    """Recheck identities/groups/content hashes across splits, not summary booleans."""
    names = ['barrier-prepared-v1'] if task == 'barrier' else ['masked-segmentation-v1', 'segmentation-negatives-v1']
    evidence = {}
    for name in names:
        path = data / name / 'manifest.json'
        manifest = read_json(path)
        seen = {}
        counts = {}
        for index, record in enumerate(manifest['records']):
            split = record['split']
            if split not in ('train', 'val', 'validation', 'test'):
                raise ValueError('Unknown split: ' + str(split))
            normalized = 'validation' if split == 'val' else split
            counts[normalized] = counts.get(normalized, 0) + 1
            keys = [('identity', record.get('image', record.get('id')))]
            keys += [('group', record['group'])] if record.get('group') else []
            for field in ('sha256', 'decoded_rgb_sha256'):
                if record.get(field):
                    keys.append((field, record[field]))
            for sample in record.get('samples', []):
                for field in ('rgb_decoded_sha256', 'source_image_sha256'):
                    if sample.get(field):
                        keys.append((field, sample[field]))
            for key in keys:
                if key in seen and seen[key] != normalized:
                    raise ValueError(f'Cross-split leakage: {name} {key[0]}')
                seen[key] = normalized
            arrays = record.get('training_arrays')
            if split == 'test' and arrays:
                raise ValueError('Held-out test has fitting arrays')
            if arrays:
                array = (data / name / arrays['path']).resolve()
                if not array.is_relative_to((data / name).resolve()) or digest(array) != arrays['sha256']:
                    raise ValueError('Fitting array path/hash mismatch: ' + str(array))
            if index % 100 == 0:
                print(f'Dataset {name}: verified {index+1}/{len(manifest["records"])} records', flush=True)
        if not counts.get('train') or not counts.get('validation'):
            raise ValueError('Missing train or validation split')
        evidence[name] = dict(manifest_sha256=digest(path), counts=counts)
        print(f'Dataset {name}: all {len(manifest["records"])} records verified',flush=True)
    return evidence


def check(args):
    print('Validating dataset identities, separation and fitting-array hashes...', flush=True)
    splits = validate_splits(args.data_root, args.task)
    print('Split/array audit passed. Checking source files, pinned weights and the Python runtime...',flush=True)
    if args.task == 'barrier':
        from run_barrier_training import preflight
        runtime = preflight(args.data_root, args.device)
    else:
        from run_training import preflight
        runtime = preflight(args.data_root, args.backbone, args.device)
    probe = "import json,platform; import mediapipe as m; assert m.__version__=='0.10.32'; print(json.dumps({'mediapipe':m.__version__,'platform':platform.platform()}))"
    if args.task == 'barrier':
        p = subprocess.run([str(args.evaluation_python), '-c', probe], capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError('Evaluation runtime failed: ' + p.stderr)
        runtime['evaluation'] = json.loads(p.stdout.strip())
    if args.device == 'gpu':
        if platform.system() != 'Linux' or 'microsoft' not in platform.release().lower():
            raise RuntimeError('GPU profile requires WSL2, not native Windows GPU fallback')
        p = subprocess.run(['/usr/lib/wsl/lib/nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'],
                           text=True, capture_output=True, timeout=30)
        if p.returncode:
            raise RuntimeError('NVIDIA WSL driver check failed: ' + p.stderr)
        runtime['nvidia'] = p.stdout.strip()
        probe = "import json,tensorflow as tf; g=tf.config.list_physical_devices('GPU'); [tf.config.experimental.set_memory_growth(x,True) for x in g]; exec('with tf.device(\"/GPU:0\"):\\n x=tf.linalg.matmul(tf.ones((8,8)),tf.ones((8,8)))'); assert 'GPU:0' in x.device; assert float(tf.reduce_sum(x).numpy())==512.; print('CUDA_KERNEL '+json.dumps({'device':x.device,'sum':512.}))"
        p = subprocess.run([sys.executable,'-c',probe],text=True,capture_output=True,timeout=90)
        if p.returncode:
            raise RuntimeError('CUDA kernel execution failed: ' + p.stdout + p.stderr)
        runtime['cuda_kernel'] = json.loads(next(line[len('CUDA_KERNEL '):] for line in p.stdout.splitlines() if line.startswith('CUDA_KERNEL ')))
    ancestor = output_parent(args.output_root)
    minimum = (16 if args.task == 'barrier' else 4) * 1024**3
    if shutil.disk_usage(ancestor).free < minimum:
        raise ValueError(f'Insufficient space: at least {minimum // 1024**3} GiB required')
    result = dict(runtime=runtime, splits=splits, platform=platform.platform())
    print(json.dumps(result, indent=2), flush=True)
    return result


def evaluation_commands(args, model, source, destination):
    data = args.data_root
    if args.task == 'barrier':
        for split in (('validation',) if args.split == 'validation' else ('test',) if args.split == 'test' else ('validation', 'test')):
            command = [str(args.evaluation_python), '-u', str(source / 'evaluate_barrier_detector.py'),
                       '--model', str(model), '--archive', str(data / 'accessibility-barriers/wm_barriers_data.zip'),
                       '--prepared', str(data / 'barrier-prepared-v1'), '--split', split,
                       '--output', str(destination / split)]
            if args.max_images:
                command += ['--max-images', str(args.max_images)]
            yield 'evaluate-' + split, command
    else:
        # Published validation is computed at export; independent evaluations only
        # read the established held-out datasets and never feed checkpoint selection.
        if args.split == 'validation':
            raise ValueError('Pothole validation is saved by training; choose test/all for existing export evaluation')
        from run_training import pipeline
        steps = pipeline(data, args.backbone, destination, args.epochs, args.threads)
        for name, command in steps[2:]:
            command = [str(item) for item in command]
            command[command.index('--model') + 1] = str(model)
            if '--conditions' in command:
                command[command.index('--conditions') + 1] = str(source / 'uk-reviewed-conditions.json')
            if args.max_images:
                command += ['--max-images', str(args.max_images)]
            yield name, [sys.executable, '-u', str(source / command[0])] + command[1:]


def training_command(args, run):
    source, training, data = run / 'source', run / 'training', args.data_root
    if args.task == 'barrier':
        command = [sys.executable, '-u', str(source / 'train_modelmaker.py'), '--data', str(data / 'barrier-coco-v1'),
                   '--checkpoint-archive', str(data / 'mobilenetv2_ssd_i320_ckpt.tar.gz'),
                   '--output', str(training), '--class-profile', 'barriers']
        if args.run:
            from modelmaker_resume import inspect_source, capture_snapshot
            info = inspect_source(args.run, read_json(data / 'barrier-coco-v1/provenance.json'), args.epochs, args.batch_size, args.device)
            capture_snapshot(info, run / 'resume-snapshot')
            command += ['--resume-from', str(run / 'resume-snapshot')]
    else:
        command = [sys.executable, '-u', str(source / 'train_masked_segmentation.py'),
                   '--data', str(data / 'masked-segmentation-v1'), '--negative-data', str(data / 'segmentation-negatives-v1'),
                   '--backbone', str(args.backbone), '--output', str(training), '--cache-batch-size', str(args.cache_batch_size)]
        if args.run:
            command += ['--resume-from', str(args.run / 'training')]
    if args.smoke:
        command += ['--smoke']
    return command + ['--epochs', str(args.epochs), '--batch-size', str(args.batch_size),
                      '--threads', str(args.threads), '--device', args.device]


def execute(args):
    if args.action == 'report':
        output = args.report_file or args.output_root / ('comparison-' + utc_now().replace(':', '-') + '.md')
        print(comparison(args.output_root, output))
        return
    if args.action == 'status':
        runs = [args.run] if args.run else sorted(p for p in args.output_root.glob('*') if (p / 'experiment.json').exists())
        for run in runs:
            status = read_json(run / 'status.json') if (run / 'status.json').exists() else {}
            # A file saying running is never proof that a process remains alive.
            state = status.get('state', 'unknown')
            if state == 'running':
                try:
                    live = process_identity(status['pid']) == status['process_created']
                except Exception:
                    live = False
                state = 'running' if live else 'NOT CONFIRMED LIVE (stale or other host; inspect before resume)'
            print(f'{run}\n  {state}; stage={status.get("stage")}; completed epochs={len(completed_history(run / "training"))}', flush=True)
        return
    if args.device == 'cpu':
        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
    if args.action == 'check':
        check(args)
        print('CHECK PASSED. No training started.')
        return
    with job_lock(args.lock_file):
        ensure_no_trainer()
        evidence = check(args)
        if args.action == 'resume' and not args.run:
            raise ValueError('resume requires -RunDirectory')
        if args.action == 'train' and args.run:
            raise ValueError('Use resume, not train, with an existing experiment')
        if args.action == 'evaluate' and not args.checkpoint:
            raise ValueError('evaluate requires -Checkpoint pointing to an existing export or saved weights')
        configuration = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
        run = new_run(args.output_root, args.task, configuration, SCRIPTS)
        atomic_json(run / 'preflight.json', evidence)
        source = run / 'source'
        environment = os.environ.copy()
        environment.update(PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8', OMP_NUM_THREADS=str(args.threads),
                           TF_NUM_INTRAOP_THREADS=str(args.threads), TF_NUM_INTEROP_THREADS='2')
        state = dict(state='running', stage='preparing', pid=os.getpid(),
                     process_created=process_identity(os.getpid()), started_utc=utc_now(), completed=[])
        atomic_json(run / 'status.json', state)
        print(f'EXPERIMENT: {run}\nCtrl+C stops the job; preserve this directory for resume.', flush=True)
        try:
            if args.action in ('train', 'resume'):
                commands = [('train', training_command(args, run))]
                model = run / 'training' / ('model.tflite' if args.task == 'barrier' else 'segmentation.tflite')
                if args.task=='pothole':
                    commands.append(('verify-runtime',[sys.executable,'-u',str(source/'verify_segmentation_runtime.py'),
                        '--data',str(args.data_root/'masked-segmentation-v1'), '--training',str(run/'training'),
                        '--output',str(run/'runtime-verification.json')]))
            else:
                model = args.checkpoint.resolve()
                if not model.is_file() or model.suffix not in ('.tflite','.h5','.keras'):
                    raise ValueError('Expected .tflite, .weights.h5 or full .keras checkpoint')
                commands = []
                if model.suffix!='.tflite':
                    commands.append(('export-checkpoint',[sys.executable,'-u',str(source/'export_experiment_checkpoint.py'),
                        '--task',args.task,'--checkpoint',str(model),'--data-root',str(args.data_root),
                        '--backbone',str(args.backbone),'--output',str(run/'checkpoint-export')]))
                    model=run/'checkpoint-export'/('model.tflite' if args.task=='barrier' else 'segmentation.tflite')
            commands += list(evaluation_commands(args, model, source, run))
            atomic_json(run / 'commands.json', commands)
            for stage, command in commands:
                state.update(stage=stage, updated_utc=utc_now())
                atomic_json(run / 'status.json', state)
                env = environment.copy()
                if stage != 'train':
                    env['CUDA_VISIBLE_DEVICES'] = '-1'
                run_step(command, run / 'logs' / (stage + '.log'), env)
                state['completed'].append(stage)
            state.update(state='completed', ended_utc=utc_now(), warning_eligible=False)
            atomic_json(run / 'status.json', state)
            comparison(args.output_root, run / 'report.md')
            print(f'COMPLETED: {run}\nReport: {run / "report.md"}', flush=True)
        except BaseException as error:
            state.update(state='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                         error=f'{type(error).__name__}: {error}', ended_utc=utc_now())
            atomic_json(run / 'status.json', state)
            raise


def main():
    def interrupted(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    if sys.argv[1:] == ['--audit-processes']:
        ensure_no_trainer()
        return
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--task', required=True, choices=['pothole', 'barrier'])
    p.add_argument('--action', required=True, choices=['check', 'train', 'evaluate', 'status', 'resume', 'report'])
    for name in ('data-root', 'output-root', 'backbone', 'evaluation-python', 'lock-file'):
        p.add_argument('--' + name, type=Path, required=True)
    for name in ('run', 'checkpoint', 'report-file'):
        p.add_argument('--' + name, type=Path)
    p.add_argument('--device', choices=['cpu', 'gpu'], default='gpu')
    p.add_argument('--epochs', type=int, default=20)
    p.add_argument('--batch-size', type=int, default=8)
    p.add_argument('--cache-batch-size', type=int, default=32)
    p.add_argument('--threads', type=int, default=8)
    p.add_argument('--split', choices=['validation', 'test', 'all'], default='all')
    p.add_argument('--max-images', type=int)
    p.add_argument('--smoke', action='store_true', help='Barrier only: one epoch on 16 real train / 16 validation images; evaluate four validation images')
    args = p.parse_args()
    if not 1 <= args.epochs <= 1000 or not 1 <= args.batch_size <= 128 or not 1 <= args.threads <= 64 or not 1 <= args.cache_batch_size <= 128:
        p.error('Invalid epochs, batch or thread count')
    if args.max_images is not None and args.max_images < 1:
        p.error('max-images must be positive')
    if args.smoke:
        if args.task!='barrier' or args.action!='train':
            p.error('Smoke is supported only for a new barrier training experiment')
        args.max_images=4
        args.split='validation'
    for name in ('data_root', 'output_root', 'backbone', 'run', 'checkpoint', 'lock_file'):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, value.resolve())
    execute(args)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('INTERRUPTED. Completed checkpoints preserved; use status before resume.', file=sys.stderr)
        sys.exit(130)
    except Exception as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
