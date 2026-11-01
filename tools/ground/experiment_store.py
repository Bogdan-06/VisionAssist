"""Dependency-free, cross-platform experiment bookkeeping (no ML imports)."""
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import uuid


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def process_identity(pid):
    """Return an OS creation token, so PID reuse cannot make stale status live."""
    if os.name != 'nt':
        stat = Path(f'/proc/{pid}/stat').read_text()
        return Path('/proc/sys/kernel/random/boot_id').read_text().strip() + ':' + stat[stat.rindex(')')+2:].split()[19]
    command = f'(Get-Process -Id {int(pid)} -ErrorAction Stop).StartTime.ToUniversalTime().Ticks'
    result = subprocess.run(['powershell.exe','-NoProfile','-Command',command],
                            capture_output=True,text=True,timeout=15)
    if result.returncode:
        raise ProcessLookupError(pid)
    return result.stdout.strip()


def ensure_no_trainer():
    """Detect legacy/direct trainers which did not acquire the unified lock."""
    names = ('train_masked_segmentation.py', 'train_modelmaker.py', 'run_training.py', 'run_barrier_training.py')
    if os.name != 'nt':
        commands = []
        for path in Path('/proc').glob('[0-9]*/cmdline'):
            if path.parent.name == str(os.getpid()):
                continue
            try:
                commands.append(path.read_bytes().decode(errors='replace').split('\0'))
            except (OSError, PermissionError):
                continue
        if any(any(Path(arg).name in names for arg in cmd) or
               (any(Path(arg).name == 'visionassist_training.py' for arg in cmd) and
                '--action' in cmd and cmd[cmd.index('--action')+1] in ('train','resume','evaluate')) for cmd in commands):
            raise RuntimeError('An existing legacy/direct training process is active; wait before starting another job')
    else:
        command = 'Get-CimInstance Win32_Process -Filter "Name LIKE \'python%\'" | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress'
        result = subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,timeout=30)
        if result.returncode:
            raise RuntimeError('Cannot verify running training processes')
        rows = json.loads(result.stdout) if result.stdout.strip() else []
        rows = rows if isinstance(rows,list) else [rows]
        by_pid={row['ProcessId']:row for row in rows}
        # Windows venv python.exe can remain as a redirector parent with exactly
        # our command line. It is not a second experiment. Exclude only the
        # actual current-process ancestor chain, never unrelated matching jobs.
        ancestors={os.getpid()}
        cursor=os.getpid()
        while cursor in by_pid:
            cursor=by_pid[cursor].get('ParentProcessId')
            if cursor is None or cursor in ancestors:
                break
            ancestors.add(cursor)
        if any(row['ProcessId'] not in ancestors and (any(name in (row['CommandLine'] or '') for name in names) or
               ('visionassist_training.py' in (row['CommandLine'] or '') and any('--action '+a in row['CommandLine'] for a in ('train','resume','evaluate')))) for row in rows):
            raise RuntimeError('An existing Windows trainer is active; wait before starting another job')


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf8') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def job_lock(path):
    """OS advisory lock, automatically released after crashes, Windows or WSL.

    All Windows launchers must take the Windows host lock before entering WSL.
    Linux callers additionally take their own shared Linux lock. Never unlink the
    lock file: removing a locked inode lets another process bypass exclusivity.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError('Another VisionAssist job owns the lock: ' + str(path)) from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def new_run(root, task, configuration, scripts):
    root = Path(root).resolve()
    run = root / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + task + '-' + uuid.uuid4().hex[:8])
    run.mkdir(parents=True, exist_ok=False)
    (run / 'logs').mkdir()
    (run / 'source').mkdir()
    hashes = {}
    for source in sorted(Path(scripts).iterdir()):
        if source.suffix in ('.py', '.json', '.txt') and source.is_file():
            target = run / 'source' / source.name
            with target.open('xb') as stream:
                stream.write(source.read_bytes())
            hashes[source.name] = digest(target)
    atomic_json(run / 'experiment.json', dict(schema=1, task=task, started_utc=utc_now(),
        host=socket.gethostname(), configuration=configuration, source_sha256=hashes,
        installs_android_model=False, warning_eligible=False))
    return run


def completed_history(training):
    path = Path(training) / 'history.csv'
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    # A partially written trailing line is never a completed epoch.
    valid = []
    for index, row in enumerate(rows):
        try:
            if int(row['epoch']) != index or any(value is None or value == '' for value in row.values()):
                break
        except (ValueError, KeyError, TypeError):
            break
        valid.append(row)
    return valid


def metric_rows(value, prefix=''):
    """Retain metric scope/threshold; never compare pixels with objects implicitly."""
    if isinstance(value, dict):
        if all(key in value for key in ('tp', 'fp', 'fn')):
            tp, fp, fn = (value[key] for key in ('tp', 'fp', 'fn'))
            yield dict(scope=prefix, tp=tp, fp=fp, fn=fn,
                       precision=tp/(tp+fp) if tp+fp else None,
                       recall=tp/(tp+fn) if tp+fn else None,
                       f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)
        else:
            for key, child in value.items():
                if key not in ('per_clip', 'predictions'):
                    yield from metric_rows(child, prefix + '/' + str(key))


def comparison(root, destination):
    destination = Path(destination)
    # Reports are immutable just like evaluations; caller chooses a fresh filename.
    lines = ['# VisionAssist — experiment comparison', '',
             'Research only. No model is installed and no warnings are validated.', '',
             'Compare identical dataset, split, runtime, metric scope and threshold only.', '',
             '| Experiment / evidence | Scope | TP | FP | FN | Precision | Recall | F1 |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    identities = []
    progress = []
    for experiment in sorted(Path(root).iterdir()):
        if not experiment.is_dir():
            continue
        history = completed_history(experiment/'training')
        status_path = experiment/'status.json'
        status = read_json(status_path) if status_path.exists() else {}
        last = history[-1] if history else {}
        progress.append((experiment.name,status.get('state','legacy/unknown'),len(history),
                         last.get('loss',last.get('total_loss','N/A')),
                         last.get('val_loss',last.get('val_total_loss','N/A'))))
        if (experiment/'preflight.json').exists():
            preflight=read_json(experiment/'preflight.json')
            identities.append((str(experiment.relative_to(root))+'/preflight',preflight))
        for report in sorted(experiment.rglob('*.json')):
            if any(part in ('source', 'resume-snapshot') for part in report.relative_to(experiment).parts):
                continue
            try:
                value = read_json(report)
                if any(key in value for key in ('model_sha256','manifest_sha256','partial')):
                    identities.append((str(report.relative_to(root)), {key:value[key] for key in
                        ('model_sha256','manifest_sha256','source_sha256','dataset','split','runtime',
                         'mediapipe_version','tensorflow','partial','images','available_images',
                         'clips','available_clips','warning_eligible','selected_epoch','selection') if key in value}))
                for row in metric_rows(value):
                    scores = ['N/A' if row[key] is None else f'{row[key]:.4f}' for key in ('precision', 'recall', 'f1')]
                    label = str(report.relative_to(root)).replace('|', '\\|')
                    lines.append(f"| {label} | {row['scope']} | {row['tp']} | {row['fp']} | {row['fn']} | " + ' | '.join(scores) + ' |')
            except (ValueError, OSError, TypeError, KeyError) as error:
                lines.append(f'\nUnreadable evidence {report.name}: {type(error).__name__}.\n')
    lines += ['', '## Training progress', '',
              'Status files are historical snapshots; use the status command to verify a running process.', '',
              '| Experiment | Recorded state | Completed epochs | Last training loss | Last validation loss |',
              '| --- | --- | ---: | ---: | ---: |']
    lines += ['| '+' | '.join(map(str,row))+' |' for row in progress]
    lines += ['', '## Evidence identities and limitations', '',
              'Partial evaluations are smoke evidence only. Different runtime/platform results are not interchangeable.', '']
    for label, identity in identities:
        lines += [f'### {label}', '', '```json', json.dumps(identity,indent=2), '```', '']
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf8') as stream:
        stream.write('\n'.join(lines) + '\n')
    return destination
