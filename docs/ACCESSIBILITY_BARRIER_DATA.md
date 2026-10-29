# Accessibility-barrier source assessment

Source: [Image Dataset of Accessibility Barriers](https://doi.org/10.5281/zenodo.6382090),
Jakob Stolberg, HIIG, 2022; data collectors Christopher Richters and Sami Nenno.
The [publisher API](https://zenodo.org/api/records/6382090) declares CC BY 4.0.
Keep attribution and the [license link](https://creativecommons.org/licenses/by/4.0/)
when distributing examples or derivatives. Our review sheet resizes images and
adds annotation/prediction rectangles; those visual changes are not original data.

The published ZIP has 7,972,407,510 bytes and publisher MD5
`d96051ca1339d1c1afa9ac736eabd058`. The initial review used only the sample below.
Full acquisition and duplicate-aware preparation completed on 27 October. The complete ZIP
passed the publisher MD5 and all member CRCs; its SHA-256 is
`f4da6d044d55f1e21c7ca31dd2ff12a48bd5dbeabfa9d11d48fad932f7d6658b`.
See [BARRIER_TRAINING.md](BARRIER_TRAINING.md) for the split audit and training status.
`fetch_barrier_sample.py` uses bounded HTTP ranges, checks the exact Content-Range,
and verifies ZIP-member CRCs for the annotation file and eight selected images.
It checks image dimensions and valid annotation bounds, then records SHA-256 hashes.
The sample fetch itself did not verify the full-archive MD5; the later complete acquisition did.

The full annotation XML contains 5,538 images, 3,564 step boxes, 1,492 stair boxes,
922 grab-bar boxes and 143 ramp boxes. Of the step boxes, 1,185 explicitly carry
the `type=curb` attribute. Annotation XML SHA-256:
`9a19dc3a95acd01c30e1a40320de49e19a3d5fe5b1b9c7253f045aa2e590930c`.
These counts were computed from the actual XML, not inferred from visual appearance.

For the initial execution sample, source member names are sorted by SHA-256 and
the first four stair-positive and first four no-stair/no-step-annotation images
are selected. Selection precedes inference. It downloaded 10,839,560 bytes including
index/range overhead. The sample contains five stair boxes. It had not been used for
training during the initial checkpoint review; the later preparation forces these already
reviewed examples and their duplicate groups into the training partition.
The complete manifest is `barrier-sample-manifest.json`; inference results are in
[STAIR_MODEL_RESEARCH.md](STAIR_MODEL_RESEARCH.md).

Limitations matter for future data preparation:

- Source boxes cover visible barriers; invisible downward steps may be omitted.
- Annotations were made by one person per image, with wheelchair accessibility in mind.
- Source step heights and ramp widths are visual estimates, not physical measurements.
- No-annotation images are not independently verified to be free of all hazards.
- Location/time independence and overlap with model pretraining remain unknown. The later
  exact/pHash duplicate audit does not establish that every similar image was found.
- Eight images cannot establish generalization, false alarms per hour or warning reliability.

This source offers explicit curb and stair supervision that the RDD pothole data
lacks. Full acquisition, duplicate grouping and train/validation/test preparation have now
completed. A real three-class training/export check passed, and a full training/evaluation
run has started. The preparation preserves `step` versus `stair` labels and curb attributes;
never convert estimated height categories into measured camera distances.
