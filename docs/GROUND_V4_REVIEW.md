# Ground model v4 review — 19 October 2026

The completed run fine-tuned the v3 multi-scale MobileNetV2-0.5 backbone and head for
12 epochs on the same 3,000 training images. BatchNorm statistics stayed frozen; horizontal
flip and brightness augmentation were used. No validation or external images entered
optimization. Training took 2,713.88 seconds on this computer.

Artifact SHA-256: `038522a5f41a7d1e269f51765e7c4d1c745d5b89903f5487e57ae61f179d6adf`.
Size: 2,221,740 bytes. This artifact is **not bundled** in the Android application.

| Set, score 0.30 and IoU 0.5 | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| RDD validation, 1,330 images | 111 | 563 | 415 | 16.47% | 21.10% |
| UK external development benchmark, 708 images | 18 | 148 | 1,129 | 10.84% | 1.57% |

Validation F1 rose from v3 0.15883 to v4 0.18500, but the model still misses almost every
external pothole. At the proposed warning threshold 0.65, validation TP/FP/FN is 9/7/517;
external TP/FP/FN is 0/0/1,147. Raising the threshold until outputs disappear is not a fix.
The external benchmark has already informed development and is not a fresh independent test.

Decision: preserve the tested 0.6.0/v3 APK and its disabled ground-warning gate. Do not spend
another Android rebuild presenting v4 as a validated improvement. Reports are retained as
`ground-v4-training.json`, `ground-v4-validation.json` and `ground-v4-external-evaluation.json`.

## Next comparison

Compare an established detector pretrained for localization with the custom center/box head.
Google's [MediaPipe detector customization guide](https://developers.google.com/edge/mediapipe/solutions/customization/object_detector)
supports retraining MobileNet-based SSD models and exporting a model with task metadata.
The [model specifications](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/model_maker/python/vision/object_detector/model_spec.py)
identify Google-hosted pretrained checkpoints. This supplies a concrete alternative to a head
trained from image-classification features alone; it does not guarantee pothole accuracy.

Model Maker is now marked deprecated by Google. Its training dependencies require TensorFlow
below 2.16 and include text components unavailable as native Windows wheels. Any compatibility
work must remain isolated, documented and tested; it must not modify the working Android
application or the existing TensorFlow 2.20 training environment. A successful import is not
evidence of successful training or export.

`tools/ground/export_coco.py` exports only the frozen training/validation selection, preserving
original JPEG bytes, negatives and box geometry. It rejects split leakage, invalid boxes,
duplicate IDs and unsafe output reuse. The first export has 3,000 training images/2,111 boxes
and 1,330 validation images/526 boxes. No test images are exported. Three contract tests pass.

The connected-device inventory is empty. Physical camera/depth, battery and handset inference
checks remain pending; the prior emulator tests must not be presented as physical-device evidence.
