# Milestone 3 validation — 10 October 2026

The authoritative project is `C:\Users\Moth\Desktop\VisionAssist`, version 0.3.0.
This is an assistive prototype, not a replacement for a white cane. These checks establish
software behavior; they do not establish safe navigation or a measured recognition accuracy.

Final result: debug and release builds pass; seven JVM tests and fifteen Android
instrumentation tests pass. The final instrumentation runs use the selected float32 model.

## Build environment and checks

- Windows, Microsoft OpenJDK 21.0.12, Android SDK 36.1, Build Tools 36.0.0.
- Gradle 8.13, AGP 8.13.2, Kotlin 2.2.21; dependencies pinned in the version catalog.
- Debug APK, optimized unsigned release APK and all three instrumentation APKs compile.
- Seven JVM tests pass: three preview-state tests and four detection geometry/policy tests.
- Android lint: zero errors, 15 warnings, all dependency/tool update notices.
- Debug APK signature verification and 16 KiB page-alignment verification pass.
- The installed APK contains the pinned 13,836,895-byte model, uncompressed. Test images are
  absent from the production APK. The merged manifest has no INTERNET or ACCESS_NETWORK_STATE.

Commands (from the project root):

```powershell
.\gradlew.bat :app:assembleDebug :app:assembleRelease :app:testDebugUnitTest :core:detection:testDebugUnitTest :app:lintDebug
.\gradlew.bat :app:assembleDebugAndroidTest :core:camera:assembleDebugAndroidTest :core:detection:assembleDebugAndroidTest
```

## Emulator validation

A dedicated API 36 x86_64 emulator was used, with an emulated rear camera. Wi-Fi and mobile
data were disabled before running instrumentation. No installation or testing was performed
on the connected personal phone. Each test APK was installed explicitly on `emulator-5580`
and run with `am instrument -w -r` using AndroidJUnitRunner.

- Four camera tests pass: real CameraX coordinate transforms at 0/90/180/270 degrees with
  a nontrivial crop; rescaling and offscreen rejection; inference on a rotated fixture;
  closing successful, failed and cancelled frames.
- Seven app tests pass: live CameraX STREAMING and active local inference; background/return,
  activity recreation and stop/restart; stale-result expiry; failure/stop cleanup; permission
  recovery controls; help dismissal; semantic labels and 200% font-size layout; rendering
  actual model results with boxes, Romanian labels, scores and directions.
- Four model tests pass: packaged SHA-256, real cat and dog inference, rotated pixels,
  actual people/bus/bicycle/vehicle detection, missing-model failure, idempotent close and
  rejection of use after close.

Raw final outputs: `milestone3-model-tests.txt` (4), `milestone3-camera-tests.txt` (4),
`milestone3-app-tests.txt` (7), `milestone3-build.txt`, JVM XML reports and `milestone3-lint.xml`.

The rendered fixture is saved as `milestone3-detection-render.png`. Its boxes correspond to
real model output. Visual review prompted a caption-placement correction to avoid overlap in
this scene. Dense scenes can still overlap captions; the accessible text list remains available.

## Requirement coverage

| Requirement | Implementation and verification |
| --- | --- |
| Real local model | `core:detection/ObjectDetector.kt`; packaged model SHA and positive fixture tests |
| Continuous camera analysis | `core:camera/CameraPreview.kt`; live stream and active-analysis lifecycle test |
| Work off the UI thread | Single inference executor owns model initialization, inference and close |
| Rotation and coordinate mapping | `DetectionAnalyzer.kt` and `DetectionMapper.kt`; all four rotations and crop tests |
| Boxes, labels and scores | `DetectionOverlay.kt` and `DetectionPanel.kt`; real-model rendering test and screenshot review |
| Left/center/right | Normalized visible-box midpoint in `DetectionResult.kt`; boundary tests and rendered descriptions |
| Backpressure | CameraX KEEP_ONLY_LATEST plus 125 ms throttle before conversion; throttle policy test |
| Cleanup and error recovery | Frame `finally` closure, native ownership, cancelled callbacks, retry session, lifecycle and failure tests |
| Fresh observations | `DetectionViewModel.kt`; one-second expiry, stop/error clearing and late-result rejection tests |
| Offline and truthful output | Bundled asset, no network permissions, disconnected emulator; no simulated production results or distances |

The user-facing list uses Romanian language spans and accessible text. Per-frame results do
not automatically interrupt TalkBack; only phase changes use a polite live region. Actual
spoken TalkBack behavior still needs hands-on validation.

## Recognition findings

The selected EfficientDet-Lite0 float32 model recognized the bus and three people, the bicycle,
car and dog in the overlapping-object street image, and both cats and both dogs in the animal
image. The earlier int8 model missed the bicycle and misclassified both dogs as cats. Removing
its category denylist did not fix that miss. A comparison with official SSD MobileNetV2 float32
also missed the dogs. EfficientDet-Lite0 float32 was selected without lowering the 50% threshold
or weakening the street assertions; the animal assertion was strengthened to require both
categories. The extra model size and possible latency cost are documented in MODEL.md.

Raw comparison output is retained in `milestone3-model-comparison.txt`; the original int8
failure is retained in `milestone3-int8-evaluation.txt`. A confidence score is a model score,
not a calibrated probability or safety rating. Three smoke-test scenes cannot establish
per-class accuracy. Recognizing a class in one image does not guarantee it in a live scene.

## Still requires a physical Android device

- Validate real rear-camera YUV conversion and overlay alignment in portrait, landscape and
  upside-down orientations on representative phones and camera aspect ratios.
- Check permission dialogs, permission revocation and spoken TalkBack focus/readout by hand.
- Test people, bicycles, cars and motorcycles at varied scale, lighting, motion and occlusion.
  Collect a labeled evaluation set and report per-class precision/recall before warning logic.
- Measure sustained latency, frame age, battery drain and thermal throttling on target phones.
  The implementation caps inference starts at eight per second; this is not a measured FPS claim.
- Repeat start/stop, background/return, screen lock and offline operation on the target phone.

No potholes, stairs, curbs or poles are claimed. There are no metric distances, hazard
priorities, spoken warnings, vibrations, OpenAI integration or backend in this milestone.
No result must never be interpreted as a clear path.
