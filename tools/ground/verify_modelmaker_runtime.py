"""Compare a restored checkpoint, exported LiteRT tensors, and actual Tasks scores.

Uses real validation images but does not measure accuracy or alter the running trainer.
"""
import argparse
import hashlib
import json
import pathlib

import cv2
import numpy as np

from train_modelmaker import tf, object_detector, model_spec, prepare_checkpoint
from evaluate_task_detector import mp, detector_options


def main():
    parser = argparse.ArgumentParser()
    for name in ('snapshot', 'data', 'checkpoint-archive', 'output'):
        parser.add_argument('--'+name, type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): raise ValueError('Use a new output directory')
    snapshot = json.loads((args.snapshot/'snapshot.json').read_text(encoding='utf8'))
    artifact = args.snapshot/'model.tflite'
    weights = args.snapshot/'best.weights.h5'
    for path, key in ((artifact, 'model_sha256'), (weights, 'weights_sha256')):
        if hashlib.sha256(path.read_bytes()).hexdigest() != snapshot[key]:
            raise ValueError('Snapshot checksum mismatch')
    labels_path = args.data/'validation'/'labels.json'
    labels = json.loads(labels_path.read_text(encoding='utf8'))
    positive_ids = {a['image_id'] for a in labels['annotations'] if a['category_id'] == 1}
    images = [im for im in labels['images'] if im['id'] in positive_ids][:3]
    if len(images) != 3: raise ValueError('Three real positive validation images required')
    args.output.mkdir(parents=True)
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    cv2.setNumThreads(2)
    checkpoint = prepare_checkpoint(args.checkpoint_archive, args.output/'pretrained')
    model_spec.MOBILENET_V2_I320_FILES.path = str(checkpoint.resolve())
    model = object_detector.ObjectDetector(
        model_spec=model_spec.SupportedModels.get(object_detector.SupportedModels.MOBILENET_V2_I320),
        label_names=['background', 'pothole'],
        hparams=object_detector.HParams(export_dir=str(args.output)),
        model_options=object_detector.ModelOptions())
    model._create_model()
    model._model(tf.zeros([1,320,320,3]), image_shape=tf.constant([[320.,320.]]), training=False)
    model._model.load_weights(str(weights))
    interpreter = tf.lite.Interpreter(model_path=str(artifact), num_threads=2)
    interpreter.allocate_tensors()
    input_detail = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()
    outputs_by_width = {int(d['shape'][-1]):d['index'] for d in output_details}
    if set(outputs_by_width) != {2,4}: raise ValueError('Unexpected output contract')
    results = []
    with mp.tasks.vision.ObjectDetector.create_from_options(detector_options(artifact)) as detector:
        graph = detector.get_graph_config()
        selected_nodes = [str(n) for n in graph.node if n.calculator in (
            'ImageToTensorCalculator', 'TensorsToDetectionsCalculator', 'NonMaxSuppressionCalculator')]
        (args.output/'runtime-options.pbtxt').write_text('\n'.join(selected_nodes), encoding='utf8')
        for record in images:
            name = record['file_name']
            if pathlib.Path(name).name != name or '\\' in name or '/' in name:
                raise ValueError('Unsafe image name')
            path = args.data/'validation'/'images'/name
            source = cv2.imread(str(path))
            if source is None: raise ValueError('Cannot decode real image')
            # Identical prepared pixels isolate export/normalization from resize-algorithm differences.
            rgb = cv2.cvtColor(cv2.resize(source, (320,320), interpolation=cv2.INTER_LINEAR), cv2.COLOR_BGR2RGB)
            value = rgb.astype(np.float32)[None]/127.5-1
            original = model._model(tf.constant(value), image_shape=tf.constant([[320.,320.]]), training=False)
            levels = sorted(original['cls_outputs'], key=int)
            expected_scores = tf.sigmoid(tf.concat([
                tf.reshape(original['cls_outputs'][level], [1,-1,2]) for level in levels], axis=1)).numpy()
            expected_boxes = tf.concat([
                tf.reshape(original['box_outputs'][level], [1,-1,4]) for level in levels], axis=1).numpy()
            interpreter.set_tensor(input_detail['index'], value); interpreter.invoke()
            actual_scores = interpreter.get_tensor(outputs_by_width[2])
            actual_boxes = interpreter.get_tensor(outputs_by_width[4])
            np.testing.assert_allclose(actual_scores, expected_scores, rtol=1e-3, atol=2e-5)
            np.testing.assert_allclose(actual_boxes, expected_boxes, rtol=1e-3, atol=2e-4)
            result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
            scores = [float(d.categories[0].score) for d in result.detections]
            expected_top = float(actual_scores[0,:,1].max())
            if expected_top >= .05:
                if not scores: raise AssertionError('Tasks lost all qualifying real predictions')
                np.testing.assert_allclose(max(scores), expected_top, rtol=1e-3, atol=2e-5)
            elif scores: raise AssertionError('Tasks returned scores below configured minimum')
            results.append(dict(image_id=record['id'], image_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                prepared_rgb_sha256=hashlib.sha256(rgb.tobytes()).hexdigest(),
                score_max_absolute_error=float(np.max(np.abs(actual_scores-expected_scores))),
                box_max_absolute_error=float(np.max(np.abs(actual_boxes-expected_boxes))),
                raw_top_pothole_score=expected_top, tasks_top_score=max(scores) if scores else None))
            print(json.dumps(results[-1]), flush=True)
    report = dict(model_sha256=snapshot['model_sha256'], weights_sha256=snapshot['weights_sha256'],
        selected_epoch=snapshot['selected_epoch'], images=len(results), results=results,
        tensorflow_version=tf.__version__, mediapipe_version=mp.__version__, passed=True,
        score_tolerance=dict(rtol=.001,atol=.00002), box_tolerance=dict(rtol=.001,atol=.0002),
        limitations=['Three prepared real images check export numerics, not detection accuracy.',
            'Raw box tensor agreement does not independently validate every decoded bounding box.',
            'Tasks top-score agreement checks normalization/score handling on 320-square inputs, not arbitrary camera geometry.',
            'No Android runtime, camera, microphone or cloud call is exercised.'])
    (args.output/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')


if __name__ == '__main__': main()
