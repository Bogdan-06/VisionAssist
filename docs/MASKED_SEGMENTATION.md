# Smartphone-mask segmentation experiment

This experiment addresses a concrete failure of the previous models: they missed nearly
all annotated regions in the downward-facing smartphone clips. It changes both the
training domain and target representation. It does not change Android assets or enable
ground warnings. Only the pothole class is labelled by this dataset.

## Data preparation

The source is the CC BY 4.0 [Mendeley pothole video dataset, version 3](https://data.mendeley.com/datasets/5bwfg4v4cd/3)
by Muhammad Ihsan, Agus Harjoko and Muhammad Alfian Amrizal. The archive provenance,
license and mask limitations are recorded in `MASKED_VIDEO_EVALUATION.md`.

`prepare_masked_segmentation.py` verifies the pinned archive SHA-256, safe paths,
unique names, exact RGB/mask pairing and the published 372/124/123 train/validation/test
clip counts. It decodes paired streams completely and checks dimensions, frame rates,
actual frame counts and foreground presence. Samples are at least 400 ms apart. Every
clip stays in its original partition; no adjacent-frame random split is performed.

RGB is reduced from 1080 square to 320 square using area interpolation. Compressed
masks are first thresholded at grayscale 128 at source resolution and then reduced with
nearest-neighbour interpolation. The script stores uint8 RGB and binary masks in NPZ
files for training and validation only. Each file and sampled source frame has a hash.
Test videos are decoded for the duplication audit, but test arrays are not exported for
fitting. The archive and videos are not added to the Android application.

Cross-partition identical RGB files and sampled decoded RGB frames are reported and
cause a failed preparation. A grayscale nearest-neighbour montage supports manual
inspection of similar clips. It is not a reliable near-duplicate classifier. Absence of
exact matches does not establish independent locations or source recording sessions.
This test partition has already informed development of earlier detectors and must not
be presented as an untouched safety test.

## Model and selection

`train_masked_segmentation.py` uses a frozen MobileNetV2 alpha 0.5 encoder and a new
small decoder with bilinear upsampling, lateral feature connections and separable
convolutions. The approach is informed by TensorFlow's [segmentation tutorial](https://www.tensorflow.org/tutorials/images/segmentation),
but uses its own smaller decoder. No tutorial dependency or third-party executable
checkpoint is downloaded. The official Keras ImageNet HDF5 weights already reviewed
in `GROUND_MODEL.md` are loaded only after their SHA-256 matches
`279052de2cfa801003aa6cc25cc4d007d35dd0b76f06935268c79788b7642d05`.

The input is float32 RGB `[1,320,320,3]`, normalized by `/127.5 - 1`. The output is
`[1,80,80,1]`, a sigmoid pothole mask. Frozen intermediate features are cached as
float16 to limit disk/RAM use; the exported backbone runs in float32. The decoder is
trained using per-image binary cross-entropy plus soft Dice loss. This first baseline
does not augment cached features. The default run is capped at 12 epochs, with early
stopping after four epochs without validation-loss improvement. Only the minimum
validation-loss checkpoint is exported. Test pixels do not enter optimization or
checkpoint selection.

The export permits only built-in LiteRT operations. Validation runs the actual exported
LiteRT model, upsamples probabilities to 320 square, and reports pixel IoU, Dice,
precision and recall at fixed thresholds 0.3, 0.5 and 0.65. It also retains per-clip
results and mean clip IoU. The first three validation clips are checked against the
restored Keras model with absolute tolerance 0.0001 and relative tolerance 0.001.
Desktop invocation timing is not a phone or live-camera measurement.

## Reproduction

Use the TensorFlow/Keras environment in `tools/ground/requirements.txt`, with the
OpenCV dependency in `tools/ground/requirements-video.txt`. Both commands require new
output directories and preserve earlier evidence.

```powershell
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\prepare_masked_segmentation.py --archive C:\VisionAssistGround\masked-videos\pothole_video.zip --output C:\VisionAssistGround\masked-segmentation-v1
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\train_masked_segmentation.py --data C:\VisionAssistGround\masked-segmentation-v1 --backbone "$env:USERPROFILE\.keras\models\mobilenet_v2_weights_tf_dim_ordering_tf_kernels_0.5_224_no_top.h5" --output C:\VisionAssistGround\segmentation-run-v1 --epochs 12
```

## Acceptance remains separate

Neither high pixel overlap nor successful conversion would validate warnings. Further
checks must address external images and videos, representative negative scenes,
component localization, temporal behaviour, real phone latency and camera preprocessing.
The dataset's semi-manual mask boundaries, correlated short clips and road close-up
viewpoint limit conclusions. No curb, stair, surface-height or distance claim follows
from this model. Any production replacement requires its own evidence and runtime
adapter; the existing warning-quality gate remains false.

## Verified preparation, 25 October 2026

The complete preparation finished successfully: 372 training clips / 1,860 sampled
frames, 124 validation clips / 620 frames, and 123 test clips / 615 audit samples.
No identical RGB video files or sampled decoded RGB frames crossed partition boundaries.
All 3,095 sampled masks contained foreground; there are no entirely negative sampled
frames. At 320 square, foreground pixel totals are 30,082,834 / 11,164,809 / 11,325,127
for train/validation/test. `masked-segmentation-preparation.json` retains the audit.

Three actual training image/mask pairs (clips 0001, 0307 and 0612, sample frame 20) were
visually inspected for alignment, as were the eight closest cross-partition thumbnail
pairs from the grayscale review aid. These spot checks do not prove annotation accuracy
or geographic independence. The source paper describes sunny/cloudy acquisition and
cropped top-down views; it does not establish a location-disjoint split.

A real-data training-path check on two frames from training clip 0001 passed: finite
per-image losses, finite nonzero decoder gradients, an actual optimizer update, expected
`[2,80,80,1]` output, and zero trainable encoder variables. It is recorded in
`segmentation-training-smoke.json`. Both new scripts passed Python compilation, and
cross-split duplicate detection was checked on deliberately duplicated identifiers.

## Completed candidate and evaluation, 26 October 2026

The run completed all 12 epochs and selected epoch 12 by minimum validation loss
(0.6097403). Export and validation completed successfully. The float32 LiteRT model is
1,997,104 bytes, SHA-256
`c1c7a8354a894cb77fa7d0d8bf8aa87ddf7b1bf18f26ba6c95c6967e01759536`.
The actual model remains in `work/ground/segmentation-run-v1` in the Codex workspace.
It was **not added to Android** because independent-domain evaluation failed.

| Fixed pixel threshold 0.5 | Validation, 620 frames | Published test, 615 frames |
| --- | ---: | ---: |
| Pixel IoU | 58.03% | 62.44% |
| Pixel precision | 74.71% | 80.18% |
| Pixel recall | 72.22% | 73.84% |
| Pixel Dice | 73.44% | 76.88% |

The test run decoded all 5,904 RGB frames and their paired masks across 123 clips,
sampling five frames per clip. The 320-square semantic masks had 639 connected
regions. At pixel threshold 0.5, their proxy boxes produced 499 TP, 1,002 FP and
140 FN (33.24% precision, 78.09% recall at matching IoU 0.5). Every predicted component
was retained, including small fragments. Region statistics are not interchangeable
with pixel metrics, nor are they reviewed object or warning-event ground truth.

`evaluate_segmentation_rdd.py` then evaluated all 1,342 images in the existing RDD
test partition. At each fixed pixel threshold (0.3, 0.5, 0.65), it matched **zero of
550 annotated potholes**. At 0.5 it produced 3,021 false regions. All 1,063 images
without D40 or difficult-pothole boxes produced predictions (2,453 regions in that
subset). These are annotation-defined negatives, not independently verified
hazard-free scenes. RDD was previously used in detector development and is not a
new safety-validation set.

Visual review of actual outputs on India_001000, India_001005 and India_001006
confirmed large false masks covering road, sky and vegetation, rather than localized
potholes. This domain failure prevents replacing the packaged detector or enabling
warnings. The label/viewpoint mismatch is a plausible explanation, not a proven sole
cause. A justified next experiment needs representative negative scenes and broader
viewpoints; additional epochs on these positive-only clips would not address that
missing coverage.

The first 15 validation frames passed Keras/LiteRT probability agreement, maximum
absolute error 0.0000450313, within the declared tolerances. Independently,
`verify_segmentation_runtime.py` reran the shared external-evaluation adapter on all
124 validation clips / 620 frames: every TP/FP/FN pixel total at all three thresholds
matched the direct-interpreter validation exactly. This is evidence against a
preprocessing discrepancy between those paths, not evidence of good generalization.
Desktop LiteRT invocation median/p95 was 5.09/5.74 ms during validation, 3.53/4.97 ms
for video evaluation and 3.55/4.82 ms for RDD. No phone timing is claimed for this model.

Preserved evidence: `segmentation-v1-training.json`, `segmentation-v1-history.csv`,
`segmentation-v1-validation.json`, `segmentation-v1-videos.json`,
`segmentation-v1-rdd.json`, and `segmentation-v1-runtime-verification.json`.
The evaluator and adapter scripts passed Python compilation. No Android source,
packaged model, camera configuration or warning gate changed in this experiment.

```powershell
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\evaluate_segmentation_videos.py --data C:\VisionAssistGround\masked-videos-test --model C:\VisionAssistGround\segmentation-run-v1\segmentation.tflite --output C:\VisionAssistGround\segmentation-v1-videos
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\evaluate_segmentation_rdd.py --dataset C:\VisionAssistGround\RDD2022_India.zip --manifest C:\VisionAssistGround\training-v3\manifest.json --model C:\VisionAssistGround\segmentation-run-v1\segmentation.tflite --output C:\VisionAssistGround\segmentation-v1-rdd
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\verify_segmentation_runtime.py --data C:\VisionAssistGround\masked-segmentation-v1 --training C:\VisionAssistGround\segmentation-run-v1 --output C:\VisionAssistGround\segmentation-v1-runtime-verification.json
```

## Annotation-defined negative training follow-up

`prepare_segmentation_negatives.py` verifies the existing RDD archive and frozen
split-manifest hashes, then selects 1,993 previously selected training images and
1,086 validation images without D40 boxes or ignored potholes. It reopens each
source XML and refuses any image containing a D40 object before writing an empty
pothole mask. This does not convert positive bounding boxes into invented pixel
masks. Images with other road-damage classes are negative only for the pothole
class, not for terrain safety generally.

All 3,079 preparations completed successfully, with source-image/XML hashes and
compressed-array hashes retained. No test arrays are exported. Exact image-file
duplication is rejected within this preparation and against the existing RDD test
partition. `segmentation-negatives-preparation.json` records provenance and counts.
The absence of an annotation is a training assumption, not an independent human
review confirming the absence of a pothole.

The optional `--negative-data` argument adds these records to the existing phone
mask training pipeline. The combined run uses 3,853 training frames and 1,706
validation frames, preserving each source's original split. It selects the best
combined validation loss. The phone-mask pixel report remains separate from the
negative-image false-positive report so that suppressing all output cannot be
mistaken for better pothole recognition. It also records the negative-manifest
hash and saves the exact training source beside the run's artifacts.

The v2 run completed all 12 epochs on 26 October 2026 with the same decoder, seed
and optimizer as v1. It selected epoch 9 by minimum combined validation loss
(0.2234701); epoch 12 had loss 0.2266749. RDD supplies only negative masks here;
positive examples from the forward-facing road domain are still absent from
segmentation training.

```powershell
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\prepare_segmentation_negatives.py --archive C:\VisionAssistGround\RDD2022_India.zip --manifest C:\VisionAssistGround\training-v3\manifest.json --output C:\VisionAssistGround\segmentation-negatives-v1
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\train_masked_segmentation.py --data C:\VisionAssistGround\masked-segmentation-v1 --negative-data C:\VisionAssistGround\segmentation-negatives-v1 --backbone "$env:USERPROFILE\.keras\models\mobilenet_v2_weights_tf_dim_ordering_tf_kernels_0.5_224_no_top.h5" --output C:\VisionAssistGround\segmentation-run-v2 --epochs 12
```

Three geometry tests in `test_segmentation_runtime.py` passed: padding is removed
without producing scene components at threshold 0.5, tiny regions and coordinates
are preserved, RGB order is correct, and nonfinite probabilities are rejected.
These validate the evaluation adapter, not the model's reliability.

## UK transfer check for v1

The new `evaluate_segmentation_external.py` uses the same verified UK archive,
708 accepted images, five excluded invalid annotations and reviewed condition tags
as earlier detector evaluations. At pixel threshold 0.5, v1 produced 234 TP,
2,996 FP and 913 FN (7.24% precision, 20.40% recall). The wet subset had 8 TP,
104 FP and 26 FN across 17 images. Both shadow images (six potholes) and the single
night/low-light image (one pothole) had no matches. Those tiny subsets cannot
establish general performance in those conditions. The model remains unsuitable
for warnings. See `segmentation-v1-uk.json` for all thresholds and condition groups.
This run overlapped v2 feature caching, so its desktop timing includes uncontrolled
CPU contention and should not be used for a performance comparison.

```powershell
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\evaluate_segmentation_external.py --dataset C:\VisionAssistGround\external-uk\Potholes.zip --model C:\VisionAssistGround\segmentation-run-v1\segmentation.tflite --conditions tools\ground\uk-reviewed-conditions.json --output C:\VisionAssistGround\segmentation-v1-uk
```

## Completed negative-data comparison: v2 is not ready for warnings

The v2 export is 1,997,104 bytes, SHA-256
`a145296eca9ed48aa73ea3a2b29cbe354f20e36d8645d5f999f86ce2ff613f8d`.
All evaluation reports were checked against the actual model-file hash. Built-in
LiteRT conversion and Keras agreement on the first 15 validation frames passed.
The shared evaluation adapter also reproduced the direct-interpreter validation's
pixel TP/FP/FN totals exactly across all 620 frames and all three fixed thresholds.

| Metric at fixed pixel threshold 0.5 | v1, positive phone clips | v2, phone clips + RDD negatives |
| --- | ---: | ---: |
| Phone validation pixel IoU, 620 frames | 58.03% | 58.08% |
| Phone test pixel IoU, 615 frames | 62.44% | 61.00% |
| Phone test proxy regions TP / FP / FN | 499 / 1,002 / 140 | 476 / 1,419 / 163 |
| Phone test proxy region precision / recall | 33.24% / 78.09% | 25.12% / 74.49% |
| RDD test TP / FP / FN, 1,342 images | 0 / 3,021 / 550 | 0 / 8 / 550 |
| RDD negative images with any prediction, out of 1,063 | 1,063 | 4 |
| UK TP / FP / FN, 708 accepted images | 234 / 2,996 / 913 | 250 / 1,641 / 897 |
| UK proxy region precision / recall | 7.24% / 20.40% | 13.22% / 21.80% |

The additional negative validation report covers all 1,086 annotation-defined
validation images; four produced foreground at each of 0.3, 0.5 and 0.65. These
images influenced checkpoint selection. The separate RDD test subset above has
4/1,063 negative images with predictions at 0.5 (0.376%), but the model also missed
every annotated positive pothole in that test set. Suppression on this domain is
not successful hazard recognition. Within the phone videos, predicted foreground
pixel errors decreased while false connected regions increased, so pixel overlap
alone would conceal a worse region-level result.

The v2 UK wet subset has 5 TP, 45 FP and 29 FN across 17 images. The two shadow
images have 1 TP, 3 FP and 5 FN; the single night/low-light image has one match.
That one image is not evidence of reliable nighttime detection. All condition
counts and thresholds are retained in `segmentation-v2-uk.json`.

This experiment addresses one data omission but does not close the quality gap.
The result does not justify more epochs on the same negative-only road-domain
addition. Forward-facing positive masks or explicitly evaluated weak box
supervision, representative walking negatives, and independent event-level
evaluation remain needed. Neither v1 nor v2 was added to Android, and the
production ground-warning gate remains false.

Preserved v2 evidence: `segmentation-v2-training.json`, `segmentation-v2-history.csv`,
`segmentation-v2-validation.json`, `segmentation-v2-negative-validation.json`,
`segmentation-v2-rdd.json`, `segmentation-v2-videos.json`, `segmentation-v2-uk.json`
and `segmentation-v2-runtime-verification.json`. All three external evaluator
processes exited successfully. They ran concurrently, so desktop timing should
not be used to rank models or infer phone performance. No training/evaluation job
from this v2 run remains active.
