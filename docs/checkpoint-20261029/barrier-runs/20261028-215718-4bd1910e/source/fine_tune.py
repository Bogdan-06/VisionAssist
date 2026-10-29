"""Fine-tune the baseline using training images only and validation checkpoint selection.

The earlier test report is retained; this iteration is development, not an independent trial.
BatchNorm statistics remain frozen. No evaluation images enter the optimizer.
"""
import argparse, hashlib, io, json, pathlib, shutil, time, zipfile
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from train_baseline import tf, keras, SIZE, GRID, SEED, make_backbone, make_head, letterbox, targets


def localization_loss(target, prediction):
    p=tf.clip_by_value(prediction[...,0],1e-5,1-1e-5); truth=target[...,0]
    mask=target[...,5]; positive=tf.cast(truth==1,tf.float32); negative=1-positive
    count=tf.maximum(1.,tf.reduce_sum(mask))
    heat=-tf.reduce_sum(positive*tf.square(1-p)*tf.math.log(p)+negative*tf.pow(1-truth,4)*tf.square(p)*tf.math.log(1-p))/count
    xx,yy=tf.meshgrid(tf.range(GRID,dtype=tf.float32),tf.range(GRID,dtype=tf.float32))
    grid=tf.stack([xx,yy],axis=-1)
    def bounds(value):
        center=(value[...,1:3]+grid)/GRID; size=value[...,3:5]
        return center-size/2,center+size/2
    plo,phi=bounds(prediction); tlo,thi=bounds(target)
    intersection=tf.reduce_prod(tf.maximum(0.,tf.minimum(phi,thi)-tf.maximum(plo,tlo)),axis=-1)
    union=tf.reduce_prod(phi-plo,axis=-1)+tf.reduce_prod(thi-tlo,axis=-1)-intersection
    enclosing=tf.reduce_prod(tf.maximum(phi,thi)-tf.minimum(plo,tlo),axis=-1)
    giou=intersection/(union+1e-7)-(enclosing-union)/(enclosing+1e-7)
    regression=tf.reduce_sum(mask*(1-giou))/count
    offsets=tf.reduce_sum(tf.abs(prediction[...,1:3]-target[...,1:3])*mask[...,None])/count
    return heat+2*regression+.5*offsets


def main():
    parser=argparse.ArgumentParser()
    for name in ['dataset','initial','output']: parser.add_argument('--'+name,type=pathlib.Path,required=True)
    parser.add_argument('--epochs',type=int,default=12)
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    tf.config.threading.set_intra_op_parallelism_threads(4); tf.config.threading.set_inter_op_parallelism_threads(2)
    keras.utils.set_random_seed(SEED); tf.config.experimental.enable_op_determinism()
    manifest=json.loads((args.initial/'manifest.json').read_text(encoding='utf8'))
    with args.dataset.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=manifest['source_sha256']: raise ValueError('Dataset changed')
    train=[r for r in manifest['records'] if r['used_for_training']]
    validation=[r for r in manifest['records'] if r['split']=='validation' and not r['ignored']]
    if any(r['split']!='train' for r in train): raise ValueError('Training split mismatch')
    shutil.copyfile(args.initial/'manifest.json',args.output/'manifest.json')
    architecture=json.loads((args.initial/'training.json').read_text(encoding='utf8')).get('architecture_key','center')
    backbone=make_backbone(architecture); backbone.load_weights(args.initial/'backbone.weights.h5')
    head=make_head(backbone.output_shape[-1],architecture); head.load_weights(args.initial/'head.weights.h5')
    backbone.trainable=True
    for layer in backbone.layers:
        if isinstance(layer,keras.layers.BatchNormalization): layer.trainable=False
    inputs=keras.Input((SIZE,SIZE,3)); model=keras.Model(inputs,head(backbone(inputs,training=False)))
    model.compile(optimizer=keras.optimizers.Adam(1e-4,clipnorm=5),loss=localization_loss)
    rng=np.random.default_rng(SEED)
    def dataset(records,augment):
        def generate():
            order=np.arange(len(records))
            if augment: rng.shuffle(order)
            with zipfile.ZipFile(args.dataset) as archive:
                for index in order:
                    record=dict(records[index]); image=Image.open(io.BytesIO(archive.read(record['image']))).convert('RGB')
                    if augment:
                        if rng.random()<.5:
                            image=ImageOps.mirror(image); width=record['width']
                            record['boxes']=[[width-b[2],b[1],width-b[0],b[3]] for b in record['boxes']]
                        image=ImageEnhance.Brightness(image).enhance(float(rng.uniform(.65,1.3)))
                    value,transform=letterbox(image)
                    yield value,targets(record,transform)
        result=tf.data.Dataset.from_generator(generate,output_signature=(tf.TensorSpec((SIZE,SIZE,3),tf.float32),tf.TensorSpec((GRID,GRID,6),tf.float32)))
        options=tf.data.Options(); options.threading.private_threadpool_size=2
        return result.apply(tf.data.experimental.assert_cardinality(len(records))).with_options(options).batch(16).prefetch(1)
    start=time.time()
    model.fit(dataset(train,True),validation_data=dataset(validation,False),epochs=args.epochs,verbose=2,
        callbacks=[keras.callbacks.ModelCheckpoint(str(args.output/'best.weights.h5'),save_best_only=True,save_weights_only=True),
                   keras.callbacks.ReduceLROnPlateau(patience=3,factor=.5,min_lr=1e-6),keras.callbacks.CSVLogger(str(args.output/'history.csv'))])
    model.load_weights(args.output/'best.weights.h5')
    backbone.save_weights(args.output/'backbone.weights.h5'); head.save_weights(args.output/'head.weights.h5')
    inputs=keras.Input((SIZE,SIZE,3),batch_size=1,name='rgb_minus_one_to_one')
    export=keras.Model(inputs,head(backbone(inputs,training=False))); export.save(args.output/'ground_baseline.keras')
    converter=tf.lite.TFLiteConverter.from_keras_model(export)
    converter.target_spec.supported_ops=[tf.lite.OpsSet.TFLITE_BUILTINS]
    content=converter.convert(); (args.output/'ground_baseline.tflite').write_bytes(content)
    report=dict(architecture='MobileNetV2 + center/box head, fine-tuned convolution weights with frozen BatchNorm',architecture_key=architecture,
                initial_model_sha256=hashlib.sha256((args.initial/'ground_baseline.tflite').read_bytes()).hexdigest(),
                model_sha256=hashlib.sha256(content).hexdigest(),bytes=len(content),seed=SEED,epochs=args.epochs,
                training_images=len(train),validation_images=len(validation),elapsed_seconds=time.time()-start,
                augmentations=['horizontal flip','brightness 0.65 to 1.3'],loss='focal heatmap + 2 GIoU + 0.5 offset L1',
                classes=['RDD2022 D40 pothole'],tensorflow=tf.__version__,keras=keras.__version__)
    (args.output/'training.json').write_text(json.dumps(report,indent=2),encoding='utf8'); print(report,flush=True)


if __name__=='__main__': main()
