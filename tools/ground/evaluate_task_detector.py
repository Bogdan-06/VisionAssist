"""Real MediaPipe Tasks inference on the frozen COCO-format validation export.

Supports Model Maker metadata/anchors directly instead of assuming the custom grid tensor.
No cloud call. Partial runs are explicitly marked and are not representative accuracy evidence.
"""
import argparse
import hashlib
import json
import math
import pathlib
import time
import mediapipe as mp
import numpy as np
from PIL import Image
from detection_metrics import match

TASK_CONFIG = dict(max_results=100, score_threshold=.05, category_allowlist=['pothole'])

def detector_options(model):
    return mp.tasks.vision.ObjectDetectorOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model)), **TASK_CONFIG)


def predict(detector, rgb):
    height, width = rgb.shape[:2]
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    before = time.perf_counter()
    result = detector.detect(image)
    elapsed_ms = (time.perf_counter()-before)*1000
    predictions = []
    for detection in result.detections:
        category = detection.categories[0]; box = detection.bounding_box
        if category.category_name != 'pothole': raise ValueError('Unexpected model category')
        score = float(category.score)
        if not math.isfinite(score) or not 0 <= score <= 1: raise ValueError('Invalid model score')
        bounds = [max(0, box.origin_x), max(0, box.origin_y),
                  min(width, box.origin_x+box.width), min(height, box.origin_y+box.height)]
        if bounds[2] > bounds[0] and bounds[3] > bounds[1]:
            predictions.append(dict(score=score, box=bounds))
    predictions.sort(key=lambda item: -item['score'])
    return predictions, elapsed_ms


def main():
    parser=argparse.ArgumentParser()
    for name in ('model','data','output'): parser.add_argument('--'+name,type=pathlib.Path,required=True)
    parser.add_argument('--max-images',type=int)
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('Use a new output directory')
    labels_path=args.data/'validation'/'labels.json'
    document=json.loads(labels_path.read_text(encoding='utf8'))
    provenance=json.loads((args.data/'provenance.json').read_text(encoding='utf8'))
    if provenance['test_images_exported'] or provenance['image_folder']!='images':
        raise ValueError('Unexpected export provenance')
    if {c['id']:c['name'] for c in document['categories']}!={0:'background',1:'pothole'}:
        raise ValueError('Unexpected annotation classes')
    by_image={item['id']:[] for item in document['images']}
    for annotation in document['annotations']:
        if annotation['category_id']!=1 or annotation.get('iscrowd',0): raise ValueError('Unsupported ground truth')
        x,y,w,h=annotation['bbox']
        by_image[annotation['image_id']].append([x,y,x+w,y+h])
    images=document['images']
    if args.max_images is not None:
        if args.max_images<=0: raise ValueError('max-images must be positive')
        images=images[:args.max_images]
    options=detector_options(args.model)
    thresholds=[.1,.2,.3,.4,.5,.6,.65,.7,.75,.8,.9]
    totals={str(t):np.zeros(3,dtype=np.int64) for t in thresholds}
    latency=[]; processing=[]
    args.output.mkdir(parents=True)
    with mp.tasks.vision.ObjectDetector.create_from_options(options) as detector, \
            (args.output/'predictions.jsonl').open('w',encoding='utf8') as output:
        for index,record in enumerate(images):
            start=time.perf_counter()
            name=record['file_name']
            if pathlib.Path(name).name!=name or '/' in name or '\\' in name: raise ValueError('Unsafe image name')
            with Image.open(args.data/'validation'/'images'/name) as source:
                rgb=np.array(source.convert('RGB'))
            height,width=rgb.shape[:2]
            if (width,height)!=(record['width'],record['height']): raise ValueError('Annotation dimensions differ')
            predictions, elapsed_ms = predict(detector, rgb)
            latency.append(elapsed_ms)
            for threshold in thresholds:
                totals[str(threshold)]+=match(predictions,by_image[record['id']],[],threshold)
            processing.append((time.perf_counter()-start)*1000)
            output.write(json.dumps(dict(id=record['id'],file=name,detections=predictions,
                                         task_detect_ms=latency[-1]))+'\n')
            if index%100==0: print(f'{index}/{len(images)}',flush=True)
    metrics={}
    for threshold,total in totals.items():
        tp,fp,fn=map(int,total)
        metrics[threshold]=dict(tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp) if tp+fp else None,
            recall=tp/(tp+fn) if tp+fn else None,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)
    report=dict(split='validation',images=len(images),available_images=len(document['images']),
        partial=len(images)!=len(document['images']),model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
        annotations_sha256=hashlib.sha256(labels_path.read_bytes()).hexdigest(),data_provenance=provenance,
        runtime='MediaPipe Tasks Python CPU; metadata-based detector decoding',iou_threshold=.5,
        mediapipe_version=mp.__version__,detector_options=TASK_CONFIG,
        metrics=metrics,task_detect_ms={f'p{p}':float(np.percentile(latency,p)) for p in (50,95,99)},
        processing_ms={f'p{p}':float(np.percentile(processing,p)) for p in (50,95,99)},
        limitations=['Task detect timing includes graph preprocessing/postprocessing; not bare interpreter or phone timing.',
                    'Validation is used during development; not an independent safety evaluation.',
                    'Road imagery does not establish walking-camera warning reliability.'])
    (args.output/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__': main()
