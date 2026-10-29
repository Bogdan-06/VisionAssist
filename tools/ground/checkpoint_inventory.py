"""Inventory preserved local experiments without reading secrets or changing weights.

Run with --project, --work and --output (a NEW JSON file). Does not train or download.
Dataset directories are listed, not rehashed; model/checkpoint/report files are hashed.
Python environments, caches and downloaded source packages are skipped.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('project', 'work', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new inventory path; existing evidence is preserved')
    roots = [args.project / 'training-runs', args.project / 'barrier-training-runs', args.work]
    artifacts, directories = [], []
    suffixes = {'.tflite', '.h5', '.ckpt', '.pt', '.pth', '.onnx', '.safetensors', '.npz'}
    reports = {'evaluation.json', 'training.json', 'run.json', 'history.csv', 'status.json',
               'manifest.json', 'summary.json', 'resume.json', 'snapshot.json', 'metadata.json'}
    for root in roots:
        if not root.exists():
            directories.append(dict(path=str(root), exists=False))
            continue
        for child in sorted(root.iterdir()):
            if child.is_dir():
                directories.append(dict(path=str(child), exists=True))
        for folder, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not any(x in d.lower() for x in
                      ('venv', '__pycache__', 'site-packages', 'python-runtimes', 'mp-inspection', '.cache'))]
            for name in sorted(files):
                path = Path(folder) / name
                if (path.suffix.lower() not in suffixes and name not in reports
                        and not name.startswith('ckpt-') and '.data-' not in name
                        and not (name.endswith('.index') and 'ckpt' in name)):
                    continue
                stat = path.stat()
                with path.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                if path.stat().st_size != stat.st_size or path.stat().st_mtime_ns != stat.st_mtime_ns:
                    raise RuntimeError(f'Artifact changed during inventory: {path}')
                artifacts.append(dict(path=str(path), bytes=stat.st_size, sha256=digest))
    # Bundled models and test-only exports are deliberate, distinct categories.
    for path in sorted((args.project / 'core').rglob('*.tflite')):
        if 'build' in path.parts:
            continue
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        artifacts.append(dict(path=str(path), bytes=path.stat().st_size, sha256=digest,
                              role='bundled-runtime' if 'main' in path.parts else 'test-only'))
    report = dict(created_utc=datetime.now(timezone.utc).isoformat(),
                  project=str(args.project), work=str(args.work), roots=directories,
                  artifacts=artifacts,
                  limitations=['Local files are preserved in place, not a remote backup.',
                               'Dataset image contents/archives are not rehashed by this inventory.',
                               'Environments and caches are excluded; use pinned requirements to rebuild.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(dict(output=str(args.output), hashed_artifacts=len(artifacts))))


if __name__ == '__main__':
    main()
