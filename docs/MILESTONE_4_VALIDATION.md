# Milestone 4: implementation and validation

Historical OpenAI milestone. For the subsequent optional Google provider, see
[Gemini validation](GEMINI_VALIDATION.md) and [Gemini setup](GEMINI_SETUP.md).

Offline baseline: 12 October 2026; live authentication and diagnosis: 14 October 2026.
Authoritative project: `C:\Users\Moth\Desktop\VisionAssist`.

## Implemented

- New `core:voice` module: native WebRTC audio and data channel, GA SDP exchange at
  `/v1/realtime/calls`, temporary credentials, Romanian status and error messages,
  audio focus, foreground ownership, bounded reconnects and explicit cleanup.
- New dependency-free Node backend: `/realtime/client-secret` authenticates a separate
  private app token, calls OpenAI `/v1/realtime/client_secrets`, fixes the session policy
  server-side, limits requests and returns only the short-lived secret and expiry.
  Main OpenAI credentials never belong in the APK or phone configuration.
- Romanian voice instructions and optional `request_camera_image` tool. A tool call only
  requests confirmation on the phone. Pressing the image control captures one new frame,
  encodes an in-memory JPEG (maximum 512 pixels / 44 KB), and sends a GA `input_image`.
  No recording, continuous image upload, retained frame cache or fabricated AI responses.
- Accessible Compose start/stop, five connection states, microphone permission recovery,
  server settings, photo consent and optional local speech controls. Phone settings use
  Android Keystore encryption. Cleartext backend access is limited to debug loopback.
- Optional Romanian offline TTS announcements from actual fresh recognition results.
  These were newly added: the previous milestone did not contain a speech implementation.
  They describe recognized objects, not validated obstacles, danger or distance.
- Native microphone and assistant playback mute before each local announcement. Remote
  audio is cancelled/cleared; unmuting requires local completion and buffer-clear acknowledgement.
  Missing acknowledgement stops the conversation. The independent camera worker keeps running.
- Existing model, CPU inference, coordinate mapping, Romanian labels and camera lifecycle
  remain in place. No pothole, curb, stair, pole or depth detector was added.

## Verification status

- Android debug and optimized release builds passed. Lint: zero errors, 17 warnings
  (16 dependency/tool version suggestions and one Kotlin extension suggestion).
  Release WebRTC Java/JNI class names are preserved by `core/voice/consumer-rules.pro`;
  checked `PeerConnectionFactory`, `WebRtcAudioRecord` and `WebRtcAudioTrack` in R8 mapping.
  Debug APK passed ZIP alignment verification with 16 KB native-library alignment requested.
- JVM tests: 10 passed (app state 3, detection geometry 4, voice policy/configuration 3).
- Backend contract tests: 7 passed, including quota versus rate-limit classification.
  The test transport supplies API response fixtures;
  production code makes real HTTP requests and contains no mocked assistant responses.
- Actual backend process starts on `127.0.0.1:8787`: health returns 200 with
  `configured:true`. Before provisioning it correctly returned 503 for secret minting.
- The user supplied a key in `.env.example`; it was moved to ignored `backend/.env.local`,
  the example was restored to an empty template, and a separate random backend access token
  was configured. No secret was printed or embedded in the Android application. The previous
  source archive's example template was checked and contains no key.
- **Live authentication passed:** `verify-live.mjs` rejected unauthorized client access and
  minted a real GA temporary client secret with a future expiry using the configured key.
- **Live Android session opening is blocked by account credits:** the opt-in emulator test
  reached OpenAI but received HTTP 429 `credit_balance_exhausted` before entering Listening.
  The error is now classified as exhausted credits, not a temporary rate limit. No image was
  uploaded because the test stopped at session initialization. Streamed speech and live
  interruption assertions remain unexecuted. Add API credits before another live attempt.
- Emulator instrumentation: 21 passed with Wi-Fi and mobile data disabled on the isolated
  API 36 x86_64 emulator. App: 9 (camera lifecycle, actual-model rendering, result expiry,
  permission/help UI and 200% font voice controls); camera: 6 (mapping, analyzer ownership,
  fresh one-shot capture and cancellation); detector: 4 (real bundled model/fixtures,
  checksum, missing-model failure and cleanup); voice: 2 (GA event shape and actual native
  WebRTC audio/data SDP offer creation with resource disposal). No physical phone was used.
- Bundled model SHA-256 remained
  `40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58`.
- After the HTTP error-classification change, app and voice instrumentation were rerun
  offline: the 9 existing app checks and 2 native/protocol checks passed. The opt-in live
  test exits through its assumption guard in the default suite and is not counted as a
  successful live call. JVM tests (10) and backend tests (7) also pass.

Build/test logs are in the task workspace under `work/realtime`: `build-quota.log`,
`backend-tests-quota.log`, `instrumentation-{app,camera,detection,voice}.log`,
`instrumentation-live-diagnosis.log`, `instrumentation-app-quota.log` and
`instrumentation-voice-quota.log`. Debug/release and lint passed after the quota-error fix.
The optimized release APK is unsigned; only the debug APK is ready for test installation.

## Physical phone acceptance procedure

1. Restore API credits at https://platform.openai.com/settings/organization/billing for the
   account owning the configured key. The key and separate `APP_ACCESS_TOKEN` are already
   saved in the ignored backend env file on this computer. Never enter the OpenAI key into
   the phone. Other installations need their own private credentials; see `backend/README.md`.
2. Run `npm test`, then `node --env-file=.env.local scripts/verify-live.mjs` in `backend`.
   This verifies real secret minting without displaying the secret; it does not test audio.
3. Start the backend with `npm start`. Install the debug APK on a deliberately selected test
   phone. For USB access, run `adb -s YOUR_TEST_DEVICE reverse tcp:8787 tcp:8787` and enter
   `http://127.0.0.1:8787` plus the separate backend access token in the phone's server settings.
   Release builds require a reachable HTTPS backend.
4. Start the rear camera, grant permission, and check live local object results. Start the
   AI conversation, grant microphone permission, then ask a Romanian question. Confirm
   connecting → listening → speaking → listening, intelligible streamed speech and no echo.
5. Ask what is in front of you. Confirm that the tool requests permission on the phone and
   sends nothing until you press the photo button. Decline once, then request and approve a
   fresh image. Stop the camera and confirm that image requests fail clearly without an old
   image being sent. Confirm that the assistant admits uncertainty and does not claim distance.
6. Install/select an offline Romanian TTS voice. During AI speech use the explicitly labelled
   local voice test; then test actual recognized-object announcements while stationary.
   Check immediate AI mute, no TTS leaking into the conversation, and correct resumption or
   explicit stop. Repeat with overlapping announcements, headphones and Bluetooth audio.
7. Toggle airplane mode during conversation. Verify bounded retry/error while local detection
   continues. With installed Romanian voice data, local speech must also work offline.
   Restore connectivity and explicitly restart. Previous conversation history is not restored.
8. Stop conversation, background app, rotate, revoke microphone access, interrupt with another
   audio app, and repeat rapid start/stop. Check Android mic indicator turns off after cleanup,
   no residual assistant audio, and camera restarts correctly when requested.
9. Test Romanian TalkBack, Switch Access and 200% font size through all controls, errors,
   permission denial and server settings. Verify focus order, labels and no status chatter.

Emulator/native offer tests cannot establish real microphone quality, audio routing, acoustic
echo cancellation, Romanian TTS availability or live interruption timing. These require a
physical phone. Do not test navigation in traffic; this remains an assistive prototype and
does not replace a white cane. Generated descriptions are never local safety detections.

## Scope and next work

Restore account credits and finish live call acceptance first. Then measure audio interruption and
camera latency on representative devices, validate accessibility with users, and introduce
per-user backend authentication before any public deployment. Validated hazards, haptics and
capability-checked depth are separate future milestones.

The changes span `core/voice`, `backend`, `app/.../voice`, the app route/screen/strings and
manifests, one-shot snapshot support in `core/camera`, Gradle configuration and tests.
The detector and model are unchanged. Earlier milestone reports are historical evidence.

## API references

- [Official WebRTC guide](https://developers.openai.com/api/docs/guides/voice-webrtc)
- [GA client-secret endpoint](https://developers.openai.com/api/reference/resources/realtime/subresources/client_secrets/methods/create)
- [Realtime conversations and images](https://developers.openai.com/api/docs/guides/realtime-conversations)
- [GA server events](https://developers.openai.com/api/reference/resources/realtime/server-events)
- [Android WebRTC distribution](https://github.com/webrtc-sdk/android)
