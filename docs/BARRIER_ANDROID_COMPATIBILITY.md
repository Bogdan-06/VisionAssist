# Barrier detector format: Android compatibility check

On 28 October 2026, the real three-class Model Maker export ran on the SM-S931B using
MediaPipe Tasks Vision 0.10.32 CPU inference. Five instrumentation tests passed: the new
barrier-format check and four existing pothole inference, Python/LiteRT fixture, bitmap
ownership and worker lifecycle checks. Five ground-policy JVM tests also passed. The app
debug build and the instrumentation build succeeded.

This uses the rejected single-epoch smoke model, SHA-256
`0097090945bbf0b73301c33803c00c5d200f564d1e9d75bd42682a274e22e7ed`.
It establishes that Android can load the export, read its named categories, produce finite
scores/boxes, and preserve caller bitmap ownership. It is not model accuracy approval,
a live CameraX benchmark, or ground-warning activation. Subsequent numerical comparisons
are recorded below.

## Enforced local execution

The final instrumentation APK has no INTERNET, CAMERA or RECORD_AUDIO permission. The
new test asserts all three are denied before loading the model; all five tests still pass.
The production app retains its existing permissions for camera and optional voice services.
Only the separate ground instrumentation APK was installed for this check. No camera or
microphone was opened, no photographs were captured, and no cloud request is part of the test.
The phone's wireless debugging/Wi-Fi connection was left available.

The model and four resized public photographs exist under
`core/ground/src/androidTest/assets/barrier-compat`, not production assets. An APK inventory
check confirms that the app debug APK contains none of these test assets. The generator
verifies the model, dataset/archive and source-image hashes, selects only previously reviewed
training examples, and writes lossless 320x320 RGB PNGs plus actual Python predictions.
The resize is a compatibility transform, not an accuracy evaluation or invented annotation.

Source photographs: [HIIG accessibility barriers](https://doi.org/10.5281/zenodo.6382090),
Jakob Stolberg, HIIG (2022), collectors Christopher Richters and Sami Nenno, CC BY 4.0.
The fixture JSON retains attribution, license, source names and transformations. The local
trained model derives from the previously reviewed Google MobileNetV2 320 checkpoint and
the audited barrier training data; no new external weights were downloaded for this test.

## Observations and limits

Four images were each inferred four times; the first call for each image is excluded from
timing, leaving 12 samples. Median task-call latency was 95.5 ms; nearest-rank p95 was 109 ms.
These include task graph preprocessing/postprocessing but exclude bitmap copying, CameraX
delivery and sustained scene analysis. Process PSS was 63,637 KB before detector creation
and 165,908 KB with the detector loaded after calls. The baseline includes the copied model
buffers, and both values include test/runtime allocations; they are not isolated model memory.
No new battery or thermal measurement is claimed.

The first test incorrectly assumed that every category has a numeric label index. Actual
Android output had `index=-1` with valid category names. The installed SDK bytecode and
[Google's Category API](https://developers.google.com/edge/api/mediapipe/java/com/google/mediapipe/tasks/components/containers/Category)
confirm that -1 denotes an unset index. The corrected test requires exact known names and,
when an index is present, checks it against the label list. Any future Android adapter must
map these names explicitly rather than indexing a label array with an optional index.

Update at the 29 October checkpoint: the legacy Windows Python SDK0.10.21 reference has282
clipped predictions on four images, versus225 for the recorded phone SDK0.10.32 output.
Windows Python SDK0.10.32 on the same decoded RGB hashes matched all225 clipped predictions
exactly (scores and coordinates); see `barrier-smoke-sdk32-comparison.json` and
`barrier-smoke-sdk32-reference.json`. The legacy comparison failed and is preserved.
Linux Python SDK0.10.32 comparison also failed (`barrier-smoke-sdk32-linux-comparison.json`);
the cause remains unresolved. A shared SDK version alone does not prove platform agreement.
The comparator gates scores0.3 and0.65 with explicit tolerance/ambiguity bands. These are
outputs of an unstable, rejected smoke model, not valid hazards or final-model evidence.

The full20-epoch candidate has a separate `barrier-candidate` fixture folder, with four
aspect-preserved reviewed training images and real Windows SDK32 predictions. Its test APK
builds, but its physical numeric comparison is still pending. The comparator checks image,
RGB, model and fixture hashes before comparing. Follow `../RESUME_GROUND_HAZARDS.md` for
the explicit candidate arguments and restoration of ignored test weights. No production
model was replaced and no warnings were activated.

## Evidence and reproduction

- [Structured offline result](barrier-android-offline-verification.json)
- [Final test output](barrier-phone-compatibility-offline.txt), [timing logs](barrier-phone-timing.txt)
- [APK inventory/hashes](barrier-android-packaging.json), [installed test permissions](barrier-test-permissions.txt)
- [Initial index-assumption failure](barrier-phone-compatibility-initial.txt)
- [Debug/unit build](barrier-android-build.log), [offline test build](barrier-android-offline-build.log)

From the Desktop project, with the existing SDK/JDK and a connected phone:

```powershell
cd C:\Users\Moth\Desktop\VisionAssist
$env:JAVA_HOME = 'C:\Program Files\Microsoft\jdk-21.0.12.101-hotspot'
.\gradlew.bat :core:ground:testDebugUnitTest :core:ground:assembleDebugAndroidTest :app:assembleDebug
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb devices -l
# Replace PHONE_SERIAL with the exact connected device identifier.
& $adb -s PHONE_SERIAL install -r -t core\ground\build\outputs\apk\androidTest\debug\ground-debug-androidTest.apk
& $adb -s PHONE_SERIAL shell am instrument -w -r -e class ro.visionassist.core.ground.BarrierModelCompatibilityTest,ro.visionassist.core.ground.GroundInferenceTest ro.visionassist.core.ground.test/androidx.test.runner.AndroidJUnitRunner
```

Check the instrumentation summary/statuses: an adb process exit code of zero alone does not
prove that tests passed. The successful run reports `OK (5 tests)` and five success statuses.
Prepared-scene physical depth accuracy still requires the user's independently measured
reference distance and readiness; this fixture check does not resolve that requirement.
