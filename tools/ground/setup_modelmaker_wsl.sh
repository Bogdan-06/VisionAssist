#!/usr/bin/env bash
# Run inside the already configured Ubuntu-24.04 WSL2 distribution.
# Uses the existing Windows NVIDIA driver, never installs a Linux display driver.
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
bootstrap=/opt/visionassist/modelmaker-bootstrap
runtime=/opt/visionassist/modelmaker-venv
export UV_PYTHON_INSTALL_DIR=/opt/visionassist/python-runtimes
/usr/lib/wsl/lib/nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
python3 -m venv "$bootstrap"
"$bootstrap/bin/python" -m pip install uv==0.13.1
"$bootstrap/bin/uv" python install 3.11.17
if [ ! -x "$runtime/bin/python" ]; then
    "$bootstrap/bin/uv" venv --python 3.11.17 "$runtime"
fi
"$bootstrap/bin/uv" pip install --python "$runtime/bin/python" -r "$source_dir/requirements-modelmaker-linux-gpu.txt"
"$bootstrap/bin/uv" pip install --python "$runtime/bin/python" --no-deps mediapipe-model-maker==0.2.1.4 tf-models-official==2.15.0
"$runtime/bin/python" "$source_dir/modelmaker_windows_vision.py"
"$runtime/bin/python" "$source_dir/check_training_gpu.py"
"$runtime/bin/python" "$source_dir/train_modelmaker.py" --help
evaluation=/opt/visionassist/barrier-runtime-venv
if [ ! -x "$evaluation/bin/python" ]; then
    "$bootstrap/bin/uv" venv --python /usr/bin/python3 "$evaluation"
fi
"$bootstrap/bin/uv" pip install --python "$evaluation/bin/python" -r "$source_dir/requirements-barrier-runtime.txt"
"$evaluation/bin/python" -c 'import mediapipe as mp; assert mp.__version__ == "0.10.32"; print("Android-aligned evaluation runtime:", mp.__version__)'
