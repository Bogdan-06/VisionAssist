# Reproduce the ground baseline

Use a separate Python 3.12 environment. Keep datasets outside the Android project and
generated artifacts out of version control. This workflow does not need or read API keys.

For the prepared setup on this computer, use the root `Train-GroundModel.ps1` launcher.
See [the one-command guide](../../docs/TRAINING_COMMAND.md). It trains the pothole segmentation
candidate and evaluates it, saving separate runs in the ignored `training-runs` folder.

Additional research workflows are documented separately:

- [Smartphone-mask segmentation and annotation-defined negative training](../../docs/MASKED_SEGMENTATION.md):
  source verification, mask preparation, actual LiteRT export, image/video evaluation
  and runtime parity. These candidates are not the Android model.
- [GOOSE curb labels](../../docs/GOOSE_CURB_DATA.md): verified validation-data coverage
  and limitations; no curb detector is claimed.
- [Official stair-label research checkpoint](../../docs/STAIR_MODEL_RESEARCH.md): pinned
  safetensors acquisition, isolated offline execution sample and NVIDIA's
  research/evaluation restriction; not bundled.
- [Accessibility-barrier data](../../docs/ACCESSIBILITY_BARRIER_DATA.md): verified
  annotation/sample acquisition with explicit stair and curb labels; no model trained yet.

```powershell
python -m venv C:\VisionAssistGround\venv
& C:\VisionAssistGround\venv\Scripts\python.exe -m pip install -r tools\ground\requirements.txt
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\fetch_rdd.py --help
```

`fetch_rdd.py` streams a selected country archive from the public Figshare release using byte
ranges, verifies its CRC and byte count, and writes a SHA-256 provenance record. See its CLI
help for country/output arguments. Dataset attribution and license statements are in
`docs/GROUND_MODEL.md`. Inspect them before redistributing data or derived image fixtures.

```powershell
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\train_baseline.py --dataset C:\VisionAssistGround\RDD2022_India.zip --output C:\VisionAssistGround\v1 --epochs 35
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\evaluate.py --dataset C:\VisionAssistGround\RDD2022_India.zip --training C:\VisionAssistGround\v1 --output C:\VisionAssistGround\v1-test --conditions original synthetic_dark synthetic_shadow
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\test_evaluation.py
```

Training exports the split manifest, backbone/head weights, Keras model, float32 TFLite,
loss history and training metadata. The manifest identifies every optimization image.
Evaluation verifies the source archive hash and rejects a split containing optimization images.
It reports one-to-one IoU 0.5 precision/recall, TP/FP/FN, ignored difficult annotations, inference
and preprocessing/decode times, plus per-image predictions. Read all thresholds; never interpret
no predictions as perfect precision. Condition transforms are synthetic and explicitly named.

Optional fine-tuning uses the same training/validation groups, with GIoU localization, frozen
BatchNorm statistics, trainable convolution weights, flip/brightness augmentation:

```powershell
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\fine_tune.py --dataset C:\VisionAssistGround\RDD2022_India.zip --initial C:\VisionAssistGround\v1 --output C:\VisionAssistGround\v2 --epochs 12
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\evaluate.py --dataset C:\VisionAssistGround\RDD2022_India.zip --training C:\VisionAssistGround\v2 --output C:\VisionAssistGround\v2-validation --split validation
```

A third architecture experiment uses `train_baseline.py --architecture fpn --epochs 40` with
a fresh output directory. It combines pooled 40×40, 20×20 and upsampled 10×10 MobileNetV2-0.5
features and trains a separable-convolution head with GIoU. It preserves the tensor/decoder
contract, but is a distinct trained artifact requiring its own checksum and evaluation.
This v3 artifact is bundled in version 0.6.0. Validation F1 improved, but external recall
remained extremely low; warnings are still disabled. Full evidence is in the model card.

To reproduce the selected fixture and lossless interpreter/decoder parity input:

```powershell
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\evaluate.py --dataset C:\VisionAssistGround\RDD2022_India.zip --training C:\VisionAssistGround\v3 --output C:\VisionAssistGround\v3-validation --split validation
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\export_fixture.py --dataset C:\VisionAssistGround\RDD2022_India.zip --training C:\VisionAssistGround\v3 --evaluation C:\VisionAssistGround\v3-validation --output core\ground\src\androidTest\assets
```

The fixture is selected for correct localization from validation; it is deliberately not
accuracy evidence. Its metadata contains source attribution, original JPEG SHA-256, model
SHA-256, original annotations and Python predictions for the lossless prepared PNG.

The v1 test has already informed development. Subsequent comparisons on that same split are
development results, not independent validation. Preserve reports for unsuccessful models too.
Do not replace the packaged model merely because training loss fell. Evaluate localization,
false positives, device behavior, preprocessing parity and real difficult conditions first.

To adopt another compatible trained artifact, update `core/ground/src/main/assets/ground_baseline.tflite`,
its immutable SHA-256 in `GroundHazardDetector`, and the model card. Changing tensor semantics
requires updating and testing both Python and Kotlin decoders. The warning-quality gate must
not be enabled based solely on model export, compile success or synthetic tests.

Pending evaluation work: independent walking videos with per-frame boxes/track IDs, real wet,
shadow/night strata, temporal false alarms and misses, physical-device latency, concurrent
CameraX frame delivery, memory and battery measurements, and calibrated ARCore region depth.

## Export for a pretrained detector comparison

The custom v4 fine-tuning run still failed external evaluation; see `docs/GROUND_V4_REVIEW.md`.
To compare another detector without moving examples between splits:

```powershell
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\test_coco_export.py
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\export_coco.py --dataset C:\VisionAssistGround\RDD2022_India.zip --manifest C:\VisionAssistGround\v3\manifest.json --output C:\VisionAssistGround\rdd-coco-v1
```

Use a new output directory. Training includes the exact manifest selection (including negatives),
validation excludes ambiguous ignored annotations, and test images are never exported. The
exporter verifies the source archive hash, source groups, bounds and image CRCs. Generated data
and training environments belong outside this source tree and must not enter the Android APK.
