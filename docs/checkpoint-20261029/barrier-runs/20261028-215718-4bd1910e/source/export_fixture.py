"""Export one attributed real photograph for Android inference/ownership regression tests.

Selection is a correctly localized prediction, not a representative accuracy sample.
The complete held-out report, including misses/false positives, remains the accuracy evidence.
"""
import argparse, hashlib, io, json, pathlib, zipfile
import numpy as np
from PIL import Image
from evaluate import iou, tf, letterbox, decode

parser=argparse.ArgumentParser()
for name in ['dataset','training','evaluation','output']: parser.add_argument('--'+name,type=pathlib.Path,required=True)
args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
records={r['id']:r for r in json.loads((args.training/'manifest.json').read_text(encoding='utf8'))['records']}
candidates=[]
for line in (args.evaluation/'predictions.jsonl').read_text(encoding='utf8').splitlines():
    prediction=json.loads(line)
    if prediction['condition']!='original': continue
    record=records[prediction['id']]
    for detection in prediction['detections']:
        if any(iou(detection['box'],box)>=.5 for box in record['boxes']):
            candidates.append((detection['score'],record,prediction))
score,record,prediction=max(candidates,key=lambda item:item[0])
with zipfile.ZipFile(args.dataset) as archive: data=archive.read(record['image'])
(args.output/'rdd_pothole.jpg').write_bytes(data)
model=args.training/'ground_baseline.tflite'
with Image.open(io.BytesIO(data)) as image:
    value,_=letterbox(image)
# Lossless, already resized input isolates interpreter/decoder parity from JPEG/resize differences.
prepared=np.rint((value+1)*127.5).clip(0,255).astype(np.uint8)
Image.fromarray(prepared).save(args.output/'rdd_preprocessed.png')
interpreter=tf.lite.Interpreter(model_path=str(model),num_threads=2); interpreter.allocate_tensors()
interpreter.set_tensor(interpreter.get_input_details()[0]['index'],value[None]); interpreter.invoke()
golden=decode(interpreter.get_tensor(interpreter.get_output_details()[0]['index'])[0],(1.,1.,0,0),320,320,threshold=.3)
metadata=dict(source=record['image'],doi='10.6084/m9.figshare.21431547.v1',source_sha256=hashlib.sha256(data).hexdigest(),
              source_url='https://doi.org/10.6084/m9.figshare.21431547.v1',
              license_urls=['https://creativecommons.org/licenses/by/4.0/','https://creativecommons.org/licenses/by-sa/4.0/'],
              attribution='Arya et al., RDD2022: A multi-national image dataset for automatic Road Damage Detection',
              license='Figshare release: CC BY 4.0; source repository states CC BY-SA 4.0. Preserve attribution/share-alike for this fixture.',
              changes='Original JPEG renamed; PNG is the RGB 320px letterbox used for tensor parity.',record=record,python_prediction=prediction,
              model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),preprocessed_predictions=golden,
              purpose='Runtime regression fixture selected for correct localization; not an unbiased evaluation subset.')
(args.output/'rdd_pothole.json').write_text(json.dumps(metadata,indent=2),encoding='utf8')
print(record['id'],score,hashlib.sha256(data).hexdigest())
