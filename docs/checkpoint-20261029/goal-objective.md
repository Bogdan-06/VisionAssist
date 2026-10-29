Continue developing the existing VisionAssist Android application.

# Milestone 5 – Advanced Ground Hazard Detection

The application already includes:

- CameraX camera preview
- On-device object detection
- Romanian voice warnings and vibration feedback
- OpenAI Realtime voice assistant
- Accessible Jetpack Compose UI

Preserve all existing functionality.

## Main objective

Extend VisionAssist with specialized on-device detection of ground-level hazards, particularly potholes, curbs, stairs, and uneven walking surfaces.

This feature is especially important because the application is intended to assist blind and visually impaired users.

## Phase 1 – Research and architecture

1. Inspect the existing codebase and object detection pipeline.
2. Research suitable lightweight models and legally usable datasets for pothole and sidewalk hazard detection.
3. Evaluate object detection versus semantic segmentation for identifying ground hazards.
4. Investigate ARCore Depth API support and whether depth information could improve hazard identification.
5. Design a separate GroundHazardDetector module that integrates with the existing detection architecture.

## Phase 2 – Implement a real detection baseline

1. Select an appropriate model architecture that can run locally on Android.
2. If a suitable trained model is available, integrate it and document its training data and limitations.
3. Otherwise, create a reproducible dataset preparation and training pipeline and document how to obtain trained model weights.
4. Integrate actual inference into the existing CameraX pipeline when a usable model is available.
5. Detect supported ground hazard categories and return their confidence scores and image locations.
6. Avoid blocking the camera preview or existing object detection.
7. Optimize inference frequency and resource usage.

Do not simulate detections or describe unsupported hazard categories as functional.

## Phase 3 – Depth estimation

Investigate ARCore Depth API integration.

If the device supports it:

- Estimate relative distances to detected hazards.
- Investigate discontinuities in walking surfaces.
- Combine depth information with visual detections where technically justified.

If unsupported, preserve existing functionality and provide a graceful fallback.

Never fabricate distance measurements.

## Phase 4 – Warning integration

Integrate validated detection results with the existing Romanian warning system.

Example warnings:

- "Atenție, posibilă groapă în față."
- "Atenție, bordură detectată."
- "Posibile trepte în față."

Use confidence thresholds, temporal filtering and warning cooldowns.

Potential hazards must be clearly identified as uncertain when detection confidence is insufficient.

The local warning system must continue to have priority over the OpenAI voice assistant.

## Phase 5 – Testing and evaluation

Add a repeatable evaluation workflow that measures:

- Detection precision and recall.
- False positives and missed hazards.
- Inference latency.
- Frame processing performance.
- Memory and battery impact where measurable.

Test with representative images and videos, including difficult conditions such as shadows, wet surfaces, and poor lighting.

Do not claim the application is safe for independent navigation without formal evaluation.

## Important development rules

- Preserve all existing features.
- Use real AI inference, never mocked results in production.
- Keep ground hazard detection offline.
- Do not hardcode fake distance values.
- Do not download untrusted model weights without inspecting their provenance and licenses.
- Maintain clean Kotlin architecture.
- Compile the application and fix build errors.
- Document any functionality that cannot yet be verified.

## Final deliverables

Explain:

1. Which model or architecture was selected and why.
2. Which hazard classes are actually supported.
3. Which files were created or modified.
4. Whether the new feature works on a physical Android device.
5. Which tests were performed and their results.
6. What is still missing before the detection can be considered reliable.

Start by inspecting the existing project and making an implementation plan. Implement the first working baseline, rather than claiming full detection accuracy without evidence.