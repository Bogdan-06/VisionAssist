# Run pothole training yourself

Open PowerShell and paste this command from any folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Moth\Desktop\VisionAssist\Train-GroundModel.ps1"
```

Keep the PowerShell window open and the computer awake, preferably plugged into power.
The launcher automatically uses the configured GTX 1650 Ti through WSL2. It allows eight
CPU threads, batches 32 frames for feature caching, and keeps the optimization batch at 16.
No Codex session, API key, API credit or internet connection is required after setup.
ExecutionPolicy Bypass applies to this invocation only.

Each invocation starts a fresh training run, up to 12 epochs, followed by export verification
and RDD, smartphone-video and UK image evaluations. Early stopping may finish before the
requested epoch count. The older four-thread CPU implementation took about 15 minutes for
12-epoch training/export/validation; that is not a GPU timing estimate. Separate evaluations
add time. Allow at least 4 GiB free per run, plus the one-time Linux/CUDA environment.

**Running the command repeatedly does not add more training to the previous model.**
It starts from the original backbone with the same seed each time. The two full GPU
runs reviewed on 27 October produced byte-for-byte identical models. Repeating unchanged
settings is useful for reproducibility checks, not cumulative learning.

Results are saved in a new timestamped folder under
`C:\Users\Moth\Desktop\VisionAssist\training-runs`:

- `training/segmentation.tflite`: exported model candidate.
- `training/history.csv`, `training/training.json`: learning history and selected checkpoint.
- `training/validation.json`, `training/negative-validation.json`: validation results.
- `rdd/evaluation.json`, `videos/evaluation.json`, `uk/evaluation.json`: external results.
- `runtime-verification.json`: export adapter verification.
- `logs/`: output and errors for every stage.
- `run.json`, `status.json`, `source/`: commands, stage status and source snapshot.

The terminal prints each stage and the output folder. `state: completed` in the run's
`status.json` means all commands succeeded; it does not mean detection quality passed.
Ctrl+C stops the active process and retains partial results. A later invocation starts a
new run; it does not resume interrupted training. Existing runs are preserved.

## Options

Check dependencies and input file presence without starting training:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Moth\Desktop\VisionAssist\Train-GroundModel.ps1" -CheckOnly
```

Explicitly select the GPU and allow all 12 logical CPU threads:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Moth\Desktop\VisionAssist\Train-GroundModel.ps1" -Device Gpu -Threads 12
```

The default eight threads leaves more CPU capacity for other applications. More threads
are not guaranteed to make every stage faster. `-Device Cpu` selects the original Windows
environment. `-Epochs 20` changes the maximum epoch count. `-BatchSize 32` changes the
optimizer batch and therefore training dynamics; the default stays at 16. If GPU memory
is exhausted, reduce `-CacheBatchSize` and/or `-BatchSize` to 8 or 16 and start a new run.
No global power plan, overclocking or WSL memory settings are changed.

GPU usage varies by stage. The encoder and decoder use CUDA. LiteRT export verification
and image/video evaluations use CPU, matching the deployed interpreter. High GPU usage
throughout every stage is neither expected nor required.

## One-time GPU setup

Already configured on this computer: Ubuntu-24.04 under WSL2, with an isolated Python
environment at `/opt/visionassist/venv`. The Windows NVIDIA driver is reused; no Linux
display driver is installed. The launcher reads `training-gpu.local.json` to select it.
The existing Windows CPU environment remains available.

To reproduce or repair this setup:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Moth\Desktop\VisionAssist\Setup-GpuTraining.ps1"
```

Setup downloads Ubuntu if absent, Python environment support and the pinned TensorFlow
CUDA dependencies. It verifies a real GPU convolution before enabling automatic GPU
selection. This one-time setup needs internet and several GB of disk space. A requested
GPU that is unavailable causes an error rather than a silent CPU training run.

[TensorFlow's official installation guide](https://www.tensorflow.org/install/pip)
documents WSL2 for modern NVIDIA training on Windows;
[NVIDIA's WSL guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html) explains
reuse of the Windows driver.

This launcher uses the prepared environment and datasets in
`C:\Users\Moth\Documents\Codex\2026-10-09\new-chat\work\ground` and the reviewed backbone in
`C:\Users\Moth\.keras\models`. Keep those folders. If relocated, pass `-DataRoot`,
`-Backbone` or `-OutputRoot` as needed; `-Python` overrides the native CPU interpreter.
Check-only checks file presence, backbone checksum, runtime imports and GPU availability
when selected; the individual training and evaluation stages verify data content hashes.
It does not download or prepare replacement data. Dataset preparation and licenses are in
[MASKED_SEGMENTATION.md](MASKED_SEGMENTATION.md).

## What this trains

This reproduces the current MobileNetV2 pothole segmentation experiment using prepared
phone masks and annotated road negatives. It does not train stairs, curbs or general hazards,
and does not automatically replace the Android model or enable warnings. More epochs on
the same data do not fill the missing positive road-domain examples. Identical settings use
the same seed and should produce similar results. The current experiment still misses all
550 annotated potholes on the RDD test set; representative new labelled data and validation
are required before considering a candidate for navigation warnings.

The external sets have already been examined during development. Repeated evaluation is a
regression check, not a new untouched safety test. Do not select epochs using test results.

## Launcher verification (2026-10-26)

The real prepared setup passed `-CheckOnly` through both Windows PowerShell 5.1 and the
installed PowerShell 7 runtime. Subprocess smoke checks verified live stdout/stderr capture,
saved logs, propagation of exit code 7 as a failure, and a nonzero PowerShell exit when data
is missing. Check-only and failed preflight created no run directory. Python syntax compilation
passed. No new full training run was started for this launcher check; the underlying training,
export and evaluation scripts were previously exercised in the documented v2 experiment.
The packaged Android model checksum and disabled ground-warning gate remained unchanged.

## Completed GPU runs (reviewed 2026-10-27)

The one-epoch GPU verification run completed training, LiteRT export, export agreement,
shared-runtime validation, and all three external evaluations. Two subsequent 12-epoch
GPU runs also completed every stage. Model hashes were checked against the actual files
and against every evaluation report. Their recorded pipeline runtimes were 10.3 and
10.0 minutes, compared with 18.8 minutes for the earlier 12-epoch CPU pipeline; these
exclude preflight and should not be interpreted as time including any system pause.

Both full GPU runs produced SHA-256
`802ff63dc513e1c5030e9105d8603d8e3d880643406319c08274ec6ee85b9994`.
All software checks passed, but the model still missed all 550 RDD test potholes.
No model was installed into Android or approved for warnings. See
[the run review](TRAINING_RUN_REVIEW.md) and [hardware evidence](TRAINING_HARDWARE.md).
