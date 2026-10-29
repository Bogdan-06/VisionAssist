# Stair, curb and step detector experiment

**Checkpoint update, 29 October 2026:** resumed run `20261028-215718-4bd1910e` completed
all 20 epochs and exported the selected epoch 20 model. Full Windows MediaPipe 0.10.32
validation (825 images) and test (802 images) reports exist. At score 0.65 / IoU 0.5,
test results are TP93/FP8/FN616 (precision 92.08%, recall 13.12%); curb recall is 1/178.
This is not warning approval. Production integration remains pending. The original
controller's running/evaluate-test status is stale; no trainer is live. Historical progress
notes below are retained as history. Use [RESUME_GROUND_HAZARDS.md](../RESUME_GROUND_HAZARDS.md)
as the authoritative restart guide. Future launchers isolate SDK 0.10.32 evaluation from
the legacy trainer. Do not automatically repeat the already completed resume command below.

This pipeline adds explicit supervision for classes absent from the pothole datasets.
It is a separate experiment; it does not replace the Android model or enable warnings.
Full-source preparation, export, GPU training and LiteRT runtime checks are complete.
The small check model is unusable for detection. A full 20-epoch experiment has started;
accuracy results and Android suitability remain unverified.
The export format has now passed a physical-phone instrumentation compatibility check
with INTERNET/CAMERA/RECORD_AUDIO denied. This is test-only and does not approve the smoke
model or establish numeric parity: see [BARRIER_ANDROID_COMPATIBILITY.md](BARRIER_ANDROID_COMPATIBILITY.md).

## One command for future runs

After the current run finishes, use this from PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Moth\Desktop\VisionAssist\Train-BarrierModel.ps1"
```

It uses the GTX 1650 Ti through WSL2, eight CPU threads, batch size eight and 20 epochs.
Each invocation starts fresh from the original reviewed checkpoint, then evaluates the
selected model on all validation and test images. It saves an independent timestamped folder
under `VisionAssist\barrier-training-runs`, including source snapshots, logs, status, model
and metrics. It never installs the model on Android or enables warnings. Run one GPU
training job at a time on this 4 GiB card.

`-CheckOnly` checks paths, manifest consistency, free space and runtime/GPU imports without
creating a run. Full image/archive hashes are checked in the actual stages. `-Device Cpu`
uses the existing Windows Model Maker environment. `-Smoke` runs a one-epoch software check
and only a partial validation evaluation; it does not evaluate test images. `-Epochs`,
`-Threads`, `-BatchSize`, `-DataRoot` and `-OutputRoot` are explicit options. The original
`Train-GroundModel.ps1` still trains the separate pothole-mask model.

Both GPU and CPU `-CheckOnly` paths passed under Windows PowerShell 5. Missing-runtime and
missing-dataset checks returned exit 1 without creating output. The first full run is
`barrier-training-runs/20261027-190343-192c18c7`. Its process must be checked before restarting;
a saved `status.json` alone does not prove that it is still alive.
The first epoch completed with training total loss 2.7101 and validation total loss 1.1682;
epoch two was observed running. These losses do not establish detection precision or recall.
On 28 October the original handle was missing and no matching trainer/controller process
remained. Three epochs had completed; the interruption cause is unknown. The original status
was corrected to interrupted. The latest checkpoint has optimizer step 1,464, while the best
validation checkpoint is epoch one, step 488. Both are preserved.

To resume that stopped run from the Desktop project:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Moth\Desktop\VisionAssist\Train-BarrierModel.ps1" -ResumeFrom "C:\Users\Moth\Desktop\VisionAssist\barrier-training-runs\20261027-190343-192c18c7"
```

Resume keeps the original 20-epoch schedule and batch eight, continues from the latest
completed epoch, and separately preserves the earlier best validation model. It requires
matching data, package versions and device, finite checkpoint tensors/losses, consecutive
history and exact optimizer-step consistency. A source trainer still running is rejected;
checkpoint/history hashes are checked before and after snapshot copying. The trainer then
verifies every restored optimizer variable against HDF5 before taking another step.
Shuffle order and GPU results are not bitwise equivalent to an uninterrupted run.

Four checkpoint-consistency tests and the real stopped-run preflight passed. The continuation
was launched in `barrier-training-runs/20261028-215718-4bd1910e`. Actual model/optimizer
restoration was verified against HDF5 at step 1,464, and epoch four began with finite losses.
Evidence: [barrier-resume-verification.json](barrier-resume-verification.json). The remaining
epochs and final evaluations are still pending. Do not launch another copy of the command
while that continuation is active.

The source is the [HIIG accessibility-barrier dataset](https://doi.org/10.5281/zenodo.6382090)
under CC BY 4.0. Credit Jakob Stolberg, HIIG (2022), and collectors Christopher Richters
and Sami Nenno. Keep the [CC BY 4.0 notice](https://creativecommons.org/licenses/by/4.0/)
with any redistributed data or derivatives. Original boxes are retained as boxes;
they are never used as invented segmentation masks or measured distances.

The three ordered classes are `stairs` (source `stair`), `curb` (source `step` with
`type=curb`), and `step` (source `step` with `type=doorstep` or `other`). Ramp and grab-bar
annotations remain in the audit manifest but are not targets of this detector. No generic
uneven-surface or pothole class is supplied by this source. A no-target image means only
that these three labels are absent from its source annotation, not that it is hazard-free.

## Acquisition and preparation

Run these PowerShell commands in order. The Python environment already exists on this PC.
Output directories must be new, except that the downloader resumes its verified partial file.

```powershell
$python = 'C:\Users\Moth\Documents\Codex\2026-10-09\new-chat\work\ground\venv\Scripts\python.exe'
$tools = 'C:\Users\Moth\Desktop\VisionAssist\tools\ground'
$data = 'C:\Users\Moth\Documents\Codex\2026-10-09\new-chat\work\ground'
& $python -u "$tools\fetch_barrier_archive.py" --output "$data\accessibility-barriers\wm_barriers_data.zip"
& $python -u "$tools\prepare_barrier_dataset.py" --archive "$data\accessibility-barriers\wm_barriers_data.zip" --output "$data\barrier-prepared-v1" --previous-sample-manifest "$data\barrier-sample-v1\manifest.json"
& $python -u "$tools\export_barrier_coco.py" --archive "$data\accessibility-barriers\wm_barriers_data.zip" --prepared "$data\barrier-prepared-v1" --output "$data\barrier-coco-v1"
```

The 7,972,407,510-byte download uses at most four concurrent 64 MiB ranges. Each completed
range gets a SHA-256 checkpoint. Resume rehashes those bytes; incomplete responses retry at
most five times. Wrong ranges and permanent HTTP failures stop. The final ZIP is accepted
only after the publisher MD5, all member CRCs and expected inventory pass. A preallocated
partial file's size is not download progress. Never run two downloaders against the same file.

Preparation rehashes the archive and pinned annotation XML, decodes every image, checks box
bounds and image dimensions, and records exact byte/RGB hashes. Nontrivial EXIF orientations
are excluded for coordinate review. Identical images with conflicting target annotations are
excluded; other exact duplicates retain one canonical image. DCT perceptual hashes with
Hamming distance <=4 and aspect-ratio difference <=1% form transitive groups. Groups receive
a deterministic 70/15/15 hash split. Earlier reviewed samples and contact-sheet examples
are forced into training, including their duplicate groups.

These checks do not establish geographic or recording-session independence or find all near
duplicates. The resulting test set is a provisional internal holdout, not a navigation trial.
Source boxes describe visible barriers using wheelchair-oriented conventions; descending
stairs outside view can be omitted. Subjective height attributes are not metric ground truth.

The COCO export copies only training and validation JPEGs, preserves original bytes, converts
xyxy boxes to xywh, and records per-image and annotation hashes. Test/excluded images stay out
of the export. The trainer verifies the barrier export's hashes and class map before fitting.

## Detector and GPU environment

The candidate is Google's previously reviewed COCO-pretrained MobileNetV2 320 detector with
FPN/anchors, retrained for these three labels. Its existing pretrained archive must match
SHA-256 `73dd229998007e47259b93b00f65aca410ec053a15e67d78519ce5c1779f521f`.
It has a real MediaPipe/LiteRT export path already exercised by the pothole experiment.
This is an implementation choice, not evidence that it will achieve useful barrier accuracy.

[Google's customization guide](https://developers.google.com/edge/mediapipe/solutions/customization/object_detector)
now marks Model Maker deprecated. This research keeps its pinned 0.2.1.4 / Model Garden 2.15.0
versions isolated. The narrow vision-only compatibility patch and negative-image loader fix
remain hash-checked; no model, TensorFlow operation or loss is mocked. See
[MODELMAKER_WINDOWS.md](../tools/ground/MODELMAKER_WINDOWS.md) for their provenance.

The WSL setup script creates `/opt/visionassist/modelmaker-venv` using Python 3.11.17 and
TensorFlow 2.15.1 plus its CUDA dependencies. It does not alter `/opt/visionassist/venv`, the
TensorFlow 2.20 environment used by `Train-GroundModel.ps1`, or install a Linux display driver.
[TensorFlow's installation guide](https://www.tensorflow.org/install/pip) documents GPU
support through WSL2 and the CUDA pip extra. A real GPU convolution must pass before setup
reports success; successful installation alone is insufficient.

```powershell
wsl.exe -d Ubuntu-24.04 -u root --exec /bin/bash /mnt/c/Users/Moth/Desktop/VisionAssist/tools/ground/setup_modelmaker_wsl.sh
```

The training script accepts `--class-profile barriers --device gpu --threads 8` in that
environment. Existing pothole runs keep their default class profile. A barrier `--smoke` run
uses 16 training and 16 validation images: eight positives covering all three classes and
eight negatives in each split. Its single epoch tests optimization, class handling and export;
it is not an accuracy experiment. Full runs use the entire exported training split and select
the checkpoint by validation total loss. Test performance must not select a checkpoint.
The separate GPU environment passed a real convolution on the GTX 1650 Ti (compute capability
7.5, output device GPU:0, checksum 194400) and imported the actual detector stack on 27 October.
TensorFlow 2.15.1 uses CUDA 12.2 / cuDNN 8.9; exact installed packages are retained in
[barrier-gpu-environment.txt](barrier-gpu-environment.txt). The existing TF 2.20 GPU trainer
remains separate. A device listing or convolution is not proof that detector training fits
GPU memory; the subsequent batch-four training check completed successfully. The current
full run also completed more than 100 batch-eight optimizer steps with finite losses.
A device-wide NVIDIA snapshot during training showed 2,125/4,096 MiB allocated, 43% GPU
utilization and 65 degrees C. These are instantaneous device-wide readings, not sustained
averages or memory attributed solely to this process. See
[barrier-full-run-gpu-observation.txt](barrier-full-run-gpu-observation.txt).

The pinned library scales base learning rate 0.3 by batch size / 256, then applies 10% step
warmup and cosine decay. At batch 8 the scaled initial rate is 0.009375. New runs record the
effective schedule, installed framework versions and source-file snapshots with hashes.
The first GPU attempt stopped before optimization because TF 2.15 has no deterministic CUDA
`ResizeNearestNeighborGrad` implementation for this FPN. GPU runs now retain seed 4217 and
fixed data/configuration but allow nondeterministic GPU operations. Repeated GPU runs may
produce different weights; no bitwise reproducibility is claimed. CPU training retains
deterministic operations. The failed attempt remains in `work/ground/barrier-smoke-v1`.

## Completed full-data audit

The full archive passed its published MD5 and all 5,540 ZIP member CRCs. SHA-256:
`f4da6d044d55f1e21c7ca31dd2ff12a48bd5dbeabfa9d11d48fad932f7d6658b`.
All 5,538 JPEGs decoded with matching annotation dimensions. No exact duplicates, conflicting
identical-image labels or nontrivial EXIF orientations were found. One pHash-distance-zero
near-duplicate pair shows the same entrance (`000011653.jpg` and `000011656.jpg`); both are
kept in the same training group. This does not rule out other similar images or shared sites.

| Split | Images | Stair boxes | Curb boxes | Other step boxes | No target labels |
| --- | ---: | ---: | ---: | ---: | ---: |
| Training | 3,911 | 1,090 | 822 | 1,665 | 1,565 |
| Validation | 825 | 213 | 185 | 372 | 351 |
| Test | 802 | 189 | 178 | 342 | 321 |

The prepared manifest SHA-256 is
`d359f75d00beb6ca186ccb30b6b1163b2b2110ec78752840dcf0437d6ee04eee`.
An additional export audit verified every source/COCO box and category, split membership,
image dimensions, label/hash inventory and absence of extra/test files in training folders.
All 4,347 training/validation boxes are preserved. The trainer separately rehashes every
exported JPEG before fitting. See [barrier-data-audit.json](barrier-data-audit.json),
[barrier-preparation-summary.json](barrier-preparation-summary.json),
[barrier-export-provenance.json](barrier-export-provenance.json) and
[barrier-source-provenance.json](barrier-source-provenance.json).

The eight overview examples show labelled entry stairs, roadside curbs and raised doorsteps;
the distant small stair box remains hard to judge at overview scale. This was a limited
annotation review, not a full semantic relabelling audit. All displayed examples were placed
in training before fitting. [Label overview](barrier-label-review.png) and
[near-duplicate pair](barrier-near-duplicate-review.png) are resized/annotated derivatives
of the credited CC BY 4.0 source above.

## Checks performed so far

Eight offline regression tests passed on 27 October 2026. Their synthetic fixtures test
transfer recovery, permanent/range error rejection, label/subtype preservation, invalid box
rejection, exact conflicts, near-duplicate grouping, EXIF exclusion, reviewed-group placement,
COCO conversion, original-byte preservation, hash tampering, absence of test images from
training exports, and class-aware matching (including wrong-class and duplicate predictions).
Synthetic images are temporary software-test data, never training evidence.

Two additional Model Maker tests passed for finite-loss handling. This custom trainer logs
`total_loss`, so Keras `TerminateOnNaN`'s standard `loss` lookup was insufficient. The new
callback rejects nonfinite training and validation losses before a checkpoint is accepted.

The changed detector trainer also completed its existing pothole smoke profile on Windows:
eight negative training images, 16 validation images, one epoch, a real LiteRT export and
MediaPipe inference on four validation images. Every history value and every predicted
class/score/box matched the earlier smoke run exactly. The new export's actual hash matches
both training and inference reports. Evidence: [barrier-pothole-regression.json](barrier-pothole-regression.json).
This stress-check model is unusable: it produces 226 false boxes on those four negative images.
Passing the regression means preserved software behavior, not useful detection quality.

The packaged Android model was rehashed unchanged on 27 October:
`bb8ebf2bce188df2206e3fa78891888764f095ab40cad5a508c3da307cc7af88`.
`GroundModelReadiness.WARNINGS_VALIDATED` remains false. No Android code changed in this
data-pipeline work, so the earlier Android builds/device checks were not rerun or broadened.

```powershell
cd C:\Users\Moth\Desktop\VisionAssist
& 'C:\Users\Moth\Documents\Codex\2026-10-09\new-chat\work\ground\venv\Scripts\python.exe' -m unittest discover -s tools/ground -p test_barrier_data.py -v
```

`evaluate_barrier_detector.py` evaluates the frozen validation or test split using real
MediaPipe metadata/anchor decoding. It verifies the model, training, dataset and image hashes,
reports each class and micro totals at scores 0.1/0.3/0.5/0.65 with one-to-one IoU 0.5 matching,
and records negative-image false detections and desktop timing. Partial runs and smoke models
are explicitly identified. Its runtime has now been checked on an actual three-class export.

The second GPU smoke run completed four optimization steps on 16 real training images,
validated on 16 images, and exported a 10,462,141-byte model. Its hash is
`0097090945bbf0b73301c33803c00c5d200f564d1e9d75bd42682a274e22e7ed`.
Actual embedded labels are `background`, `stairs`, `curb`, `step`; source/image/model hashes
matched. It then ran on 64 validation images containing 24 stair, 18 curb and 24 step boxes,
plus 23 annotation-defined negatives. This verifies the three-class runtime/evaluation path.

The smoke model had divergent but finite losses and **zero matched objects, 5,809 false
boxes and 66 misses** at each tested score threshold (0.1/0.3/0.5/0.65). Every negative image
had false detections. It is rejected for use. Its four-step schedule had zero warmup steps;
it is not the full training schedule. CPU task-inference p50/p95 was 62.8/69.2 ms on this
desktop, not the phone. Reports: [barrier-smoke-training.json](barrier-smoke-training.json)
and [barrier-smoke-evaluation.json](barrier-smoke-evaluation.json).

Required next evidence: completed full training, class-aware validation/holdout metrics and false-alarm review,
then Android runtime parity/performance if a candidate merits integration. Nothing here
establishes spoken-warning eligibility or safe independent navigation.
