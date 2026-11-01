# Unified training pipeline — implementation milestones

The authoritative project is the Desktop checkout. Existing trainers, data,
checkpoints and Android assets must be preserved. No full training is authorized
during implementation. Evaluation results never authorize application warnings.

1. Inspect existing launchers, dataset contracts, trainer/runtime environments and
   resume evidence. Reuse trainers and evaluators rather than replacing them.
2. Add `Train-VisionAssist.ps1` and a versioned experiment controller: preflight,
   globally exclusive job lock, immutable run directories, logs, status, source and
   configuration snapshots, explicit failures and bounded subprocess shutdown.
3. Support complete epoch-boundary resume for both profiles. Preserve optimizer,
   selected best model, schedule/callback state and dataset/environment identity;
   reject incomplete/incompatible checkpoints. Resume into a new experiment.
4. Run isolated evaluation of existing exports/checkpoints, preserve test holdouts,
   record precision/recall/F1/TP/FP/FN with metric units and generate comparable
   Markdown reports. Never select a model using held-out test results.
5. Test invariants and actual commands on prepared environments, perform only
   bounded smoke/evaluation probes, document exact Romanian PowerShell commands,
   audit the requirements, then commit/push the implementation to GitHub.

Inspection findings: barrier training already restores last weights and optimizer,
but its legacy resume validator is hard-coded to 20 epochs / batch 8. Pothole
training saves best weights only and cannot safely resume its optimizer or
EarlyStopping/ReduceLROnPlateau state. Both legacy controllers lack a shared
exclusive lock. Their status files can remain stale after a killed controller.
Windows MediaPipe 0.10.32 is the recorded barrier evaluation reference; the pinned
Linux runtime previously differed numerically, so platform identity must remain
visible in reports. Existing test partitions have been examined previously and
must not be described as an untouched safety validation set.
