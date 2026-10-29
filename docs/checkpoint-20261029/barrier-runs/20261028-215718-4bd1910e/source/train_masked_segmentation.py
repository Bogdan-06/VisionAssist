"""Train an offline pothole segmentation candidate on published smartphone masks.

Research output only: never modifies Android assets or the production warning gate.
Frozen, pinned Keras ImageNet backbone; new compact decoder trained from actual masks.
"""
import argparse
import hashlib
import json
import os
import pathlib
import time

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
import cv2
import numpy as np
import tensorflow as tf
from tensorflow import keras

from prepare_masked_videos import SOURCE_SHA256
from training_hardware import configure

SEED = 4217
SIZE = 320
OUTPUT_SIZE = 80
BACKBONE_SHA = '279052de2cfa801003aa6cc25cc4d007d35dd0b76f06935268c79788b7642d05'
LAYERS = ('block_2_add', 'block_5_add', 'block_12_add', 'block_16_project')


def file_sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def make_encoder(weights):
    if file_sha(weights) != BACKBONE_SHA:
        raise ValueError('Backbone differs from reviewed official Keras weights')
    base = keras.applications.MobileNetV2(input_shape=(SIZE, SIZE, 3), alpha=.5,
                                         include_top=False, weights=None)
    base.load_weights(weights)
    encoder = keras.Model(base.input, [base.get_layer(name).output for name in LAYERS], name='frozen_mobilenet')
    encoder.trainable = False
    return encoder


def make_decoder(shapes):
    inputs = [keras.Input(shape, name=f'skip_{index}') for index, shape in enumerate(shapes)]
    x = keras.layers.Conv2D(32, 1, activation='relu')(inputs[-1])
    for skip in reversed(inputs[:-1]):
        x = keras.layers.UpSampling2D(2, interpolation='bilinear')(x)
        lateral = keras.layers.Conv2D(24, 1, activation='relu')(skip)
        x = keras.layers.Concatenate()([x, lateral])
        x = keras.layers.SeparableConv2D(24, 3, padding='same', activation='relu')(x)
        x = keras.layers.SeparableConv2D(24, 3, padding='same', activation='relu')(x)
    output = keras.layers.Conv2D(1, 1, activation='sigmoid', name='pothole_probability')(x)
    return keras.Model(inputs, output, name='pothole_mask_decoder')


@keras.utils.register_keras_serializable(package='VisionAssist')
def segmentation_loss(truth, probability):
    # Both losses average per image; large masks do not get a larger sample weight.
    probability = tf.clip_by_value(probability, 1e-6, 1-1e-6)
    bce = -tf.reduce_mean(truth*tf.math.log(probability)+(1-truth)*tf.math.log(1-probability), axis=(1, 2, 3))
    intersection = tf.reduce_sum(truth*probability, axis=(1, 2, 3))
    denominator = tf.reduce_sum(truth+probability, axis=(1, 2, 3))
    dice_loss = 1-(2*intersection+1)/(denominator+1)
    return bce+dice_loss


def verified_arrays(root, record):
    entry = record['training_arrays']
    if not entry or record['split'] not in ('train', 'val'):
        raise ValueError('Test/unprepared arrays are forbidden in fitting')
    path = (root/entry['path']).resolve()
    if not path.is_relative_to(root.resolve()) or file_sha(path) != entry['sha256']:
        raise ValueError('Array path/checksum mismatch')
    with np.load(path, allow_pickle=False) as data:
        images, masks = data['images'], data['masks']
    count = len(record['samples'])
    if (images.shape != (count, SIZE, SIZE, 3) or masks.shape != (count, SIZE, SIZE)
            or images.dtype != np.uint8 or masks.dtype != np.uint8 or not np.isin(masks, (0, 1)).all()):
        raise ValueError('Invalid prepared image/mask arrays')
    if record.get('negative_annotation_verified') and np.any(masks):
        raise ValueError('An annotation-defined negative has a nonempty mask')
    return images, masks


def scores(tp, fp, fn):
    return dict(tp=int(tp), fp=int(fp), fn=int(fn),
                iou=float(tp/(tp+fp+fn)) if tp+fp+fn else None,
                dice=float(2*tp/(2*tp+fp+fn)) if 2*tp+fp+fn else None,
                precision=float(tp/(tp+fp)) if tp+fp else None,
                recall=float(tp/(tp+fn)) if tp+fn else None)


def verified_batches(records, root_for, batch_size):
    """Preserve record/frame order while batching across singleton negative records."""
    if batch_size < 1:
        raise ValueError('Cache batch size must be positive')
    images_batch, masks_batch = [], []
    for record in records:
        images, masks = verified_arrays(root_for(record), record)
        for image, mask in zip(images, masks):
            images_batch.append(image)
            masks_batch.append(mask)
            if len(images_batch) == batch_size:
                yield np.stack(images_batch), np.stack(masks_batch)
                images_batch, masks_batch = [], []
    if images_batch:
        yield np.stack(images_batch), np.stack(masks_batch)


def run(args):
    if args.output.exists():
        raise ValueError('Use a new output directory')
    if min(args.epochs, args.threads, args.batch_size, args.cache_batch_size) <= 0:
        raise ValueError('Epochs/threads/batch sizes must be positive')
    manifest_path = args.data/'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf8'))
    summary = manifest['summary']
    if summary['source_sha256'] != SOURCE_SHA256 or not summary['exact_duplicate_audit_passed']:
        raise ValueError('Dataset source/duplicate audit failed')
    for split, count in (('train', 372), ('val', 124), ('test', 123)):
        if sum(r['split'] == split for r in manifest['records']) != count:
            raise ValueError('Unexpected published split')
    records = [{**r, 'domain':'phone'} for r in manifest['records'] if r['split'] in ('train','val')]
    if any(r['training_arrays'] for r in manifest['records'] if r['split'] == 'test'):
        raise ValueError('Unexpected test training arrays')
    negative_manifest_sha = None
    if args.negative_data is not None:
        from prepare_segmentation_negatives import RDD_SHA, MANIFEST_SHA
        negative_manifest_path = args.negative_data/'manifest.json'
        negative_manifest_sha = file_sha(negative_manifest_path)
        negatives = json.loads(negative_manifest_path.read_text(encoding='utf8'))
        meta = negatives['summary']
        if (meta['kind'] != 'rdd_annotated_negatives' or meta['source_sha256'] != RDD_SHA
                or meta['split_manifest_sha256'] != MANIFEST_SHA or not meta['no_exact_cross_split_duplicates']):
            raise ValueError('Unexpected negative-data provenance')
        if ({split:sum(r['split']==split for r in negatives['records']) for split in ('train','val')}
                != {'train':1993,'val':1086} or len(negatives['records']) != 3079
                or any(not r['negative_annotation_verified'] or len(r['samples']) != 1 for r in negatives['records'])):
            raise ValueError('Unexpected negative-data records')
        records.extend({**r, 'domain':'rdd_negative'} for r in negatives['records'])
    if len({(r['domain'],r['id']) for r in records}) != len(records):
        raise ValueError('Duplicate training/validation record identity')
    records.sort(key=lambda r: 0 if r['split']=='train' else 1)
    def data_root(record):
        return args.data if record['domain']=='phone' else args.negative_data
    args.output.mkdir(parents=True)
    script_bytes = pathlib.Path(__file__).read_bytes()
    (args.output/'train_masked_segmentation.source.py').write_bytes(script_bytes)
    started = time.time()
    def status(stage, **extra):
        (args.output/'status.json').write_text(json.dumps(dict(stage=stage, pid=os.getpid(),
            elapsed_seconds=time.time()-started, **extra), indent=2), encoding='utf8')
    try:
        hardware = configure(args.device, args.threads)
        print('Training hardware: ' + json.dumps(hardware), flush=True)
        cv2.setNumThreads(2)
        keras.utils.set_random_seed(SEED)
        tf.config.experimental.enable_op_determinism()
        encoder = make_encoder(args.backbone)
        encode = tf.function(lambda value: encoder(value, training=False),
                             input_signature=[tf.TensorSpec((None, SIZE, SIZE, 3), tf.float32)])
        shapes = [tuple(output.shape[1:]) for output in encoder.outputs]
        decoder = make_decoder(shapes)
        count = sum(len(r['samples']) for r in records)
        training_count = sum(len(r['samples']) for r in records if r['split'] == 'train')
        features = [np.lib.format.open_memmap(args.output/f'features-{i}.npy', mode='w+',
                    dtype='float16', shape=(count, *shape)) for i, shape in enumerate(shapes)]
        labels = np.lib.format.open_memmap(args.output/'labels.npy', mode='w+', dtype='uint8',
                                          shape=(count, OUTPUT_SIZE, OUTPUT_SIZE, 1))
        offset = 0
        status('caching_features', total_frames=count)
        cache_started = time.perf_counter()
        for batch_index, (images, masks) in enumerate(verified_batches(records, data_root, args.cache_batch_size)):
            length = len(images)
            values = encode(images.astype(np.float32)/127.5-1)
            if batch_index == 0:
                hardware['encoder_output_device'] = values[0].device
                if hardware['selected'] == 'gpu' and 'GPU:' not in values[0].device:
                    raise RuntimeError('GPU was selected but encoder output is not on the GPU')
            for feature, value in zip(features, values):
                feature[offset:offset+length] = value.numpy().astype(np.float16)
            for sample_index, mask in enumerate(masks):
                labels[offset+sample_index, ..., 0] = cv2.resize(mask, (OUTPUT_SIZE, OUTPUT_SIZE), interpolation=cv2.INTER_NEAREST)
            offset += length
            if batch_index % 10 == 0 or offset == count:
                print(f'Cached {offset}/{count} real frames', flush=True)
                status('caching_features', frames=offset, total_frames=count)
        if offset != count:
            raise ValueError('Batched cache lost or duplicated frames')
        cache_seconds = time.perf_counter() - cache_started
        for feature in features:
            feature.flush()
        labels.flush()
        rng = np.random.default_rng(SEED)
        def dataset(start, stop, shuffle):
            def generate():
                indices = np.arange(start, stop)
                if shuffle:
                    rng.shuffle(indices)
                for offset in range(0, len(indices), args.batch_size):
                    batch = indices[offset:offset+args.batch_size]
                    yield tuple(feature[batch].astype(np.float32) for feature in features), labels[batch].astype(np.float32)
            data = tf.data.Dataset.from_generator(generate, output_signature=(
                tuple(tf.TensorSpec((None, *shape), tf.float32) for shape in shapes),
                tf.TensorSpec((None, OUTPUT_SIZE, OUTPUT_SIZE, 1), tf.float32)))
            options = tf.data.Options()
            options.threading.private_threadpool_size = 2
            batches = (stop-start+args.batch_size-1)//args.batch_size
            return data.apply(tf.data.experimental.assert_cardinality(batches)).with_options(options).prefetch(2)
        class Progress(keras.callbacks.Callback):
            def on_epoch_end(self, epoch, logs=None):
                status('training', completed_epochs=epoch+1, metrics={k:float(v) for k,v in (logs or {}).items()})
        decoder.compile(optimizer=keras.optimizers.Adam(1e-3), loss=segmentation_loss)
        status('training', completed_epochs=0)
        history = decoder.fit(dataset(0, training_count, True),
            validation_data=dataset(training_count, count, False), epochs=args.epochs, verbose=2,
            callbacks=[keras.callbacks.ModelCheckpoint(str(args.output/'decoder.weights.h5'), monitor='val_loss',
                        save_best_only=True, save_weights_only=True),
                keras.callbacks.EarlyStopping(monitor='val_loss', patience=4, min_delta=0),
                keras.callbacks.ReduceLROnPlateau(monitor='val_loss', patience=2, factor=.5, min_lr=1e-5),
                keras.callbacks.CSVLogger(str(args.output/'history.csv')), Progress()])
        decoder.load_weights(args.output/'decoder.weights.h5')
        inputs = keras.Input((SIZE, SIZE, 3), batch_size=1, name='rgb_minus_one_to_one')
        model = keras.Model(inputs, decoder(encoder(inputs, training=False)), name='visionassist_pothole_segmentation')
        model.save_weights(args.output/'segmentation.weights.h5')
        status('exporting')
        converter = tf.lite.TFLiteConverter.from_keras_model(model)
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
        content = converter.convert()
        (args.output/'segmentation.tflite').write_bytes(content)
        interpreter = tf.lite.Interpreter(model_content=content, num_threads=2)
        interpreter.allocate_tensors()
        input_index = interpreter.get_input_details()[0]['index']
        output_index = interpreter.get_output_details()[0]['index']
        totals = {str(t): np.zeros(3, np.int64) for t in (.3, .5, .65)}
        clips, latency, differences = [], [], []
        status('evaluating_validation')
        for clip_index, record in enumerate(r for r in records if r['split'] == 'val' and r['domain'] == 'phone'):
            images, masks = verified_arrays(args.data, record)
            clip_totals = {key: np.zeros(3, np.int64) for key in totals}
            for image, truth in zip(images, masks):
                value = image[None].astype(np.float32)/127.5-1
                interpreter.set_tensor(input_index, value)
                before = time.perf_counter()
                interpreter.invoke()
                latency.append((time.perf_counter()-before)*1000)
                output = interpreter.get_tensor(output_index)[0, ..., 0]
                if clip_index < 3:
                    expected = model(value, training=False).numpy()[0, ..., 0]
                    np.testing.assert_allclose(output, expected, rtol=1e-3, atol=1e-4)
                    differences.append(float(np.max(np.abs(output-expected))))
                probability = cv2.resize(output, (SIZE, SIZE), interpolation=cv2.INTER_LINEAR)
                truth = truth.astype(bool)
                for key in totals:
                    prediction = probability >= float(key)
                    observed = np.array([np.count_nonzero(prediction & truth),
                        np.count_nonzero(prediction & ~truth), np.count_nonzero(~prediction & truth)], np.int64)
                    clip_totals[key] += observed
                    totals[key] += observed
            clips.append(dict(id=record['id'], frames=len(images),
                              metrics={key:scores(*value) for key, value in clip_totals.items()}))
        evaluation = dict(split='published validation; development evidence', clips=len(clips),
            frames=len(latency), resolution=[SIZE, SIZE],
            pixel_metrics={key:scores(*value) for key, value in totals.items()},
            mean_clip_iou={key:float(np.mean([clip['metrics'][key]['iou'] for clip in clips])) for key in totals},
            tflite_invoke_ms=dict(p50=float(np.percentile(latency, 50)), p95=float(np.percentile(latency, 95))),
            keras_tflite_parity=dict(frames=len(differences), max_absolute_error=max(differences), rtol=.001, atol=.0001),
            per_clip=clips)
        (args.output/'validation.json').write_text(json.dumps(evaluation, indent=2), encoding='utf8')
        if args.negative_data is not None:
            status('evaluating_negative_validation')
            negative_metrics = {key:dict(images_with_prediction=0,foreground_pixels=0) for key in totals}
            negative_count = 0
            for record in (r for r in records if r['split']=='val' and r['domain']=='rdd_negative'):
                images, _ = verified_arrays(data_root(record), record)
                for image in images:
                    interpreter.set_tensor(input_index, image[None].astype(np.float32)/127.5-1)
                    interpreter.invoke()
                    probability = cv2.resize(interpreter.get_tensor(output_index)[0,...,0], (SIZE,SIZE), interpolation=cv2.INTER_LINEAR)
                    for key, metric in negative_metrics.items():
                        foreground = int(np.count_nonzero(probability >= float(key)))
                        metric['images_with_prediction'] += int(foreground > 0)
                        metric['foreground_pixels'] += foreground
                    negative_count += 1
            negative_report = dict(images=negative_count, resolution=[SIZE,SIZE], metrics=negative_metrics,
                negative_manifest_sha256=negative_manifest_sha,
                limitation='Annotation-defined validation negatives used in checkpoint selection; not untouched test data.')
            (args.output/'negative-validation.json').write_text(json.dumps(negative_report,indent=2),encoding='utf8')
        report = dict(architecture='Frozen MobileNetV2 alpha 0.5 + separable multiscale mask decoder',
            classes=['pothole mask'], input=[1,SIZE,SIZE,3], input_normalization='RGB / 127.5 - 1',
            output=[1,OUTPUT_SIZE,OUTPUT_SIZE,1], output_semantics='sigmoid probability per stride-four pixel',
            backbone_sha256=BACKBONE_SHA, manifest_sha256=file_sha(manifest_path), source_sha256=SOURCE_SHA256,
            script_sha256=hashlib.sha256(script_bytes).hexdigest(), model_sha256=hashlib.sha256(content).hexdigest(),
            bytes=len(content), seed=SEED, requested_epochs=args.epochs, completed_epochs=len(history.history['loss']),
            selected_epoch=int(np.argmin(history.history['val_loss']))+1,
            selection='minimum validation BCE plus soft-Dice loss over phone frames and supplied RDD negatives; no test fitting/selection',
            training_frames=training_count, validation_frames=count-training_count,
            phone_validation_frames=evaluation['frames'], negative_manifest_sha256=negative_manifest_sha,
            training_negative_frames=sum(len(r['samples']) for r in records if r['split']=='train' and r['domain']=='rdd_negative'),
            validation_negative_frames=sum(len(r['samples']) for r in records if r['split']=='val' and r['domain']=='rdd_negative'),
            sampling='Uniform per frame; five sampled frames per phone clip, one frame per RDD negative image',
            frozen_encoder=True, augmentation='none for this initial cached-feature baseline',
            feature_cache_dtype='float16; exported backbone inference remains float32',
            tensorflow=tf.__version__, keras=keras.__version__, elapsed_seconds=time.time()-started,
            hardware=hardware, batch_size=args.batch_size, cache_batch_size=args.cache_batch_size,
            cache_seconds=cache_seconds,
            limitations=summary['limitations']+[
                'Pixel metrics at 320x320 do not measure calibrated hazard confidence or warning-event reliability.',
                'RDD negatives, when supplied, are annotation-defined road scenes, not reviewed negative walking clips.',
                'Only negative RDD images enter mask training; positive road-domain mask coverage remains missing.',
                'No Android runtime integration, curb/stair classes or depth estimation in this candidate.'])
        (args.output/'training.json').write_text(json.dumps(report, indent=2), encoding='utf8')
        status('completed', model_sha256=report['model_sha256'])
        print(json.dumps(report, indent=2), flush=True)
        print(json.dumps(evaluation['pixel_metrics']), flush=True)
    except BaseException as error:
        status('failed', error=f'{type(error).__name__}: {error}')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('data', 'backbone', 'output'):
        parser.add_argument('--'+name, type=pathlib.Path, required=True)
    parser.add_argument('--epochs', type=int, default=12)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--negative-data', type=pathlib.Path)
    parser.add_argument('--device', choices=['auto', 'cpu', 'gpu'], default='auto')
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--cache-batch-size', type=int, default=32)
    run(parser.parse_args())
