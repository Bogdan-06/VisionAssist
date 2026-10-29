"""Evaluate mask-derived regions on separate RDD boxes and annotated negatives.

RDD contains boxes, not masks: no pixel segmentation IoU is claimed on this source.
"""
import argparse
import hashlib
import io
import json
import os
import pathlib
import time
import zipfile

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
import cv2
import numpy as np
from PIL import Image
from detection_metrics import match
from segmentation_runtime import Segmenter, components, detection_scores


def main():
    parser = argparse.ArgumentParser()
    for name in ('dataset', 'manifest', 'model', 'output'):
        parser.add_argument('--'+name, type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new evaluation directory')
    manifest = json.loads(args.manifest.read_text(encoding='utf8'))
    with args.dataset.open('rb') as stream:
        source_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    if source_hash != manifest['source_sha256']:
        raise ValueError('RDD source hash mismatch')
    records = [record for record in manifest['records'] if record['split'] == 'test']
    if len(records) != 1342 or any(record['used_for_training'] for record in records):
        raise ValueError('Unexpected RDD evaluation split')
    cv2.setNumThreads(2)
    segmenter = Segmenter(args.model)
    thresholds = (.3, .5, .65)
    totals = {str(t): np.zeros(3, np.int64) for t in thresholds}
    negative_count = negative_with_ignored = 0
    false_positive_images = {str(t): 0 for t in thresholds}
    negative_components = {str(t): 0 for t in thresholds}
    latency, processing = [], []
    args.output.mkdir(parents=True)
    with zipfile.ZipFile(args.dataset) as archive, (args.output/'predictions.jsonl').open('w', encoding='utf8') as log:
        for index, record in enumerate(records):
            start = time.perf_counter()
            with Image.open(io.BytesIO(archive.read(record['image']))) as image:
                if image.size != (record['width'], record['height']):
                    raise ValueError('Annotation/image dimensions differ')
                rgb = np.asarray(image.convert('RGB'))
            probability, elapsed = segmenter.predict(rgb)
            latency.append(elapsed)
            negative = not record['boxes'] and not record['ignored']
            negative_count += int(negative)
            negative_with_ignored += int(not record['boxes'] and bool(record['ignored']))
            predictions = {}
            for threshold in thresholds:
                key = str(threshold)
                detections = components(probability, threshold)
                totals[key] += match(detections, record['boxes'], record['ignored'], 0)
                predictions[key] = detections
                if negative:
                    false_positive_images[key] += int(bool(detections))
                    negative_components[key] += len(detections)
            processing.append((time.perf_counter()-start)*1000)
            log.write(json.dumps(dict(id=record['id'], annotated_negative=negative,
                detections_by_pixel_threshold=predictions, inference_ms=elapsed))+'\n')
            if index % 200 == 0:
                print(f'Evaluated {index+1}/{len(records)} RDD images', flush=True)
    report = dict(model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
        source_sha256=source_hash, manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        dataset='RDD2022 India, existing held-out test partition', images=len(records),
        component_rule='8-connected regions of restored probability >= pixel threshold; no minimum area or top-k limit',
        component_score='mean member pixel probability; uncalibrated, no additional score threshold',
        matching='greedy descending component score, one-to-one box IoU >= 0.5; difficult boxes ignored',
        metrics={key:detection_scores(value) for key,value in totals.items()},
        annotated_negative_images=negative_count, excluded_from_negative_subset_due_to_ignored_boxes=negative_with_ignored,
        negatives={key:dict(images_with_prediction=false_positive_images[key], predicted_components=negative_components[key],
            fraction_with_prediction=false_positive_images[key]/negative_count if negative_count else None) for key in totals},
        inference_ms={f'p{p}':float(np.percentile(latency,p)) for p in (50,95,99)},
        image_processing_ms={f'p{p}':float(np.percentile(processing,p)) for p in (50,95,99)},
        tensorflow=segmenter.runtime_version, threads=2,
        limitations=['Annotated negatives mean no D40 boxes, not independently reviewed hazard-free scenes.',
            'RDD box labels cannot validate segmentation pixel accuracy.',
            'Dataset was previously examined during detector development; not an untouched safety test.',
            'Pixel/component scores are not calibrated event confidence; no warnings are enabled.',
            'Desktop timing, with image decode and region extraction in processing; not phone latency.'])
    (args.output/'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
