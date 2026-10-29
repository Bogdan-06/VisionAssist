# VisionAssist private prototype backend

Node.js 22 or newer. No third-party runtime dependencies. The main Google and OpenAI keys exist only in
the backend environment, never in Android, Gradle properties, source code or shipped artifacts.

The local `.env.local` file is ignored and contains the user-provided key on this computer.
Real client-secret generation has passed. Never paste the key into chat or put credentials
in `.env.example`, which is a shareable template. Source archives exclude `.env.local`.
`APP_ACCESS_TOKEN` is a separate random private access token (minimum 32 characters). Provision
it to your test phone through the app's server settings, not as an OpenAI key. This is a
single-user prototype access mechanism; public deployment needs per-user authentication,
external rate limits and operational secret management.

```powershell
npm start
npm test
node --env-file=.env.local scripts/verify-live.mjs
node --env-file=.env.local scripts/verify-gemini.mjs --session
```

- GET `/health`: process status and configuration presence only.
- POST `/gemini/client-secret`: same private access authentication, no body. Mints a one-use
  Gemini ephemeral token with one minute to connect and a ten-minute expiry, and locks the
  Romanian prompt, tools and audio settings. Returns only `value`, `expires_at`, and `model`.
  Set `GEMINI_API_KEY` in `.env.local`; optional `GEMINI_LIVE_MODEL` defaults to `gemini-3.8-live`.
  Gemini works without an OpenAI key. There is no automatic provider fallback.
- POST `/realtime/client-secret`: requires `Authorization: Bearer <APP_ACCESS_TOKEN>` and no
  body. Mints a 60-second OpenAI client secret using `/v1/realtime/client_secrets` and returns
  only `value` and `expires_at`, with `Cache-Control: no-store`.
- Missing configuration returns 503. Invalid client auth returns 401. Web origins and caller
  session overrides are rejected. At most six attempts/minute and two in-flight requests are
  allowed for this private instance. Upstream failures are redacted.

The default listener is `127.0.0.1:8787`. For a USB test phone, explicitly select its adb serial
and run `adb -s DEVICE_SERIAL reverse tcp:8787 tcp:8787`, then configure the debug app with
`http://127.0.0.1:8787`. The emulator can use `http://10.0.2.2:8787`. Cleartext is limited to
loopback in debug; release requires HTTPS. For remote use, terminate TLS at a trusted reverse
proxy and keep this server on its private interface. Never expose an unauthenticated minting
endpoint. Do not use the main OpenAI key as APP_ACCESS_TOKEN.

The backend uses the current GA model `gpt-realtime-2.1` by default, with Romanian instructions,
audio responses and explicit image-request tooling. `OPENAI_REALTIME_MODEL` can select another
compatible GA model if the account requires it. No beta header is sent.

`npm test` validates transport contracts using test-only response fixtures. It does not claim
live API access or voice quality. `verify-live.mjs` performs an actual OpenAI mint request and
must be run after credentials are provisioned. Android WebRTC must then establish a real call
and be tested for microphone input and spoken responses on a physical phone.

HTTP 429 quota/billing errors are distinguished from temporary rate limits. The backend only
returns a safe category, never upstream messages or credentials. An account quota failure
requires checking API billing/limits before another live test; creating a new key will not
resolve an exhausted account quota.

Google Gemini token minting, a real Live session and streamed audio have passed with the saved
Google key. See [step-by-step Gemini setup](../docs/GEMINI_SETUP.md). Free-tier quotas are limited;
pricing depends on the Google project's tier. This backend never enables billing. Main API
keys remain on the server; only constrained ephemeral tokens reach the phone. The Google
token is passed through the WebSocket Authorization header, not a logged URL.
