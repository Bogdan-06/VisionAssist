"""Offline execution sample for the restricted SegFormer checkpoint; no Android writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

# Disable hub access and telemetry before importing its libraries.
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'

import cv2
import numpy as np
from PIL import Image, ImageDraw
import torch
import transformers
from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor

from detection_metrics import match
from fetch_segformer_research import FILES, REVISION

STAIRS = (53, 59)
THRESHOLDS = (.3, .5, .65)


def regions(mask, probability, width, height):
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    detections = []
    for index in range(1, count):
        x, y, w, h, area = stats[index]
        detections.append(dict(box=[float(x * width / 512), float(y * height / 512),
                                    float((x + w) * width / 512), float((y + h) * height / 512)],
                               score=float(probability[labels == index].mean()), pixels=int(area)))
    return sorted(detections, key=lambda item: -item['score'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('model', 'data', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    if args.output.exists() or args.threads < 1:
        raise ValueError('Use a new output directory and positive thread count')
    for name, (size, expected) in FILES.items():
        content = (args.model / name).read_bytes()
        actual = (hashlib.sha256(content).hexdigest() if name.endswith('.safetensors') else
                  hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\x00' + content).hexdigest())
        if len(content) != size or actual != expected:
            raise ValueError(f'Reviewed model/configuration changed: {name}')
    license_bytes = (args.model / 'LICENSE').read_bytes()
    if hashlib.sha256(license_bytes).hexdigest() != 'f549820c06519e3105e5174a2fd7285224ffd2268a7f879a843b1a255fd04a61':
        raise ValueError('Reviewed research license changed')
    manifest_bytes = (args.data / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(1)
    processor = SegformerImageProcessor.from_pretrained(str(args.model), local_files_only=True)
    model, loading = SegformerForSemanticSegmentation.from_pretrained(
        str(args.model), local_files_only=True, use_safetensors=True, output_loading_info=True)
    if any(loading.get(key) for key in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs')):
        raise ValueError(f'Incomplete checkpoint load: {loading}')
    if (model.config.id2label[53], model.config.id2label[59], model.config.id2label[121]) != ('stairs', 'stairway', 'step'):
        raise ValueError('Class mapping differs')
    model.eval()
    args.output.mkdir(parents=True)
    script_bytes = Path(__file__).read_bytes()
    (args.output / 'evaluate_stair_research.source.py').write_bytes(script_bytes)
    totals = {str(t): np.zeros(3, np.int64) for t in THRESHOLDS}
    records, latency, processing = [], [], []
    sheet = Image.new('RGB', (1024, 640), 'white')
    for index, record in enumerate(manifest['records']):
        path = (args.data / record['path']).resolve()
        if not path.is_relative_to(args.data.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Input checksum/path mismatch')
        image = Image.open(path).convert('RGB')
        if image.size != (record['width'], record['height']):
            raise ValueError('Source dimensions changed')
        started = time.perf_counter()
        inputs = processor(images=image, return_tensors='pt')
        if inputs['pixel_values'].shape != (1, 3, 512, 512) or not torch.isfinite(inputs['pixel_values']).all():
            raise ValueError('Unexpected preprocessing result')
        with torch.inference_mode():
            if index == 0:
                model(**inputs)  # One explicitly excluded warmup.
                started = time.perf_counter()
                inputs = processor(images=image, return_tensors='pt')
            before = time.perf_counter()
            logits = model(**inputs).logits
            elapsed = (time.perf_counter() - before) * 1000
            if logits.shape != (1, 150, 128, 128) or not torch.isfinite(logits).all():
                raise ValueError('Unexpected output contract')
            logits = torch.nn.functional.interpolate(logits, size=(512, 512), mode='bilinear', align_corners=False)
            probabilities = logits.softmax(dim=1)[0]
            classes = logits.argmax(dim=1)[0].numpy()
            probability = probabilities[list(STAIRS)].sum(dim=0).numpy()
        eligible = np.isin(classes, STAIRS)
        truth = [box['box'] for box in record['boxes'] if box['label'] == 'stair']
        metrics, predictions = {}, {}
        for threshold in THRESHOLDS:
            key = str(threshold)
            predicted = regions(eligible & (probability >= threshold), probability, *image.size)
            tp, fp, fn = match(predicted, truth, [], 0.)
            totals[key] += (tp, fp, fn)
            metrics[key] = dict(tp=tp, fp=fp, fn=fn)
            predictions[key] = predicted
        total = (time.perf_counter() - started) * 1000
        latency.append(elapsed)
        processing.append(total)
        # Review visualization: published boxes green; model regions orange, threshold .5.
        tile = image.copy()
        tile.thumbnail((256, 270))
        draw = ImageDraw.Draw(tile)
        sx, sy = tile.width / image.width, tile.height / image.height
        for color, boxes in (('green', truth), ('orange', [p['box'] for p in predictions['0.5']])):
            for box in boxes:
                draw.rectangle([box[0]*sx, box[1]*sy, box[2]*sx, box[3]*sy], outline=color, width=2)
        x, y = index % 4 * 256, index // 4 * 320
        sheet.paste(tile, (x, y))
        ImageDraw.Draw(sheet).text((x + 3, y + 273), f'{record["path"]} GT={len(truth)} pred={len(predictions["0.5"])}\nGreen: label; orange: prediction', fill='black')
        records.append(dict(path=record['path'], archive_entry=record['archive_entry'],
                            stratum=record['stratum'], metrics=metrics, predictions=predictions,
                            inference_ms=elapsed, processing_ms=total,
                            predicted_step_pixels=int(np.count_nonzero(classes == 121))))
        print(f'{index + 1}/{len(manifest["records"])} {record["path"]}: {metrics["0.5"]}; inference {elapsed:.1f} ms', flush=True)
    sheet.save(args.output / 'review.png')
    summary = {}
    for key, (tp, fp, fn) in totals.items():
        summary[key] = dict(tp=int(tp), fp=int(fp), fn=int(fn), precision=float(tp/(tp+fp)) if tp+fp else None,
                            recall=float(tp/(tp+fn)) if tp+fn else None)
    report = dict(model_revision=REVISION, model_sha256=FILES['model.safetensors'][1],
                  script_sha256=hashlib.sha256(script_bytes).hexdigest(),
                  research_only=True, android_integrated=False, model_loading=loading,
                  input=[1, 3, 512, 512], raw_output=[1, 150, 128, 128],
                  dataset_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
                  torch=torch.__version__, transformers=transformers.__version__, cpu_threads=args.threads,
                  images=len(records), stair_classes=list(STAIRS), thresholds=list(THRESHOLDS),
                  semantics='Argmax stairs/stairway AND summed class probability >= pixel threshold; all connected components retained.',
                  box_metrics=summary, per_image=records,
                  inference_ms=dict(p50=float(np.percentile(latency, 50)), p95=float(np.percentile(latency, 95))),
                  processing_ms=dict(p50=float(np.percentile(processing, 50)), p95=float(np.percentile(processing, 95))),
                  limitations=manifest['limitations'] + [
                      'Four stair-positive and four annotation-defined negative images; no accuracy/generalization claim.',
                      'Merged ADE stair regions and source visible-stair boxes use different annotation conventions.',
                      'Step class is recorded separately, not mapped to curb or included in stair metrics.',
                      'CPU desktop timing is not Android performance; processing excludes disk load and drawing.',
                      'One warmup inference is excluded; processing includes preprocessing and postprocessing.',
                      'No depth, direction, step count, safe-route claim, warning activation or cloud inference.'])
    (args.output / 'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(dict(box_metrics=summary, inference_ms=report['inference_ms']), indent=2))


if __name__ == '__main__':
    main()
