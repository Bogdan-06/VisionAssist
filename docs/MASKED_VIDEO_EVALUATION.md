# Labelled pothole video evaluation

This adds a repeatable evaluation of actual model predictions against published video
masks. It does not train a model, change the packaged weights, or enable ground warnings.

## Source and extraction

Muhammad Ihsan, Agus Harjoko and Muhammad Alfian Amrizal published the
[pothole video dataset, version 3](https://data.mendeley.com/datasets/5bwfg4v4cd/3)
under CC BY 4.0 (DOI `10.17632/5bwfg4v4cd.3`). Their
[dataset paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10867608/)
describes downward-facing smartphone clips with semi-manual semantic masks, including
tracking-related boundary uncertainty. These are road close-ups, not walking-route trials.

The individual archive is 1,025,786,813 bytes, SHA-256
`34a98a297f2e29c646cbdada37d820d2c8648e2ed5d15a28f72744d365fe9522`.
`fetch_masked_videos.ps1` checks the public file metadata and downloaded bytes against
that pinned value. This is the individual file hash, not Mendeley's generated download-all
bundle hash. `prepare_masked_videos.py` verifies it again and extracts only the 123 paired
RGB/mask test clips. It checks archive paths, pairing, sizes and CRCs and records a hash for
each extracted file. This evaluation workflow does not extract train and validation clips.
A separate, later smartphone-mask training experiment is documented in
`MASKED_SEGMENTATION.md`; it preserves the published clip partitions. Dataset videos
are not packaged in the Android app.

## Measurement method

`evaluate_masked_videos.py` verifies extracted-file hashes before decoding. Paired streams
must have equal frame rates, dimensions and frame counts, including the actually decoded
count. Frame-index timestamps use the nominal rate; the inspected source pair reports
23.976 fps, so the evaluator does not hardcode 24 fps. Both streams are decoded in lockstep.
Samples are at least 400 ms apart, matching the earlier replay evaluator.

Masks are converted to grayscale and thresholded at 128 to handle compressed boundaries.
Every eight-connected foreground component produces its tight bounding box; no small
component is removed. A first RGB/mask pair was visually inspected for alignment. This
spot check does not establish the correctness of every annotation. Entirely empty mask
clips halt evaluation for investigation rather than silently becoming negative clips.

The evaluator reports confidence thresholds 0.1, 0.3 and 0.65 with greedy, one-to-one box
matching at IoU 0.5, including TP, FP, FN, precision and recall. Mask-component boxes are
**proxy instance labels**: touching potholes merge, and disconnected fragments may split.
The separate box-union/mask overlap measures coverage and localization, not segmentation
accuracy of a detector that only outputs boxes. Overlapping predicted boxes do not count
the same pixel twice. Per-frame predictions and derived labels remain in JSONL for review.

Temporal replay uses the existing confidence/position/consistency policy and resets for
each clip. Eligibility is recorded without matching warning events to ground truth. These
roughly two-second clips cannot test the 12-second cooldown or estimate false alarms per
walking hour. Clips and adjacent frames may be correlated; counts are not independent
samples. Use of this published test partition during development means it is no longer an
untouched safety-evaluation set. Capture setup descriptions are never used as distance labels.

Timing is desktop-only and may include concurrent training contention. MediaPipe `detect`
includes graph preprocessing/postprocessing; grid timing covers only LiteRT invocation.
Sample processing additionally includes mask extraction and metric calculation, and excludes
video decoding. Neither number is an Android live-camera frame rate.

## Reproduction

From the project root, choose a new scratch directory; scripts refuse existing output
directories to preserve previous evidence. These paths illustrate the environment described
in `tools/ground/MODELMAKER_WINDOWS.md` and the grid training instructions.

```powershell
.\tools\ground\fetch_masked_videos.ps1 -OutputDirectory C:\VisionAssistGround\masked-videos
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\prepare_masked_videos.py --archive C:\VisionAssistGround\masked-videos\pothole_video.zip --output C:\VisionAssistGround\masked-videos-test
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\evaluate_masked_videos.py --data C:\VisionAssistGround\masked-videos-test --model core\ground\src\main\assets\ground_baseline.tflite --runtime grid --output C:\VisionAssistGround\masked-grid
& C:\VisionAssistGround\modelmaker-venv\Scripts\python.exe tools\ground\evaluate_masked_videos.py --data C:\VisionAssistGround\masked-videos-test --model C:\VisionAssistGround\checkpoint-snapshot\model.tflite --runtime mediapipe --output C:\VisionAssistGround\masked-task
```

An optional `--max-clips` creates a clearly marked partial report, not a full evaluation.
Three numerical tests cover small mask regions, threshold boundaries, nonduplicated pixel
coverage, and one-to-one component matching. Together with existing data/metric checks,
nine Python tests passed on 2026-10-25.

## Packaged v3 result — 2026-10-25

The complete run decoded 5,904 RGB frames with their masks across all 123 test clips and
evaluated 615 sampled frames. Every sampled frame had foreground annotations: this is not
a negative-scene evaluation. There were 639 connected regions; the smallest contained
3,263 pixels, so the miss count is not inflated by one-pixel compression fragments.

| Confidence | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0.1 | 0 | 1,925 | 639 | 0% | 0% |
| 0.3 | 0 | 0 | 639 | Undefined: no predictions | 0% |
| 0.65 | 0 | 0 | 639 | Undefined: no predictions | 0% |

At 0.1, predicted box unions cover 10.41% of labelled pixels with 7.62% aggregate mask
IoU. At 0.3 and 0.65 there are no predicted boxes. No clip triggers the replay policy.
The packaged model therefore fails on these close-up pothole clips; an absence of warnings
does not mean the scenes are clear. This supports retaining the disabled warning gate.

Bare interpreter median/p95 latency was 7.70/13.81 ms on the development computer. Sample
processing including mask metrics was 55.65/82.49 ms. Concurrent training and the different
timing scopes prevent interpreting these figures as comparative phone performance.
Evidence: `masked-video-grid-v3.json`, `masked-video-test-manifest.json` and
`masked-video-source.json`. Full per-frame predictions are retained in the scratch output.

## Pretrained-detector epoch-three comparison — 2026-10-25

The saved Model Maker snapshot (`modelmaker-epoch-snapshot-v2`, selected epoch three)
completed the same 123 clips and 615 samples through the actual MediaPipe Tasks runtime.
All 615 sample identifiers, timestamps, mask boxes and component areas matched the grid
evaluation exactly. The model SHA-256 is
`3266cd1f8db6367b9da2e29e214e8c78269a51534846812a0b50d3ba221e5927`.

| Confidence | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0.1 | 34 | 285 | 605 | 10.66% | 5.32% |
| 0.3 | 0 | 0 | 639 | Undefined: no predictions | 0% |
| 0.65 | 0 | 0 | 639 | Undefined: no predictions | 0% |

At 0.1, predicted box unions cover 34.48% of labelled pixels with 13.76% aggregate mask
IoU. No clip produces a warning-eligible replay event. This checkpoint is also inadequate
for warnings and is not promoted. The small improvement at a low score does not justify
lowering thresholds. Later training epochs require their own evaluation.

MediaPipe graph-call median/p95 was 72.20/101.36 ms; sample processing including mask
metrics was 98.87/135.42 ms. These were measured with concurrent training, and the graph
timing scope differs from the bare grid interpreter. Evidence is retained in
`masked-video-task-epoch3.json`; this is not a phone performance comparison.

## Completed training run — selected epoch-eight export

The subsequent 20-epoch run selected epoch eight by validation loss. Its full video
evaluation again covered the same 123 clips/615 samples. At 0.1 it yielded 7 TP, 91 FP and
632 FN (7.14% precision, 1.10% recall); at 0.3 and 0.65 it yielded no predictions and missed
all 639 mask-derived regions. No warning-eligible event occurred. This shows that improved
scores on the road-image development set did not translate into useful close-up phone-video
performance. The export was not promoted. Evidence: `masked-video-task-final.json` and
`MODELMAKER_CHECKPOINT_REVIEW.md`; the same mask/proxy-label limitations above apply.
