"""Export a stable copy of a completed epoch's best weights without interrupting training.

Uses the pinned Model Maker model/exporter. It performs no training and changes no run files.
The result is explicitly an intermediate checkpoint, not the final 20-epoch artifact.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import pathlib
from train_modelmaker import tf, object_detector, model_spec, prepare_checkpoint, CHECKPOINT_SHA256


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    for name in ('run', 'data', 'checkpoint-archive', 'output'):
        parser.add_argument('--'+name, type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): raise ValueError('Use a new snapshot directory')
    history_path = args.run/'history.csv'
    weights_path = args.run/'best.weights.h5'
    if weights_path.stat().st_mtime_ns > history_path.stat().st_mtime_ns:
        raise ValueError('Checkpoint save precedes its history flush; retry after the epoch save')
    history_bytes = history_path.read_bytes()
    history = list(csv.DictReader(io.StringIO(history_bytes.decode('utf8'))))
    if not history: raise ValueError('No completed epoch available')
    losses = [float(row['val_total_loss']) for row in history]
    if not all(math.isfinite(loss) for loss in losses): raise ValueError('Nonfinite validation loss')
    weights = weights_path.read_bytes()
    if (digest(weights_path.read_bytes()) != digest(weights) or history_path.read_bytes() != history_bytes
            or weights_path.stat().st_mtime_ns > history_path.stat().st_mtime_ns):
        raise ValueError('Training updated the checkpoint during the snapshot; retry after the epoch save')
    provenance = json.loads((args.data/'provenance.json').read_text(encoding='utf8'))
    if provenance['test_images_exported'] or provenance['image_folder'] != 'images':
        raise ValueError('Unexpected data contract')
    args.output.mkdir(parents=True)
    snapshot = args.output/'best.weights.h5'
    snapshot.write_bytes(weights)
    (args.output/'history.csv').write_bytes(history_bytes)
    del weights
    checkpoint = prepare_checkpoint(args.checkpoint_archive, args.output/'pretrained')
    model_spec.MOBILENET_V2_I320_FILES.path = str(checkpoint.resolve())
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(4217)
    model = object_detector.ObjectDetector(
        model_spec=model_spec.SupportedModels.get(object_detector.SupportedModels.MOBILENET_V2_I320),
        label_names=['background', 'pothole'],
        hparams=object_detector.HParams(export_dir=str(args.output)),
        model_options=object_detector.ModelOptions())
    model._create_model()
    model._model(tf.zeros([1,320,320,3]), image_shape=tf.constant([[320.,320.]]), training=False)
    model._model.load_weights(str(snapshot))
    model.export_model()
    artifact = args.output/'model.tflite'
    report = dict(intermediate_checkpoint=True, source_run=str(args.run.resolve()),
        completed_epochs=len(history), selected_epoch=int(history[losses.index(min(losses))]['epoch'])+1,
        selection='lowest completed validation total loss; no accuracy-based selection',
        weights_sha256=digest(snapshot.read_bytes()), history_sha256=digest(history_bytes),
        pretrained_checkpoint_sha256=CHECKPOINT_SHA256, data_provenance=provenance,
        model_sha256=digest(artifact.read_bytes()), model_bytes=artifact.stat().st_size,
        warning_eligible=False,
        limitations=['Intermediate export of completed weights; source training may be running or stopped.',
                    'Export does not establish detection quality, Android compatibility or walking safety.'])
    (args.output/'snapshot.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2),flush=True)


if __name__ == '__main__': main()
