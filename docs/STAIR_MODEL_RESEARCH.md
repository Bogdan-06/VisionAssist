# Pretrained stair-label research candidate

Reviewed and acquired for local research/evaluation on 26 October 2026. This is not
an implemented Android stair detector and does not enable warnings.

## Provenance and use restriction

The official [NVIDIA Hugging Face model](https://huggingface.co/nvidia/segformer-b0-finetuned-ade-512-512)
is pinned to revision `489d5cd81a0b59fab9b7ea758d3548ebe99677da`. Its model card links
the [NVIDIA SegFormer license](https://github.com/NVlabs/SegFormer/blob/1022b45ddb0d18c6288683d60139ac9b1e83a5f2/LICENSE).
Section 3.3 limits use to research/evaluation; sections 3.1–3.2 require license and
notice preservation for redistribution/derivatives. Local research acquisition is
kept separate from any decision about general app use or distribution. The file
was read before acquisition and preserved alongside the checkpoint.

The Qualcomm AI Hub [listing](https://aihub.qualcomm.com/mobile/models/segformer_base)
labels its model entry Apache-2.0, while the upstream checkpoint card explicitly
links NVIDIA's more restrictive license. This project follows the checkpoint's
linked terms and does not treat the listing as permission to change those terms.

The model card describes ImageNet-1k encoder pretraining and ADE20K fine-tuning.
No source imagery, raw camera feed, microphone data or user credentials were sent
to either host. Acquisition used only public model/documentation endpoints.

## Verified artifact

`fetch_segformer_research.py` downloads pinned configuration/documentation files
and the safetensors variant. It checks each exact file length, verifies the model
against the publisher's LFS SHA-256, and checks the configuration/documentation
against publisher Git blob hashes. It does not execute repository code or fetch
pickle checkpoints. It parses the safetensors header as bounded JSON and checks
tensor offsets against the file payload.

- Safetensors: 15,036,944 bytes.
- SHA-256: `6ae39addd01de6b1b8bde2cf677d43a5cd733424b8d186de3f95d1c51fee23f9`.
- Parsed tensor entries: 208; classifier shape `[150,256,1,1]`, float32.
- License SHA-256: `f549820c06519e3105e5174a2fd7285224ffd2268a7f879a843b1a255fd04a61`.
- Configuration class IDs: 53 `stairs`, 59 `stairway`, 121 `step`.
- There is **no curb class**. A sidewalk label must not be relabelled as a curb.

The source/configuration checks completed successfully. The model has now run
locally on an eight-image labelled execution sample, as recorded below. It has
not been converted to LiteRT or measured on a phone. A semantic stair region
does not establish step direction, tread count, height, distance or a safe route.

## Reproduction and next checks

```powershell
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\fetch_segformer_research.py --output C:\VisionAssistGround\segformer-research-v1
```

The directory must be new. In this workspace, the research files are under
`work/ground/segformer-research-v1`; no weights were placed in Android assets.
`segformer-research-provenance.json` preserves the acquisition details.

The isolated official-library inference check is complete, using legally sourced
labelled stair examples and annotation-defined negative scenes. Next work needs
a representative evaluation/training split and an appropriate deployable model.
Any Android prototype evaluation would need the license restrictions retained,
actual conversion/parity checks and measured performance; ordinary assistive use
and production distribution must not be inferred from this research acquisition.

## Actual local execution, 26 October 2026

`evaluate_stair_research.py` loads only the pinned local safetensors/configuration
using the explicit Transformers SegFormer implementation. All file hashes and the
license hash are checked again before loading. Both hub-offline switches and the
telemetry-disable switch are set; `local_files_only=True` and `use_safetensors=True`
are passed. No remote repository code is used. Missing, unexpected and mismatched
checkpoint keys were all empty. The isolated runtime is PyTorch 2.8.0+cpu,
Transformers 4.57.1, safetensors 0.6.2, NumPy 2.2.6, Pillow 11.3.0 and OpenCV 4.12.0.
The existing TensorFlow training environment was not modified.

The model's 512-square RGB preprocessing produced `[1,3,512,512]` finite inputs;
actual outputs were finite `[1,150,128,128]` logits. Logits were resized bilinearly
to 512 square with `align_corners=False`. Stair candidates require an argmax class
of 53 or 59 and summed probability for those classes above the pixel threshold.
Every connected region is retained, scored by mean member probability, and mapped
back to source image coordinates. Boxes are matched once at IoU 0.5. Class 121
is recorded separately and is not silently converted to stairs or curbs.

The legacy configuration emits a warning about `feature_extractor_type` and
`reduce_labels` being ignored. Label reduction concerns supplied training masks;
no masks are supplied here. The inference size, scaling, normalization and output
contract are retained. Implementation references:
[Transformers 4.57.1 SegFormer](https://huggingface.co/docs/transformers/v4.57.1/en/model_doc/segformer),
[official PyTorch CPU installation](https://pytorch.org/get-started/previous-versions/).

Eight images were selected without seeing model predictions from the
[HIIG accessibility-barrier dataset](https://doi.org/10.5281/zenodo.6382090): four
with stair annotations (five boxes), and four with no stair/step annotations.
This is a small execution sample, not a representative quality evaluation.

| Pixel threshold | TP | FP | FN |
| --- | ---: | ---: | ---: |
| 0.30 | 1 | 4 | 4 |
| 0.50 | 0 | 4 | 5 |
| 0.65 | 0 | 5 | 5 |

These counts repeated exactly across both executions. Visual inspection confirmed
partial/fragmented regions on the first stair image, misses on the remaining stair
images, and a false region over stacked chairs in an annotation-defined negative.
No sample pixel had argmax class 121. These results do not justify app integration
or warnings, nor establish broad accuracy. ADE semantic regions and this dataset's
visible-stair boxes have different annotation conventions.

The final execution measured desktop CPU inference p50/p95 381.7/533.3 ms with four
threads. One warmup was excluded. These are not Android performance measurements.
Evidence: `stair-research-smoke.json`, `stair-research-review.png`,
`barrier-sample-manifest.json`, and `stair-research-environment.txt`. The run retains
the exact evaluation source and its SHA-256. No Android assets or warning gate changed.

## Reproduce the inference sample

Use a separate Python 3.12 environment. Install `torch==2.8.0` from the official CPU
index `https://download.pytorch.org/whl/cpu`, then install
`tools/ground/requirements-stair-research.txt`. The paths below are illustrative;
the environment prepared here is `work/ground/stair-research-venv`.

```powershell
python tools/ground/fetch_barrier_sample.py --output C:\VisionAssistGround\barrier-sample
python tools/ground/evaluate_stair_research.py --model C:\VisionAssistGround\segformer-research-v1 --data C:\VisionAssistGround\barrier-sample --output C:\VisionAssistGround\stair-evaluation
```

Both output directories must be new. These commands are research tools and are
separate from the pothole training launcher.
