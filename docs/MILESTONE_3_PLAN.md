# Milestone 3 — offline object detection

1. Inspect the existing Desktop project and verify the real model/runtime: EfficientDet-Lite0
   float32, MediaPipe Tasks Vision 0.10.32, packaged assets with a recorded SHA-256.
2. Add `core:detection`: detector ownership, factual results and coordinate/direction types.
3. Bind CameraX Preview and ImageAnalysis to one viewport. Infer on one worker, keep only
   the latest frame, throttle before conversion, rotate pixels and map through CameraX transforms.
4. Add Romanian bounding-box labels and a TalkBack-readable list, plus model loading,
   error/retry and stale-result handling. Preserve permission/start/stop/lifecycle behavior.
5. Verify Gradle builds/lint, positive model inference, rotation/crop/view mapping, disposal,
   and live camera analysis on an isolated emulator. Record physical-device limitations.

No metric distances, unsupported terrain classes, safety decisions, OpenAI, or spoken warnings.

Implementation and automated validation completed on 10 October 2026. The float32 model was
selected after fixture comparison; see [validation results](MILESTONE_3_VALIDATION.md).
Real-phone performance and accessibility checks remain explicitly documented follow-up work.
