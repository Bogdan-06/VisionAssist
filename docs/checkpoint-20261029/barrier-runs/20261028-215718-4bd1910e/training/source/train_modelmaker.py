"""Train the official COCO-pretrained MobileNetV2 320 detector on audited boxes.

Requires the isolated, documented Model Maker environment. Smoke artifacts are never accuracy
evidence. Only the exported training/validation selection is read; the test split is absent.
"""
import argparse
import csv
import hashlib
import json
import importlib.metadata
import math
import os
import pathlib
import shutil
import tarfile
import time

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
import tensorflow as tf
from mediapipe_model_maker import object_detector
from mediapipe_model_maker.python.vision.object_detector import model_spec
import h5py
import numpy as np

CHECKPOINT_SHA256='73dd229998007e47259b93b00f65aca410ec053a15e67d78519ce5c1779f521f'
CHECKPOINT_URL='https://storage.googleapis.com/tf_model_garden/vision/qat/mobilenetv2_ssd_coco/mobilenetv2_ssd_i320_ckpt.tar.gz'


def prepare_checkpoint(archive, destination):
    with archive.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=CHECKPOINT_SHA256:
            raise ValueError('Unrecognized pretrained checkpoint archive')
    destination.mkdir(parents=True,exist_ok=False)
    with tarfile.open(archive) as source:
        for member in source.getmembers():
            if not (member.isfile() or member.isdir()):
                raise ValueError('Checkpoint archive contains a link or special file')
            if not (destination/member.name).resolve().is_relative_to(destination.resolve()):
                raise ValueError('Checkpoint archive escapes its destination')
        source.extractall(destination,filter='data')
    indices=list(destination.rglob('ckpt-277200.index'))
    if len(indices)!=1 or not indices[0].with_name('ckpt-277200.data-00000-of-00001').is_file():
        raise ValueError('Unexpected checkpoint contents')
    return indices[0].parent


def smoke_subset(source, target, negatives_only=False, required_classes=()):
    doc=json.loads((source/'labels.json').read_text(encoding='utf8'))
    positives={a['image_id'] for a in doc['annotations']}
    negative=[i for i in doc['images'] if i['id'] not in positives][:8]
    positive=[]
    if not negatives_only:
        for category in required_classes:
            candidates={a['image_id'] for a in doc['annotations'] if a['category_id']==category}
            if not any(i['id'] in candidates for i in positive):
                positive.append(next(i for i in doc['images'] if i['id'] in candidates))
        chosen_positive_ids={i['id'] for i in positive}
        positive += [i for i in doc['images'] if i['id'] in positives and i['id'] not in chosen_positive_ids][:8-len(positive)]
    chosen=positive+negative
    if len(negative)!=8 or (not negatives_only and len(positive)!=8):
        raise ValueError('Smoke check requires real labelled positive and negative images')
    selected={i['id'] for i in chosen}
    (target/'images').mkdir(parents=True)
    for item in chosen:
        shutil.copyfile(source/'images'/item['file_name'],target/'images'/item['file_name'])
    doc['images']=chosen
    doc['annotations']=[a for a in doc['annotations'] if a['image_id'] in selected]
    (target/'labels.json').write_text(json.dumps(doc),encoding='utf8')
    return target


class FiniteLosses(tf.keras.callbacks.Callback):
    """Model Maker logs total_loss, not the loss key TerminateOnNaN expects."""
    @staticmethod
    def check(logs, stage):
        for name,value in (logs or {}).items():
            if (name=='loss' or name.endswith('_loss')) and not math.isfinite(float(value)):
                raise FloatingPointError(f'Nonfinite {name} during {stage}: {value}')

    def on_train_batch_end(self, batch, logs=None):
        self.check(logs,f'training batch {batch}')

    def on_epoch_end(self, epoch, logs=None):
        self.check(logs,f'epoch {epoch}')


class ReviewedDetector(object_detector.ObjectDetector):
    def __init__(self, *args, resume=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._resume=resume

    def _create_and_train_model(self, train_data, validation_data):
        # The upstream API exposes its history/callback hooks internally in this pinned version.
        output=pathlib.Path(self._hparams.export_dir)
        best_loss=None
        if self._resume:
            history=list(csv.DictReader((self._resume['path']/'history.csv').open(encoding='utf8')))
            history=[row for row in history if int(row['epoch'])<self._resume['selected_epoch']]
            best_loss=min(float(row['val_total_loss']) for row in history)
            # The snapshot reader treats the history flush as completion of a weights save.
            shutil.copyfile(self._resume['path']/'best.weights.h5',output/'best.weights.h5')
            with (output/'history.csv').open('w',newline='',encoding='utf8') as stream:
                writer=csv.DictWriter(stream,fieldnames=history[0].keys()); writer.writeheader(); writer.writerows(history)
        self._callbacks=[FiniteLosses(),
            tf.keras.callbacks.ModelCheckpoint(str(output/'best.weights.h5'),monitor='val_total_loss',
                save_best_only=True,save_weights_only=True,initial_value_threshold=best_loss),
            tf.keras.callbacks.ModelCheckpoint(str(output/'last.weights.h5'),save_weights_only=True),
            tf.keras.callbacks.CSVLogger(str(output/'history.csv'),append=bool(self._resume))]
        super()._create_and_train_model(train_data,validation_data)
        self._model.load_weights(str(output/'best.weights.h5'))
        self._save_float_ckpt()

    def _train_model(self, train_data, validation_data, preprocessor=None, checkpoint_path=None):
        if not self._resume:
            return super()._train_model(train_data,validation_data,preprocessor,checkpoint_path)
        # Match the pinned upstream data/compile path, adding an explicit epoch/optimizer restore.
        steps=train_data.size//self._hparams.batch_size
        train_dataset=train_data.gen_tf_dataset(batch_size=self._hparams.batch_size,is_training=True,
            shuffle=self._shuffle,preprocess=preprocessor).take(steps)
        validation_dataset=validation_data.gen_tf_dataset(batch_size=self._hparams.batch_size,
            is_training=False,preprocess=preprocessor)
        self._model.compile(optimizer=self._optimizer,loss=self._loss_function,metrics=self._metric_functions)
        self._model(tf.zeros([1,320,320,3]),image_shape=tf.constant([[320.,320.]]),training=False)
        self._optimizer.build(self._model.trainable_variables)
        weights=self._resume['path']/self._resume.get('resume_weights_filename','best.weights.h5')
        self._model.load_weights(str(weights))
        # Loading weights must not silently skip momentum or the iteration/schedule position.
        with h5py.File(weights,'r') as saved:
            saved_variables=saved['optimizer/vars']
            variables=self._optimizer.variables()
            if len(variables)!=len(saved_variables): raise ValueError('Optimizer variable count differs')
            for index,variable in enumerate(variables):
                if not np.array_equal(variable.numpy(),saved_variables[str(index)][()]):
                    raise ValueError(f'Optimizer variable {index} was not restored exactly')
        restored_step=int(self._optimizer.iterations.numpy())
        initial_epoch=self._resume['selected_epoch']
        if not initial_epoch*steps <= restored_step <= initial_epoch*(steps+1):
            raise ValueError('Saved optimizer step is inconsistent with the selected epoch')
        report=dict(source_snapshot=str(self._resume['path'].resolve()),initial_epoch=initial_epoch,
            restored_optimizer_step=restored_step,verified_optimizer_variables=len(variables),
            weights_sha256=self._resume['weights_sha256'],
            limitation='Optimizer/model state and schedule restored; shuffled data order after restart is not bitwise identical to an uninterrupted run.')
        (pathlib.Path(self._hparams.export_dir)/'resume.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print('RESUME_VERIFIED '+json.dumps(report),flush=True)
        self._history=self._model.fit(x=train_dataset,initial_epoch=initial_epoch,epochs=self._hparams.epochs,
            steps_per_epoch=None,validation_data=validation_dataset,callbacks=self._callbacks,
            class_weight=self._hparams.class_weights)


def main():
    parser=argparse.ArgumentParser()
    for name in ('data','checkpoint-archive','output'):
        parser.add_argument('--'+name,type=pathlib.Path,required=True)
    parser.add_argument('--epochs',type=int,default=20)
    parser.add_argument('--batch-size',type=int,default=8)
    parser.add_argument('--class-profile',choices=('pothole','barriers'),default='pothole')
    parser.add_argument('--device',choices=('auto','cpu','gpu'),default='cpu')
    parser.add_argument('--threads',type=int,default=4)
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--resume-from',type=pathlib.Path)
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('Use a new output directory; never overwrite a run')
    provenance=json.loads((args.data/'provenance.json').read_text(encoding='utf8'))
    if provenance['test_images_exported'] or provenance['image_folder']!='images':
        raise ValueError('Unexpected COCO export contract')
    classes=['pothole'] if args.class_profile=='pothole' else ['stairs','curb','step']
    if provenance['classes']!=classes:
        raise ValueError('Exported classes do not match the requested training profile')
    if args.class_profile=='barriers':
        if provenance['source']!='https://doi.org/10.5281/zenodo.6382090' or provenance['license']!='CC BY 4.0':
            raise ValueError('Unexpected barrier source/license')
        # The new export carries immutable annotation/image hashes; validate before fitting.
        for split in ('train','validation'):
            folder=args.data/split
            for filename,key in [('labels.json','labels_sha256'),('image-sha256.json','image_hashes_sha256')]:
                if hashlib.sha256((folder/filename).read_bytes()).hexdigest()!=provenance['files'][split][key]:
                    raise ValueError('Barrier export metadata changed')
            hashes=json.loads((folder/'image-sha256.json').read_text(encoding='utf8'))
            if len(hashes)!=provenance['counts'][split]['images']:
                raise ValueError('Barrier image inventory differs')
            print(f'Checking {len(hashes)} original {split} image hashes...',flush=True)
            for index,(name,expected) in enumerate(hashes.items(),1):
                if pathlib.Path(name).name!=name or '/' in name or '\\' in name:
                    raise ValueError('Invalid barrier image filename')
                if hashlib.sha256((folder/'images'/name).read_bytes()).hexdigest()!=expected:
                    raise ValueError('Barrier training image changed')
                if index%1000==0 or index==len(hashes):
                    print(f'Image hashes verified: {split} {index}/{len(hashes)}',flush=True)
    resume=None
    if args.resume_from:
        if args.smoke or args.epochs!=20 or args.batch_size!=8:
            raise ValueError('Snapshot resume preserves the original 20-epoch, batch-8 schedule')
        resume=json.loads((args.resume_from/'snapshot.json').read_text(encoding='utf-8-sig'))
        if resume['data_provenance']!=provenance or resume['pretrained_checkpoint_sha256']!=CHECKPOINT_SHA256:
            raise ValueError('Resume snapshot has different data or pretrained provenance')
        if not 0<resume['selected_epoch']<args.epochs: raise ValueError('No remaining epochs')
        resume_weights=resume.get('resume_weights_filename','best.weights.h5')
        if resume_weights not in ('best.weights.h5','last.weights.h5'):
            raise ValueError('Invalid resume checkpoint filename')
        checks=[(resume_weights,'weights_sha256'),('history.csv','history_sha256')]
        if resume_weights=='last.weights.h5': checks.append(('best.weights.h5','best_weights_sha256'))
        for name,key in checks:
            if hashlib.sha256((args.resume_from/name).read_bytes()).hexdigest()!=resume[key]:
                raise ValueError('Resume snapshot checksum mismatch')
        resume['path']=args.resume_from
    from training_hardware import configure
    hardware=configure(args.device,args.threads)
    tf.keras.utils.set_random_seed(4217)
    # TF 2.15 has no deterministic CUDA ResizeNearestNeighborGrad kernel used by
    # this FPN. Preserve the architecture and GPU training; do not promise bitwise
    # repeatability. Native CPU regression retains its original deterministic path.
    deterministic_ops=hardware['selected']=='cpu'
    if deterministic_ops:
        tf.config.experimental.enable_op_determinism()
    reproducibility=dict(seed=4217,deterministic_ops=deterministic_ops,
        limitation=None if deterministic_ops else
        'Pinned TF 2.15 GPU resize gradients are nondeterministic; same seed/data/settings need not produce identical weights.')
    print('REPRODUCIBILITY '+json.dumps(reproducibility),flush=True)
    args.output.mkdir(parents=True)
    source_snapshot=args.output/'source'
    source_snapshot.mkdir()
    source_hashes={}
    for name in ('train_modelmaker.py','training_hardware.py','modelmaker_windows_vision.py'):
        content=(pathlib.Path(__file__).parent/name).read_bytes()
        (source_snapshot/name).write_bytes(content)
        source_hashes[name]=hashlib.sha256(content).hexdigest()
    checkpoint=prepare_checkpoint(args.checkpoint_archive,args.output/'pretrained')
    # A verified existing absolute directory avoids upstream download/extraction at import time.
    model_spec.MOBILENET_V2_I320_FILES.path=str(checkpoint.resolve())
    train_path=args.data/'train'; val_path=args.data/'validation'
    if args.smoke:
        # Pothole regression preserves the existing all-negative optimization check.
        # Barrier smoke additionally exercises real boxes from every new class.
        required=(1,2,3) if args.class_profile=='barriers' else ()
        train_path=smoke_subset(train_path,args.output/'smoke-train',
                                negatives_only=args.class_profile=='pothole',required_classes=required)
        val_path=smoke_subset(val_path,args.output/'smoke-validation',required_classes=required)
    train=object_detector.Dataset.from_coco_folder(str(train_path),cache_dir=str(args.output/'cache-train'))
    validation=object_detector.Dataset.from_coco_folder(str(val_path),cache_dir=str(args.output/'cache-validation'))
    expected_train=(16 if args.class_profile=='barriers' else 8) if args.smoke else provenance['counts']['train']['images']
    expected_validation=16 if args.smoke else provenance['counts']['validation']['images']
    if (train.size,validation.size)!=(expected_train,expected_validation):
        raise ValueError('Loader dropped labelled images, including negatives')
    if train.label_names!=['background']+classes or validation.label_names!=train.label_names:
        raise ValueError('Unexpected label map')
    print(f'LOADER_OK train={train.size} validation={validation.size} labels={train.label_names}',flush=True)
    epochs=1 if args.smoke else args.epochs
    batch_size=4 if args.smoke else args.batch_size
    from mediapipe_model_maker.python.core.utils import model_util
    steps=model_util.get_steps_per_epoch(steps_per_epoch=None,batch_size=batch_size,train_data=train)
    optimizer_settings=dict(type='SGD',momentum=.9,base_learning_rate=.3,
        batch_scaled_initial_rate=.3*batch_size/256,steps_per_epoch=steps,
        warmup_steps=int(steps*epochs*.1),cosine_decay_steps=steps*epochs,cosine_decay_alpha=.1)
    versions={name:importlib.metadata.version(name) for name in
              ('tensorflow','keras','mediapipe','mediapipe-model-maker','tf-models-official','numpy')}
    (args.output/'run.json').write_text(json.dumps(dict(epochs=epochs,batch_size=batch_size,seed=4217,
        data_provenance=provenance,learning_rate=.3,cosine_decay_alpha=.1,
        optimizer_settings=optimizer_settings,versions=versions,source_sha256=source_hashes,reproducibility=reproducibility,
        class_profile=args.class_profile,classes=classes,hardware=hardware,
        resume_snapshot=str(args.resume_from.resolve()) if args.resume_from else None),indent=2),encoding='utf8')
    hparams=object_detector.HParams(export_dir=str(args.output),epochs=epochs,batch_size=batch_size,
        learning_rate=.3,cosine_decay_epochs=epochs,cosine_decay_alpha=.1,shuffle=True)
    options=object_detector.ObjectDetectorOptions(
        supported_model=object_detector.SupportedModels.MOBILENET_V2_I320,hparams=hparams)
    started=time.time()
    if resume:
        model=ReviewedDetector(model_spec=model_spec.SupportedModels.get(options.supported_model),
            label_names=train.label_names,hparams=hparams,model_options=object_detector.ModelOptions(),resume=resume)
        model._create_and_train_model(train,validation)
    else:
        model=ReviewedDetector.create(train_data=train,validation_data=validation,options=options)
    variable_devices=sorted({v.device for v in model._model.trainable_variables})
    if hardware['selected']=='gpu' and not any('GPU:' in device for device in variable_devices):
        raise RuntimeError('GPU selected, but no trainable variable resides on the GPU')
    model.export_model()
    artifact=args.output/'model.tflite'
    runtime=tf.lite.Interpreter(model_path=str(artifact),num_threads=2)
    runtime.allocate_tensors()
    tensor_info=lambda tensor:dict(name=tensor['name'],shape=tensor['shape'].tolist(),dtype=str(tensor['dtype']))
    completed_history=list(csv.DictReader((args.output/'history.csv').open(encoding='utf8')))
    report=dict(architecture='COCO-pretrained MobileNetV2 320, FPN and anchor-based detection head',
        trainable_variable_devices=variable_devices,
        tensorflow_gpu_allocator_bytes=tf.config.experimental.get_memory_info('GPU:0') if hardware['selected']=='gpu' else None,
        optimizer_settings=optimizer_settings,versions=versions,source_sha256=source_hashes,reproducibility=reproducibility,
        classes=classes,class_profile=args.class_profile,hardware=hardware,
        smoke_only=args.smoke,warning_eligible=False,seed=4217,epochs=len(completed_history),
        configured_epochs=epochs,initial_epoch=resume['selected_epoch'] if resume else 0,batch_size=batch_size,
        selected_epoch=int(min(completed_history,key=lambda row:float(row['val_total_loss']))['epoch'])+1,
        training_images=train.size,validation_images=validation.size,
        checkpoint_url=CHECKPOINT_URL,checkpoint_sha256=CHECKPOINT_SHA256,
        data_provenance=provenance,model_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
        model_bytes=artifact.stat().st_size,elapsed_seconds=time.time()-started,
        inputs=[tensor_info(t) for t in runtime.get_input_details()],
        outputs=[tensor_info(t) for t in runtime.get_output_details()],
        limitations=['Smoke runs test plumbing only, not detection quality.',
                    'Source-image performance does not establish walking-camera or warning reliability.',
                    'Step includes doorstep/other source step labels; it is not general uneven-ground detection.']
                    if args.class_profile=='barriers' else
                    ['Smoke runs test plumbing only, not detection quality.',
                     'Road imagery; walking-domain validation and independent evaluation still required.'])
    (args.output/'training.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__': main()
