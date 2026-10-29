# VisionAssist milestones

The initial preview-only milestone is complete. The user's current milestone numbering calls
local object detection **Milestone 3**; this replaces the earlier provisional numbering.

## Milestone 3 — real-time on-device object detection

Implementation: EfficientDet-Lite0 float32 via MediaPipe, CameraX ImageAnalysis on a background
worker, shared-viewport coordinate mapping, bounding boxes, Romanian labels/confidence,
left/center/right, stale-result expiry, local error recovery and offline assets.

See [the implementation plan](MILESTONE_3_PLAN.md), [model contract](MODEL.md), and
[current validation evidence](MILESTONE_3_VALIDATION.md). Physical camera performance,
TalkBack behavior and supervised usability remain device/user validation work.

## Next — validated hazard perception and depth

- Evaluate each class in real Romanian navigation scenarios, including false positives,
  missed objects, low light, motion blur, occlusion, latency, battery and thermal load.
- Potholes, curbs, stairs and poles need suitable dedicated training data/models and measured
  validation. The current COCO model must not be relabeled as detecting these classes.
- Add an Android-independent hazard policy over timestamped observations with provenance
  and uncertainty; do not declare an area safe because detection output is empty.
- Add ARCore Depth only after capability checks, alignment/calibration and uncertainty work.
  Design shared camera-session ownership before combining CameraX and ARCore. A device without
  depth must remain useful. Never derive physical distance from bounding-box size alone.

## Milestone 4 — conversational assistant and local audio priority

Implemented native WebRTC GA transport, a private Node.js client-secret backend, Romanian
session instructions, accessible voice controls, encrypted phone backend configuration,
microphone consent, explicit one-shot photo sharing and independent local detection.
Optional offline Romanian object announcements now mute AI recording/playback before TTS;
resumption requires both local completion and remote buffer-clear acknowledgement.

Build and local validation are documented in [Milestone 4 validation](MILESTONE_4_VALIDATION.md).
The user-provided key is configured and real client-secret generation passed. Live Android
session verification encountered HTTP 429 `credit_balance_exhausted`. API credits are required
before repeating the live test. Physical Romanian speech, routing and interruption validation follows.

## Milestone 5 — optional Google Gemini voice

Implemented a provider-neutral voice interface and provider selection, preserving old OpenAI
settings. Gemini uses native 16 kHz PCM input / 24 kHz output over a constrained Live WebSocket.
The backend alone holds the Google key and issues one-use ephemeral tokens with locked settings.
Explicit single-photo sharing and Romanian safety instructions apply to both providers.
Local announcements synchronously close Gemini's audio devices and session before TTS;
the user restarts manually afterward. Camera analysis stays independent of both voice providers.
See [Gemini setup](GEMINI_SETUP.md) and [validation](GEMINI_VALIDATION.md).

## Next — validated local warnings

- Extend the existing offline TextToSpeech object announcements with validated hazard policy.
- Add haptic patterns, cooldowns and a deterministic warning priority coordinator.
- Critical local warnings must remain available without any network/session and interrupt
  conversational playback immediately. Validate arbitration and cancellation race conditions.

## Later — deployment and conversational validation

- Validate real calls, Romanian speech quality, headset routing, interruptions and reconnection
  on physical devices. Confirm that voice failure leaves local inference running.
- Before deployment, replace private prototype access tokens with per-user authentication,
  managed secrets, HTTPS hosting, external rate limits and service monitoring.
- Gemini/OpenAI handle conversations/environmental descriptions only. Uncertain generated
  descriptions must never be converted into local safety detections.

## Ongoing — accessible, supervised validation

Test with blind and low-vision participants, Romanian TalkBack voices, Switch Access, font
and display scaling, varied physical devices, noisy spaces/headphones, disconnected networks,
stale frames, sensor privacy, low battery and thermal throttling. Publish measured limitations.
VisionAssist remains an assistive prototype and does not replace a white cane.
