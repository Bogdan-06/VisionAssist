# Milestone 4 — Realtime voice

Inspected 12 October 2026. The Desktop checkout is 0.3.0: CameraX preview and local
EfficientDet-Lite0 inference work; there is no previous TTS/warning implementation to preserve.
The earlier milestone's source and test evidence remain in the project.

1. Keep camera/detection independent. Add a dedicated `core:voice` Android module and a
   Node.js backend using the GA client-secrets and WebRTC calls endpoints.
2. Add native microphone/remote audio, Romanian instructions, accessible controls, explicit
   connection state, bounded reconnects, foreground-only capture, audio focus and cleanup.
3. Add offline Romanian factual object announcements and a priority controller that mutes
   microphone/AI output before speaking. Do not infer critical danger from box size or labels.
4. Add one-shot image capture from the next camera frame. A voice tool may request a photo,
   but only an explicit confirmation/button sends it. No periodic upload or saved camera frames.
5. Validate backend authentication and error contracts, native WebRTC lifecycle, priority,
   image authorization, Android builds, regression tests and live API initialization when
   secure credentials are available. Document physical phone checks and any remaining gates.

Official references checked:
- https://developers.openai.com/api/docs/guides/voice-webrtc
- https://developers.openai.com/api/docs/guides/realtime-conversations
- https://developers.openai.com/api/reference/resources/realtime/subresources/client_secrets/methods/create
- https://developers.openai.com/api/reference/resources/realtime/client-events
- https://developers.openai.com/api/docs/models/gpt-realtime-2.1

Use `gpt-realtime-2.1` as the backend-configurable GA default from the current official guide.
No beta header or preview model. A main API key is never placed in Android configuration.
