# Validation

This is the historical preview-only milestone report. Current object-detection results are
documented in [Milestone 3 validation](MILESTONE_3_VALIDATION.md).

## Verified on 2026-10-09

Environment: Windows, Microsoft OpenJDK 21, Gradle 8.13, Android SDK 36.1,
Build Tools 36.0.0. The workspace started without an Android project. No existing
application files were overwritten. The connected personal phone was not used.

| Check | Result |
| --- | --- |
| `:app:assembleDebug` | Passed; installable debug APK |
| `:app:assembleRelease` | Passed; minified unsigned release APK |
| `:app:testDebugUnitTest` | Passed: 3 tests, 0 failures/errors |
| `:app:lintDebug` | Passed: 0 errors, 13 non-blocking warnings |
| `:app:assembleDebugAndroidTest` | Passed |
| AndroidJUnitRunner on isolated API 36 x86_64 emulator | Passed: 5 tests, 24.206 seconds |
| APK signing verification (`apksigner verify`) | Passed for debug APK |
| APK alignment (`zipalign -c -P 16 4`) | Passed for debug APK |
| Main UI color contrast calculations | 10.31:1–16.67:1 for the four checked text/button pairs |
| Visual inspection | Default-size Romanian stopped-camera screen inspected on emulator |

The camera integration test used CameraX and the emulator's rear camera with real streaming
callbacks, not mocked status. It verified start, return from background, activity recreation
while active, explicit stop, retention of stop after recreation, and restart. Four screen
tests verified the labeled permission button and live-region semantics, actionable settings
at 200% font scale, the stop action with truthful capability text, and help dismissal.
Wi-Fi and mobile data were disabled in the dedicated emulator during all five tests.
An emulator camera is not evidence of physical-camera performance or hazard detection.

Tests were run directly with the packaged AndroidJUnitRunner to avoid running a Gradle
daemon alongside the emulator on a memory-constrained host:

```powershell
adb -s emulator-5580 install -r app/build/outputs/apk/debug/app-debug.apk
adb -s emulator-5580 install -r app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb -s emulator-5580 shell am instrument -w -r ro.visionassist.app.test/androidx.test.runner.AndroidJUnitRunner
```

The final lint warnings comprise 12 newer-dependency notices for the intentionally pinned
SDK-compatible versions and one backup-rule recommendation. Backup is explicitly disabled
using both `allowBackup=false` and `fullBackupContent=false`; Android 12+ extraction rules
also exclude the only stored data, the camera-permission preference. No lint baseline or
error suppression was used. The SDK parser and unavailable native-symbol stripping emitted
non-fatal build warnings; APK generation, signing checks, alignment and runtime tests passed.

Initial validation caught and fixed a missing instrumentation-test dependency, an API 27
theme attribute in the API 26 base theme, and an unescaped local Windows SDK property.

## Remaining validation

Actual TalkBack spoken output, Romanian voice availability/pronunciation, Switch Access,
permission dialogs and permanent-denial recovery end to end, sensor privacy toggles,
physical-device camera failures/rotation, and real-world low-vision usability need hands-on
testing. Automated semantics checks do not certify full TalkBack accessibility.

The checks below remain the acceptance checklist for physical-device testing; some basic
lifecycle and screen behavior already has the emulator coverage described above.

## Manual acceptance checklist

- Fresh install: preview is off; no permission prompt until the labeled action is selected.
- Grant permission: the real rear-camera image appears; active status follows actual streaming.
- Deny, deny permanently, and grant in Settings: actionable recovery and no crash or prompt loop.
- Stop/start repeatedly; rotate; background/return; lock/unlock; revoke permission in Settings.
  Camera is released in the background, and an explicitly stopped camera stays stopped.
- Open another camera app / disable the camera: failure must not be reported as an active feed.
- Try a device without a rear camera: explain unavailability, with no front-camera substitution.
- TalkBack: Romanian pronunciation, heading navigation, logical traversal, labeled controls,
  status announcements without frame-by-frame spam, help dialog focus/return, no preview focus trap.
- Font scale 200%, enlarged display, landscape and small screen: controls reachable by scroll,
  no clipped control text. Check TalkBack and Switch Access with a physical device.
- Airplane mode: camera and all UI remain usable; no network requirement.
- No hazard markers, distances, clear-path claims, assistant voice, recording or upload.

Instrumented screen tests do not prove TalkBack speech quality or real camera reliability.
Physical-device checks and supervised user validation remain necessary before navigation use.
