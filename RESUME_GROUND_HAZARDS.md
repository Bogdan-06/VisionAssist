# Resume Milestone 5: ground hazards

Checkpoint date: **29 October 2026 (Europe/Bucharest)**. Work intentionally stopped after
checkpoint creation at the user's request. The milestone is **incomplete**.
Authoritative project: `C:\Users\Moth\Desktop\VisionAssist`.
The Documents folder below contains dependencies/data, not another project checkout.

## Read first / preserve invariants

- Original full objective: `C:\Users\Moth\.codex\attachments\6c062bb6-e4e4-4acd-88b0-f5b24447675b\goal-objective.md`.
  A verbatim copy is saved as `docs/checkpoint-20261029/goal-objective.md`.
- Keep CameraX/COCO, Romanian TTS/haptics, accessibility and both voice providers working.
- `GroundModelReadiness.WARNINGS_VALIDATED` is **false**. Leave it false. Model completion,
  compatibility, confidence scores and a green build do not establish warning reliability.
- Never invent hazards/distances, overwrite checkpoints, delete experimental work or run
  overlapping GPU jobs. No new training was started to create this checkpoint.
- No camera/microphone was opened for this checkpoint. Physical depth validation still
  needs the user's measured reference distance and explicit readiness.

## Implemented versus incomplete

Production has a separate offline pothole LiteRT detector/worker, bounded frame ownership,
temporal filtering/cooldown, Romanian warning plumbing with local priority, and an ARCore
depth experiment with invalid/stale/confidence filtering and unsupported-device fallback.
The experimental pothole model is not validated for reliable navigation; warnings remain
gated. Production `GroundClass` is still **Pothole only**.

The separate MobileNetV2 SSD320/FPN Model Maker barrier experiment really trains and exports
`stairs`, `curb`, `step`. It has reproducible dataset preparation, GPU/CPU launchers, exact
optimizer-restoration verification, runtime fixtures, metrics and physical-phone format
tests. It has **not** been integrated into the live production ground pipeline. `step` means
doorstep/other annotated step, not generic uneven ground. No generic unevenness model exists.

Remaining: candidate phone numeric verification, a modular barrier adapter and actual live
integration if justified, better curb/step quality, representative walking videos/hard
weather/lighting validation, defensible warning operating points, sustained phone resource
checks for the new model, and measured physical depth accuracy. No independent-navigation
safety claim is justified. Preserve existing poor-quality results as evidence.

## Preserved artifacts and results

`docs/checkpoint-20261029/artifact-inventory-final.json` records **absolute paths, sizes and SHA-256**
for local model/checkpoint/report/config artifacts, including older experiments. It excludes
Python environments/caches and does not rehash raw dataset archives/images. Everything
remains in place; this commit is a source/evidence checkpoint, **not a remote data backup**.
Small barrier run reports/configs/history and archived Python source were copied verbatim under
`docs/checkpoint-20261029/barrier-runs/`; original files were not changed.

Final barrier run:
`C:\Users\Moth\Desktop\VisionAssist\barrier-training-runs\20261028-215718-4bd1910e`.

- `training/model.tflite`: 10,462,141 bytes, SHA-256
  `9e5e8ed50eec603097a9d34274dbe89712625b0a868e2b02f93efb2ea09ef0ce`.
- All **20/20 epochs completed**, selected epoch 20. `training/best.weights.h5`,
  `last.weights.h5`, `float_ckpt.*`, `history.csv`, `run.json`, `training.json`,
  `resume.json` and source snapshots are preserved.
- Original interrupted run `barrier-training-runs/20261027-190343-192c18c7` has three
  completed epochs, last optimizer step 1464, best epoch 1/step 488. It was successfully
  resumed into the final run; all 280 optimizer variables were verified restored.
- Final `status.json` still says running/evaluate-test, but is **stale**: process audit
  found no matching Windows training/evaluation or WSL Python process. Do not restart
  training based on that file. Legacy controller's test evaluation has no final report.
- `validation-sdk32/evaluation.json`: all 825 images; `test-sdk32/evaluation.json`: all
  802 images, both MediaPipe 0.10.32, partial=false, warning_eligible=false.
- At IoU 0.5 / score >=0.65: validation TP99/FP7/FN671, precision93.40%, recall12.86%;
  test TP93/FP8/FN616, precision92.08%, recall13.12%. Test by class: stairs73/4/116,
  curb1/0/177, step19/4/323 (TP/FP/FN). High precision does not offset the missed hazards.
- Legacy `validation/evaluation.json` uses SDK0.10.21. Preserve it as a legacy comparison.
- Rejected smoke weights: Documents work root `barrier-smoke-v2/model.tflite`, SHA
  `0097090945bbf0b73301c33803c00c5d200f564d1e9d75bd42682a274e22e7ed`.
- Bundled production pothole model: `core/ground/src/main/assets/ground_baseline.tflite`,
  SHA `bb8ebf2bce188df2206e3fa78891888764f095ab40cad5a508c3da307cc7af88`.
  Existing failed pothole/mask experiments remain in `training-runs` and the work root.

## Data and environments (local, outside Git)

PowerShell variables for the following commands:

```powershell
Set-Location 'C:\Users\Moth\Desktop\VisionAssist'
$data = 'C:\Users\Moth\Documents\Codex\2026-10-09\new-chat\work\ground'
$run = Join-Path $PWD 'barrier-training-runs\20261028-215718-4bd1910e'
```

- HIIG CC BY4.0 archive: `$data\accessibility-barriers\wm_barriers_data.zip`, 7,972,407,510
  bytes, recorded verified SHA `f4da6d044d55f1e21c7ca31dd2ff12a48bd5dbeabfa9d11d48fad932f7d6658b`.
- Prepared: `$data\barrier-prepared-v1`; manifest SHA
  `d359f75d00beb6ca186ccb30b6b1163b2b2110ec78752840dcf0437d6ee04eee`.
  Train3911/validation825/test802. COCO training export: `$data\barrier-coco-v1`.
- Original reviewed pretrain: `$data\mobilenetv2_ssd_i320_ckpt.tar.gz`, SHA
  `73dd229998007e47259b93b00f65aca410ec053a15e67d78519ce5c1779f521f`.
- Other preserved sources: `external-uk`, `masked-videos`, `goose-validation`, RDD exports
  and older experiment folders in the inventory. See `docs/*DATA*.md`, provenance and
  evaluation reports for their individual licenses, acquisition and limitations.
- GPU: WSL `Ubuntu-24.04`, root, GTX1650Ti4GB; trainer
  `/opt/visionassist/modelmaker-venv/bin/python` (TF2.15.1, NumPy1.26.4, ModelMaker0.2.1.4).
- Windows trainer/comparison/resume tests: `$data\modelmaker-venv\Scripts\python.exe`.
- Data preparation/tests: `$data\venv\Scripts\python.exe` (NumPy2; required for bitwise_count).
- SDK32 evaluator: `$data\barrier-runtime-venv\Scripts\python.exe`; Linux equivalent
  `/opt/visionassist/barrier-runtime-venv/bin/python`. Windows SDK32 matched phone smoke
  output exactly; Linux SDK32 smoke comparison **failed**. Version pin alone does not
  guarantee platform numeric agreement. Use Windows SDK32 as the recorded phone reference.
- Requirements/setup scripts are under `tools/ground/requirements*.txt`,
  `setup_modelmaker_wsl.sh`, `MODELMAKER_WINDOWS.md`; environment snapshots are in `docs`.
  Keep the legacy trainer isolated from SDK32 evaluation. GPU runs are not bitwise repeatable.

## Exact next steps (no automatic training)

1. Read this file, the copied objective, `docs/BARRIER_TRAINING.md`,
   `docs/BARRIER_ANDROID_COMPATIBILITY.md` and checkpoint evidence. Verify model/dataset
   hashes against the inventory before reusing them. Run `git status` and inspect processes.
2. Verify the current launchers without training:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Train-BarrierModel.ps1 -CheckOnly
```

3. Reconnect wireless debugging (`adb devices -l`, `adb mdns services`); use the actual
   current serial, not an old IP/port. Do not request physical camera access for fixture tests.
   Candidate fixtures already exist in `core/ground/src/androidTest/assets/barrier-candidate`:
   four reviewed TRAIN images, aspect preserved, max640, real SDK32 predictions and RGB hashes.
4. Build the test APK, install **only the ground instrumentation APK**, run candidate check:

```powershell
$env:JAVA_HOME = 'C:\Program Files\Microsoft\jdk-21.0.12.101-hotspot'
.\gradlew.bat :app:assembleDebug testDebugUnitTest :core:ground:assembleDebugAndroidTest
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$serial = 'REPLACE_WITH_CONNECTED_PHONE_SERIAL'
& $adb -s $serial install -r -t core\ground\build\outputs\apk\androidTest\debug\ground-debug-androidTest.apk
& $adb -s $serial shell am instrument -w -r -e class ro.visionassist.core.ground.BarrierModelCompatibilityTest -e barrier_fixture barrier-candidate -e barrier_model_sha256 9e5e8ed50eec603097a9d34274dbe89712625b0a868e2b02f93efb2ea09ef0ce ro.visionassist.core.ground.test/androidx.test.runner.AndroidJUnitRunner
```

Require explicit test success, not just adb exit0. Pull `files/barrier-runtime-results.json`
using `adb shell run-as ro.visionassist.core.ground.test cat ...` to a **new** docs filename.
Run `tools/ground/compare_barrier_android.py --fixtures ... --android-results ... --output ...`
with the Windows ModelMaker Python (SciPy required); compare identical RGB/model hashes,
named classes, scores and geometry. Default smoke fixture remains separate. Do not overwrite
recorded comparison reports. Candidate numeric parity on the phone is still pending.

5. Only after evidence review, design a separate Tasks detector adapter; current custom-grid
   pothole decoder cannot decode raw SSD outputs. Map exact categoryName (`index` may be -1),
   preserve bounded worker/bitmap lifecycle and timestamp/confidence, extend actual class/UI
   mappings, and leave warning readiness false. Resolve weak curb/step recall with justified
   experiments rather than repeating identical training or relaxing warnings blindly.
6. Future fresh training, **only when intentionally requested/resumed**, is
   `powershell -NoProfile -ExecutionPolicy Bypass -File .\Train-BarrierModel.ps1`.
   It creates a new timestamped run, uses GPU/B8/8threads/20epochs, then evaluates. Do not
   use `-ResumeFrom` on the completed20-epoch run. The old3-epoch resume command in historical
   docs was already executed; repeating it would duplicate finished work. Resume only a
   genuinely interrupted compatible run after checking live processes/checkpoint history.
7. Physical depth: user must position rear camera at a flat textured wall and provide a real
   camera-to-wall measurement (0.5–8m) and readiness. UI: scroll below voice controls to
   “Gropi · model experimental” -> “Deschide experimentul de adâncime”. No measured distance
   has been provided. Never substitute a guessed reference or call axial depth walking distance.

## Git and verification

An initial local Git commit was requested because this project had no repository. No push.
Ignored local files remain untouched: `.env*` secrets (except checked placeholder template),
local settings, run directories, model checkpoints, generated APKs/caches and test model
exports. **Intentionally tracked** runtime weights are only the existing bundled COCO
`efficientdet_lite0.tflite` and experimental `ground_baseline.tflite`, required by the app.
Gradle wrapper JAR and small reviewed image fixtures are also intentional dependencies.

On another checkout, restore the two excluded test `model.tflite` files from the smoke/final
locations above after checking hashes, only if the destination is missing. Test images and
fixture manifests are committed. Do not overwrite any existing destination. Data, Python
environments and `.env.local` must be retained separately; this Git commit cannot restore them.

Checkpoint verification: Android debug build +19 JVM tests passed; Python data8/comparison5/
resume+finite-loss6 passed in their specified environments. Two initial aggregate Python
runs failed from mismatched environments (NumPy1 lacks bitwise_count; main data venv lacks
SciPy); their logs are preserved, followed by passing per-environment logs. Prior phone
smoke5 tests passed without INTERNET/CAMERA/RECORD_AUDIO; candidate fixture APK builds, but
candidate physical run is pending. No current phone test was claimed for this checkpoint.
Build/test logs are `docs/checkpoint-*-20261029.log`. `git log -1 --oneline` identifies the
checkpoint commit. After commit verification, stop edits and leave the milestone unfinished.
