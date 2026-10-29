"""Independent UK wet/dry benchmark; no optimization and no invented condition labels.

Invalid annotation images are reported and excluded, never silently counted as negatives.
Optional reviewed condition JSON maps image IDs to lists such as ["wet", "shadow"].
"""
import argparse, hashlib, io, json, pathlib, time, zipfile
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image
from detection_metrics import match


def records(archive):
    accepted=[]; excluded=[]
    for name in sorted(n for n in archive.namelist() if n.endswith('.xml')):
        root=ET.fromstring(archive.read(name)); image='IMG/'+root.findtext('filename')
        with Image.open(io.BytesIO(archive.read(image))) as photo: width,height=photo.size
        problems=[]
        if (width,height)!=(int(root.findtext('size/width')),int(root.findtext('size/height'))): problems.append('XML/image dimensions differ')
        boxes=[]; ignored=[]
        for obj in root.findall('object'):
            if obj.findtext('name').lower()!='pothole': problems.append('Unknown annotation class'); continue
            b=obj.find('bndbox'); values=[float(b.findtext(k)) for k in ['xmin','ymin','xmax','ymax']]
            x1,y1,x2,y2=values
            if not np.isfinite(values).all() or x1<0 or y1<0 or x2>width or y2>height or x2<=x1 or y2<=y1:
                problems.append(dict(invalid_box=values,image_size=[width,height])); continue
            box=[max(0,x1-1),max(0,y1-1),x2,y2]
            (ignored if obj.findtext('difficult','0')=='1' else boxes).append(box)
        record=dict(id=pathlib.PurePosixPath(image).stem,image=image,width=width,height=height,boxes=boxes,ignored=ignored)
        if problems: excluded.append(dict(id=record['id'],problems=problems))
        else: accepted.append(record)
    return accepted,excluded


def main():
    from evaluate import tf, letterbox, decode
    parser=argparse.ArgumentParser()
    for name in ['dataset','model','output']: parser.add_argument('--'+name,type=pathlib.Path,required=True)
    parser.add_argument('--conditions',type=pathlib.Path)
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    with args.dataset.open('rb') as stream: dataset_hash=hashlib.file_digest(stream,'sha256').hexdigest()
    if dataset_hash!='a154cab487415c02269041f674e9e790b6ca61afc1c9ac417e9f1aae3e283a22': raise ValueError('External benchmark hash mismatch')
    condition_tags=json.loads(args.conditions.read_text(encoding='utf8')) if args.conditions else {}
    interpreter=tf.lite.Interpreter(model_path=str(args.model),num_threads=2); interpreter.allocate_tensors()
    input_index=interpreter.get_input_details()[0]['index']; output_index=interpreter.get_output_details()[0]['index']
    thresholds=[.1,.2,.3,.4,.5,.6,.65,.7,.75,.8,.9]
    strata={'all':dict(images=0,totals={str(t):np.zeros(3,dtype=np.int64) for t in thresholds})}
    latencies=[]
    with zipfile.ZipFile(args.dataset) as archive, (args.output/'predictions.jsonl').open('w',encoding='utf8') as stream:
        accepted,excluded=records(archive)
        for index,record in enumerate(accepted):
            with Image.open(io.BytesIO(archive.read(record['image']))) as image: value,transform=letterbox(image)
            interpreter.set_tensor(input_index,value[None]); started=time.perf_counter(); interpreter.invoke()
            latencies.append((time.perf_counter()-started)*1000)
            detections=decode(interpreter.get_tensor(output_index)[0],transform,record['width'],record['height'])
            tags=condition_tags.get(record['id'],[])
            for stratum in ['all']+list(dict.fromkeys(tags)):
                if stratum not in strata: strata[stratum]=dict(images=0,totals={str(t):np.zeros(3,dtype=np.int64) for t in thresholds})
                strata[stratum]['images']+=1
                for t in thresholds: strata[stratum]['totals'][str(t)]+=match(detections,record['boxes'],record['ignored'],t)
            stream.write(json.dumps(dict(**record,conditions=tags,detections=detections,inference_ms=latencies[-1]))+'\n')
            if index%100==0: print(index,'/',len(accepted),flush=True)
    result_strata={}
    for name,stratum in strata.items():
        metrics={}
        for threshold,total in stratum['totals'].items():
            tp,fp,fn=map(int,total)
            metrics[threshold]=dict(tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None)
        result_strata[name]=dict(images=stratum['images'],metrics=metrics)
    report=dict(dataset_doi='10.17632/tp95cdvgm8.1',source_sha256=dataset_hash,
                model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),excluded_images=excluded,strata=result_strata,
                inference_ms={f'p{p}':float(np.percentile(latencies,p)) for p in [50,95,99]},
                conditions_source='Reviewed condition tags only; no tags are inferred from the dataset title.',
                limitations=['Mostly positive close-up road photos; not an unbiased walking-camera or negative-scene sample.',
                             'Annotation mismatch images excluded as a whole; exclusion details retained.',
                             'Research evaluation only; no independent-navigation safety claim.'])
    (args.output/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf8'); print(json.dumps(report,indent=2))


if __name__=='__main__': main()
