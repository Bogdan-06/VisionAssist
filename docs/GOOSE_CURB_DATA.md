# Curb annotation assessment — 25 October 2026

The official [GOOSE setup page](https://goose-dataset.de/docs/setup/) publishes the dataset
under CC BY-SA 4.0. Its [ontology](https://goose-dataset.de/docs/class-definitions/) includes
curb, sidewalk and several terrain classes. The data was collected on robotic platforms;
see the [authors' paper](https://arxiv.org/html/2310.16788v2). That viewpoint is different from
a pedestrian's phone camera. Credit: Peter Mortimer, Raphael Hagmanns, Miguel Granero,
Thorsten Luettel, Janko Petereit and Hans-Joachim Wuensche.

Only the official validation archive was downloaded, for annotation inspection. No GOOSE
model weights were downloaded, and no GOOSE data entered training or Android assets.
The archive's included license confirms CC BY-SA 4.0. Its size is 2,857,251,081 bytes and
locally computed SHA-256 is
`9fed0dacfef36fa18c866dc724e63ea7a42796244fdd998bc91330555ed071d1`.
This is a reproducibility pin, not a publisher-provided cryptographic checksum. Acquisition
checked the official HTTPS origin, expected size and ETag; inspection checked all ZIP CRCs.

## Observed contents

`inspect_goose_curbs.py` checked 4,813 ZIP entries and decoded all 962 semantic masks.
Each mask has a matching RGB image header with equal dimensions. It counted numeric label
IDs directly, preserving the archive's class map; it did not infer labels from colors.

| Measurement | Result |
| --- | ---: |
| RGB/mask pairs | 962 |
| Frames containing curb label 22 | 190 |
| Frames without annotated curb pixels | 772 |
| Curb pixels | 5,116,227 |
| Share of all pixels labelled curb | 0.2597% |
| Distinct source sequences | 8 |
| Sequences with curb annotations | 6 |
| Stair class in the archive taxonomy | None |

The two Neubiberg sequences account for 136 of the 190 curb-positive frames and about
85.8% of curb pixels. Frame count therefore overstates independent scene diversity.
Sequence names containing `rain` or `sunny` are source metadata, not a manually verified
weather label for every frame. Two deterministic positive samples (median and largest curb
area) were inspected visually alongside their binary curb masks; the visible curbs and masks
align in those samples. This is a spot check, not a complete annotation-quality review.

Curb is a semantic class without instance IDs. The masks contain neither curb height nor
walking traversability labels. A no-curb frame is not necessarily hazard-free. The dataset
does not add stair support. Public test images lack public ground-truth masks according to
the setup page; validation results must not be described as independent test accuracy.

## Decision and next step

GOOSE is a plausible lawful data source for a separate curb segmentation experiment.
Before training, inspect the official training split for actual curb coverage and preserve
the published validation split. Use sequence-aware reporting and explicit negative-scene
evaluation. Thin boundaries favor pixel segmentation over treating an entire long curb as
one warning box. Any later phone implementation still needs actual mobile inference,
phone-view evaluation, and measured depth before claiming a curb height or distance.

The packaged app still has no curb detector. This assessment supports the data choice;
it does not close the curb-recognition requirement.

```powershell
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\fetch_goose_validation.py --output C:\VisionAssistGround\goose-validation
& C:\VisionAssistGround\venv\Scripts\python.exe tools\ground\inspect_goose_curbs.py --archive C:\VisionAssistGround\goose-validation\goose_2d_val.zip --output C:\VisionAssistGround\goose-curb-inspection
```

Use new output directories. The inspection retains the archive license, class map, source
changelog, per-mask hashes and paired paths. Full results are in `goose-curb-inspection.json`
and acquisition evidence in `goose-validation-provenance.json`. Original RGB samples and
their derived mask visualizations remain in the scratch inspection directory.
