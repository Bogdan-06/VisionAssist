# Isolated pretrained detector comparison on Windows

This experiment uses MediaPipe Model Maker 0.2.1.4 and Model Garden 2.15.0. Google marks
Model Maker deprecated. The Windows profile below is a project compatibility adaptation,
not a claim of upstream Windows training support. Keep it outside the Android source tree
and separate from the TensorFlow 2.20 custom-model environment.

The starting checkpoint is the Google-hosted MobileNetV2 320 COCO detector identified by
the installed `object_detector/model_spec.py`. It initializes the backbone, FPN, localization
head and compatible classification weights; the class-specific final layer is retrained.
The model has 2,555,830 parameters. No third-party pickle checkpoint is loaded.

- [Google customization guide](https://developers.google.com/edge/mediapipe/solutions/customization/object_detector)
- [Model specifications](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/model_maker/python/vision/object_detector/model_spec.py)
- [MediaPipe Apache-2.0 license](https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE)
- [Model Garden Apache-2.0 license](https://github.com/tensorflow/models/blob/master/LICENSE)

## Environment

Use Python 3.11 in a new virtual environment. The development run used CPython 3.11.17
installed by uv 0.13.1 into a dedicated workspace runtime directory. The main Python and
Android environments were not replaced.

```powershell
python3.11 -m venv C:\VisionAssistGround\modelmaker-venv
& C:\VisionAssistGround\modelmaker-venv\Scripts\python.exe -m pip install -r tools\ground\requirements-modelmaker-windows-core.txt
& C:\VisionAssistGround\modelmaker-venv\Scripts\python.exe -m pip install --no-deps mediapipe-model-maker==0.2.1.4 tf-models-official==2.15.0
& C:\VisionAssistGround\modelmaker-venv\Scripts\python.exe tools\ground\modelmaker_windows_vision.py
```

TensorFlow Text lacks a compatible native Windows package, and newer TensorFlow Addons
releases lack Windows wheels. This profile removes eager imports of unused text/other tasks.
Model Garden's actual vision layers, pretrained model, losses and TensorFlow operations remain
real. NLP text tasks are intentionally unavailable; a general `pip check` is not a claim that
the full upstream multi-task dependency graph is installed. Setuptools is pinned because
this legacy stack imports `pkg_resources`.

`modelmaker_windows_vision.py` verifies versions and original source SHA-256 before editing
three files inside the active venv. It retains originals and upstream license headers. It also
fixes two COCO-loader issues: silent removal of negative images and type inference from empty
annotation lists. Empty boxes are serialized as typed empty lists, never as a fake object.
Unknown local edits cause failure; the patch is idempotent for recognized versions.

## Checkpoint and data

```powershell
Invoke-WebRequest 'https://storage.googleapis.com/tf_model_garden/vision/qat/mobilenetv2_ssd_coco/mobilenetv2_ssd_i320_ckpt.tar.gz' -OutFile C:\VisionAssistGround\mobilenetv2_ssd_i320_ckpt.tar.gz
Get-FileHash C:\VisionAssistGround\mobilenetv2_ssd_i320_ckpt.tar.gz -Algorithm SHA256
```

The archive is 19,584,370 bytes. Required SHA-256:
`73dd229998007e47259b93b00f65aca410ec053a15e67d78519ce5c1779f521f`.
The training script checks this hash, rejects archive links/special files/path escapes, and
uses the verified local TensorFlow checkpoint instead of the framework's automatic downloader.
COCO pretraining is separate from RDD image licensing; no COCO photographs are distributed.

Run `export_coco.py` as described in the main README, using the unchanged training/validation
manifest and a new output directory. The pinned loader expects `images`, not the `data` folder
shown in some guide versions. No test images are exported. Retain RDD attribution and the
release/source CC BY / CC BY-SA notices in the generated provenance file.

## Smoke check, then training

```powershell
& C:\VisionAssistGround\modelmaker-venv\Scripts\python.exe tools\ground\train_modelmaker.py --data C:\VisionAssistGround\rdd-coco-v2 --checkpoint-archive C:\VisionAssistGround\mobilenetv2_ssd_i320_ckpt.tar.gz --output C:\VisionAssistGround\modelmaker-smoke --smoke
& C:\VisionAssistGround\modelmaker-venv\Scripts\python.exe tools\ground\train_modelmaker.py --data C:\VisionAssistGround\rdd-coco-v2 --checkpoint-archive C:\VisionAssistGround\mobilenetv2_ssd_i320_ckpt.tar.gz --output C:\VisionAssistGround\modelmaker-run --epochs 20 --batch-size 8
```

The smoke run trains only on eight real negative images, validating empty-target handling,
and validates on eight positives plus eight negatives. It is not an accuracy experiment.
Full runs require the loader counts to equal all 3,000 training and 1,330 validation images.
Checkpoints are selected by validation total loss, with history and immutable provenance saved.
Exported TFLite tensors are inspected, but successful export alone does not prove Android
compatibility, representative accuracy or warning eligibility. Do not replace the bundled model
until those independent checks pass. Every run uses a new directory.

## Runtime and accuracy evaluation

```powershell
& C:\VisionAssistGround\modelmaker-venv\Scripts\python.exe tools\ground\evaluate_task_detector.py --model C:\VisionAssistGround\modelmaker-smoke\model.tflite --data C:\VisionAssistGround\rdd-coco-v2 --output C:\VisionAssistGround\smoke-runtime --max-images 4
& C:\VisionAssistGround\modelmaker-venv\Scripts\python.exe tools\ground\evaluate_task_detector.py --model C:\VisionAssistGround\modelmaker-run\model.tflite --data C:\VisionAssistGround\rdd-coco-v2 --output C:\VisionAssistGround\modelmaker-validation
```

Use MediaPipe Tasks' actual metadata/anchor decoding; the existing custom-grid decoder is
incompatible with this export. Both evaluators share framework-independent one-to-one IoU
matching in `detection_metrics.py`, tested by `test_evaluation.py`. The separated metrics
module also avoids importing the older Python 3.12 training script into this Python 3.11
runtime. Reports retain model/annotation hashes, TP/FP/FN, thresholds and desktop latency.
Partial runs are explicitly marked and must not be reported as representative accuracy.

On 2026-10-24, the negative-training smoke run, TFLite export and real MediaPipe inference on
four validation photographs passed. This verifies software plumbing only. The full 20-epoch
training run was then started with evaluation scheduled only after successful export. It has
not yet supplied accuracy evidence or replaced the packaged Android detector.

The same metadata-based inference is available for the verified UK external archive:

```powershell
& C:\VisionAssistGround\modelmaker-venv\Scripts\python.exe tools\ground\evaluate_task_external.py --dataset C:\VisionAssistGround\external-uk\Potholes.zip --model C:\VisionAssistGround\modelmaker-run\model.tflite --conditions tools\ground\uk-reviewed-conditions.json --output C:\VisionAssistGround\modelmaker-external
```

This reuses the earlier model's annotation reader and exclusions, retains the archive hash
check, and reports reviewed condition strata separately. It uses no training and does not
select thresholds. Add `--max-images 4` only for a partial execution smoke check. The UK
benchmark has already been examined during development; it is not an untouched safety test.

For a long Windows run, `run_modelmaker.ps1 -WorkRoot C:\VisionAssistGround -RunName modelmaker-run-v2`
executes training, validation and external evaluation in order, with separate logs and a status
JSON containing the runner PID and terminal outcome. Launch it in a separate hidden PowerShell
process if the controlling tool session may be interrupted. Always verify the actual process
before treating a `running` status file as live. It refuses an existing run name and never
replaces an earlier report. An interrupted first run stopped at batch 56 without a completed
epoch or export; its log is retained. A new detached run started on 2026-10-24. No quality
conclusion is drawn from the interrupted run or the smoke model's unstable negative-only loss.

## Evaluate completed checkpoints without restarting training

The detached run later stopped during epoch four; three completed epochs and the best weights
remain available. Process inspection confirmed it was no longer running, despite its old
status file. Do not interpret a launcher as protection against computer restarts or shutdown.

```powershell
& C:\VisionAssistGround\modelmaker-venv\Scripts\python.exe tools\ground\export_modelmaker_checkpoint.py --run C:\VisionAssistGround\modelmaker-run-v2 --data C:\VisionAssistGround\rdd-coco-v2 --checkpoint-archive C:\VisionAssistGround\mobilenetv2_ssd_i320_ckpt.tar.gz --output C:\VisionAssistGround\checkpoint-snapshot
```

This copies a stable completed-epoch checkpoint and history, verifies they did not change
during the snapshot, recreates the pinned detector architecture and exports through the real
Model Maker converter. It does not train, modify the original run or ignore mismatched weights.
The output records weight/history/model hashes and the completed and selected epochs.
An epoch-one snapshot exported successfully; evaluate snapshots with the same image commands
above before deciding whether to continue training or integrate a different Android model.

The existing actual-video evaluator also accepts metadata-based models:

```powershell
& C:\VisionAssistGround\modelmaker-venv\Scripts\python.exe tools\ground\evaluate_video.py --runtime mediapipe --video C:\VisionAssistGround\Cars_Moving_into_pothole.webm --model C:\VisionAssistGround\checkpoint-snapshot\model.tflite --output C:\VisionAssistGround\checkpoint-video
```

The default `--runtime grid` retains the original model path in its Python 3.12 environment.
Video sampling and the temporal policy are shared. Unlabelled frames never count as negatives,
and MediaPipe graph-call latency is explicitly distinguished from bare LiteRT invocation.

## Continue a verified snapshot

```powershell
.\tools\ground\run_modelmaker.ps1 -WorkRoot C:\VisionAssistGround -RunName modelmaker-resumed -ResumeFrom C:\VisionAssistGround\checkpoint-snapshot
```

Continuation accepts a checksum-verified snapshot with matching data/pretrained provenance,
retains the original batch-eight, 20-epoch learning-rate schedule, restores model and optimizer
state, and starts at the selected completed epoch. Every optimizer variable is compared with
its saved HDF5 value; missing or mismatched state stops the run. Source history through that
epoch and the prior best checkpoint are preserved in the new output directory. Both best and
latest weights are saved after subsequent epochs. The full training report distinguishes
configured epochs, completed epochs and the selected best epoch. Shuffled data order after
restart is not guaranteed identical to an uninterrupted run.

The three-epoch snapshot resumed successfully: all 280 optimizer variables matched, step
1,126 was restored and epoch four produced finite losses. The earlier encoding-name error is
retained as a failed run, not counted as training. Saved-checkpoint evaluation and video
regression results are in `../../docs/MODELMAKER_CHECKPOINT_REVIEW.md`.

## Check exported runtime numerics

For a checksum-recorded snapshot, compare the restored Keras outputs, exported LiteRT
tensors and actual MediaPipe top scores on three real validation images:

```powershell
& C:\VisionAssistGround\modelmaker-venv\Scripts\python.exe tools\ground\verify_modelmaker_runtime.py --snapshot C:\VisionAssistGround\checkpoint-snapshot --data C:\VisionAssistGround\rdd-coco-v2 --checkpoint-archive C:\VisionAssistGround\mobilenetv2_ssd_i320_ckpt.tar.gz --output C:\VisionAssistGround\runtime-verification
```

Use a new output directory. The check preserves source weights/training and records model,
weight, source-image and prepared-pixel hashes. It compares all raw score and box elements
with explicit tolerances, then checks the Tasks top score. The epoch-six snapshot passed.
This is a limited export/preprocessing check, not a detection-accuracy or Android test.
