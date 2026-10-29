"""Run the metadata-based detector on the verified external UK benchmark.

Uses the same accepted images, exclusions, condition tags and matching as the grid model.
This dataset has already been examined during development; it is not an untouched safety test.
"""
import argparse
import hashlib
import io
import json
import pathlib
import time
import zipfile
import mediapipe as mp
import numpy as np
from PIL import Image
from detection_metrics import match
from evaluate_external import records
from evaluate_task_detector import detector_options, predict, TASK_CONFIG

SOURCE_SHA256 = 'a154cab487415c02269041f674e9e790b6ca61afc1c9ac417e9f1aae3e283a22'


def main():
    parser = argparse.ArgumentParser()
    for name in ('dataset', 'model', 'output'):
        parser.add_argument('--'+name, type=pathlib.Path, required=True)
    parser.add_argument('--conditions', type=pathlib.Path)
    parser.add_argument('--max-images', type=int)
    args = parser.parse_args()
    if args.output.exists(): raise ValueError('Use a new output directory')
    if args.max_images is not None and args.max_images <= 0:
        raise ValueError('max-images must be positive')
    with args.dataset.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != SOURCE_SHA256:
            raise ValueError('External benchmark hash mismatch')
    tags = json.loads(args.conditions.read_text(encoding='utf8')) if args.conditions else {}
    if not isinstance(tags, dict) or any(
        not isinstance(values, list) or any(not isinstance(tag, str) or tag == 'all' for tag in values)
        for values in tags.values()
    ): raise ValueError('Expected reviewed condition lists; all is reserved')
    thresholds = [.1, .2, .3, .4, .5, .6, .65, .7, .75, .8, .9]
    strata = {}; latency = []; processing = []
    args.output.mkdir(parents=True)
    with zipfile.ZipFile(args.dataset) as archive, \
            mp.tasks.vision.ObjectDetector.create_from_options(detector_options(args.model)) as detector, \
            (args.output/'predictions.jsonl').open('w', encoding='utf8') as stream:
        accepted, excluded = records(archive)
        available = len(accepted)
        if not available: raise ValueError('No valid evaluation images')
        if set(tags)-{r['id'] for r in accepted}:
            raise ValueError('Condition tags refer to unavailable or excluded images')
        if args.max_images is not None: accepted = accepted[:args.max_images]
        for index, record in enumerate(accepted):
            started = time.perf_counter()
            with Image.open(io.BytesIO(archive.read(record['image']))) as image:
                rgb = np.array(image.convert('RGB'))
            detections, elapsed_ms = predict(detector, rgb)
            latency.append(elapsed_ms)
            conditions = list(dict.fromkeys(tags.get(record['id'], [])))
            for stratum in ['all']+conditions:
                if stratum not in strata:
                    strata[stratum] = dict(images=0, totals={str(t): np.zeros(3, dtype=np.int64) for t in thresholds})
                strata[stratum]['images'] += 1
                for threshold in thresholds:
                    strata[stratum]['totals'][str(threshold)] += match(
                        detections, record['boxes'], record['ignored'], threshold)
            processing.append((time.perf_counter()-started)*1000)
            stream.write(json.dumps(dict(**record, conditions=conditions, detections=detections,
                                         task_detect_ms=elapsed_ms))+'\n')
            if index % 100 == 0: print(f'{index}/{len(accepted)}', flush=True)
    results = {}
    for name, stratum in strata.items():
        metrics = {}
        for threshold, counts in stratum['totals'].items():
            tp, fp, fn = map(int, counts)
            metrics[threshold] = dict(tp=tp, fp=fp, fn=fn,
                precision=tp/(tp+fp) if tp+fp else None, recall=tp/(tp+fn) if tp+fn else None,
                f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)
        results[name] = dict(images=stratum['images'], metrics=metrics)
    report = dict(dataset_doi='10.17632/tp95cdvgm8.1', source_sha256=SOURCE_SHA256,
        model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
        conditions_sha256=hashlib.sha256(args.conditions.read_bytes()).hexdigest() if args.conditions else None,
        images=len(accepted), available_images=available, partial=len(accepted)!=available,
        excluded_images=excluded, strata=results, iou_threshold=.5,
        runtime='MediaPipe Tasks Python CPU; metadata-based detector decoding',
        mediapipe_version=mp.__version__, detector_options=TASK_CONFIG,
        task_detect_ms={f'p{p}': float(np.percentile(latency, p)) for p in (50, 95, 99)},
        processing_ms={f'p{p}': float(np.percentile(processing, p)) for p in (50, 95, 99)},
        limitations=['Mostly positive road close-ups; not representative walking-camera negatives.',
                    'Previously examined development benchmark, not an untouched safety evaluation.',
                    'Condition tags are reviewed small subsets, not inferred from filenames.',
                    'Task timing includes graph preprocessing/postprocessing; not phone latency.',
                    'Partial smoke runs only check execution; no representative accuracy claim.'])
    (args.output/'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__': main()
