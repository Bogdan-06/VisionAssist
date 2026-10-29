# Accessibility-first UI redesign

Project: `C:\Users\Moth\Desktop\VisionAssist`. Goal started 29 October 2026.

## Milestones and boundaries

1. Inspect existing Compose, camera session, local announcements and voice ownership (done).
2. Add first-launch layout selection and DataStore layout/theme/developer preferences.
3. Replace the scrolling shell with Assistance, AI voice and Settings destinations, a fixed
   assistance control and a camera host whose dimensions/composition do not change on navigation.
4. Preserve backend/provider configuration, local speech, permissions, help and depth access.
   Keep experimental ground inference disabled; do not edit model/training/checkpoint files.
5. Verify debug/release builds, existing tests, onboarding/persistence/navigation/large text,
   and camera lifetime across navigation. Document actual verification and remaining limits.

CameraX currently binds its session to PreviewView size, rotation and composition. Therefore
the new shell must keep a stable, measured camera slot behind opaque voice/settings pages.
Navigation must not remove the camera, resize it, restart the detector or stop the voice client.
Foreground/background and explicit user Stop still govern capture as before.

Existing screen/camera tests need navigation/onboarding setup updates because entry points
move; their underlying lifecycle, rendering, permission and stop assertions must be preserved.
Use emulator cameras for automated camera tests, not an unprepared physical scene.

## Implementation

- `MainActivity.kt`, `ui/UiPreferences.kt`: asynchronous DataStore loading, first-launch
  layout choice, atomic preference writes, visible read/write failures, saved layout/theme/
  developer mode/local announcements. No backend credentials are moved into this store.
- `ui/VisionAssistScreen.kt`: three destinations, fixed 64dp camera/assistance action on
  every destination, camera-focused and compact preview sizes, persistent camera host,
  status/results, actual warning and object-announcement histories, settings/help entry points.
- `ui/VisionAssistTheme.kt`: coherent light/dark palettes and system-theme option.
  Radio groups, switch semantics, headings, Romanian spans, large controls and constrained,
  wrapping navigation labels support TalkBack and text scaling. Navigation height scales
  with font size; a 200% visual check exposed and corrected label overlap.
- `ui/VisionAssistRoute.kt`: existing camera/voice ownership remains above navigation.
  CameraX results continue arriving while voice/settings are visible. Explicit Stop and
  app backgrounding still govern camera/voice; changing the preview layout may rebind its
  viewport, intentionally preserving the existing coordinate-mapping contract.
- `voice/VoiceControls.kt`: existing provider/server setup, encrypted credential storage,
  microphone permission flow, start/stop, explicit photograph consent, decline action,
  local speech controls and audio priority remain available. The voice transport classes
  and backend were not rewritten. The privacy copy describes what starting a session does;
  it does not imply an inactive microphone is sending audio.
- `voice/LocalAnnouncements.kt`: separate bounded histories of actual accepted speech
  requests for object announcements and ground warnings. Voice tests are excluded. Empty
  warning history is shown honestly while ground detectors remain disabled; no sample
  hazards are inserted. Histories are session-only, not persisted into a different scene.
- `ui/DetectionViewModel.kt`, `DetectionPanel.kt`, `DetectionOverlay.kt`: optional developer
  overlay scores, real result inference duration and rolling analyzed-result FPS. FPS is
  computed from received result timestamps; it is not presented as sensor capture FPS.
- `ui/GroundPanel.kt`: experimental detector controls visibly disabled, depth entry retained.
  `DepthActivity.kt` follows the saved theme. `core/depth/DepthCameraView.kt` has one optional,
  default-off ground-worker guard so depth-only use does not load an unvalidated detector.
  Existing ARCore depth sampling and ground inference algorithms/weights are unchanged.
  Depth-only output has null inference metrics, not an invented zero duration.

Ground warning readiness remains false. Developer Mode cannot enable experimental ground
inference or warnings. Training scripts, run configurations, checkpoint files and models
were not changed; no training was started. Existing root ground-resume instructions refer
to the prior checkpoint UI: the depth experiment is now under **Settings**, not the Home scroll.

## Requirement verification map

| Requirement | Evidence |
| --- | --- |
| Three functional screens and all existing controls | `InterfaceFlowTest`, updated camera/depth lifecycle tests, existing `VoiceControlsTest`, actual UI screenshots |
| First-launch accessible onboarding, both layout choices | `OnboardingAccessibilityTest` at 2x text, first-launch screenshot, `UiPreferencesPersistenceTest` initial missing choice |
| Persist layout/theme/developer choice; change from Settings | Real disk DataStore close/reopen test; actual MainActivity settings change/recreation test; process-stop/relaunch visual check |
| Material 3, themes, large controls, scalable text, TalkBack semantics | Actual light/dark screenshots; 2x onboarding/permission/navigation tests; navigation label bounds and primary visibility assertions |
| Start/Stop without scrolling | Fixed top action; component assertions and actual CameraX explicit-stop/background/recreation test |
| Detection/connection/warning state | Existing StateFlows; separate real announcement/warning histories; disabled warning empty state; no mocked production indicators |
| Analysis independent of navigation | Persistent host mount/size test AND actual CameraX result timestamps advancing on voice/settings destinations |
| Unvalidated ground detectors disabled | Route constant false; disabled experimental button assertion; default-off depth worker; unchanged false warning gate |
| Optional measured developer diagnostics | Saved toggle; actual DetectionResult timing, confidence/boxes and rolling timestamp FPS; no synthetic runtime metrics |
| Preserve OpenAI and assistance functionality | Existing voice setup/priority/protocol/native WebRTC tests; actual COCO/model/bitmap/frame tests; unchanged transport/backend/model files |
| Successful build and regressions | Build/test logs and `ui-redesign-verification.json` |

## Reproduce

```powershell
cd C:\Users\Moth\Desktop\VisionAssist
$env:JAVA_HOME = 'C:\Program Files\Microsoft\jdk-21.0.12.101-hotspot'
.\gradlew.bat :app:assembleDebug testDebugUnitTest :app:assembleDebugAndroidTest :app:lintDebug :app:assembleRelease
# Use an isolated emulator with emulated cameras, not an unprepared personal phone.
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb -s emulator-5580 install -r app\build\outputs\apk\debug\app-debug.apk
& $adb -s emulator-5580 install -r app\build\outputs\apk\androidTest\debug\app-debug-androidTest.apk
& $adb -s emulator-5580 shell am instrument -w -r ro.visionassist.app.test/androidx.test.runner.AndroidJUnitRunner
```

Check individual instrumentation statuses and the final summary, not adb's process exit
code alone. Real cloud conversation, prepared-scene physical depth and sustained ground
benchmark tests remain opt-in. They must not be counted as passed when skipped.

## Scope of verification

Final result, 29 October 2026: all five milestones above completed. Debug and minified
release builds passed; all 19 JVM tests passed. Android instrumentation recorded 37 passed
cases and three designed opt-in skips (live cloud conversation, prepared physical depth,
sustained ground benchmark), with no failures. Lint reports zero errors and 26 warnings
(dependency-version suggestions, unused resources and an existing KTX suggestion).

Final build: `ui-redesign-accessibility-build.log`; final app suite:
`ui-redesign-delivery-app-tests.log`; unchanged-module regressions:
`ui-redesign-regression-{camera,detection,voice,ground}.log`. Machine-readable results,
APK/model hashes and protected-source comparisons are in `ui-redesign-verification.json`.
The original local checkpoint remains the baseline; training/voice/backend/camera/detection/
ground source files are byte-preserved. The only core change is the documented optional
depth-worker enable flag, default false.

Actual emulator captures: [Home, dark](ui-home-dark.png), [Compact](ui-home-compact-dark.png),
[Voice](ui-voice-dark.png), [Settings](ui-settings-dark.png), [Light](ui-home-light.png),
[200% text after correction](ui-large-text-dark-fixed.png), [first launch](ui-onboarding.png).
The native navigation area uses a stable dark background and light system controls in both
themes. The emulator font scale was restored to 1.0 after visual checks. The personal phone
was not installed, opened or used for this work.

The offline emulator checks do not establish physical-camera performance, measured depth
accuracy or navigation safety. A new paid/cloud voice conversation was not opened. Human
TalkBack usability testing remains advisable; automated checks cover roles, labels, state,
large text and available actions, not a formal accessibility certification.

Logs from failed intermediate builds/tests are retained for traceability. Use the final
verification JSON and final successful logs for current results. Initial failure causes
were a shadowed preference variable, text-file encoding, obsolete scroll-to-fixed-control
test steps and the visually detected large-text navigation overlap; all were corrected.
