# Milestone 5: ground-hazard baseline implementation plan

Objective source: user-provided goal-objective.md, read before implementation.
This milestone is distinct from the preceding Gemini addition (application version 0.5.0).

## Starting evidence

CameraX supplies upright frames on one worker to MediaPipe EfficientDet-Lite0 COCO inference.
That model has no pothole, curb, stair or uneven-ground class. Optional Romanian offline TTS
and Gemini/OpenAI priority are implemented. No vibration or depth implementation exists yet.
The new milestone must preserve those working features without representing missing ones as existing.

## Milestones and completion evidence

1. Research and model decision: record primary sources, model/data licenses, training provenance,
   supported classes and detection-versus-segmentation tradeoffs. Inspect provenance before any
   weight download. Investigate ARCore compatibility and camera ownership constraints.
2. Ground inference: add independent `core:ground` contracts, a real local runtime and model
   adapter where usable weights exist. Otherwise supply reproducible data preparation/training
   and explicit unavailable-model behavior. Record immutable model checksum and preprocessing.
3. Camera integration: bounded independent worker, no retained frame backlog, ownership-safe
   bitmap copy before MediaPipe recycling, configurable sampling and failure isolation. Return
   real confidence/image bounds and measured inference time; expire stale results.
4. Depth: runtime support check, optional correctly owned ARCore capture, measured depth with
   invalid/stale/low-confidence samples rejected. Investigate surface discontinuities; never
   fabricate metric distances or infer them from bounding-box size. Unsupported devices retain
   camera and object recognition. Document any unverified path explicitly.
5. Warnings and accessibility: opt-in Romanian uncertain warnings, confidence thresholds,
   spatial/temporal consistency and cooldowns; local speech/haptics preempt AI. Keep labels and
   states readable with TalkBack. Never announce a safe route or treat low scores as confirmed.
6. Evaluation: reproducible held-out precision/recall/FP/FN, condition strata, video temporal
   behavior, latency/frame counters and memory/battery measurements where available. Separate
   synthetic robustness transforms from genuinely observed wet/dark/shadow conditions.
7. Verification and delivery: debug/release builds, appropriate unit/instrumentation regression
   checks, actual model inference fixtures, provenance/license notices, model card and evaluation
   report. Report physical-device verification status honestly. No independent-navigation claim.

## Scope discipline

Do not turn COCO objects or arbitrary depth edges into named ground hazards. Only classes
supported by the actual trained model may appear as detected. Research/training support for
other requested classes must be labelled as such. Every documented limitation remains a
limitation, not evidence that its corresponding requirement has been achieved.

## Progress

- Research and reproducible RDD acquisition/training implemented. Three architectures/training
  variants exported; v3 selected by validation F1. v3 tested on 1,342 RDD test images, synthetic
  dark/shadow variants, 708 external UK photographs including reviewed wet/shadow/night subsets,
  and 52 samples from a real licensed video. Accuracy still fails warning eligibility; all reports
  retained, including poor external recall. Curbs, stairs and general unevenness remain unsupported.
- `core:ground`, bounded CameraX worker, accessible experimental results and warning policy added.
  v3 and Python/Android parity fixtures bundled. A concurrent close/offer race was fixed.
- Optional `core:depth` ARCore capture and same-frame region measurement implemented. Four pure
  geometry tests passed. Physical capture, registration and depth accuracy remain unverified.
- Ground speech/haptic path is integrated but deliberately gated off by measured poor model quality.
  Existing object announcements and voice providers are preserved.
- v3 debug/release builds passed, with zero lint errors. All 19 JVM tests, 31 executed Android
  tests and three metric tests passed. A strengthened depth fallback test also verified return
  to actual CameraX/COCO; lossless prepared-image inference matched Python. A physical
  fixture-only run subsequently passed all four ground tests on SM-S931B on 2026-10-24.
  Median/p95 inference was 13/14 ms; total image processing was 27/28 ms. No camera or
  microphone was activated. Logs and scope limits are in the validation report.
- See `MILESTONE_5_VALIDATION.md` for the requirement audit and measured timing/PSS. Remaining:
  model quality sufficient for ground warnings, supported
  depth registration and accuracy, and controlled sustained power measurements. A two-minute
  background fixture benchmark subsequently passed on the phone, with whole-device battery
  counters recorded; it does not attribute power use to inference. The tested v3 build is
  preserved. Backbone fine-tuning (v4) completed without sufficient quality; a separate
  COCO-pretrained detector completed 20 epochs and full image/video evaluation, but also failed
  the quality review. Its weights were not bundled; that detector experiment is complete.
- A labelled smartphone-video evaluation now covers 123 clips/615 samples. All tested models
  remain weak. A GOOSE curb-label audit found 190 positive frames among 962 validation pairs;
  it provides a concrete segmentation data candidate, with strong scene-concentration limits.
  See `MASKED_VIDEO_EVALUATION.md`, `MODELMAKER_CHECKPOINT_REVIEW.md` and `GOOSE_CURB_DATA.md`.
- A separate smartphone-mask segmentation preparation/training pipeline now changes the
  training viewpoint and label representation instead of repeating the failed RDD recipe.
  It audits published train/validation/test partitions for exact cross-split duplicates,
  excludes test arrays from fitting, and checks real LiteRT export against Keras. See
  `MASKED_SEGMENTATION.md` for the experiment and its outstanding acceptance checks.
  Its first 12-epoch run completed: smartphone-mask overlap improved, but it predicted
  false regions on all annotation-defined RDD negative images and missed every RDD
  test pothole at box IoU 0.5. It was not integrated. Representative negative-scene
  training and broader viewpoints are the next concrete data gap to address.
- The negative-data follow-up has prepared 1,993 training and 1,086 validation
  annotation-defined negatives, checking each original XML before assigning an empty
  pothole mask. Its completed 12-epoch run suppressed most road-domain false positives,
  but still missed all RDD test potholes and worsened phone-video region precision;
  it was not integrated. A separate official
  stair-label checkpoint was acquired for research only after license/hash checks.
  It has now run offline on an eight-image labelled sample: one of five stair boxes
  matched at pixel threshold 0.3, none at 0.5. No Android integration is justified.
  `STAIR_MODEL_RESEARCH.md` records the runtime check; `ACCESSIBILITY_BARRIER_DATA.md`
  records explicit stair/curb supervision available for future dataset preparation.
- Reliability work beyond the first baseline: annotated walking videos, representative negative
  scenes, curb/stair boundary labels, calibrated measurements and sustained phone power/thermal
  studies. Measured weak model quality must never be concealed by a passing software test.
- On 27 October, full HIIG barrier acquisition and duplicate-aware preparation were started.
  The new pipeline retains explicit stairs/curb/step boxes, excludes conflicting duplicates,
  groups near duplicates across splits, and exports training/validation separately from test.
  Eight data/metric regression tests passed. A three-class detector profile and class-aware
  evaluation were added; full-source preparation, GPU environment and real training/export
  checks remain pending. See `BARRIER_TRAINING.md` for reproducible commands and current evidence.
- The full HIIG preparation/export subsequently completed: 3,911 train / 825 validation /
  802 test images, with one near-duplicate pair grouped and all source boxes preserved.
  The dedicated TF 2.15 GPU environment, three-class optimization/export and real inference
  checks passed. The four-step smoke model has unusable accuracy and was rejected. A full
  20-epoch experiment has started through `Train-BarrierModel.ps1`; validation and holdout
  evaluation will follow automatically. Its results, warning quality and Android suitability
  are still pending. CPU training behavior remained unchanged in the regression check.
- On 28 October, the stopped run's last checkpoint/optimizer state was restored exactly
  (280 variables, step 1,464) and training continued from epoch four. A separate test-only
  Android export check then passed on SM-S931B with network/camera/microphone permissions
  denied: all five ground instrumentation tests passed. It exposed an optional category
  index (-1), now handled correctly in the test. Production features are unchanged, and
  trained-candidate numeric parity/quality remain pending. See `BARRIER_ANDROID_COMPATIBILITY.md`.
