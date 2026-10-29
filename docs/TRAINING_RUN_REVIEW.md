# Saved training runs reviewed on 27 October 2026

All four runs completed training, runtime verification, RDD evaluation, smartphone-video
evaluation and UK evaluation. No matching Windows or WSL training/evaluation process was
active at review. Each actual TFLite file's SHA-256 matched its training report and every
evaluation report. All runtime verifications passed and epoch counts matched history.csv.
Structured evidence: `training-runs-review-2026-10-27.json`.

| Run | Device | Epochs / selected | Recorded pipeline minutes | Validation mask IoU at 0.5 |
| --- | --- | ---: | ---: | ---: |
| 20261026-154128-a9c34157 | Windows CPU | 12 / 9 | 18.84 | 58.08% |
| 20261026-160447-593cabb0 | GTX 1650 Ti, WSL2 | 1 / 1 | 6.45 | 32.58% |
| 20261026-160708-4946f458 | GTX 1650 Ti, WSL2 | 12 / 12 | 10.29 | 59.02% |
| 20261026-162116-30937d54 | GTX 1650 Ti, WSL2 | 12 / 12 | 10.02 | 59.02% |

Times are the runner's elapsed counters after preflight, not a controlled hardware
comparison or a promise about wall-clock completion including sleep/suspension. Some
runs overlapped. Both GPU runs used eight CPU threads, optimization batch 16 and cache
batch 32. The one-epoch run was a software check, not a proposed trained replacement.

The two full GPU runs are byte-identical, SHA-256
`802ff63dc513e1c5030e9105d8603d8e3d880643406319c08274ec6ee85b9994`.
The command starts from the original backbone and fixed seed every time; these are
independent repetitions, not 24 accumulated epochs. No resume option is implemented.

GPU versus CPU floating-point differences changed the trajectory and selected epoch.
The selection criterion remains minimum validation BCE plus Dice loss. Selected loss
was 0.223470 for the CPU run and 0.225433 for the full GPU runs. Slightly better mask IoU
does not mean the GPU run wins under the original loss criterion, and test results must
not be used to select a new epoch. Neither result qualifies for warnings.

## External quality of the full GPU model

At pixel threshold 0.5, one-to-one region-box matching at IoU 0.5:

| Evaluation | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| RDD, 1,342 images | 0 | 9 | 550 | 0% | 0% |
| Phone videos, 615 samples / 123 clips | 491 | 1,123 | 148 | 30.42% | 76.84% |
| UK, 708 accepted images | 263 | 1,560 | 884 | 14.43% | 22.93% |

Phone components are proxy instances derived from semantic masks. These already-examined
datasets are development evidence, not new independent safety trials. Region probabilities
are not calibrated warning confidence. Counts from one dataset do not establish reliability
in another viewpoint or lighting condition.

The GPU request is implemented and verified. The model-quality gap remains: repeatedly
running the same recipe will not supply the positive forward-view pothole masks or labelled
walking scenes it lacks. Better representative data is the next useful training change.
The Android model and disabled ground-warning gate were not modified.
