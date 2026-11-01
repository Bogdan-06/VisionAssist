"""Export explicitly selected saved weights, without fitting or changing the source."""
import argparse
import json
from pathlib import Path
import shutil

from experiment_store import atomic_json, digest, read_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--task',choices=['pothole','barrier'],required=True)
    for name in ('checkpoint','data-root','backbone','output'):
        p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():
        raise ValueError('Export needs a new output directory')
    expected=digest(args.checkpoint)
    args.output.mkdir(parents=True,exist_ok=False)
    snapshot=args.output/args.checkpoint.name
    shutil.copyfile(args.checkpoint,snapshot)
    if digest(snapshot)!=expected or digest(args.checkpoint)!=expected:
        raise ValueError('Source checkpoint changed while copying')
    if args.task=='barrier':
        from train_modelmaker import tf, object_detector, model_spec, prepare_checkpoint
        settings=read_json(args.checkpoint.parent/'run.json')
        provenance=read_json(args.data_root/'barrier-coco-v1/provenance.json')
        if settings['classes']!=['stairs','curb','step'] or settings['data_provenance']!=provenance:
            raise ValueError('Checkpoint class/data mismatch')
        if 'smoke_only' not in settings:
            settings['smoke_only']=read_json(args.checkpoint.parent/'training.json')['smoke_only']
        checkpoint=prepare_checkpoint(args.data_root/'mobilenetv2_ssd_i320_ckpt.tar.gz',args.output/'pretrained')
        model_spec.MOBILENET_V2_I320_FILES.path=str(checkpoint.resolve())
        detector=object_detector.ObjectDetector(
            model_spec=model_spec.SupportedModels.get(object_detector.SupportedModels.MOBILENET_V2_I320),
            label_names=['background','stairs','curb','step'],
            hparams=object_detector.HParams(export_dir=str(args.output)),
            model_options=object_detector.ModelOptions())
        detector._create_model()
        detector._model.compile(optimizer=tf.keras.optimizers.SGD(momentum=.9))
        detector._model(tf.zeros([1,320,320,3]),image_shape=tf.constant([[320.,320.]]),training=False)
        detector._model.optimizer.build(detector._model.trainable_variables)
        from portable_modelmaker_weights import load_weights
        load_report=load_weights(detector._model,snapshot)
        atomic_json(args.output/'weight-loading.json',load_report)
        detector.export_model()
        model=args.output/'model.tflite'
        atomic_json(args.output/'training.json',dict(model_sha256=digest(model),classes=settings['classes'],
            data_provenance=provenance,smoke_only=settings['smoke_only'],warning_eligible=False,
            selection='explicit checkpoint requested for evaluation; not test-based selection'))
    else:
        from train_masked_segmentation import tf, keras, make_encoder, make_decoder, segmentation_loss
        if snapshot.suffix!='.keras' and snapshot.name not in ('decoder.weights.h5','segmentation.weights.h5'):
            raise ValueError('Use decoder.weights.h5, segmentation.weights.h5 or a full .keras decoder checkpoint')
        encoder=make_encoder(args.backbone)
        if snapshot.suffix=='.keras':
            decoder=keras.models.load_model(snapshot,custom_objects={'segmentation_loss':segmentation_loss})
        else:
            decoder=make_decoder([tuple(t.shape[1:]) for t in encoder.outputs])
            if snapshot.name=='decoder.weights.h5':
                decoder.load_weights(snapshot)
        inputs=keras.Input((320,320,3),batch_size=1,name='rgb_minus_one_to_one')
        model=keras.Model(inputs,decoder(encoder(inputs,training=False)))
        if snapshot.name=='segmentation.weights.h5':
            model.load_weights(snapshot)
        converter=tf.lite.TFLiteConverter.from_keras_model(model)
        converter.target_spec.supported_ops=[tf.lite.OpsSet.TFLITE_BUILTINS]
        (args.output/'segmentation.tflite').write_bytes(converter.convert())
    atomic_json(args.output/'export.json',dict(source_checkpoint=str(args.checkpoint),
        checkpoint_sha256=expected,warning_eligible=False,installs_android_model=False))


if __name__=='__main__':
    main()
