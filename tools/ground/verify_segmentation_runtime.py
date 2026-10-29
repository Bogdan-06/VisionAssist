"""Verify the shared adapter reproduces all validation pixel counts exactly."""
import argparse
import hashlib
import json
import os
import pathlib
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
import numpy as np
from segmentation_runtime import Segmenter


def main():
    parser = argparse.ArgumentParser()
    for name in ('data', 'training', 'output'):
        parser.add_argument('--'+name, type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new verification file')
    report = json.loads((args.training/'training.json').read_text(encoding='utf8'))
    expected = json.loads((args.training/'validation.json').read_text(encoding='utf8'))
    manifest_path = args.data/'manifest.json'
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != report['manifest_sha256']:
        raise ValueError('Training manifest changed')
    model = args.training/'segmentation.tflite'
    if hashlib.sha256(model.read_bytes()).hexdigest() != report['model_sha256']:
        raise ValueError('Export hash mismatch')
    manifest = json.loads(manifest_path.read_text(encoding='utf8'))
    segmenter = Segmenter(model)
    counts = {key:np.zeros(3, np.int64) for key in expected['pixel_metrics']}
    frames = clips = 0
    for record in manifest['records']:
        if record['split'] != 'val':
            continue
        entry = record['training_arrays']
        path = (args.data/entry['path']).resolve()
        if not path.is_relative_to(args.data.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('Prepared data differs')
        with np.load(path, allow_pickle=False) as data:
            for rgb, truth in zip(data['images'], data['masks']):
                probability, _ = segmenter.predict(rgb)
                truth = truth.astype(bool)
                for key in counts:
                    prediction = probability >= float(key)
                    counts[key] += [np.count_nonzero(prediction & truth),
                                    np.count_nonzero(prediction & ~truth), np.count_nonzero(~prediction & truth)]
                frames += 1
        clips += 1
    if frames != expected['frames'] or clips != expected['clips']:
        raise ValueError('Validation coverage differs')
    for key, value in counts.items():
        np.testing.assert_array_equal(value, [expected['pixel_metrics'][key][name] for name in ('tp','fp','fn')])
    result = dict(passed=True, clips=clips, frames=frames, model_sha256=report['model_sha256'],
                  counts={key:value.tolist() for key,value in counts.items()},
                  scope='Exact shared-adapter pixel count agreement with direct-interpreter validation; not detection quality')
    args.output.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
