"""Actual-video inference and temporal replay; unannotated frames never count as negatives.

Optional JSON labels: {"frames": [{"index": 0, "reviewed": true, "boxes": [...],
"ignored": [...]}]}. Boxes use original video pixels and the decoded zero-based frame index.
"""
import argparse, hashlib, json, pathlib, time
import cv2
import numpy as np
from PIL import Image
from detection_metrics import match, iou


class TemporalReplay:
    def __init__(self): self.previous=None; self.last=-1; self.first=-1; self.hits=0; self.warned=-12000
    def observe(self,detections,stamp,width,height):
        candidates=[d for d in detections if d['score']>=.65 and d['box'][3]>height*.5 and
                    d['box'][2]>width*.25 and d['box'][0]<width*.75]
        if not candidates: self.previous=None; self.hits=0; self.last=-1; return False
        candidate=max(candidates,key=lambda d:d['score'])
        consistent=self.previous is not None and 0<stamp-self.last<=800 and iou(self.previous['box'],candidate['box'])>=.25
        if consistent: self.hits+=1
        else: self.hits=1; self.first=stamp
        self.previous=candidate; self.last=stamp
        if self.hits>=3 and stamp-self.first>=800 and stamp-self.warned>=12000:
            self.warned=stamp; self.previous=None; self.hits=0; self.last=-1; return True
        return False


def main():
    parser=argparse.ArgumentParser()
    for name in ['video','model','output']: parser.add_argument('--'+name,type=pathlib.Path,required=True)
    parser.add_argument('--annotations',type=pathlib.Path); parser.add_argument('--interval-ms',type=int,default=400)
    parser.add_argument('--runtime',choices=['grid','mediapipe'],default='grid')
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    if args.interval_ms<=0: raise ValueError('Sampling interval must be positive')
    labels={r['index']:r for r in json.loads(args.annotations.read_text(encoding='utf8'))['frames']} if args.annotations else {}
    detector=None
    if args.runtime=='grid':
        from evaluate import tf, letterbox, decode
        interpreter=tf.lite.Interpreter(model_path=str(args.model),num_threads=2); interpreter.allocate_tensors()
        input_index=interpreter.get_input_details()[0]['index']; output_index=interpreter.get_output_details()[0]['index']
    else:
        from evaluate_task_detector import mp, detector_options, predict, TASK_CONFIG
        detector=mp.tasks.vision.ObjectDetector.create_from_options(detector_options(args.model))
    capture=cv2.VideoCapture(str(args.video))
    if not capture.isOpened(): raise ValueError('Video cannot be decoded')
    fps=capture.get(cv2.CAP_PROP_FPS)
    if fps<=0: raise ValueError('Video has no usable constant frame-rate metadata')
    # Frame-index time is deterministic for this CFR benchmark, not a physical sensor clock.
    index=0; next_sample=0.; analyzed=0; reviewed=0; eligible=[]; latencies=[]; processing=[]; totals=np.zeros(3,dtype=np.int64)
    replay=TemporalReplay(); started=time.perf_counter()
    with (args.output/'predictions.jsonl').open('w',encoding='utf8') as stream:
        while True:
            ok,frame=capture.read()
            if not ok: break
            stamp=index/fps*1000
            if stamp+1e-6<next_sample: index+=1; continue
            next_sample=stamp+args.interval_ms
            before=time.perf_counter(); height,width=frame.shape[:2]
            rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
            if args.runtime=='grid':
                value,transform=letterbox(Image.fromarray(rgb))
                interpreter.set_tensor(input_index,value[None]); inference_start=time.perf_counter(); interpreter.invoke()
                latency=(time.perf_counter()-inference_start)*1000
                detections=decode(interpreter.get_tensor(output_index)[0],transform,width,height)
            else:
                detections,latency=predict(detector,rgb)
            qualifies=replay.observe(detections,int(stamp),width,height)
            if qualifies: eligible.append(stamp)
            if index in labels and labels[index].get('reviewed') is True:
                label=labels[index]; totals+=match(detections,label['boxes'],label.get('ignored',[]),.3); reviewed+=1
            latencies.append(latency); processing.append((time.perf_counter()-before)*1000)
            stream.write(json.dumps(dict(index=index,timestamp_ms=stamp,detections=detections,warning_policy_eligible=qualifies,inference_ms=latency))+'\n')
            analyzed+=1; index+=1
    capture.release(); elapsed=time.perf_counter()-started
    if detector is not None: detector.close()
    if not analyzed: raise ValueError('Video yielded no decodable sampled frames')
    tp,fp,fn=map(int,totals)
    report=dict(source_sha256=hashlib.sha256(args.video.read_bytes()).hexdigest(),model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
                decoded_frames=index,analyzed_frames=analyzed,nominal_fps=fps,interval_ms=args.interval_ms,
                runtime=args.runtime,
                mediapipe_version=mp.__version__ if detector is not None else None,
                detector_options=TASK_CONFIG if detector is not None else None,
                inference_timing_scope='Bare LiteRT invoke' if args.runtime=='grid' else 'MediaPipe detect including graph preprocessing/postprocessing; not bare inference',
                reviewed_frames=reviewed,metrics_at_point3=dict(tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None) if reviewed else None,
                warning_policy_eligible_timestamps_ms=eligible,production_ground_warnings_enabled=False,
                inference_ms={f'p{p}':float(np.percentile(latencies,p)) for p in [50,95,99]},
                sampled_processing_ms={f'p{p}':float(np.percentile(processing,p)) for p in [50,95,99]},
                elapsed_seconds=elapsed,decode_and_inference_frames_per_second=index/elapsed,
                limitations=['Unreviewed frames have no precision/recall labels. No detection is not evidence of safety.',
                             'Temporal replay uses video timestamps; offline throughput is not live Android preview frame rate.',
                             'A single clip is not a representative walking-camera evaluation.'])
    (args.output/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf8'); print(json.dumps(report,indent=2))


if __name__=='__main__': main()
