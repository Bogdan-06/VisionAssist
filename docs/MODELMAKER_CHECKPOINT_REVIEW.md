# Pretrained detector checkpoint review — 24–25 October 2026

The MobileNetV2 320 detector comparison has not produced a model suitable for ground warnings.
The resumed run completed all 20 epochs and final export, validation, external-image and
video evaluations on 25 October. Its selected model is from epoch eight, chosen by the
lowest validation total loss, not by test accuracy. It is not bundled. Earlier checkpoint
results below remain historical evidence; final results are summarized at the end.
The first long run was interrupted before an epoch completed. A second run completed three
epochs before stopping during epoch four. Its checkpoint and training history were preserved;
the source processes were confirmed absent before any continuation was attempted.

The epoch-one checkpoint was exported while training was live. The best checkpoint from the
three completed epochs was subsequently exported after the interruption. Both exports use
the actual pinned Model Maker architecture, restored weights and official exporter. Snapshot
reports retain model, weights, history and pretrained-checkpoint hashes. Neither export has
replaced the Android model. No test-set images were used for training or checkpoint selection.

## Full image evaluations

One-to-one matching uses IoU 0.5. Scores are not calibrated probabilities. Blank precision
means there were no predictions at that threshold; it does not mean perfect precision.

| Checkpoint / data | Score | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Epoch 1 / RDD validation, 1,330 images | 0.3 | 0 | 0 | 526 | undefined | 0% |
| Epoch 3 / RDD validation, 1,330 images | 0.1 | 108 | 704 | 418 | 13.30% | 20.53% |
| Epoch 3 / RDD validation, 1,330 images | 0.3 | 5 | 2 | 521 | 71.43% | 0.95% |
| Epoch 6 / RDD validation, 1,330 images | 0.1 | 149 | 494 | 377 | 23.17% | 28.33% |
| Epoch 6 / RDD validation, 1,330 images | 0.3 | 8 | 5 | 518 | 61.54% | 1.52% |
| Epoch 3 / UK external, 708 images | 0.1 | 41 | 225 | 1,106 | 15.41% | 3.57% |
| Epoch 3 / UK external, 708 images | 0.3 | 0 | 0 | 1,147 | undefined | 0% |

At score 0.65, the epoch-three validation model produced no predictions. At 0.3 it also missed
all 34 labelled potholes in the 17 reviewed wet images. Full thresholds, condition subsets,
the five excluded UK images and timing scope are retained in the accompanying JSON reports.
The external set has already been examined during development and is not an untouched safety
test. Mostly positive road photos do not establish walking-camera or negative-scene reliability.

## Actual video replay

Both checkpoints ran on the licensed 621-frame road clip, sampling 52 frames with the existing
400 ms interval and temporal policy. Neither produced a policy-eligible warning. No frames
have reviewed ground-truth boxes, so precision and recall remain unavailable. Absence of a
warning is not evidence of a safe scene. For epoch three, desktop MediaPipe detection-call
median/p95 latency was 43.05/50.04 ms; this includes graph preprocessing and postprocessing,
not bare LiteRT inference or sustained phone camera throughput.

## Decision and continuation

Keep the packaged v3 model, attribution and disabled ground-warning gate unchanged. The
three-epoch result does not justify lowering the warning threshold or announcing detections.
Training loss improved across the completed epochs, but image evaluation shows that loss
alone cannot establish useful detection quality.

The saved Keras checkpoint contains optimizer state. The continuation implementation verifies
every optimizer variable against the saved HDF5 data before fitting further epochs, retains
the original 20-epoch schedule, and writes both best and latest epoch checkpoints. Shuffled
data order after restart is not claimed to match an uninterrupted run bit for bit. The first
resume attempt failed before training because of an encoding-name typo; that failure was
retained and the typo corrected. The corrected continuation restored all 280 optimizer
variables exactly, including step 1,126, and began epoch four with actual finite training
losses. Evidence is retained in `modelmaker-resume.json`. The remaining epochs and final
evaluation were still incomplete at that observation; the final results are recorded below.

The original grid-model video path was rerun after adding MediaPipe support: all 52 sampled
frames had exactly the same detections and temporal decisions as the previous v3 replay.
Six Python metric/data contract tests also passed. These software checks do not alter the
poor detection-quality results above.

Evidence: `modelmaker-snapshot-v1/v2.json` and the corresponding `-validation.json`,
`-external.json` and `-video.json` files. Reproduction commands and environment restrictions
are in `../tools/ground/MODELMAKER_WINDOWS.md`.

On 2026-10-25, the epoch-three snapshot also completed all 123 paired-mask test videos
(615 samples). At score 0.1 it matched 34 mask-derived regions, produced 285 unmatched
boxes and missed 605 regions. At scores 0.3 and 0.65 it produced no predictions and missed
all 639 regions. No replay warning was eligible. The packaged v3 model likewise produced
no detections at 0.3 on this set. These are component-derived proxy labels in short road
close-ups, not walking-safety evidence. See `MASKED_VIDEO_EVALUATION.md` and the two full
JSON reports. The production model and warning gate remain unchanged.

## Six-epoch continuation check

The resumed run completed six epochs and entered epoch seven. Its best completed checkpoint
was selected by validation total loss (0.99612 at epoch six), copied without changing the
running training job, and exported successfully. The snapshot is
`modelmaker-epoch-snapshot-v3`, model SHA-256
`60f4fcd74d60916378eebc0cc9b59eb872695770db6595c789a3d00bbcd80746`.
The full validation evaluation contains 1,330 unique image predictions and matches that
artifact hash. Reports are `modelmaker-snapshot-v3.json` and
`modelmaker-snapshot-v3-validation.json`.

At score 0.1, precision/recall improved from 13.30%/20.53% at epoch three to 23.17%/28.33%
at epoch six. This is a development-set trend, not independent confirmation. At 0.3 the
model still missed 518 of 526 boxes, with 8 TP and 5 FP. At every evaluated threshold from
0.4 upwards, including 0.65, it produced no predictions. The lower validation loss therefore
does not establish useful warnings. No threshold or production model was changed, and no
new external/video claims are made for epoch six. The configured 20-epoch run was still
incomplete then; its process was verified live after this intermediate evaluation.

## Export and score-handling check

On 2026-10-25, `verify_modelmaker_runtime.py` restored the exact epoch-six weights and
compared Keras output tensors with the exported LiteRT model on three real positive
validation images. Each engine received identical prepared 320-square RGB pixels. All
38,250 class scores and 76,500 raw box values per image were compared. The largest absolute
score difference was 4.10e-7 and the largest raw box difference was 7.39e-5, within the
predeclared numerical tolerances. Actual MediaPipe Tasks top pothole scores also matched
the raw LiteRT maxima within tolerance.

The inspected runtime graph uses 320-square input with range [-1,1], two classes, 19,125
anchors, class 1 allowed, and no additional sigmoid. The pinned exporter already applies
sigmoid before exporting scores. All 3,000 training and 1,330 validation images are
720-square, so a square-versus-rectangular resize difference does not explain their weak
validation results. Graph NMS uses IoU 0.3; evaluation matching separately uses IoU 0.5.

This checks export numerics and score handling on the sampled inputs. It does not prove
all decoded boxes, arbitrary camera geometry, Android compatibility, or detection accuracy.
The measured poor precision/recall remains unresolved. Evidence is retained in
`modelmaker-epoch6-runtime-verification.json` and `modelmaker-epoch6-runtime-options.pbtxt`.

## Completed 20-epoch run

The runner finished successfully at 11:03 on 25 October 2026 (Bucharest time), including
both full image evaluations. Training history contains all epochs 0–19. The best validation
total loss was 0.99057 at epoch eight. At epoch twenty training total loss had fallen to
0.30738 while validation total loss rose to 1.14429, a pattern consistent with overfitting.
The selected export is 10,452,901 bytes, SHA-256
`26a1e05f8296fd7b037e49baa5654950a45d64244f674027743a540ac58e3d39`.

| Data / score | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| RDD validation / 0.1 | 153 | 566 | 373 | 21.28% | 29.09% |
| RDD validation / 0.3 | 11 | 7 | 515 | 61.11% | 2.09% |
| UK external / 0.1 | 68 | 187 | 1,079 | 26.67% | 5.93% |
| UK external / 0.3 | 10 | 7 | 1,137 | 58.82% | 0.87% |
| Paired-mask videos / 0.1 | 7 | 91 | 632 | 7.14% | 1.10% |
| Paired-mask videos / 0.3 | 0 | 0 | 639 | Undefined | 0% |

There were no predictions at 0.65 in any of these evaluations. The wet-image subset at
0.3 had 1 TP, 0 FP and 33 FN; its apparent 100% precision is based on one detection and
does not establish reliability. The tiny shadow and night subsets had no true positives.
All 1,330 validation and 708 accepted external images were evaluated. The mask-video run
completed 123 clips/615 samples; its boxes are semantic-mask component proxies as described
in `MASKED_VIDEO_EVALUATION.md`. The separate road video decoded all 621 frames/52 samples,
but has no reviewed box labels. Neither video run produced a policy-eligible warning.

Final desktop MediaPipe detect median/p95 was 38.67/41.88 ms on validation images and
38.51/43.58 ms on mask-video samples. These include graph preprocessing/postprocessing and
are not Android measurements. Earlier timings involved concurrent training contention.

Decision: reject this candidate for production warning use. Keep the packaged v3 artifact
and disabled warning gate. Do not restart the same training recipe merely to accumulate
epochs. A further experiment needs a justified data/representation change and independent
phone-view evidence. The smartphone mask dataset offers a concrete segmentation research
path, while curb data coverage is documented separately in `GOOSE_CURB_DATA.md`.

Evidence: `modelmaker-final-training.json`, `modelmaker-final-history.csv`,
`modelmaker-final-validation.json`, `modelmaker-final-external.json`,
`masked-video-task-final.json` and `modelmaker-final-video.json`. Every evaluation report's
model hash was checked against the exported bytes. The Android asset hash still matches v3.
