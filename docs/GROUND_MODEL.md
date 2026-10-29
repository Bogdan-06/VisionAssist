# Ground-hazard research baseline (VisionAssist 0.6.0)

This is real offline inference, but the current model is **not accurate enough for hazard
warnings**. Its outputs are experimental visual candidates. No navigation safety claim is made.

## Architecture and actual classes

The bundled v3 model uses MobileNetV2 alpha 0.5 with frozen ImageNet features from
`block_6_expand_relu`, `block_13_expand_relu` and `block_16_project`. Pooling/upsampling combines
these at 20 × 20; a separable-convolution center/box head learns focal and GIoU losses.
Input is float32 RGB, 320 × 320, letterboxed with
RGB 114, normalized by `/127.5 - 1`. Output is `[1,20,20,5]`: score, cell x/y offsets,
normalized width/height. A 3 × 3 local-maximum filter and IoU 0.4 NMS keep at most 20 boxes.
The display threshold is 0.30. These scores are not calibrated probabilities of danger.

Only **RDD2022 D40 pothole** was trained. Curbs, stairs, generic uneven surfaces and pothole
depth are not supported classes. A box does not establish whether the walking route intersects it.

The head trains on 3,000 India photographs (1,007 positive images), with 1,330 validation
images and 40 training epochs. The selected checkpoint is 2,225,580 bytes. Bundled SHA-256:
`bb8ebf2bce188df2206e3fa78891888764f095ab40cad5a508c3da307cc7af88`.
Android verifies this checksum and tensor shapes before inference. LiteRT Interpreter 1.4.2
runs on the CPU with two threads; no Play Services inference or network download is required.
Earlier v1 (frozen alpha 0.35) and v2 (fine-tuned alpha 0.35) artifacts remain documented in
their reports. At score 0.30, validation F1 was 0.08659, 0.13678 and 0.15883 respectively.
v3 was selected using validation localization results, before its external evaluation. It is
still a weak diagnostic baseline, not a validated warning model.

## Data and provenance

RDD2022, Arya et al., *A multi-national image dataset for automatic Road Damage Detection*:
[published release](https://doi.org/10.6084/m9.figshare.21431547.v1),
[author repository](https://github.com/sekilab/RoadDamageDetector).
The downloaded India nested ZIP is 526,709,145 bytes, CRC32 `f186f6f8`, SHA-256
`28eab0aa85638855e1907e63b175be2305a0accd018c54603037d3fb8cab963a`.
The public Figshare metadata labels this release CC BY 4.0. The author repository states
CC BY-SA 4.0 for images. Both statements are retained; redistributed image fixtures retain
attribution and share-alike notices. No unlabelled official test images enter measured evaluation.
This is road inspection imagery, not a walking-camera dataset; geography, camera viewpoint,
weather, small objects and sidewalk surfaces can differ substantially from intended use.

The backbone is the official Keras HDF5 artifact from Google's tensorflow/keras-applications
storage, `mobilenet_v2_weights_tf_dim_ordering_tf_kernels_0.5_224_no_top.h5`, SHA-256
`279052de2cfa801003aa6cc25cc4d007d35dd0b76f06935268c79788b7642d05`.
The earlier alpha 0.35 backbone hash was
`df1c3db1d0d9193719c4c70f707c56f7021f999f825bdc57454c275cf6def19f`.
[Keras source license](https://github.com/keras-team/keras/blob/master/LICENSE) is Apache 2.0;
the backbone's ImageNet origin is recorded separately from RDD training provenance. No third-party
pickle or opaque community checkpoint is loaded. The head is trained by this project.

## Why this approach

[Keras MobileNetV2](https://keras.io/api/applications/mobilenet/) provides an official lightweight
backbone with transferable visual features. A center/size representation is inspired by
[Objects as Points](https://arxiv.org/abs/1904.07850); this custom baseline is not the paper's
implementation and inherits none of its reported accuracy. The small output is easy to decode
and the current artifact is inexpensive to run; evaluation shows that size alone is insufficient.

Object detection fits RDD's box annotations and supports inexpensive localization. Segmentation
would better represent thin curbs, steps and irregular surface boundaries, but needs suitable
pixel-level annotations and more detailed evaluation. A sidewalk mask does not prove walkability.

Other primary research candidates inspected (not downloaded or bundled):

| Candidate | Relevance | Constraint for this baseline |
| --- | --- | --- |
| [StairNet-DepthIn](https://github.com/MrChenWang/StairNet-DepthIn) | RGB-D stair-line localization with 0.5/0.75/1.0 width variants and documented training data. | Project states CC BY-NC 3.0; hardware depth-camera training does not establish ARCore compatibility. Needs mobile conversion and stair-specific evaluation. |
| [Segments sidewalk-semantic](https://huggingface.co/datasets/segments/sidewalk-semantic) | Semantic labels include curb, stairs, sidewalk and terrain. | CC BY-NC 4.0, gated access requiring contact-sharing agreement. No access agreement was submitted. A class mask still does not measure a height discontinuity. |
| [Project Sidewalk ASSETS 2019](https://github.com/ProjectSidewalk/sidewalk-cv-assets19) | Crop classification of ramps, missing ramps, surface problems and obstructions. | Google Street View crop classification is not phone-frame localization. Repository code availability does not itself establish rights to redistribute imagery or mobile weights. |

[ADE20K](https://ade20k.csail.mit.edu/index.html) is a relevant scene-parsing research source,
but its [image terms](https://ade20k.csail.mit.edu/terms/) restrict use to non-commercial research
and education and distinguish images from annotations/software. It has not been downloaded or
used here. Future curb/stair work needs explicit instance/boundary labels and walking-camera data.

On 26 October, an official ADE20K-trained SegFormer B0 checkpoint was separately acquired
for local noncommercial research/evaluation after reviewing its NVIDIA license. The
checkpoint explicitly includes stairs (53), stairway (59) and step (121), but no curb.
Its pinned safetensors hash and metadata were verified; it has not been executed or
added to Android. This does not change the raw ADE20K dataset status above or establish
permission for ordinary app use. See `STAIR_MODEL_RESEARCH.md` for provenance and terms.

A later [GOOSE](https://goose-dataset.de/docs/setup/) data assessment identified explicit
curb masks under CC BY-SA 4.0. The downloaded validation archive contains 190 curb-positive
frames among 962 pairs, with strong concentration in a few robotic-platform sequences.
It has no stair label. No GOOSE weights were downloaded or integrated. See
`GOOSE_CURB_DATA.md` for the verified data contents and segmentation research path.

The original RoadDamageDetector MobileNet SSD weight URL returned 403. Community pothole
models reviewed did not supply enough training provenance or suitable documented licensing.
Instead of shipping an unverifiable checkpoint, this project includes acquisition, training,
evaluation and Android inference for its own baseline.

## Split and evaluation limits

Duplicate image CRC/size pairs are excluded. Adjacent numeric source IDs are grouped by
`country:id // 100`, then deterministically split by SHA-256 with seed 4217. Groups do not cross
train/validation/test; they are **not proven location-disjoint**. Train selection includes all
1,007 available positive images in those training groups plus 1,993 sampled negative images.
Validation selects checkpoints. No test images enter optimization. The v1 test report has now
been examined during development, so later results on that same split are not a fresh independent
trial. A new external evaluation is required before any reliability claim.

See `ground-v3-evaluation.json`: 1,342 test-split photographs, 550 labelled potholes, IoU ≥ 0.5
matching. At score 0.30: TP 72, FP 370, FN 478, precision 16.29%, recall 13.09%. At score 0.65:
TP 4, FP 1, FN 546. Synthetic darkness reduces recall to 1.82%; synthetic shadow to 3.27%.
These are development results because the earlier model's test results informed development.
The external UK benchmark is worse: TP 5, FP 44, FN 1,142 at 0.30 (10.20% precision, 0.44%
recall). All 34 labelled potholes in the 17 reviewed wet images were missed at this threshold.
See `GROUND_EXTERNAL_EVALUATION.md` for genuine wet, shadow and night samples, small-subset
limitations, and the real video evaluation. No threshold provides dependable coverage.

The warning eligibility gate remains false. Raising the threshold until nothing is detected
is not evidence of safety. Desktop original-image median inference was 4.20 ms, p95 5.82 ms;
these numbers are not physical-phone latency. Timing during other host workloads differs.
Python uses Pillow bilinear resizing; Android uses Canvas bilinear resizing. A lossless
already-preprocessed fixture checks interpreter/decoder parity independently, and the original
JPEG exercises Android preprocessing. This does not establish pixel-exact parity for arbitrary
camera frames; dataset scores must not be presented as measured phone-camera accuracy.

## Runtime and warning architecture

`core:ground` is independent of CameraX, MediaPipe and voice providers. CameraX copies the upright
image before MediaPipe takes ownership. One separate worker accepts at most one frame every
400 ms, drops offers while busy, and has no image backlog. Ground failures do not stop COCO
inference, camera preview or explicit snapshots. Results are mapped using CameraX transforms,
clipped to the visible viewport, and expired after one second.

Warning policy requires score ≥ 0.65, three overlapping observations spanning ≥ 800 ms,
no inter-frame gap > 800 ms, a recent frame, and a 12-second cooldown. It rejects stale,
duplicate, low-score and spatially inconsistent evidence. This filter does not repair a bad
model; production ground warnings remain disabled by `GroundModelReadiness` until quality is
validated. The integrated warning path uses uncertain Romanian speech and vibration, calls the
existing local-warning interruption contract before output, and prevents test speech from
interrupting a ground warning. Existing COCO announcements remain available.

## Depth investigation

[ARCore Depth](https://developers.google.com/ar/develop/java/depth/developer-guide) is checked
at runtime; unsupported devices keep the ordinary camera. Depth values are axial measurements,
not walking distances. [Raw Depth](https://developers.google.com/ar/develop/java/depth/raw-depth)
has invalid pixels and per-pixel confidence, and may reproject older observations.
[SharedCamera](https://developers.google.com/ar/reference/java/com/google/ar/core/SharedCamera)
is a Camera2 ownership integration and cannot use a hardware depth sensor. The prototype instead
uses an optional isolated ARCore mode, pausing CameraX and conversational audio while it owns the camera.

CPU image, depth, confidence and coordinate transforms are copied from one ARCore frame.
Depth older than 200 ms, invalid/out-of-range pixels, confidence below 153/255, insufficient
distinct samples and mixed surface regions are rejected. A candidate region's central samples
can yield a median axial depth; this does not identify the pothole bottom or height of a curb.
Adjacent z-discontinuities are exposed only as research diagnostics. Perspective, occlusion and
slopes can cause them; they do not create a hazard class or spoken warning. Physical capture,
registration, device behavior and depth accuracy remain unverified.
