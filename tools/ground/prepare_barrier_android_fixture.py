"""Prepare test-only, real-image Android compatibility fixtures for a barrier export.

This does not copy weights into production assets or establish model quality.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import zipfile

import mediapipe as mp
import numpy as np
from PIL import Image
from evaluate_barrier_detector import predict
from export_barrier_coco import CLASSES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('model','archive','prepared','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--preserve-aspect',action='store_true')
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('Use a new fixture directory')
    training=json.loads((args.model.parent/'training.json').read_text(encoding='utf8'))
    manifest_bytes=(args.prepared/'manifest.json').read_bytes()
    manifest=json.loads(manifest_bytes)
    if (hashlib.sha256(args.model.read_bytes()).hexdigest()!=training['model_sha256'] or
            training['classes']!=CLASSES or
            hashlib.sha256(manifest_bytes).hexdigest()!=training['data_provenance']['manifest_sha256']):
        raise ValueError('Model/training/data identity mismatch')
    with args.archive.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=manifest['source_sha256']:
            raise ValueError('Archive differs from prepared source')
    with zipfile.ZipFile(args.model) as model:
        labels=model.read('labels.txt').decode('utf8').splitlines()
    if labels!=['background']+CLASSES: raise ValueError('Unexpected embedded label order')
    # Only already-reviewed training examples; no validation/test image selection.
    seen=set(manifest['reviewed_images_forced_into_training'])
    eligible=[r for r in manifest['records'] if r['split']=='train' and r['image'] in seen]
    chosen=[]
    for category in CLASSES+[None]:
        candidates=[r for r in eligible if r['image'] not in {c['image'] for c in chosen} and
                    (any(b['target_class']==category for b in r['boxes']) if category else
                     not any(b['target_class'] for b in r['boxes']))]
        candidates.sort(key=lambda r:hashlib.sha256(r['image'].encode()).hexdigest())
        if not candidates: raise ValueError('Missing reviewed training stratum')
        chosen.append(candidates[0])
    options=mp.tasks.vision.ObjectDetectorOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(args.model)),
                                                max_results=100,score_threshold=.05,category_allowlist=CLASSES)
    args.output.mkdir(parents=True)
    shutil.copyfile(args.model,args.output/'model.tflite')
    records=[]
    with zipfile.ZipFile(args.archive) as archive, mp.tasks.vision.ObjectDetector.create_from_options(options) as detector:
        for index,record in enumerate(chosen):
            original=archive.read(record['image'])
            if hashlib.sha256(original).hexdigest()!=record['sha256']: raise ValueError('Image changed')
            with Image.open(io.BytesIO(original)) as source:
                # Identical RGB pixels on both platforms; not an accuracy-test transform.
                image=source.convert('RGB')
                if args.preserve_aspect:
                    image.thumbnail((640,640),Image.Resampling.BILINEAR)
                else:
                    image=image.resize((320,320),Image.Resampling.BILINEAR)
            name=f'frame-{index}.png'
            image.save(args.output/name)
            rgb=np.array(image)
            predicted,elapsed=predict(detector,rgb)
            records.append(dict(file=name,source_image=record['image'],source_sha256=record['sha256'],
                                png_sha256=hashlib.sha256((args.output/name).read_bytes()).hexdigest(),
                                rgb_sha256=hashlib.sha256(rgb.tobytes()).hexdigest(),
                                width=image.width,height=image.height,python_predictions=predicted,python_task_detect_ms=elapsed))
    report=dict(test_only=True,warning_eligible=False,smoke_model=training['smoke_only'],
                model_sha256=training['model_sha256'],labels=labels,
                source='https://doi.org/10.5281/zenodo.6382090',license='CC BY 4.0',
                attribution='Jakob Stolberg; collectors Christopher Richters and Sami Nenno; HIIG, 2022',
                transformations=('Reviewed training JPEGs decoded RGB and resized with aspect ratio preserved to at most 640 pixels on each side.' if args.preserve_aspect else
                                 'Reviewed training JPEGs decoded RGB and resized to 320x320.')+' Lossless PNG for runtime checks.',
                source_sha256=manifest['source_sha256'],manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
                mediapipe_version=mp.__version__,records=records,
                limitations=['Compatibility fixtures are not held-out accuracy evidence.',
                             'The smoke model is rejected for use; its detections are real inference outputs, not valid hazards.',
                             'Structural Android checks do not establish numerical cross-platform parity or warning reliability.'])
    (args.output/'fixture.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(dict(output=str(args.output),model_sha256=training['model_sha256'],
                         frames=len(records),prediction_counts=[len(r['python_predictions']) for r in records]),indent=2))


if __name__=='__main__': main()
