# GPU training on this computer

Configured on 26 October 2026 for the user's request to use more available resources.
Hardware discovered locally: Intel Core i7-10750H (6 cores, 12 logical processors),
approximately 16 GiB RAM, NVIDIA GeForce GTX 1650 Ti with Max-Q Design (4 GiB VRAM),
Windows NVIDIA driver 610.62. No training process was active when setup began.

TensorFlow 2.20 on native Windows is CPU-only. The new GPU path uses Ubuntu-24.04
under WSL2 and `/opt/visionassist/venv`, with TensorFlow 2.20.0, Keras 3.15.1 and
CUDA dependencies from the official TensorFlow package extra. The existing Windows
environment is retained for `-Device Cpu`. A separate stair-research environment
is unrelated to this pothole trainer.

`Setup-GpuTraining.ps1` installs the environment and requires a real GPU convolution
to pass before saving `training-gpu.local.json`. The convolution ran on `/GPU:0`
with the exact expected sum 194400. TensorFlow identified compute capability 7.5.
No Linux display driver, system-wide power plan, overclock or `.wslconfig` was added.
The NVIDIA Windows driver supplies WSL's GPU access.

## Training changes

- `Train-GroundModel.ps1` defaults to automatic GPU selection after setup, eight
  CPU threads, feature-cache batches of 32, and optimization batches of 16.
- Feature extraction batches across records, including formerly singleton road
  negatives. A compiled TensorFlow encoder reduces repeated Python dispatch.
- The input generator yields full optimization batches and prefetches two batches.
- Source frame order and split boundaries remain intact. Cache extraction can
  cross a split boundary because the encoder is frozen; decoder training still
  sees only the original training indices. Loss, learning rate and default training
  batch size are unchanged. CPU/GPU numerical results are not bitwise identical.
- GPU memory grows on demand. The selected device and actual encoder output device,
  both batch sizes and cache time are included in the training report.
- Explicit GPU selection fails if no GPU is available; it does not silently train
  on CPU. Subsequent LiteRT evaluations explicitly disable CUDA in their processes.

## Measured short benchmark

`benchmark_training_hardware.py` used 32 verified training frames: four phone clips
(20 frames) and 12 annotated negative images. It checked that batching preserved
the exact RGB/mask arrays and their order. Batched versus per-record encoder outputs
passed rtol/atol 0.001, with maximum absolute differences approximately 0.000104.
Both environments performed four finite optimizer updates and changed decoder weights.
GPU encoder outputs and decoder weights were confirmed on `/GPU:0`.

| Operation | Windows CPU, 8 threads | WSL2 GPU, 8 CPU threads |
| --- | ---: | ---: |
| Encoder batch of 32, median of five | 519.5 ms | 156.3 ms |
| Decoder batch of 16, median of three after initial trace | 89.0 ms | 42.3 ms |

This short benchmark showed ratios of 3.32x and 2.10x respectively. It compares the
actual Windows and WSL environments and is not an isolated hardware experiment or
a promise about full training speed. File I/O, startup, tracing, export and CPU
evaluation add time. A setup-check process overlapped part of the CPU benchmark;
these timings should be treated as approximate. TensorFlow's reported peak GPU
allocator usage was 576.3 MiB; this excludes some driver/runtime allocations and
does not establish a maximum for longer or larger-batch runs.

Evidence: `training-cpu-benchmark.json`, `training-gpu-benchmark.json`, and
`training-gpu-environment.txt`. The benchmark checks real computation and batching,
not model quality. Ground-warning eligibility is unchanged.

See [the command guide](TRAINING_COMMAND.md) for normal use, CPU fallback and batch
options. On a 4 GiB GPU, larger batches can exhaust memory; the 16/32 defaults
have now completed full training/export/evaluation. More CPU threads may reduce
rather than improve throughput.

## Full-pipeline verification

The one-epoch check and two 12-epoch GPU runs completed all stages, verified on
27 October from their saved reports and actual model hashes. The one-epoch check
cached all 5,559 frames in 173.0 seconds, completed training/export/validation in
254.5 seconds, and completed the pipeline in 386.8 seconds after preflight.
Its GPU-trained Keras model agreed with LiteRT on all 15 parity frames, maximum
absolute difference 0.00001866. The two full runs produced identical model bytes
and each passed 15-frame parity and exact shared-adapter validation counts.
See `TRAINING_RUN_REVIEW.md` for runtimes, quality limitations and provenance.

References: [TensorFlow installation](https://www.tensorflow.org/install/pip) and
[NVIDIA CUDA on WSL](https://docs.nvidia.com/cuda/wsl-user-guide/index.html).
