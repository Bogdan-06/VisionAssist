# Milestone 5: ground-hazard baseline and evidence

Project: `C:\Users\Moth\Desktop\VisionAssist`. Version 0.6.0.
This report distinguishes implemented software from unverified or failed model behavior.
Software verification below completed on 17 October 2026. Model quality remains insufficient
for ground warnings, so this is a tested research baseline rather than the completed warning feature.

## Delivered behavior

- A separate `core:ground` library runs the bundled v3 MobileNetV2-0.5 multi-scale pothole
  model through LiteRT, offline. It returns actual model scores and normalized image boxes.
- CameraX feeds a bounded worker at most once per 400 ms, before MediaPipe recycles the frame.
  No frame queue accumulates. Ground errors are isolated from COCO recognition and snapshots.
  Closing the worker is synchronized with frame submission; results expire after one second.
- A Romanian experimental panel exposes start/stop, loading/error states, real candidates,
  image-relative directions and measured inference counters. Text provides the equivalent of
  decorative boxes for TalkBack. All controls have large touch targets.
- An optional, separate `core:depth` ARCore mode owns the camera while CameraX and conversational
  audio are paused. It pairs same-frame image coordinates with raw depth/confidence, rejects
  stale or insufficient samples, and reports median axial surface depth only when available.
  This is not walking distance, pothole depth or a safe-route estimate. Surface discontinuities
  remain diagnostics, not curb/stair detections. Unsupported devices get a fallback message.
- Romanian uncertain ground speech, vibration and voice-priority integration are present behind
  a quality gate. The gate is **false**: the model is not validated for warnings. Existing COCO
  announcements and both conversational providers remain available.

## Model evidence

Only potholes (RDD2022 D40) were trained. Curbs, stairs and generic uneven surfaces are not
implemented detection classes. Research alternatives and licensing constraints are documented
in [the model card](GROUND_MODEL.md). No detection or distance is fabricated.

The model is 2,225,580 bytes, SHA-256
`bb8ebf2bce188df2206e3fa78891888764f095ab40cad5a508c3da307cc7af88`.
Validation F1 at 0.30 improved from v1 0.08659 through v2 0.13678 to v3 0.15883. v3 was selected
before its external run; it does not generalize well to that domain.

| Evaluation at score 0.30, IoU 0.5 | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| RDD test split, 1,342 images | 72 | 370 | 478 | 16.29% | 13.09% |
| Same images, synthetic darkness | 10 | 53 | 540 | 15.87% | 1.82% |
| Same images, synthetic shadow | 18 | 92 | 532 | 16.36% | 3.27% |
| External UK, 708 accepted images | 5 | 44 | 1,142 | 10.20% | 0.44% |
| Reviewed real wet subset, 17 images | 0 | 0 | 34 | Undefined | 0% |

At the proposed warning threshold 0.65, v3 misses 546 of 550 RDD test potholes and all 1,147
external potholes. Confidence and temporal filters cannot make this a dependable warning system.
Later evaluations of previously examined datasets are development evidence, not fresh independent
trials. Full thresholds, exclusions and small-subset limitations are retained in JSON reports.

A licensed real road video was decoded (621 frames) and sampled (52 frames). No observations
qualified for the temporal policy. It has no reviewed box labels, so no video precision/recall
is claimed. The reproducible workflow accepts per-frame annotations when available.

## Verification

| Check | Current evidence |
| --- | --- |
| JVM tests | 19 passed: app 3, voice 3, detection 4, ground 5, depth 4. |
| Debug compile and lint | Debug APK built; lint 0 errors, 17 warnings (tool/dependency updates and one KTX suggestion). |
| Optimized release | R8 and release packaging passed; final debug and release ZIP alignment passed with 16 KB alignment requested. Release is unsigned and was not installed. |
| v3 Android inference, parity and worker teardown | 4 passed offline, including a real JPEG, lossless Python/Android box and score agreement, real model output through the temporal filter, frame ownership and concurrent shutdown. |
| Existing camera, voice, UI and detection regression | Voice 4, camera 7, COCO 4 and app 12 executed tests passed; one opt-in live API test skipped. Together with ground tests: 31 executed Android tests passed. |
| Actual unsupported ARCore runtime | Passed on API 36 AOSP emulator. A strengthened targeted rerun also opened depth from the main screen, returned and restarted actual CameraX/COCO. This repeats one of the 31 tests. |
| Physical phone | On 2026-10-24, all four `core:ground` fixture tests passed on SM-S931B over wireless ADB. No camera or microphone was opened. |
| Battery | A later physical fixture benchmark recorded whole-device counters (see below); no controlled model-attributable energy measurement. Emulator counters cannot establish handset battery impact. |

Three Python metric-contract tests also passed. Debug lint has zero errors and 17 warnings:
16 tool/dependency update suggestions and one existing Kotlin extension suggestion.
The APK's bundled model hash matches the model card and its attribution notice is present.
Reports and logs are retained as `ground-v3-*.json`, `ground-v3-*.txt`, and
`ground-v3-instrumentation-*.log` in this directory.

On the API 36 x86_64 emulator, 20 original-photo iterations measured median/p95 inference
10/15 ms and total preprocessing/inference/decoding 26/33 ms. Process PSS increased from
47,773 KB before loading to 69,532 KB after the loop; this includes the runtime and test
harness, not isolated model allocation. CameraX capture/delivery time is outside these numbers.

The lossless 320px fixture isolates interpreter/decoder parity; the original JPEG exercises
Android resizing. Neither proves arbitrary camera-frame preprocessing is pixel-identical to
Python. Test photos are selected runtime fixtures, not unbiased accuracy samples.

On the physical SM-S931B, the same 20-iteration fixture measured median/p95 inference
13/14 ms and preprocessing/inference/decoding 27/28 ms. Process PSS changed from
39,448 KB before loading to 61,365 KB after the loop (runtime/test harness included).
All four tests passed: actual JPEG inference, lossless Python/Android parity and temporal
filter, concurrent worker shutdown, and bitmap ownership/bounded submission. Evidence:
`ground-v3-physical-tests.txt` and `ground-v3-physical-benchmark.txt`. This is a short offline
fixture test, not a sustained camera, battery, depth or accuracy trial.

Physical CameraX with the new model, live ARCore registration/accuracy, Romanian haptic/speech
perception and TalkBack navigation still require hands-on verification. No camera or microphone
is opened for the fixture-only phone test. A short fixture loop cannot establish sustained
thermal behavior, battery drain or real-world safety.

## Files and reproducibility

- `core/ground/`: model, checksum/tensor checks, decoder, worker, temporal policy, unit and
  Android fixture tests. `core/depth/`: ARCore capture, coordinates, confidence/age filtering,
  regional measurements, diagnostic discontinuities and geometry tests.
- `core/camera/`: analyzer integration and preview-coordinate mapping; coexistence test.
- `app/`: module configuration, optional ARCore manifest metadata, vibration permission,
  accessible ground panel/overlay, isolated depth activity, warning priority and lifecycle tests.
- `tools/ground/`: pinned training environment, verified dataset acquisition, training/fine-tuning,
  image/external/video evaluation, attribution and fixture export. See its README for commands.
- `docs/GROUND_MODEL.md`, `GROUND_EXTERNAL_EVALUATION.md`, `GROUND_HAZARD_PLAN.md` and the
  `ground-v1/v2/v3-*.json` reports preserve provenance, failures, methods and limits.

Build with JDK 21 and the configured Android SDK:

```powershell
.\gradlew.bat :app:assembleDebug :app:assembleRelease testDebugUnitTest :app:lintDebug
.\gradlew.bat :core:ground:assembleDebugAndroidTest :core:camera:assembleDebugAndroidTest :app:assembleDebugAndroidTest
```

For a connected test device, set `ANDROID_SERIAL` to its exact ADB serial before running
`connectedDebugAndroidTest`. App/camera tests open the camera; the `core:ground` tests only
use bundled fixtures. The opt-in live API test is skipped without its explicit configuration.
No API key is needed for ground inference, training, evaluation or offline tests.

## Before reliable warnings

Collect independently reviewed walking-camera data with negatives, wet/shadow/night strata,
occlusion, multiple phones and geography-disjoint test splits. Add curb/stair/surface boundary
annotations for those classes. Improve and calibrate the detector, measure event-level false
alarms/misses on labelled walking videos, and establish warning acceptance criteria before
changing the quality gate. Validate ARCore alignment against known physical measurements,
then run sustained performance, power and accessibility studies with supervised users.

VisionAssist remains an assistive prototype, not a replacement for a white cane.

## Completion audit against the requested milestone

| Requirement | Authoritative evidence and remaining work |
| --- | --- |
| Research architecture, detection/segmentation, lawful datasets/models | `GROUND_MODEL.md`, dataset provenance JSON, source/license links and immutable hashes. Implemented for the first baseline. |
| Reproducible training when suitable reliable weights are unavailable | `tools/ground/` acquisition, split manifest, three training variants and evaluations; v3 exported and bundled. |
| Real offline inference, supported classes, bounded CameraX integration | Actual LiteRT fixture/parity tests, concurrent COCO/ground test and camera lifecycle instrumentation passed with emulator networking disabled. Only pothole candidates are supported. |
| Depth measurement/fusion and graceful fallback | Same-frame ARCore capture and conservative region measurement implemented; four geometry tests and real unsupported-runtime return-to-camera test passed. Supported physical depth capture/registration remain unverified. |
| Validated Romanian warnings, haptics and assistant interruption | Confidence/temporal/cooldown policy and priority integration implemented; temporal filter accepts the actual fixture prediction in instrumentation. **Production ground output remains disabled because model validation failed. This functional quality gap is unresolved.** |
| Precision/recall, FP/FN, difficult conditions, video, performance | Full JSON metrics include failures, actual wet/shadow/night samples and a licensed real video. Android fixture latency/frame processing/PSS measured. Walking-video labels, physical battery/thermal behavior and live depth accuracy remain missing. |
| Compile, preserve existing features, explain limitations | Debug/release/lint, 19 JVM tests, 31 executed Android tests and three metric tests passed; API live test skipped. Current model, affected files, physical-test status and limitations are documented above. |

The broader milestone remains active while the warning-quality gap is addressed. The v4
backbone fine-tuning experiment completed but failed to establish warning quality; it was
not bundled (see `GROUND_V4_REVIEW.md`). A separate COCO-pretrained MobileNetV2 detector
comparison started on 2026-10-24. Its real negative-image training, mixed validation,
TFLite export and MediaPipe runtime smoke checks passed. Completed epoch-one and epoch-three
checkpoints were subsequently evaluated and remain too weak for warning use; the configured
20-epoch run has now completed and also failed the quality review. See `MODELMAKER_CHECKPOINT_REVIEW.md` and
`../tools/ground/MODELMAKER_WINDOWS.md`.
The packaged v3 model and disabled ground-warning quality gate remain unchanged.

## Follow-up on 2026-10-24

The experimental depth screen now displays a central-surface measurement using the existing
raw-depth filters, independently of pothole candidates. It explicitly labels this as a
surface measurement, not a hazard or walking distance. The app and instrumentation debug
APKs compiled, and all four depth geometry tests passed again (`physical-depth-build.log`).
The prepared-scene physical test is compiled but has not yet measured a user-provided
reference distance; see `PHYSICAL_DEPTH_CHECK.md`. Earlier release/lint/full-regression
results above describe the baseline before this small display addition.
The follow-up optimized unsigned release and debug lint also passed on 2026-10-24
(`depth-followup-release-lint.log`). Lint has zero errors and 18 warnings: 17 dependency/tool
update suggestions and the existing KTX suggestion. Both current debug and unsigned release
APKs passed ZIP alignment checks with 16 KB alignment requested. The debug APK retains the
documented v3 model SHA-256. The unsigned release was not installed on the phone.
The update is installed on SM-S931B. Its initial optional-test check found an Espresso
reflection failure on API 37; pinning test-only Espresso 3.7.0 resolved it. The rebuilt
test correctly skips without its explicit arguments, before opening the camera. This is
an opt-in guard verification, not evidence of physical depth accuracy.

The first full pretrained-detector run was interrupted at training batch 56, with no completed
epoch or exported model. Its process was absent and its tool handle missing; the cause is
unknown. A separate background runner started a fresh run, with validation and external
evaluation following only successful training/export. The runner's live process must be
checked independently of its status JSON. The external evaluation adapter passed a partial
four-image real-inference smoke check, retaining 708 valid source images and five exclusions;
this is execution evidence only. Six Python data/metric tests passed.

That detached run later stopped after three completed epochs. Saved checkpoints were exported
and fully evaluated: at score 0.3, epoch three detected 5/526 validation potholes with 2 false
positives and missed all 1,147 external potholes. It was not promoted. Continuation from epoch
three restored and compared all 280 optimizer variables and resumed at step 1,126, with real
training output in epoch four. New runs retain both best and latest epoch weights. The model
and schedule are restored, but shuffled data order is not claimed to be bitwise identical.
The updated video evaluator's grid path reproduced all 52 earlier frame predictions and
temporal decisions exactly; the new model path also processed all 621 frames/52 samples.

## Labelled video follow-up on 2026-10-25

The additional published semantic-mask video test partition passed archive and per-file
checksum checks. The packaged v3 detector processed all 123 clips (5,904 decoded frames,
615 sampled frames). At score 0.3 it produced no boxes and missed all 639 mask-derived
connected regions. All sampled frames were positive; these short clips cannot establish
false alarms per walking hour or warning reliability. The nine Python data/metric tests
passed. See `MASKED_VIDEO_EVALUATION.md` for source attribution, proxy-label limitations,
reproduction commands, full threshold counts and measured timing. This extends real-video
evaluation without enabling warnings or changing Android behavior.
The saved epoch-three Model Maker detector also completed the same samples with identical
derived labels. At 0.1 it produced 34 TP, 285 FP and 605 FN; at 0.3 and 0.65 it produced no
predictions. Neither model justified a warning-policy change. The ongoing resumed training
run has separately completed six epochs. A stable epoch-six export was evaluated on all
1,330 validation images: 8 TP, 5 FP and 518 FN at score 0.3, with no detections at 0.65.
Low-score precision/recall improved, but remain inadequate. These weights were not bundled;
see `MODELMAKER_CHECKPOINT_REVIEW.md`. The physical reference-distance test still awaits a
prepared, connected phone.

An additional epoch-six numerical check restored its Keras weights and compared all raw
score/box tensors with LiteRT on three actual validation images, then checked real MediaPipe
top scores. All comparisons passed their stated tolerances. Runtime graph inspection also
confirmed the expected input normalization and single sigmoid handling. This provides
limited evidence against an export/score mismatch; it does not resolve poor detection quality
or replace the outstanding physical-depth check. See the checkpoint review for exact scope.

## Completed detector comparison and curb-data assessment

The 20-epoch run finished on 2026-10-25. Its selected epoch-eight export achieved only
11 TP/7 FP/515 FN on validation and 10 TP/7 FP/1,137 FN on external images at score 0.3.
It missed all 639 proxy regions in the paired-mask video set at that threshold. Neither
video replay produced a warning event. The candidate was not bundled; the ground-warning
quality gap remains unresolved. Complete reports and the overfitting trend are recorded
in `MODELMAKER_CHECKPOINT_REVIEW.md`. Training is no longer running.

The lawful GOOSE validation archive was also acquired and audited: all ZIP CRCs passed,
all 962 RGB/mask pairs matched dimensions, and 190 masks contained curb label 22. Curb
pixels comprise 0.2597% of the data and are concentrated in a few sequences. Two actual
RGB/mask examples were visually inspected. There is no stair label and no curb-height
ground truth. No GOOSE model/data was added to the app. `GOOSE_CURB_DATA.md` records the
provenance, limitations, scripts and next data-preparation step.

## Sustained physical fixture benchmark, 25 October 2026

The opt-in `GroundSustainedBenchmarkTest` passed on SM-S931B (API 37) over wireless ADB:
300 actual v3 inferences over 120.106 seconds, after five warmup frames. Inference
p50/p95/p99 was 18/25/33 ms; complete processing was 36/43/50 ms. Frame intervals
were 400/401/401 ms. Process CPU time was 10.977 seconds, or 0.0914 CPU seconds per
elapsed second. PSS was 30,877 KB before model loading and peaked at 57,181 KB among
the collected samples. These process measurements include the runtime and test harness.

The test ran on a saved photograph in the background, with no Activity, camera,
microphone or cloud request. Whole-device charge counter fell from 2,661,945 to
2,641,870 microamp-hours; reported battery level changed from 66% to 65%, temperature
from 32.7 to 33.6 degrees Celsius, and reported thermal status stayed at 0. Without
a controlled baseline, these readings cannot establish model energy cost or battery
life. Two minutes with one fixture does not validate sustained live CameraX/COCO
concurrency, detection quality or navigation safety.

Raw evidence: `ground-v3-sustained-physical.txt` and
`ground-v3-sustained-physical.json`. The real reference-distance depth test remains
pending the user's measured distance and phone positioning; it has not been run.

## Smartphone-mask candidate, reviewed 26 October 2026

A different training domain/representation was tested: a compact segmentation decoder
on frozen MobileNetV2 features, trained on 1,860 labelled smartphone frames with 620
validation frames. Twelve epochs, built-in-only LiteRT export and Keras/export numerical
checks completed. Full 123-clip video evaluation reached 62.44% pixel IoU at threshold
0.5, but proxy region precision remained only 33.24%. More decisively, the separate
1,342-image RDD evaluation matched none of 550 annotated potholes and generated regions
on every one of the 1,063 annotation-defined negative images. Visual review confirmed
large false masks across unrelated scene content. The candidate was rejected for
Android/warning use; the packaged v3 asset and false quality gate remain unchanged.

All shared-adapter validation pixel totals matched the training script's direct LiteRT
evaluation exactly, ruling out a discrepancy between those two paths. Full counts,
hashes, training provenance, scripts and limitations are in `MASKED_SEGMENTATION.md`.
The negative-data follow-up also completed 12 epochs and full separate evaluations.
It reduced RDD negative images with predictions from 1,063 to four, but still missed
all 550 RDD potholes. Phone-video region precision fell to 25.12%; UK region precision
was only 13.22%. It was not integrated, and no model from these experiments qualifies
for warnings. Keras/export agreement and exact shared-adapter validation counts passed.
All reports are linked from `MASKED_SEGMENTATION.md`; these runs are now complete.

An official stair-labelled SegFormer checkpoint was acquired strictly for local
research/evaluation after reviewing its linked NVIDIA license and verifying its
publisher hashes. It subsequently executed on eight labelled accessibility-barrier
images using an isolated offline CPU runtime. At pixel threshold 0.5, it matched
none of five stair boxes and produced four false regions. At 0.3 it matched one.
These limited results do not justify Android integration. See `STAIR_MODEL_RESEARCH.md`.
The source annotation audit also found 1,185 explicit curb boxes, providing a
concrete future supervision source (`ACCESSIBILITY_BARRIER_DATA.md`). The outstanding
physical depth reference and unsupported curb/stair runtime classes remain unresolved.
