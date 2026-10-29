# VisionAssist 0.5.0: Gemini implementation and validation

Validated 15 October 2026. Project: `C:\Users\Moth\Desktop\VisionAssist`.

## Implemented

- Optional Google Gemini Live provider alongside the existing OpenAI WebRTC provider.
  New installs default to Gemini; stored settings without a provider keep OpenAI.
  Provider selection is exposed as an accessible radio group in the server settings dialog.
- Shared `VoiceClient` contract and single-owner `SelectableVoiceClient`. Switching providers
  closes the previous transport. No automatic fallback to another provider or paid account.
- Native Android microphone capture (mono 16-bit little-endian PCM at 16 kHz) and streamed
  playback (24 kHz). Audio focus, available echo cancellation/noise suppression, bounded
  queues, connection timeout, redacted errors, server interruption and lifecycle cleanup.
  OkHttp 4.12.0 provides the WebSocket transport. No audio is written to disk.
- Gemini credentials are obtained from `/gemini/client-secret`, authenticated with the
  separate private `APP_ACCESS_TOKEN`. Google key remains in ignored backend `.env.local`.
  The constrained token permits one session, one minute to connect and ten minutes of use.
  Romanian system instructions, audio mode and image tool are fixed on the backend using
  `bidiGenerateContentSetup`. Android authenticates with the short-lived token in a header.
- Explicit single-photo sharing, including camera requests that wait for phone confirmation.
  No automatic capture, continuous frame upload or image retention. Photo and descriptive
  request are sent together as a user turn. Unknown/cancelled tool requests are handled.
- Local announcements synchronously close Gemini capture/playback and cancel its session
  before TTS starts. Queued/stale responses cannot resume. The user restarts after the warning.
  Existing OpenAI buffer-clear/muting behavior is preserved. Offline camera and detection
  modules remain independent of either conversational provider.
- Provider-specific disclosure and errors, encrypted provider/access-code settings,
  rejection of Google/OpenAI main keys in the phone's access-code field, and a setup guide.

## Checks performed

| Check | Result |
| --- | --- |
| Debug APK and optimized unsigned release APK | Passed |
| Android lint | Zero errors, 17 warnings (dependency/version and Kotlin-extension suggestions) |
| JVM tests | 10 passed/up-to-date: app 3, detection geometry 4, voice policy 3 |
| Node backend contract tests | 9 passed |
| Offline emulator instrumentation | 24 passed: app 10, camera 6, detection 4, voice 4 |
| Actual Gemini token provisioning | Passed with saved Google key |
| Actual Gemini Live setup and streamed PCM response from Node | Passed |
| Actual Android Gemini session | Passed: native microphone opened; public fixture sent; streamed PCM reached Android playback |
| Android local-priority interruption and cleanup | Passed: warning ended Gemini; native microphone became inactive; repeated close was safe |

The offline suite ran with emulator Wi-Fi and mobile data disabled. It includes actual local
model inference, camera lifecycle, snapshot handling, 200% font UI controls, provider radio
selection, overlapping Gemini warnings and OpenAI protocol/native regression tests.
The app runner reports `OK (11 tests)` because it includes one assumption-skipped live test;
that skipped case is excluded from the 24 offline passes above. The separate opt-in live
execution reports `OK (1 test)`.

Live testing used only the isolated `emulator-5580`, not a personal phone. The image was the
public cats-and-dogs fixture. The app-private test configuration contained only backend URL,
provider selection and the separate app access token; it was deleted after the test. Provider
keys, audio, image payloads and ephemeral tokens were not printed or retained in test logs.
Node contract tests use transport fixtures and do not pretend to be live assistant responses.

Build evidence is in the task workspace under `work/realtime/`:
`build-gemini-full.log`, `build-gemini-final.log`, `backend-gemini-tests.log`,
`build-gemini-cancel.log`, `gemini-instrumentation-*.log` and `gemini-live-android.log`.
The final capture guard also rejects a tool photo if the request is declined or cancelled
while awaiting the camera frame; that race is covered by the guard, not a live speech test.

## Limits and next checks

- Emulator testing confirms capture activation and streaming/playback execution, not physical
  microphone acoustics, speaker audibility, Romanian pronunciation or conversational quality.
  Test natural Romanian speech, speaker/headset routing, TalkBack, actual offline Romanian
  TTS interruption, camera sharing, network loss and backgrounding on a phone while stationary.
- Gemini reconnects only on explicit user action, including after a local announcement,
  connection loss, expiry or a server `goAway`. Session resumption is not implemented.
- Google offers a limited free tier for the configured `gemini-3.8-live` model, but project
  tier/quotas/pricing apply. The app does not enable paid billing or guarantee free capacity.
- The OpenAI option remains implemented; its previously observed `credit_balance_exhausted`
  account error was not retried. Gemini does not require funding that OpenAI account.
- Recognition is still the bundled COCO model. No pothole/curb/stair/pole detector, depth-based
  distances, validated hazard classification, haptics or safe-route claims were added.
  Model descriptions can be mistaken; they are never converted into local safety detections.
- Public deployment still needs per-user authentication, HTTPS, managed secrets and external
  rate limits. This is a private assistive prototype, not a replacement for a white cane.

See [Gemini setup](GEMINI_SETUP.md), [implementation plan](IMPLEMENTATION_PLAN.md), and
[official Google pricing](https://ai.google.dev/gemini-api/docs/pricing).
