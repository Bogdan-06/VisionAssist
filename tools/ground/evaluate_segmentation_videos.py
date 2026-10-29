"""Evaluate the exported segmentation candidate on published test video masks."""
import argparse
import hashlib
import json
import os
import pathlib

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
import cv2
import numpy as np
from detection_metrics import match
from prepare_masked_segmentation import decode_pair
from prepare_masked_videos import SOURCE_SHA256
from segmentation_runtime import Segmenter, components, detection_scores


def pixel_scores(counts):
    tp, fp, fn = map(int, counts)
    return dict(tp=tp, fp=fp, fn=fn, iou=tp/(tp+fp+fn) if tp+fp+fn else None,
        dice=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
        precision=tp/(tp+fp) if tp+fp else None, recall=tp/(tp+fn) if tp+fn else None)


def main():
    parser = argparse.ArgumentParser()
    for name in ('data', 'model', 'output'):
        parser.add_argument('--'+name, type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new evaluation directory')
    manifest_path = args.data/'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf8'))
    if (manifest['source_sha256'] != SOURCE_SHA256 or manifest['videos'] != 123
            or len(manifest['records']) != 123 or manifest['split'] != 'published test partition'):
        raise ValueError('Unexpected test-video manifest')
    cv2.setNumThreads(2)
    segmenter = Segmenter(args.model)
    thresholds = (.3, .5, .65)
    pixels = {str(t): np.zeros(3, np.int64) for t in thresholds}
    regions = {str(t): np.zeros(3, np.int64) for t in thresholds}
    frames = decoded = truth_components = 0
    clips, latency = [], []
    args.output.mkdir(parents=True)
    with (args.output/'predictions.jsonl').open('w', encoding='utf8') as log:
        for clip_index, record in enumerate(manifest['records']):
            paths = []
            for kind in ('rgb', 'mask'):
                entry = record['files'][kind]
                path = (args.data/entry['path']).resolve()
                if not path.is_relative_to(args.data.resolve()):
                    raise ValueError('Video escapes data directory')
                with path.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                if digest != entry['sha256'] or path.stat().st_size != entry['bytes']:
                    raise ValueError('Video checksum mismatch')
                paths.append(path)
            images, masks, samples, count, fps = decode_pair(paths)
            decoded += count
            clip_pixels = {key: np.zeros(3, np.int64) for key in pixels}
            clip_regions = {key: np.zeros(3, np.int64) for key in regions}
            for rgb, truth, sample in zip(images, masks, samples):
                probability, elapsed = segmenter.predict(rgb)
                latency.append(elapsed)
                boxes = [region['box'] for region in components(truth.astype(np.float32), .5)]
                truth_components += len(boxes)
                truth = truth.astype(bool)
                predictions = {}
                for threshold in thresholds:
                    key = str(threshold)
                    foreground = probability >= threshold
                    observed = np.array([np.count_nonzero(foreground & truth),
                        np.count_nonzero(foreground & ~truth), np.count_nonzero(~foreground & truth)], np.int64)
                    pixels[key] += observed
                    clip_pixels[key] += observed
                    detections = components(probability, threshold)
                    matched = np.array(match(detections, boxes, [], 0), np.int64)
                    regions[key] += matched
                    clip_regions[key] += matched
                    predictions[key] = detections
                log.write(json.dumps(dict(clip=record['id'], frame=sample['frame'],
                    timestamp_ms=sample['timestamp_ms'], truth_component_boxes=boxes,
                    detections_by_pixel_threshold=predictions, inference_ms=elapsed))+'\n')
                frames += 1
            clips.append(dict(id=record['id'], frames=len(images), fps=fps,
                pixel_metrics={key:pixel_scores(value) for key,value in clip_pixels.items()},
                component_metrics={key:detection_scores(value) for key,value in clip_regions.items()}))
            if clip_index % 20 == 0:
                print(f'Evaluated {clip_index+1}/123 masked clips', flush=True)
    report = dict(model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
        source_sha256=SOURCE_SHA256, manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        split='published test videos, already examined during prior model development', clips=len(clips),
        sampled_frames=frames, decoded_rgb_frames=decoded, resolution=[320,320], truth_components=truth_components,
        pixel_metrics={key:pixel_scores(value) for key,value in pixels.items()},
        mean_clip_iou={key:float(np.mean([clip['pixel_metrics'][key]['iou'] for clip in clips])) for key in pixels},
        component_metrics={key:detection_scores(value) for key,value in regions.items()},
        inference_ms={f'p{p}':float(np.percentile(latency,p)) for p in (50,95,99)},
        component_rule='8-connected components at each fixed pixel threshold; retain every region; mean pixel score sorting',
        matching='one-to-one box IoU >= 0.5, no additional score threshold',
        per_clip=clips, tensorflow=segmenter.runtime_version,
        limitations=['Semantic connected components are proxy instances, not reviewed independent pothole objects.',
            'Masks are evaluated after nearest-neighbour reduction to 320x320, not at original 1080 resolution.',
            'Clips and frames are correlated; geographic independence is unestablished.',
            'Every sampled frame has labelled foreground; not an all-negative-scene test.',
            'No warning events are validated or enabled by pixel or component metrics.',
            'Desktop LiteRT invocation timings exclude decode/preprocessing/postprocessing and are not phone timings.'])
    (args.output/'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps({key:report[key] for key in ('clips','sampled_frames','truth_components','pixel_metrics','component_metrics')}, indent=2), flush=True)


if __name__ == '__main__':
    main()
