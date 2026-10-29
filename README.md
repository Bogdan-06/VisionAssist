# VisionAssist 0.6.0 — offline detection and Romanian voice assistant

The working project is on the Desktop in `VisionAssist`. It now recognizes supported objects
from the rear camera, entirely on-device. This is an assistive prototype, not a replacement
for a white cane. Object recognition is not a validated hazard detector or route planner.

## What works

To run local pothole-model training yourself, see [the PowerShell training command](docs/TRAINING_COMMAND.md).
The separate [stairs, curb and step training experiment](docs/BARRIER_TRAINING.md) has prepared data and is being tested;
it has not added those classes to the Android detector.

- Kotlin, Jetpack Compose Material 3 and a Romanian interface with large controls, headings,
  status semantics and a TalkBack-readable results list.
- Camera permission request/recovery, live rear-camera preview, start/stop and lifecycle cleanup.
- Bundled EfficientDet-Lite0 float32 model (320×320, COCO 80 named categories) through MediaPipe
  Tasks Vision 0.10.32, using the CPU. No model download, account, service or API key at runtime.
- Bounding boxes, Romanian labels, model confidence percentages, and left/center/right in the
  visible preview. No distance estimates. Results below 50% are excluded; at most 10 results.
- One background inference worker, CameraX KEEP_ONLY_LATEST and at most 8 inference starts per
  second. Actual speed depends on the phone. Stale observations disappear after one second.
- Detection loading/error/retry and explicit empty-result text. Detection failure leaves the
  preview usable. Start/stop and backgrounding release the analyzer and native detector.

- Optional Romanian offline TextToSpeech object announcements, with local audio priority.
- Native WebRTC voice-session implementation, accessible start/stop and connection states,
  microphone consent, bounded reconnects and foreground lifecycle cleanup.
- Private Node.js backend issuing short-lived GA OpenAI Realtime client secrets. The durable
  OpenAI key remains on the backend; the phone stores its separate access token in encrypted
  preferences backed by Android Keystore.
- Explicit single-photo sharing for environmental questions; no continuous frame upload.
- Google Gemini Live as an optional provider, with encrypted provider settings, native PCM
  microphone/playback and short-lived backend credentials. New installs default to Gemini;
  existing OpenAI settings are preserved. Local announcements immediately stop Gemini.

**The saved Gemini key works:** actual token minting, Live session setup and a streamed voice
response have passed. Google offers a limited free tier; account quotas and pricing apply.
The existing OpenAI account remains blocked by `credit_balance_exhausted` and is optional.
See [step-by-step Gemini setup](docs/GEMINI_SETUP.md), [backend setup](backend/README.md), and
[Gemini validation](docs/GEMINI_VALIDATION.md) for test scope and remaining physical-device checks.

**Milestone 5 baseline:** an experimental offline pothole model and optional ARCore depth mode
are included. The trained model's measured accuracy is insufficient; ground speech/vibration
remain gated off. See [ground model evidence](docs/GROUND_MODEL.md) and [milestone plan](docs/GROUND_HAZARD_PLAN.md).
The [milestone 5 verification report](docs/MILESTONE_5_VALIDATION.md) records passed software
tests, measured model failures and the remaining warning-quality and physical-depth gaps.
Curbs, stairs, generic uneven surfaces, poles and validated danger classification remain unsupported.
Spoken object recognition is not a critical-hazard detector.
No detection does not mean the path is clear.

## Try it on your phone

1. Open this folder in Android Studio. Let Gradle sync, select your USB-debugging-enabled
   Android phone (Android 8.0/API 26 or newer), then Run the `app` configuration.
   Alternatively install the supplied `VisionAssist-0.5.0-debug.apk` on your phone.
2. Open VisionAssist and select **Permite accesul la cameră**, then grant Android camera access.
   If already granted, select **Pornește camera**.
3. While stationary, point the rear camera at well-lit people, a bicycle, car, chair, bottle,
   cat or dog. Scroll down to the preview and **Obiecte recunoscute** list.
4. Wait for **Analiza locală este activă**. Recognized objects show a label, score and image
   position. Move the camera gently and check whether the boxes follow the objects.
5. Repeat in airplane mode. Rotate the phone, background/return, and stop/restart the camera.
   Use **Repornește analiza locală** if inference fails. A missing box is not proof of safety.
6. Check TalkBack labels/results and 200% font size. Physical-device accessibility and camera
   performance still need hands-on testing; see the validation report.

The multi-ABI debug APK is relatively large because it includes the model and MediaPipe's
native runtimes for ARM and emulator architectures. The optimized release APK is unsigned.

## Build and tests

Use JDK 17 or 21, Android SDK Platform 36.1 and Build Tools 36.0.0. Configure `ANDROID_HOME`
or let Android Studio create `local.properties`. Gradle 8.13 and dependencies are pinned.
Initial dependency downloads need internet. Camera, detection and installed Romanian TTS
work offline; optional Gemini/OpenAI conversations require internet and a configured backend.

```powershell
.\gradlew.bat :app:assembleDebug :app:assembleRelease :app:testDebugUnitTest :core:detection:testDebugUnitTest :core:voice:testDebugUnitTest :app:lintDebug
.\gradlew.bat :app:assembleDebugAndroidTest :core:camera:assembleDebugAndroidTest :core:detection:assembleDebugAndroidTest :core:voice:assembleDebugAndroidTest
# Use a dedicated emulator/test device for instrumentation:
.\gradlew.bat :app:connectedDebugAndroidTest :core:camera:connectedDebugAndroidTest :core:detection:connectedDebugAndroidTest :core:voice:connectedDebugAndroidTest
```

On macOS/Linux use `sh ./gradlew`. Debug APK: `app/build/outputs/apk/debug/app-debug.apk`.
Release APK: `app/build/outputs/apk/release/app-release-unsigned.apk`. Supply your own signing
configuration for release distribution; never commit signing keys or local.properties.

## Architecture and evidence

- `app`: permission/lifecycle route, `DetectionViewModel`, `DetectionOverlay`, Romanian category
  names and results panel. No model or CameraX types in the presentation result contract.
- `core:camera`: Preview + ImageAnalysis in a shared ViewPort, background `DetectionAnalyzer`,
  pixel rotation, CameraX coordinate transforms and camera/native resource ownership.
- `core:detection`: `ObjectDetector`, bundled model, immutable result geometry, direction,
  throttling/freshness policy, model and geometry tests.
- `core:voice`: shared voice contract and provider controller, OpenAI WebRTC transport,
  Gemini WebSocket/PCM transport, audio priority, connection states and photo consent handoff.
  Detection never depends on this module.
- `backend`: authenticated, rate-limited token endpoints for both providers, with no runtime npm dependencies.
- [Model provenance and categories](docs/MODEL.md)
- [Milestone 3 plan](docs/MILESTONE_3_PLAN.md)
- [Milestone 3 validation](docs/MILESTONE_3_VALIDATION.md)
- [Future milestones](docs/IMPLEMENTATION_PLAN.md)

Camera frames remain on-device except for a single JPEG explicitly requested through the
photo control. Voice-session audio is sent to the selected provider (Google Gemini or OpenAI)
while the user has started a conversation.
No microphone is started by opening the app or starting the camera. Backgrounding stops the
conversation and camera. Captured photos are held only in memory; no recording is saved.
The rendering test saves a screenshot of a public fixture in the test environment only.
