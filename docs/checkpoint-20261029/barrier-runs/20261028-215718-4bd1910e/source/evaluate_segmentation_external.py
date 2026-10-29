"""Measure mask-derived pothole regions on the existing reviewed UK benchmark."""
import argparse
import hashlib
import io
import json
import os
import pathlib
import time
import zipfile
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
import cv2
import numpy as np
from PIL import Image
from detection_metrics import match
from evaluate_external import records
from segmentation_runtime import Segmenter, components, detection_scores

SOURCE_SHA = 'a154cab487415c02269041f674e9e790b6ca61afc1c9ac417e9f1aae3e283a22'


def main():
    parser = argparse.ArgumentParser()
    for name in ('dataset','model','conditions','output'):
        parser.add_argument('--'+name,type=pathlib.Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new output directory')
    with args.dataset.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest() != SOURCE_SHA:
            raise ValueError('UK source hash mismatch')
    tags = json.loads(args.conditions.read_text(encoding='utf8'))
    if not isinstance(tags,dict) or any(not isinstance(v,list) or any(not isinstance(t,str) or t=='all' for t in v) for v in tags.values()):
        raise ValueError('Invalid reviewed condition tags')
    cv2.setNumThreads(2)
    segmenter = Segmenter(args.model)
    thresholds = (.3,.5,.65)
    strata, latencies, processing = {}, [], []
    args.output.mkdir(parents=True)
    with zipfile.ZipFile(args.dataset) as archive, (args.output/'predictions.jsonl').open('w',encoding='utf8') as log:
        accepted, excluded = records(archive)
        if len(accepted)!=708 or len(excluded)!=5 or set(tags)-{r['id'] for r in accepted}:
            raise ValueError('Unexpected accepted images/exclusions/condition identities')
        for index,record in enumerate(accepted):
            start = time.perf_counter()
            with Image.open(io.BytesIO(archive.read(record['image']))) as image:
                rgb = np.asarray(image.convert('RGB'))
            probability,elapsed = segmenter.predict(rgb)
            latencies.append(elapsed)
            predictions = {str(t):components(probability,t) for t in thresholds}
            conditions = list(dict.fromkeys(tags.get(record['id'],[])))
            for name in ['all']+conditions:
                if name not in strata:
                    strata[name] = dict(images=0,totals={str(t):np.zeros(3,np.int64) for t in thresholds})
                strata[name]['images'] += 1
                for key,detections in predictions.items():
                    strata[name]['totals'][key] += match(detections,record['boxes'],record['ignored'],0)
            processing.append((time.perf_counter()-start)*1000)
            log.write(json.dumps(dict(id=record['id'],conditions=conditions,detections_by_pixel_threshold=predictions,inference_ms=elapsed))+'\n')
            if index%100==0:
                print(f'Evaluated {index+1}/708 UK images',flush=True)
    report = dict(dataset_doi='10.17632/tp95cdvgm8.1',source_sha256=SOURCE_SHA,
        model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
        conditions_sha256=hashlib.sha256(args.conditions.read_bytes()).hexdigest(),
        images=len(accepted),excluded_images=excluded,
        strata={name:dict(images=value['images'],metrics={key:detection_scores(counts) for key,counts in value['totals'].items()}) for name,value in strata.items()},
        component_rule='8-connected mask regions at each fixed pixel threshold; all regions retained, mean probability sorting',
        matching='one-to-one box IoU >= 0.5; difficult boxes ignored; no additional confidence threshold',
        inference_ms={f'p{p}':float(np.percentile(latencies,p)) for p in (50,95,99)},
        image_processing_ms={f'p{p}':float(np.percentile(processing,p)) for p in (50,95,99)},
        tensorflow=segmenter.runtime_version,threads=2,
        limitations=['Previously examined research benchmark, not an untouched safety evaluation.',
            'Mostly positive close-up photos, not representative negative walking scenes.',
            'Wet/shadow/night tags are small reviewed subsets, not inferred from filenames.',
            'Semantic components are proxy object regions; probabilities are not calibrated hazard confidence.',
            'Desktop timing only; no phone or live-camera performance claim.'])
    (args.output/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    main()
