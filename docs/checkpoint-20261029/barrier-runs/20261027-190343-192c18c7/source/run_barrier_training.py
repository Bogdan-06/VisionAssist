"""Train and evaluate a fresh three-class barrier detector without changing Android."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

from run_training import require_file, run_step, save_json

SCRIPTS=Path(__file__).resolve().parent


def preflight(data, device):
    for name in ('accessibility-barriers/wm_barriers_data.zip','barrier-prepared-v1/manifest.json',
                 'barrier-prepared-v1/summary.json','barrier-coco-v1/provenance.json',
                 'mobilenetv2_ssd_i320_ckpt.tar.gz'):
        require_file(data/name)
    manifest=(data/'barrier-prepared-v1/manifest.json').read_bytes()
    summary=json.loads((data/'barrier-prepared-v1/summary.json').read_text(encoding='utf8'))
    provenance=json.loads((data/'barrier-coco-v1/provenance.json').read_text(encoding='utf8'))
    if hashlib.sha256(manifest).hexdigest()!=summary['manifest_sha256'] or summary['manifest_sha256']!=provenance['manifest_sha256']:
        raise ValueError('Prepared and exported datasets differ')
    if provenance['classes']!=['stairs','curb','step'] or provenance['test_images_exported']:
        raise ValueError('Unexpected training export')
    for split in ('train','validation'):
        for name in ('labels.json','image-sha256.json'):
            require_file(data/'barrier-coco-v1'/split/name)
    # Probe in a child so TensorFlow's memory/context are released before training.
    code="""import json,sys,importlib.metadata as m
import tensorflow as tf
from mediapipe_model_maker import object_detector
import mediapipe
gpus=tf.config.list_physical_devices('GPU')
if sys.argv[1]=='gpu' and not gpus: raise RuntimeError('TensorFlow cannot see the GPU')
print('PREFLIGHT_JSON '+json.dumps(dict(python=sys.version,available_gpus=[g.name for g in gpus],versions={n:m.version(n) for n in ('tensorflow','keras','mediapipe','mediapipe-model-maker','tf-models-official')})))
"""
    result=subprocess.run([sys.executable,'-c',code,device],text=True,encoding='utf8',errors='replace',capture_output=True)
    if result.returncode:
        raise RuntimeError('Detector environment check failed:\n'+result.stdout+result.stderr)
    return json.loads(next(line[len('PREFLIGHT_JSON '):] for line in result.stdout.splitlines() if line.startswith('PREFLIGHT_JSON ')))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,required=True)
    parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--device',choices=('cpu','gpu'),default='gpu')
    parser.add_argument('--epochs',type=int,default=20)
    parser.add_argument('--threads',type=int,default=8)
    parser.add_argument('--batch-size',type=int,default=8)
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    if not 1<=args.epochs<=1000 or not 1<=args.threads<=64 or not 1<=args.batch_size<=128:
        parser.error('Invalid epoch, thread or batch count')
    data,output=args.data_root.resolve(),args.output_root.resolve()
    if args.device=='cpu': os.environ['CUDA_VISIBLE_DEVICES']='-1'
    print('Checking the prepared barrier data and detector environment...',flush=True)
    versions=preflight(data,args.device)
    ancestor=output
    while not ancestor.exists(): ancestor=ancestor.parent
    if not ancestor.is_dir() or shutil.disk_usage(ancestor).free<16*1024**3:
        raise ValueError('Allow at least 16 GiB free for source-image caches and checkpoints')
    print(json.dumps(versions,indent=2),flush=True)
    print('Fresh stairs/curb/step run; earlier weights are not continued. Android is not modified.',flush=True)
    if args.check_only:
        print('Check-only passed. Full image/archive hashes are checked by the training/evaluation stages.',flush=True)
        return 0
    run=output/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    (run/'source').mkdir(parents=True)
    (run/'logs').mkdir()
    for path in SCRIPTS.glob('*.py'): shutil.copy2(path,run/'source'/path.name)
    train=['train_modelmaker.py','--data',data/'barrier-coco-v1','--checkpoint-archive',data/'mobilenetv2_ssd_i320_ckpt.tar.gz',
           '--output',run/'training','--class-profile','barriers','--device',args.device,'--threads',args.threads,
           '--epochs',args.epochs,'--batch-size',args.batch_size]
    if args.smoke: train+=['--smoke']
    steps=[('train',train)]
    for split in (('validation',) if args.smoke else ('validation','test')):
        argv=['evaluate_barrier_detector.py','--model',run/'training/model.tflite',
              '--archive',data/'accessibility-barriers/wm_barriers_data.zip',
              '--prepared',data/'barrier-prepared-v1','--split',split,'--output',run/split]
        if args.smoke: argv+=['--max-images',64]
        steps.append(('evaluate-'+split,argv))
    commands=[(name,[sys.executable,'-u',str(run/'source'/argv[0])]+list(map(str,argv[1:]))) for name,argv in steps]
    save_json(run/'run.json',dict(started_utc=datetime.now(timezone.utc).isoformat(),versions=versions,
              arguments={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},commands=commands,
              installs_android_model=False))
    environment=os.environ.copy()
    environment.update(PYTHONUNBUFFERED='1',PYTHONIOENCODING='utf-8',TF_CPP_MIN_LOG_LEVEL='2',
                       OMP_NUM_THREADS=str(args.threads),TF_NUM_INTRAOP_THREADS=str(args.threads),TF_NUM_INTEROP_THREADS='2')
    started=time.monotonic(); completed=[]; stage='starting'
    print(f'Results: {run}\nKeep this terminal open; Ctrl+C stops the run.',flush=True)
    try:
        for stage,command in commands:
            save_json(run/'status.json',dict(state='running',stage=stage,pid=os.getpid(),completed=completed))
            stage_env=environment.copy()
            if stage!='train': stage_env['CUDA_VISIBLE_DEVICES']='-1'
            run_step(command,run/'logs'/(stage+'.log'),stage_env)
            completed.append(stage)
    except BaseException as error:
        save_json(run/'status.json',dict(state='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',
                  stage=stage,completed=completed,error=str(error),elapsed_seconds=time.monotonic()-started))
        raise
    save_json(run/'status.json',dict(state='completed',completed=completed,quality_approved=False,
                                   elapsed_seconds=time.monotonic()-started))
    print(f'Training and evaluations completed: {run}\nQuality approval and Android integration are separate.',flush=True)
    return 0


if __name__=='__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as error:
        print(f'ERROR: {error}',file=sys.stderr)
        sys.exit(1)
