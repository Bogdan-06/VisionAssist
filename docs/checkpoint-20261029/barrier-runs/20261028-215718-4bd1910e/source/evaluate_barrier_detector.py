"""Class-aware offline evaluation of a trained barrier MediaPipe detector.

Validation/test annotations come from the frozen duplicate-grouped preparation.
Partial runs and smoke models are explicitly reported, never used as quality claims.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import time
import zipfile

import numpy as np
from PIL import Image
from detection_metrics import match
from export_barrier_coco import CLASSES

THRESHOLDS = (.1, .3, .5, .65)


def class_counts(detections, boxes, threshold):
    """A wrong-class box is a false positive plus a missed true-class instance."""
    if any(d['class'] not in CLASSES for d in detections):
        raise ValueError('Unknown prediction class')
    result = {}
    for category in CLASSES:
        predicted = sorted((d for d in detections if d['class'] == category), key=lambda d: -d['score'])
        truth = [b['box'] for b in boxes if b['target_class'] == category]
        result[category] = match(predicted, truth, [], threshold)
    return result


def metrics(counts):
    tp, fp, fn = map(int, counts)
    return dict(tp=tp, fp=fp, fn=fn, precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None, f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)


def predict(detector, rgb):
    import mediapipe as mp
    height, width = rgb.shape[:2]
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    started = time.perf_counter()
    result = detector.detect(image)
    elapsed = (time.perf_counter()-started)*1000
    detections = []
    for detection in result.detections:
        category, bounds = detection.categories[0], detection.bounding_box
        score = float(category.score)
        if category.category_name not in CLASSES or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError('Unexpected class or invalid score from model')
        box = [max(0, bounds.origin_x), max(0, bounds.origin_y),
               min(width, bounds.origin_x+bounds.width), min(height, bounds.origin_y+bounds.height)]
        if box[2] > box[0] and box[3] > box[1]:
            detections.append(dict(score=score, box=box, **{'class': category.category_name}))
    return sorted(detections, key=lambda d: -d['score']), elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('model', 'archive', 'prepared', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--split', choices=('validation', 'test'), default='validation')
    parser.add_argument('--max-images', type=int)
    args = parser.parse_args()
    if args.output.exists() or (args.max_images is not None and args.max_images < 1):
        raise ValueError('Use a new output directory and positive image limit')
    raw = (args.prepared/'manifest.json').read_bytes()
    manifest_sha = hashlib.sha256(raw).hexdigest()
    manifest = json.loads(raw)
    summary = json.loads((args.prepared/'summary.json').read_text(encoding='utf8'))
    training = json.loads((args.model.parent/'training.json').read_text(encoding='utf8'))
    model_sha = hashlib.sha256(args.model.read_bytes()).hexdigest()
    if (manifest_sha != summary['manifest_sha256'] or
            training['data_provenance']['manifest_sha256'] != manifest_sha or
            training['model_sha256'] != model_sha or training['classes'] != CLASSES):
        raise ValueError('Training/model/dataset identity mismatch')
    with args.archive.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != manifest['source_sha256']:
            raise ValueError('Archive source changed')
    records = [r for r in manifest['records'] if r['split'] == args.split]
    available = len(records)
    records = records[:args.max_images] if args.max_images else records
    if not records:
        raise ValueError('Empty evaluation partition')
    import mediapipe as mp
    configuration = dict(max_results=100, score_threshold=.05, category_allowlist=CLASSES)
    options = mp.tasks.vision.ObjectDetectorOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(args.model)), **configuration)
    totals = {t: {c: np.zeros(3, dtype=np.int64) for c in CLASSES} for t in THRESHOLDS}
    negative_false = {t: 0 for t in THRESHOLDS}
    negative_count, latency, processing = 0, [], []
    args.output.mkdir(parents=True)
    with zipfile.ZipFile(args.archive) as archive, \
            mp.tasks.vision.ObjectDetector.create_from_options(options) as detector, \
            (args.output/'predictions.jsonl').open('w', encoding='utf8') as output:
        # Graph initialization is excluded; this synthetic input is not evaluated.
        predict(detector, np.zeros((320, 320, 3), dtype=np.uint8))
        for index, record in enumerate(records):
            started = time.perf_counter()
            content = archive.read(record['image'])
            if hashlib.sha256(content).hexdigest() != record['sha256']:
                raise ValueError('Evaluation image differs from preparation')
            with Image.open(io.BytesIO(content)) as image:
                rgb = np.array(image.convert('RGB'))
            if (rgb.shape[1], rgb.shape[0]) != (record['width'], record['height']):
                raise ValueError('Image/annotation dimensions differ')
            detections, elapsed = predict(detector, rgb)
            latency.append(elapsed)
            negative = not any(b['target_class'] for b in record['boxes'])
            negative_count += int(negative)
            for threshold in THRESHOLDS:
                counts = class_counts(detections, record['boxes'], threshold)
                for category, value in counts.items():
                    totals[threshold][category] += value
                negative_false[threshold] += int(negative and any(d['score'] >= threshold for d in detections))
            processing.append((time.perf_counter()-started)*1000)
            output.write(json.dumps(dict(image=record['image'], group=record['group'],
                                         detections=detections, task_detect_ms=elapsed))+'\n')
            if index % 100 == 0:
                print(f'Evaluated {index+1}/{len(records)} {args.split} images', flush=True)
    report = dict(model_sha256=model_sha, manifest_sha256=manifest_sha, source_sha256=manifest['source_sha256'],
                  split=args.split, images=len(records), available_images=available, classes=CLASSES,
                  partial=len(records) != available, smoke_model=training['smoke_only'], warning_eligible=False,
                  runtime='MediaPipe Tasks CPU; real metadata/anchor decoding', mediapipe_version=mp.__version__,
                  detector_options=configuration, iou_threshold=.5, annotation_defined_negatives=negative_count,
                  metrics={str(t): dict(by_class={c: metrics(v) for c, v in counts.items()},
                                        micro=metrics(np.sum(list(counts.values()), axis=0)),
                                        negative_images_with_false_detection=negative_false[t])
                           for t, counts in totals.items()},
                  task_detect_ms={f'p{p}': float(np.percentile(latency, p)) for p in (50, 95, 99)},
                  processing_ms={f'p{p}': float(np.percentile(processing, p)) for p in (50, 95, 99)},
                  limitations=[
                      'Scores are not calibrated warning probabilities; no production warning decision is made.',
                      'Timing is desktop CPU inference including task preprocessing/postprocessing, not phone timing.',
                      'Image processing includes archive reads, hashing, decoding and metric calculation.',
                      'Duplicate-grouped source holdout does not establish geographic independence or walking-video safety.',
                      'No generic unevenness/pothole class, metric distance ground truth, or false alarms per hour.'])
    (args.output/'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
