# External benchmark and condition review

Model selection was made using the RDD validation split before running this benchmark:
v1 F1 at score 0.30 = 0.08659; v2 F1 = 0.13678. v2 is selected for subsequent external
evaluation. Score thresholds remain 0.30 for display and 0.65 for the disabled warning policy.
Neither model is accurate enough to enable warnings. External results must not be used to
retune thresholds and then described as an independent test of those thresholds.

The subsequent v3 multi-scale model reached validation F1 0.15883 at the unchanged threshold.
It is bundled for experimental visual inference. Its external results below are development
evidence: this benchmark had already been examined for v2. The apparent validation improvement
does not generalize to the external domain.

## UK wet/dry images

Dib, Jihad; Sirlantzis, Konstantinos; Howells, Gareth (2023),
*An Annotated Water-Filled, and Dry Potholes Dataset for Deep Learning Applications*, V1,
[DOI 10.17632/tp95cdvgm8.1](https://data.mendeley.com/datasets/tp95cdvgm8/1),
[research article](https://pmc.ncbi.nlm.nih.gov/articles/PMC10197008/).
License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The authors describe varied light and water conditions, phone acquisition and UK locations.
The downloaded `Potholes.zip` is 290,505,592 bytes, published and verified SHA-256
`a154cab487415c02269041f674e9e790b6ca61afc1c9ac417e9f1aae3e283a22`.
None of these images enters training. Original XML annotations supply boxes; invalid
annotations cause exclusion of the entire affected image and are listed in the report.

The v2 run evaluated 708 images with 1,147 accepted boxes. Four images had out-of-bounds
coordinates, and Pothole-487 used the unknown class `o`; all five were excluded, without
guessing replacements. At score 0.30: TP 36, FP 628, FN 1,111 (precision 5.42%, recall 3.14%).
At score 0.65: TP 0, FP 1, FN 1,147. The 17 visually tagged wet images had TP 0, FP 9, FN 34;
the single night/glare image had TP 0, FP 1, FN 1. These failures are retained in
`ground-v2-external-evaluation.json`. A subsequent architecture experiment can use this as
development evidence, but must no longer call this an untouched external test.

The v3 run uses the same 708 images and exclusions: at 0.30, TP 5, FP 44, FN 1,142,
precision 10.20%, recall 0.44%; at 0.65, TP 0, FP 0, FN 1,147. The reviewed wet subset
has TP 0, FP 0, FN 34; shadow subset TP 0, FP 0, FN 6; night/glare TP 0, FP 0, FN 1.
The lack of false alarms at a threshold with almost no predictions is not useful reliability.
All thresholds and exclusions are in `ground-v3-external-evaluation.json`.

`tools/ground/uk-reviewed-conditions.json` contains provisional **visual condition tags** from
assistant inspection of contact sheets, not expert labels or additional hazard ground truth.
Review sampled 16 images with seed 4217 and the 16 lowest mean-luminance images. Only clearly
visible conditions were tagged; other images remain unclassified, not negative for conditions.
Dark asphalt alone was not called night. Pothole-103 shows nighttime lighting and glare;
Pothole-496 has low exposure; the wet subset visibly contains standing water. Pothole-119 and
Pothole-087 include cast shadows. These very small, selected subsets cannot estimate population
performance, and condition tags should be independently checked before publication.

## Real video

*Cars Moving into pothole.webm*, Amuzujoe, 26 February 2020,
[original source](https://commons.wikimedia.org/wiki/File:Cars_Moving_into_pothole.webm),
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
Original SHA-1 `fb87d0b140e4bdbd8ab84acd504fe4dd0802ebdf`; verified SHA-256
`2327fb7ccacc68fab10a45753d868e09a6c9855ac0acae486aeefec15265f82d`.
It is a 20.728-second daylight road video in Kumasi, with passing vehicles, shadows and damaged
pavement. Eleven sampled frames were visually reviewed. It has no reviewed per-frame box labels;
therefore no precision/recall is claimed for it. No audio was processed or uploaded.
Contact sheets are resized extracts for review under the same attribution/share-alike license.

The v1 run decoded 621 frames and analyzed 52 at approximately 400 ms intervals. No observations
qualified for the temporal warning policy. This is not evidence that the scene lacked hazards.
See the saved video report for latency and offline throughput; these are not Android preview FPS.

v3 also decoded 621 frames and analyzed 52, with no temporal-policy-eligible warning.
`ground-v3-video-evaluation.json` records an observed median inference of 12.97 ms and p95
53.48 ms while a Gradle build was also running on the host. This contention-affected run is
retained transparently and is not a device performance estimate. No per-frame precision/recall
is claimed without annotations.

## Repeat

Use `tools/ground/fetch_external.ps1 -OutputDirectory C:\VisionAssistGround\external-uk` to
download and hash-check the image archive. The same script supports the authors' front/rear
dashcam videos with `-FileName`. Use `evaluate_external.py --dataset ... --model ... --output ...
--conditions tools/ground/uk-reviewed-conditions.json` for images. `evaluate_video.py` optionally
accepts reviewed per-frame annotations; frames without such annotations are never scored as
negatives. Install `requirements-video.txt` for OpenCV video decoding.
