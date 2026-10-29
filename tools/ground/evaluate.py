"""Held-out TFLite evaluation; no training, threshold fitting, or fabricated labels.

Images are RDD road photographs, not evidence of pedestrian navigation performance.
Synthetic perturbations are explicitly named; wet surfaces require human condition labels.
"""
import argparse, hashlib, io, json, pathlib, time, zipfile
import numpy as np
from PIL import Image, ImageEnhance
import tensorflow as tf
from train_baseline import letterbox, SIZE, GRID
from detection_metrics import iou, match


def decode(output, transform, width, height, threshold=.05):
    sx, sy, left, top = transform
    candidates = []
    for y in range(GRID):
        for x in range(GRID):
            score, dx, dy, bw, bh = map(float, output[y, x])
            if not np.isfinite([score, dx, dy, bw, bh]).all() or score < threshold: continue
            if score < np.max(output[max(0,y-1):y+2,max(0,x-1):x+2,0]): continue
            cx, cy = (x+dx)/GRID*SIZE, (y+dy)/GRID*SIZE
            box = [max(0., (cx-bw*SIZE/2-left)/sx), max(0., (cy-bh*SIZE/2-top)/sy),
                   min(float(width), (cx+bw*SIZE/2-left)/sx), min(float(height), (cy+bh*SIZE/2-top)/sy)]
            if box[2] > box[0] and box[3] > box[1]: candidates.append(dict(score=score, box=box))
    kept = []
    for candidate in sorted(candidates, key=lambda d: -d['score']):
        if all(iou(candidate['box'], d['box']) <= .4 for d in kept): kept.append(candidate)
        if len(kept) >= 20: break
    return kept


def perturb(image, condition):
    if condition == 'synthetic_dark': return ImageEnhance.Brightness(image).enhance(.3)
    if condition == 'synthetic_shadow':
        data = np.asarray(image.convert('RGB')).copy()
        data[:,data.shape[1]//3:2*data.shape[1]//3] = (data[:,data.shape[1]//3:2*data.shape[1]//3]*.35).astype(np.uint8)
        return Image.fromarray(data)
    return image


def main():
    parser = argparse.ArgumentParser()
    for name in ['dataset','training','output']: parser.add_argument('--'+name, type=pathlib.Path, required=True)
    parser.add_argument('--split', choices=['validation','test'], default='test')
    parser.add_argument('--conditions', nargs='+', choices=['original','synthetic_dark','synthetic_shadow'], default=['original'])
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((args.training/'manifest.json').read_text(encoding='utf8'))
    with args.dataset.open('rb') as stream: source_hash = hashlib.file_digest(stream,'sha256').hexdigest()
    if source_hash != manifest['source_sha256']: raise ValueError('Dataset does not match training manifest')
    records = [r for r in manifest['records'] if r['split']==args.split]
    if any(r['used_for_training'] for r in records): raise ValueError('Evaluation split contains training samples')
    model = args.training/'ground_baseline.tflite'
    interpreter = tf.lite.Interpreter(model_path=str(model), num_threads=2); interpreter.allocate_tensors()
    input_index = interpreter.get_input_details()[0]['index']; output_index = interpreter.get_output_details()[0]['index']
    interpreter.set_tensor(input_index, np.zeros((1,SIZE,SIZE,3),np.float32)); interpreter.invoke()
    thresholds = [.1,.2,.3,.4,.5,.6,.65,.7,.75,.8,.9]
    report = dict(split=args.split, model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
                  source_sha256=source_hash, iou_threshold=.5, nms_iou=.4, conditions={},
                  limitation='Road photographs; synthetic dark/shadow tests are not genuine wet/night or walking videos. Scores are uncalibrated.')
    with zipfile.ZipFile(args.dataset) as archive, (args.output/'predictions.jsonl').open('w',encoding='utf8') as stream:
        for condition in args.conditions:
            totals = {str(t):np.zeros(3,dtype=np.int64) for t in thresholds}; latencies=[]; pipeline=[]
            for index, record in enumerate(records):
                started=time.perf_counter()
                with Image.open(io.BytesIO(archive.read(record['image']))) as original:
                    image=perturb(original.convert('RGB'), condition); value,transform=letterbox(image)
                interpreter.set_tensor(input_index,value[None]); before=time.perf_counter(); interpreter.invoke()
                latencies.append((time.perf_counter()-before)*1000)
                detections=decode(interpreter.get_tensor(output_index)[0],transform,record['width'],record['height'])
                pipeline.append((time.perf_counter()-started)*1000)
                for threshold in thresholds: totals[str(threshold)] += match(detections,record['boxes'],record['ignored'],threshold)
                stream.write(json.dumps(dict(id=record['id'],condition=condition,detections=detections,inference_ms=latencies[-1]))+'\n')
                if index%200==0: print(condition,index,'/',len(records),flush=True)
            metrics={}
            for threshold, (tp,fp,fn) in totals.items():
                precision=float(tp/(tp+fp)) if tp+fp else None; recall=float(tp/(tp+fn)) if tp+fn else None
                metrics[threshold]=dict(tp=int(tp),fp=int(fp),fn=int(fn),precision=precision,recall=recall,
                                        f1=float(2*tp/(2*tp+fp+fn)) if 2*tp+fp+fn else None)
            report['conditions'][condition]=dict(images=len(records),metrics=metrics,
                inference_ms={f'p{p}':float(np.percentile(latencies,p)) for p in [50,95,99]},
                pipeline_ms={f'p{p}':float(np.percentile(pipeline,p)) for p in [50,95,99]})
            (args.output/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2),flush=True)


if __name__ == '__main__': main()
