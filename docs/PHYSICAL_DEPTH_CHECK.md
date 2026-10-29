# Prepared-scene depth check

The experimental depth screen now reports a central surface measurement independently of
pothole candidates. It uses actual same-frame ARCore raw depth, the existing confidence,
freshness and spread filters, and the central part of the preview. Missing or mixed depth
remains unknown. The measurement is axial depth relative to the camera plane, not a hazard
label or walking distance. The normal CameraX and voice assistant remain paused in this mode.

For a stationary check, face the rear camera squarely toward a textured, approximately flat
surface. Independently measure the camera-to-surface distance (0.5–8 m), keep the surface
centered in the preview, and record the real value. ARCore may require small initial movement
to establish tracking; a blank, reflective or poorly lit surface may yield no valid reading.
Do not substitute a guessed reference value or treat an unavailable reading as zero.

`PhysicalDepthMeasurementTest` is opt-in and skipped before launching an activity unless
`allow_physical_depth=true`. It also requires an explicit `known_distance_m` and camera
permission already granted in the app. It opens only `DepthActivity`, waits up to 60 seconds
for an actual central reading, logs the rounded measurement and closes the activity. It does
not open the microphone, upload camera frames or save photographs.

After installing matching debug and instrumentation APKs, use the exact connected device
serial and the independently measured distance:

```powershell
# Replace the two placeholders with real values before executing.
adb -s DEVICE_SERIAL shell am instrument -w -r -e class ro.visionassist.app.ui.PhysicalDepthMeasurementTest -e allow_physical_depth true -e known_distance_m MEASURED_METRES ro.visionassist.app.test/androidx.test.runner.AndroidJUnitRunner
adb -s DEVICE_SERIAL logcat -d -s PhysicalDepthCheck:I '*:S'
```

The coarse test tolerance is the larger of 0.15 m and 15% of the reference distance. This
checks one displayed reading against a prepared reference; it does not establish depth
accuracy across surfaces, camera poses or moving scenes. Wider controlled measurements,
registration checks and repeated trials are still required. A timeout or unsupported device
is not a passing depth measurement. No physical result has been recorded for this new check.

The initial opt-out check on the phone's API 37 runtime failed in Espresso initialization,
before launching the depth activity: reflective `InputManager.getInstance` was unavailable.
The test dependency is now explicitly pinned to Espresso 3.7.0, matching the existing
AndroidX Test 1.7.0 stack. Its [official release notes](https://developer.android.com/jetpack/androidx/releases/test#espresso-3.7.0)
document replacing that reflective call with `getSystemService`. The initial failure is
retained in `physical-depth-opt-out.txt`. The replacement instrumentation APK built and
installed successfully. Rerunning on the same phone correctly produced assumption-skip
status `-4` before launching a camera activity (`physical-depth-opt-out-fixed.txt`). This
resolves the initialization failure, but is not a physical measurement test pass. This
change affects instrumentation, not the production app's dependencies.
