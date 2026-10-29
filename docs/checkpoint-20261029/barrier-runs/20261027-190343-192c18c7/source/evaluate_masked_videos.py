"""Evaluate actual detector outputs against published semantic video masks.

Connected-component boxes are proxy instance labels, not reviewed object instances.
This script never changes the production warning gate or uses videos for training.
"""
import argparse
import hashlib
import json
import math
import pathlib
import time
from contextlib import ExitStack

import cv2
import numpy as np
from PIL import Image

from detection_metrics import match
from evaluate_video import TemporalReplay
from prepare_masked_videos import SOURCE_SHA256


def mask_boxes(frame):
    # Compression creates intermediate edge intensities; retain every component.
    binary = (cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) >= 128).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    boxes = [[int(x), int(y), int(x+w), int(y+h)] for x, y, w, h, area in stats[1:]]
    return binary.astype(bool), boxes, [int(row[4]) for row in stats[1:]]


def covered_pixels(detections, threshold, truth):
    height, width = truth.shape
    coverage = np.zeros_like(truth)
    for detection in detections:
        if detection['score'] < threshold: continue
        x1, y1, x2, y2 = detection['box']
        left, top = max(0, math.floor(x1)), max(0, math.floor(y1))
        right, bottom = min(width, math.ceil(x2)), min(height, math.ceil(y2))
        coverage[top:bottom, left:right] = True
    return int(np.count_nonzero(coverage & truth)), int(coverage.sum()), int(truth.sum())


def verified_path(root, entry):
    path = (root / entry['path']).resolve()
    if not path.is_relative_to(root.resolve()): raise ValueError('Path escapes dataset')
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != entry['sha256'] or path.stat().st_size != entry['bytes']:
        raise ValueError('Video differs from verified extraction')
    return path


def main():
    cv2.setNumThreads(2)
    parser = argparse.ArgumentParser()
    for name in ('data', 'model', 'output'):
        parser.add_argument('--'+name, type=pathlib.Path, required=True)
    parser.add_argument('--runtime', choices=('grid', 'mediapipe'), required=True)
    parser.add_argument('--max-clips', type=int)
    args = parser.parse_args()
    if args.output.exists(): raise ValueError('Use a new output directory')
    if args.max_clips is not None and args.max_clips <= 0: raise ValueError('Invalid clip limit')
    manifest_path = args.data/'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf8'))
    if (manifest['source_sha256'] != SOURCE_SHA256 or manifest['videos'] != 123 or
            manifest['split'] != 'published test partition' or len(manifest['records']) != 123):
        raise ValueError('Unexpected evaluation dataset')
    records = manifest['records'][:args.max_clips]
    thresholds = (.1, .3, .65)
    totals = {str(t): np.zeros(3, dtype=np.int64) for t in thresholds}
    pixels = {str(t): np.zeros(3, dtype=np.int64) for t in thresholds}
    latencies, processing, clips = [], [], []
    args.output.mkdir(parents=True)
    with ExitStack() as stack:
        if args.runtime == 'mediapipe':
            from evaluate_task_detector import mp, predict, detector_options, TASK_CONFIG
            detector = stack.enter_context(mp.tasks.vision.ObjectDetector.create_from_options(detector_options(args.model)))
            inference = lambda rgb: predict(detector, rgb)
            runtime_details = dict(version=mp.__version__, options=TASK_CONFIG,
                timing_scope='MediaPipe detect, including graph preprocessing and postprocessing')
        else:
            from evaluate import tf, letterbox, decode
            interpreter = tf.lite.Interpreter(model_path=str(args.model), num_threads=2)
            interpreter.allocate_tensors()
            input_index = interpreter.get_input_details()[0]['index']
            output_index = interpreter.get_output_details()[0]['index']
            def inference(rgb):
                value, transform = letterbox(Image.fromarray(rgb))
                interpreter.set_tensor(input_index, value[None])
                before = time.perf_counter(); interpreter.invoke()
                elapsed = (time.perf_counter()-before)*1000
                return decode(interpreter.get_tensor(output_index)[0], transform, rgb.shape[1], rgb.shape[0]), elapsed
            runtime_details = dict(version=tf.__version__, threads=2, timing_scope='Bare LiteRT invoke')
        stream = stack.enter_context((args.output/'predictions.jsonl').open('w', encoding='utf8'))
        for clip_number, record in enumerate(records):
            with ExitStack() as clip_stack:
                captures = []
                for kind in ('rgb', 'mask'):
                    capture = cv2.VideoCapture(str(verified_path(args.data, record['files'][kind])))
                    clip_stack.callback(capture.release)
                    if not capture.isOpened(): raise ValueError('Cannot decode paired video')
                    captures.append(capture)
                fps = [c.get(cv2.CAP_PROP_FPS) for c in captures]
                counts = [int(c.get(cv2.CAP_PROP_FRAME_COUNT)) for c in captures]
                if not all(math.isfinite(f) and f > 0 for f in fps) or abs(fps[0]-fps[1]) > 1e-6 or counts[0] != counts[1]:
                    raise ValueError('Paired video metadata differs')
                index = samples = positive = 0; next_sample = 0.; warnings = []
                component_areas = []; positive_decoded = 0; replay = TemporalReplay()
                while True:
                    ok_rgb, frame = captures[0].read(); ok_mask, mask = captures[1].read()
                    if ok_rgb != ok_mask: raise ValueError('Paired streams end at different frames')
                    if not ok_rgb: break
                    if frame.shape != mask.shape: raise ValueError('RGB/mask dimensions differ')
                    # Inspect every frame for completely empty clips, even when not sampled.
                    has_mask = bool(np.any(mask >= 128)); positive_decoded += int(has_mask)
                    stamp = index/fps[0]*1000
                    if stamp+1e-6 >= next_sample:
                        before = time.perf_counter()
                        truth, boxes, areas = mask_boxes(mask)
                        detections, elapsed = inference(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        if replay.observe(detections, int(stamp), frame.shape[1], frame.shape[0]): warnings.append(stamp)
                        for threshold in thresholds:
                            totals[str(threshold)] += match(detections, boxes, [], threshold)
                            pixels[str(threshold)] += covered_pixels(detections, threshold, truth)
                        processing.append((time.perf_counter()-before)*1000); latencies.append(elapsed)
                        stream.write(json.dumps(dict(clip=record['id'], index=index, timestamp_ms=stamp,
                            mask_component_boxes=boxes, component_areas=areas, detections=detections,
                            inference_ms=elapsed))+'\n')
                        samples += 1; positive += int(bool(boxes)); component_areas.extend(areas)
                        next_sample = stamp+400
                    index += 1
                if index != counts[0] or not samples: raise ValueError('Decoded frame count differs from metadata')
                if not positive_decoded: raise ValueError('Entirely empty mask clip requires manual investigation: '+record['id'])
                clips.append(dict(id=record['id'], frames=index, fps=fps[0], samples=samples,
                    positive_sampled_frames=positive, positive_decoded_frames=positive_decoded,
                    components=len(component_areas), smallest_component_pixels=min(component_areas) if component_areas else None,
                    warning_policy_eligible_timestamps_ms=warnings))
            print(f'{clip_number+1}/{len(records)} clips', flush=True)
    metrics = {}
    for threshold, total in totals.items():
        tp, fp, fn = map(int, total); intersection, predicted, truth = map(int, pixels[threshold])
        metrics[threshold] = dict(tp=tp, fp=fp, fn=fn, precision=tp/(tp+fp) if tp+fp else None,
            recall=tp/(tp+fn) if tp+fn else None,
            box_union_mask_iou=intersection/(predicted+truth-intersection) if predicted+truth-intersection else None,
            mask_pixels_covered=intersection/truth if truth else None,
            predicted_box_pixels_on_mask=intersection/predicted if predicted else None)
    report = dict(dataset_doi=manifest['dataset_doi'], source_sha256=SOURCE_SHA256,
        manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(), runtime=args.runtime,
        runtime_details=runtime_details, available_clips=123, evaluated_clips=len(clips), partial=len(clips)!=123,
        analyzed_frames=len(latencies), interval_ms=400, mask_threshold=128, connectivity=8,
        component_filter='none', box_match_iou=.5, metrics=metrics, clips=clips,
        warning_eligible_clips=sum(bool(c['warning_policy_eligible_timestamps_ms']) for c in clips),
        inference_ms={f'p{p}':float(np.percentile(latencies,p)) for p in (50,95,99)},
        sampled_processing_ms={f'p{p}':float(np.percentile(processing,p)) for p in (50,95,99)},
        production_ground_warnings_enabled=False,
        limitations=['Mask components are proxy boxes, not manually reviewed instance labels; touching regions merge.',
            'Mask boundaries use semi-manual tracking and compressed video. No component is silently dropped.',
            'Box-union/mask overlap evaluates localization coverage, not model segmentation output.',
            'Short clips reset temporal state and cannot validate a 12-second cooldown or walking-route false-alarm rate.',
            'Warning eligibility is replay only, without warning-to-ground-truth matching.',
            'Published test data is now development evaluation, not an independent safety trial.',
            'Desktop timings include concurrent workloads; processing includes evaluation masks/metrics, excludes video decoding.',
            'Nominal frame-index timestamps assume constant frame rate; no physical distance labels.'])
    (args.output/'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(dict(clips=len(clips), frames=len(latencies), metrics=metrics)), flush=True)


if __name__ == '__main__': main()
