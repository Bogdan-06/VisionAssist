"""Run frozen RGB fixtures in a chosen MediaPipe Python environment."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import platform

import mediapipe as mp
import numpy as np
from PIL import Image
from evaluate_barrier_detector import predict
from export_barrier_coco import CLASSES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('Use a new reference output file')
    raw=(args.fixtures/'fixture.json').read_bytes()
    fixture=json.loads(raw)
    model=args.fixtures/'model.tflite'
    if hashlib.sha256(model.read_bytes()).hexdigest()!=fixture['model_sha256'] or not fixture['test_only']:
        raise ValueError('Fixture model identity differs')
    options=mp.tasks.vision.ObjectDetectorOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
                                                max_results=100,score_threshold=.05,category_allowlist=CLASSES)
    records=[]
    with mp.tasks.vision.ObjectDetector.create_from_options(options) as detector:
        for record in fixture['records']:
            name=record['file']
            if Path(name).name!=name or '\\' in name: raise ValueError('Invalid fixture file')
            image_bytes=(args.fixtures/name).read_bytes()
            if hashlib.sha256(image_bytes).hexdigest()!=record['png_sha256']: raise ValueError('PNG changed')
            with Image.open(args.fixtures/name) as image: rgb=np.array(image.convert('RGB'))
            rgb_sha=hashlib.sha256(rgb.tobytes()).hexdigest()
            if rgb_sha!=record['rgb_sha256'] or (rgb.shape[1],rgb.shape[0])!=(record['width'],record['height']):
                raise ValueError('Decoded input pixels differ')
            predictions,elapsed=predict(detector,rgb)
            records.append(dict(file=name,png_sha256=record['png_sha256'],rgb_sha256=rgb_sha,
                                width=rgb.shape[1],height=rgb.shape[0],predictions=predictions,task_detect_ms=elapsed))
    report=dict(test_only=True,warning_eligible=False,model_sha256=fixture['model_sha256'],
                fixture_sha256=hashlib.sha256(raw).hexdigest(),smoke_model=fixture['smoke_model'],
                runtime=f'MediaPipe Python {mp.__version__} CPU on {platform.system()}',
                mediapipe_version=mp.__version__,numpy_version=np.__version__,
                captured_utc=datetime.now(timezone.utc).isoformat(),records=records)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(dict(runtime=report['runtime'],counts=[len(r['predictions']) for r in records],output=str(args.output)),indent=2))


if __name__=='__main__': main()
