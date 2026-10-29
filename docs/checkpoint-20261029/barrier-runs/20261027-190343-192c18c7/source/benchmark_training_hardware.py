"""Measure actual encoder batches and decoder updates on verified training images."""
import argparse
import json
from pathlib import Path
import time

import cv2
import numpy as np
import tensorflow as tf
from tensorflow import keras
from train_masked_segmentation import (make_encoder, make_decoder, segmentation_loss,
                                       verified_arrays, verified_batches, SIZE, SEED)
from training_hardware import configure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('data-root', 'backbone', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--device', choices=['cpu', 'gpu'], required=True)
    parser.add_argument('--threads', type=int, default=8)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new benchmark output file')
    hardware = configure(args.device, args.threads)
    keras.utils.set_random_seed(SEED)
    tf.config.experimental.enable_op_determinism()
    phone = args.data_root / 'masked-segmentation-v1'
    negative = args.data_root / 'segmentation-negatives-v1'
    records = []
    for root, amount in ((phone, 4), (negative, 12)):
        candidates = json.loads((root / 'manifest.json').read_text())['records']
        records.extend({**r, 'root': root} for r in [r for r in candidates if r['split'] == 'train'][:amount])
    roots = lambda r: r['root']
    batches = list(verified_batches(records, roots, 32))
    assert len(batches) == 1 and len(batches[0][0]) == 32
    images, masks = batches[0]
    original_arrays = [verified_arrays(roots(r), r) for r in records]
    np.testing.assert_array_equal(images, np.concatenate([pair[0] for pair in original_arrays]))
    np.testing.assert_array_equal(masks, np.concatenate([pair[1] for pair in original_arrays]))
    encoder = make_encoder(args.backbone)
    encode = tf.function(lambda value: encoder(value, training=False),
                         input_signature=[tf.TensorSpec((None, SIZE, SIZE, 3), tf.float32)])
    values = images.astype(np.float32) / 127.5 - 1
    features = encode(values)
    if args.device == 'gpu' and 'GPU:' not in features[0].device:
        raise ValueError('Encoder output did not execute on GPU')
    reference = [encoder(pair[0].astype(np.float32)/127.5-1, training=False) for pair in original_arrays]
    maximum_error = 0.
    for index, result in enumerate(features):
        expected = np.concatenate([item[index].numpy() for item in reference])
        actual = result.numpy()
        np.testing.assert_allclose(actual, expected, rtol=1e-3, atol=1e-3)
        maximum_error = max(maximum_error, float(np.max(np.abs(actual-expected))))
    timings = []
    for _ in range(5):
        started = time.perf_counter()
        result = [item.numpy() for item in encode(values)]
        timings.append((time.perf_counter()-started)*1000)
    decoder = make_decoder([tuple(item.shape[1:]) for item in features])
    decoder.compile(optimizer=keras.optimizers.Adam(1e-3), loss=segmentation_loss)
    labels = np.stack([cv2.resize(mask, (80,80), interpolation=cv2.INTER_NEAREST) for mask in masks])[...,None].astype(np.float32)
    # Same 16-image optimization batch as the full training recipe.
    cache = [item[:16].astype(np.float16).astype(np.float32) for item in result]
    before = [v.numpy().copy() for v in decoder.weights]
    losses, train_ms = [], []
    for _ in range(4):
        started = time.perf_counter()
        loss = float(decoder.train_on_batch(cache, labels[:16]))
        losses.append(loss)
        train_ms.append((time.perf_counter()-started)*1000)
    if not np.isfinite(losses).all() or not any(np.any(old != new.numpy()) for old,new in zip(before,decoder.weights)):
        raise ValueError('Decoder did not complete finite optimizer updates')
    hardware['encoder_output_device'] = features[0].device
    hardware['decoder_weight_device'] = decoder.weights[0].value.device
    report = dict(hardware=hardware, tensorflow=tf.__version__, keras=keras.__version__,
                  real_images=32, batch_order_and_masks_match=True, batch_reference_max_abs_error=maximum_error,
                  encoder_batch_ms=timings, encoder_batch_median_ms=float(np.median(timings)),
                  train_batch_size=16, decoder_losses=losses, decoder_step_ms=train_ms,
                  steady_decoder_median_ms=float(np.median(train_ms[1:])),
                  optimizer_updated_weights=True,
                  limitations=['Short warm-cache benchmark, not full-run speed or accuracy.',
                               'First decoder step includes tracing/compilation; excluded from steady median.'])
    if args.device == 'gpu':
        report['gpu_memory_bytes'] = tf.config.experimental.get_memory_info('GPU:0')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
